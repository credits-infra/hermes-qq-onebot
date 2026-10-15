#!/usr/bin/env python3
"""出站白名单的回归测试(核心发送 + 工具动作参数)。

背景(交叉评审):
  * M2 —— 入站白名单只决定「谁能让机器人干活」,而核心 send()/send_image()/
    send_image_file()/send_voice()/send_document() 原来完全没有出站目标校验,
    只有 napcat_send_message 工具层查了;子代理实测 adapter.send("napcat_group_999999")
    真的发了出去。
  * M1 —— 动作白名单只管「动作能不能用」,不管「对谁用」;运维一放行 send_group_msg
    这类独立发送口,{"group_id": 999999, "message": ...} 就能直发任意群。

用法:
    python tests/test_outbound_acl.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包, 建立临时媒体策略, 注册napcat平台  # noqa: E402

加载包("tools", "security", "llm_tools", "main", "adapter")
注册napcat平台()
adapter模块 = sys.modules["napcat_plugin.adapter"]
security = sys.modules["napcat_plugin.security"]
from gateway.config import PlatformConfig  # noqa: E402

结果 = []


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


class 假WS:
    def __init__(self):
        self.记录 = []

    async def 发送群聊消息(self, 目标ID, 内容):
        self.记录.append(("群", 目标ID, str(内容)))
        return {"status": "ok", "retcode": 0}

    async def 发送私聊消息(self, 目标ID, 内容):
        self.记录.append(("私", 目标ID, str(内容)))
        return {"status": "ok", "retcode": 0}

    async def 上传群文件(self, 目标ID, 路径):
        self.记录.append(("上传群", 目标ID, str(路径)))
        return {"status": "ok", "retcode": 0}

    async def 上传私聊文件(self, 目标ID, 路径):
        self.记录.append(("上传私", 目标ID, str(路径)))
        return {"status": "ok", "retcode": 0}


def 造适配器(extra):
    adapter模块._适配器实例 = type("源", (), {"config": type("c", (), {"extra": extra})()})()
    a = adapter模块._创建适配器(PlatformConfig(enabled=True, extra=extra))
    a.ws = 假WS()
    return a


def 设插件配置(extra):
    adapter模块._适配器实例 = type("源", (), {"config": type("c", (), {"extra": extra})()})()


def 核心发送(允许目录: Path):
    图 = 允许目录 / "a.png"
    图.write_bytes(b"\x89PNG\r\n\x1a\n")
    音 = 允许目录 / "a.mp3"
    音.write_bytes(b"ID3")
    文 = 允许目录 / "a.txt"
    文.write_text("x")
    ext = {"allowed_group_ids": ["123456"], "allowed_qq_ids": ["999"]}

    print("① 白名单外的群 —— 每条发送路径都要拦(M2)")
    a = 造适配器(ext)
    r = asyncio.run(a.send("napcat_group_999999", "出去"))
    判定("send() 被拒", (not r.success) and not a.ws.记录, str(r.error)[:46])
    for 名, 调 in (("send_image", lambda: a.send_image("napcat_group_999999", "https://a.example/x.png")),
                   ("send_image_file", lambda: a.send_image_file("napcat_group_999999", str(图))),
                   ("send_voice", lambda: a.send_voice("napcat_group_999999", str(音))),
                   ("send_document", lambda: a.send_document("napcat_group_999999", str(文)))):
        r = asyncio.run(调())
        判定(f"{名}() 被拒且没碰 OneBot", (not r.success) and not a.ws.记录,
            f"success={r.success} 记录={a.ws.记录}")

    print("\n② 白名单内的群照常工作")
    a = 造适配器(ext)
    r = asyncio.run(a.send("napcat_group_123456", "正常"))
    判定("send() 正常", r.success and len(a.ws.记录) == 1, str(a.ws.记录))
    r = asyncio.run(a.send_image("napcat_group_123456", "https://a.example/x.png"))
    判定("send_image() 正常", r.success and len(a.ws.记录) == 2, str(a.ws.记录[-1]))

    print("\n③ 私聊对称")
    a = 造适配器(ext)
    r = asyncio.run(a.send("napcat_private_888", "陌生人"))
    判定("白名单外的 QQ 被拒", (not r.success) and not a.ws.记录, str(r.error)[:46])
    r = asyncio.run(a.send("napcat_private_999", "老熟人"))
    判定("白名单内的 QQ 正常", r.success, str(a.ws.记录))

    print("\n④ all / * 仍全放行(与入站同一套语义,不会「收得进、回不出」)")
    a = 造适配器({"allowed_group_ids": "all", "allowed_qq_ids": "*"})
    r = asyncio.run(a.send("napcat_group_999999", "任意群"))
    r2 = asyncio.run(a.send("napcat_private_888", "任意人"))
    判定("allow all 时群与私聊都放行", r.success and r2.success, str(a.ws.记录))

    print("\n⑤ 空名单 = 谁都发不出去(fail-closed,与入站姿态一致)")
    a = 造适配器({})
    r = asyncio.run(a.send("napcat_group_123456", "空配置"))
    判定("空名单时群发送被拒", (not r.success) and not a.ws.记录, str(r.error)[:46])


def 动作目标():
    配置 = {"allowed_actions": ["send_group_msg", "send_private_msg", "set_group_ban"],
            "allowed_group_ids": ["123456"], "allowed_qq_ids": ["999"]}

    print("\n⑥ 会「动手」的动作,其群/用户目标也要过白名单(M1)")
    设插件配置(配置)
    错误 = security.检查调用("send_group_msg", {"group_id": "999999", "message": "出去"})
    判定("send_group_msg → 白名单外的群被拒", bool(错误), str(错误)[:56])
    错误 = security.检查调用("send_group_msg", {"group_id": 123456, "message": "正常"})
    判定("send_group_msg → 白名单内的群放行", 错误 is None, str(错误))
    错误 = security.检查调用("send_private_msg", {"user_id": "888", "message": "私聊"})
    判定("send_private_msg → 白名单外的 QQ 被拒", bool(错误), str(错误)[:56])
    错误 = security.检查调用("send_private_msg", {"user_id": "999", "message": "私聊"})
    判定("send_private_msg → 白名单内的 QQ 放行", 错误 is None, str(错误))
    错误 = security.检查调用("set_group_ban", {"group_id": 999999, "user_id": 888, "duration": 60})
    判定("数字型 group_id 一样被拦", bool(错误), str(错误)[:56])

    print("\n⑦ 读取类动作也要看目标(第二轮评审:只读豁免导致可跨群读历史)")
    错误 = security.检查调用("get_group_msg_history", {"group_id": "999999"})
    判定("读群历史 → 白名单外的群被拒", bool(错误), str(错误)[:56])
    错误 = security.检查调用("get_group_msg_history", {"group_id": "123456"})
    判定("读群历史 → 白名单内的群放行", 错误 is None, str(错误))
    错误 = security.检查调用("get_group_member_list", {"group_id": "999999"})
    判定("成员列表 → 白名单外的群被拒", bool(错误), str(错误)[:56])
    错误 = security.检查调用("get_friend_msg_history", {"user_id": "888"})
    判定("读私聊历史 → 白名单外的 QQ 被拒", bool(错误), str(错误)[:56])
    错误 = security.检查调用("get_group_list", {})
    判定("本身不带目标参数的动作照常放行", 错误 is None, str(错误))

    print("\n⑧ 与既有闸门的叠加")
    错误 = security.检查调用("get_cookies", {})
    判定("凭据类动作仍被「永不放过」拦下", bool(错误) and "凭据" in str(错误), str(错误)[:36])
    错误 = security.检查调用("upload_group_file",
                             {"group_id": "999999", "file": "/etc/passwd", "name": "x"})
    判定("动作未授权 + 目标越界 → 拒绝", bool(错误), str(错误)[:56])
    设插件配置({})


def 主体():
    临时 = Path(tempfile.mkdtemp(prefix="napcat_acl_"))
    允许目录 = 临时 / "allow"
    允许目录.mkdir()
    建立临时媒体策略(允许目录)
    核心发送(允许目录)
    动作目标()

    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(主体())
