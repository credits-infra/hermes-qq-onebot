#!/usr/bin/env python3
"""动作白名单 + 路径校验的验证(security.py)。

四层里最要紧的一条:闸门必须挡在 OneBot API 调用【之前】—— 所以这里把
`_调用OneBotAPI` 换成记录器,断言被拒的动作**一次都没摸到 API**。

用法(需要装了 Hermes 依赖的 python):

    python tests/test_action_policy.py
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包  # noqa: E402

加载包("tools", "security", "llm_tools", "adapter")
security = sys.modules["napcat_plugin.security"]
llm_tools = sys.modules["napcat_plugin.llm_tools"]
adapter模块 = sys.modules["napcat_plugin.adapter"]

结果 = []


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


class 假配置:
    def __init__(self, extra):
        self.extra = extra


class 假适配器:
    def __init__(self, extra):
        self.config = 假配置(extra)


def 设配置(extra):
    """把假适配器塞进 adapter 模块,security 就会读它当 config.extra。"""
    adapter模块._适配器实例 = 假适配器(extra)


def 清配置():
    adapter模块._适配器实例 = None


# ── 调用记录器:用来证明「被拒的动作没摸到 API」 ────────────────────────────────
调用记录 = []


async def 假调用(动作, 参数):
    调用记录.append((动作, 参数))
    return {"status": "ok", "retcode": 0, "data": {"echo": "fake"}}


llm_tools._调用OneBotAPI = 假调用


def 跑工具(args):
    调用记录.clear()
    return asyncio.run(llm_tools._handle_call_action(args)), list(调用记录)


def 主体():
    print("① 默认策略:只放行只读")
    设配置({})
    判定("get_login_info 放行", security.检查动作("get_login_info") is None)
    判定("get_group_msg_history 放行", security.检查动作("get_group_msg_history") is None)
    for 名 in ("upload_group_file", "upload_private_file", "download_file",
               "delete_msg", "send_msg", "set_group_ban", "get_file"):
        判定(f"{名} 默认被拒", security.检查动作(名) is not None)
    判定("未知动作默认被拒", security.检查动作("some_unknown_action_xyz") is not None)
    判定("凭据类 get_cookies 被拒", security.检查动作("get_cookies") is not None)

    print("\n② 点名授权:只放开点到的那个")
    设配置({"allowed_actions": ["upload_group_file"]})
    判定("点名的 upload_group_file 放行", security.检查动作("upload_group_file") is None)
    判定("没点名的 delete_msg 仍被拒", security.检查动作("delete_msg") is not None)
    判定("没点名的 get_group_msg_history 仍在默认白名单里",
         security.检查动作("get_group_msg_history") is None)
    设配置({"allowed_actions": '["upload_group_file"]'})
    判定("config 写 JSON 数组字符串同样生效",
         security.检查动作("upload_group_file") is None)
    设配置({"allowed_actions": "upload_group_file;delete_msg"})
    判定("分号分隔同样生效", security.检查动作("delete_msg") is None)

    print("\n③ 全放行模式:凭据类仍然拦")
    设配置({"allowed_actions": "all"})
    判定("all 放行 delete_msg", security.检查动作("delete_msg") is None)
    判定("all 放行 upload_group_file", security.检查动作("upload_group_file") is None)
    判定("all 也拦 get_cookies(永不放过)", security.检查动作("get_cookies") is not None)
    判定("all 也拦 get_csrf_token(永不放过)", security.检查动作("get_csrf_token") is not None)

    print("\n④ 环境变量也能配(配置 > 环境变量)")
    os.environ["NAPCAT_ALLOWED_ACTIONS"] = "send_msg"
    清配置()
    判定("环境变量生效(无配置时)", security.检查动作("send_msg") is None)
    设配置({"allowed_actions": "get_status"})
    判定("配置存在时压过环境变量(环境变量里的 send_msg 失效)",
         security.检查动作("send_msg") is not None)
    判定("被配置点名的 get_status 生效", security.检查动作("get_status") is None)
    del os.environ["NAPCAT_ALLOWED_ACTIONS"]

    print("\n⑤ 路径校验:复用 Hermes 媒体白名单(严格模式)")
    临时 = tempfile.mkdtemp(prefix="napcat_policy_")
    允许目录 = Path(临时) / "allow"
    允许目录.mkdir()
    好文件 = 允许目录 / "ok.png"
    好文件.write_bytes(b"\x89PNG\r\n\x1a\n")
    档案 = Path(临时) / "profile"
    档案.mkdir()
    (档案 / "config.yaml").write_text(
        "gateway:\n"
        "  strict: true\n"
        "  trust_recent_files: false\n"
        "  media_delivery_allow_dirs:\n"
        f"    - {允许目录}\n"
    )
    from hermes_constants import set_hermes_home_override
    set_hermes_home_override(str(档案))

    判定("白名单目录内的文件放行", security.校验本地路径(str(好文件)) is None)
    判定("/etc/passwd 被拒", security.校验本地路径("/etc/passwd") is not None,
         (security.校验本地路径("/etc/passwd") or "")[:40])
    判定("file:///etc/passwd 归约后仍被拒",
         security.校验本地路径("file:///etc/passwd") is not None)
    判定("白名单目录外的 /tmp 文件被拒",
         security.校验本地路径(str(Path(临时) / "outside.png")) is not None)
    判定("http 链接不作为本机路径(不适用白名单)",
         security.校验本地路径("http://example.com/a.png") is None)
    判定("base64 数据不作为本机路径",
         security.校验本地路径("base64://AAAA") is None)

    print("\n⑥ 端到端:闸门挡在 API 调用【之前】")
    # 未授权:上传动作连 API 都不该碰
    输出, 记录 = 跑工具({"action": "upload_group_file",
                     "params": {"group_id": 123, "file": "/etc/passwd", "name": "x"}})
    判定("未授权动作被拒", "白名单" in 输出 or "不在" in 输出, 输出[:60])
    判定("未授权动作一次都没摸到 API", len(记录) == 0, f"记录={记录}")

    # 显式授权 + 路径在白名单外 → 仍然拒(两层防护,第二层不因授权而失效)
    设配置({"allowed_actions": ["upload_group_file"]})
    输出, 记录 = 跑工具({"action": "upload_group_file",
                     "params": {"group_id": 123, "file": "/etc/passwd", "name": "x"}})
    判定("授权后,/etc/passwd 仍被路径白名单拦下", len(记录) == 0, 输出[:70])

    # 显式授权 + 路径在白名单内 → 放行,真的调 API
    输出, 记录 = 跑工具({"action": "upload_group_file",
                     "params": {"group_id": 123, "file": str(好文件), "name": "x"}})
    判定("授权 + 白名单内路径 → 真的调了 API",
         len(记录) == 1 and 记录[0][0] == "upload_group_file", f"记录={记录}")

    # 嵌套参数里的路径也要被查到
    输出, 记录 = 跑工具({"action": "upload_group_file",
                     "params": {"group_id": 123, "meta": {"file": "/etc/passwd"}}})
    判定("嵌套在子对象里的路径同样被拦", len(记录) == 0)

    # 只读动作不受路径检查影响
    输出, 记录 = 跑工具({"action": "get_group_list", "params": {}})
    判定("只读动作正常放行", len(记录) == 1)

    # 参数形态
    输出, 记录 = 跑工具({"action": "", "params": {}})
    判定("空 action 被拒", len(记录) == 0)
    输出, 记录 = 跑工具({"action": "get_group_list", "params": "not-a-dict"})
    判定("params 非对象被拒", len(记录) == 0)

    清配置()

    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(主体())
