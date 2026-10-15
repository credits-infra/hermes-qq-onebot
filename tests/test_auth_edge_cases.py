#!/usr/bin/env python3
"""反向 WS 认证的边界情形。

起因:测试握手头时撞出来的 —— `hmac.compare_digest(令牌, 访问令牌)` 对 str 要求纯
ASCII,客户端发一个非 ASCII 令牌(例如中文)会抛
    TypeError: comparing strings with non-ASCII characters is not supported
而认证代码不在 try 里,于是连接带着 traceback 断开:安全上仍是失败即拒,但日志被噪音
污染,而且任何人发非 ASCII 令牌都能刷 traceback。

这里断言「干净拒绝」的两个证据:① 插件打出的是那句「认证失败，拒绝连接」;
② websockets 没有打出 connection handler 的 ERROR(traceback 会被它记成 ERROR)。

用法:
    python tests/test_auth_edge_cases.py
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包  # noqa: E402

加载包("tools", "ws")
WS = sys.modules["napcat_plugin.ws"].WS

import websockets  # noqa: E402

结果 = []
端口 = [17040]


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


class 日志捕获(logging.Handler):
    def __init__(self):
        super().__init__()
        self.记录 = []

    def emit(self, record):
        self.记录.append((record.name, record.levelno, record.getMessage()))


async def 场景(访问令牌: str, 客户端头: dict, 路径: str = "/"):
    端口[0] += 1
    p = 端口[0]
    srv = WS(lambda d: None, "127.0.0.1", p, 访问令牌)
    await srv.启动()
    捕获 = 日志捕获()
    logging.getLogger().addHandler(捕获)
    连 = None
    客户端被关 = False
    try:
        连 = await websockets.connect(f"ws://127.0.0.1:{p}{路径}", additional_headers=客户端头)
        await asyncio.sleep(0.35)
        try:
            await asyncio.wait_for(连.recv(), timeout=2)
        except Exception:
            客户端被关 = True
        await asyncio.sleep(0.2)
        return {
            "对端SelfID": srv._对端SelfID,
            "已接管": srv._ws连接实例 is not None,
            "客户端被关": 客户端被关,
            "插件认证失败日志": [m for n, lv, m in 捕获.记录
                            if n.startswith("napcat_plugin") and "认证失败" in m],
            "websockets错误": [(lv, m) for n, lv, m in 捕获.记录
                           if n.startswith("websockets") and lv >= logging.ERROR],
        }
    finally:
        if 连 is not None:
            try:
                await 连.close()
            except Exception:
                pass
        logging.getLogger().removeHandler(捕获)
        await srv.停止()


async def 主体():
    print("① 非 ASCII 令牌 → 干净拒绝(本次修的就是这条)")
    结果1 = await 场景("good-token", {"Authorization": "Bearer 中文坏令牌",
                                   "X-Self-ID": "666"})
    判定("插件打出了「认证失败，拒绝连接」", len(结果1["插件认证失败日志"]) == 1,
         str(结果1["插件认证失败日志"]))
    判定("websockets 没有 ERROR(traceback 就是它记的)", not 结果1["websockets错误"],
         str(结果1["websockets错误"][:1]))
    判定("连接被关", 结果1["客户端被关"])
    判定("没接管发送通道", not 结果1["已接管"])
    判定("没写入 X-Self-ID", 结果1["对端SelfID"] == "", repr(结果1["对端SelfID"]))

    print("\n② 普通 ASCII 错误令牌 → 同样干净(回归)")
    结果2 = await 场景("good-token", {"Authorization": "Bearer wrong"})
    判定("也是干净拒绝", len(结果2["插件认证失败日志"]) == 1 and not 结果2["websockets错误"])

    print("\n③ 双方都是非 ASCII 的令牌 → 正常放行(修复前这里会抛)")
    # 实测:头里的非 ASCII 字节被 websockets 以 surrogateescape 解出来(含代理字符),
    # 用 surrogateescape 编回去正好还原成客户端发来的原始字节,于是能正确判等 ——
    # 所以非 ASCII 令牌经头也是可用的(修复前它在 encode 那一步就抛 UnicodeEncodeError)。
    结果3 = await 场景("秘密令牌🔒", {"Authorization": "Bearer 秘密令牌🔒",
                                  "X-Self-ID": "123"})
    判定("非 ASCII 令牌正确判等 → 接管", 结果3["已接管"])
    判定("没有误报认证失败", not 结果3["插件认证失败日志"])
    判定("X-Self-ID 正常写入", 结果3["对端SelfID"] == "123", repr(结果3["对端SelfID"]))

    print("\n④ 从 URL 查询参数传令牌同样可走(含非 ASCII)")
    结果4 = await 场景("秘密令牌🔒", {}, 路径="/?access_token=秘密令牌🔒")
    判定("URL 里的令牌生效 → 接管", 结果4["已接管"])
    结果5 = await 场景("good-token", {}, 路径="/?access_token=中文乱写")
    判定("URL 里的非 ASCII 错令牌 → 干净拒绝",
         len(结果5["插件认证失败日志"]) == 1 and not 结果5["websockets错误"])

    print("\n⑤ 完全没有 Authorization 头")
    结果6 = await 场景("good-token", {})
    判定("无头 → 干净拒绝", len(结果6["插件认证失败日志"]) == 1 and not 结果6["websockets错误"])

    print("\n⑥ 服务端没配令牌时不校验(默认配置不能变严)")
    结果7 = await 场景("", {"X-Self-ID": "999"})
    判定("无令牌配置 → 照常接管", 结果7["已接管"] and 结果7["对端SelfID"] == "999")


def run():
    asyncio.run(主体())
    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(run())
