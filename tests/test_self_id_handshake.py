#!/usr/bin/env python3
"""握手头 X-Self-ID 的验证(反向 WS 层)。

OneBot v11 的反向 WS 客户端连上来时会发 `X-Self-ID`(机器人 QQ 号)、
`X-Client-Role`。这里验证我们确实读到了它,并且**只在一处**读:
认证通过之后,未授权连接不得写入任何状态(与「认证通过才接管发送通道」同一原则)。

用法:
    python tests/test_self_id_handshake.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包  # noqa: E402

加载包("tools", "ws")
WS = sys.modules["napcat_plugin.ws"].WS

import websockets  # noqa: E402

结果 = []
端口 = [17010]


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


async def 连一次(srv, 端口号, 头: dict, 令牌: str = "good-token"):
    try:
        async with websockets.connect(
            f"ws://127.0.0.1:{端口号}/", additional_headers=头
        ) as 连接:
            await asyncio.sleep(0.35)
            return 连接
    except Exception as e:
        return e


async def 主体():
    print("① 带 X-Self-ID 的正常连接")
    端口[0] += 1
    p = 端口[0]
    srv = WS(lambda d: None, "127.0.0.1", p, "good-token")
    await srv.启动()
    try:
        连 = await 连一次(srv, p, {"Authorization": "Bearer good-token",
                                 "X-Self-ID": "123456789"})
        判定("认证通过后读到了 X-Self-ID", srv._对端SelfID == "123456789",
             f"读到={srv._对端SelfID!r}")
        判定("连接仍被正常接管", srv._ws连接实例 is not None)
        del 连

        print("\n② 头名大小写不敏感(实测,非假设)")
        连 = await 连一次(srv, p, {"Authorization": "Bearer good-token",
                                 "x-self-id": "987654321"})
        判定("小写 x-self-id 也能读到", srv._对端SelfID == "987654321",
             f"读到={srv._对端SelfID!r}")
        del 连

        print("\n③ 不带该头 → 空(不瞎填)")
        连 = await 连一次(srv, p, {"Authorization": "Bearer good-token"})
        判定("没有头就是空字符串", srv._对端SelfID == "", f"读到={srv._对端SelfID!r}")
        del 连

        print("\n④ 未授权连接不得写入状态")
        srv._对端SelfID = ""          # 先清干净
        连 = await 连一次(srv, p, {"Authorization": "Bearer 坏令牌",
                                 "X-Self-ID": "666666666"})
        await asyncio.sleep(0.2)
        判定("坏令牌连接没把 SelfID 写进来", srv._对端SelfID == "",
             f"读到={srv._对端SelfID!r}(应为空)")
        判定("坏令牌也没接管发送通道", srv._ws连接实例 is None)
        del 连
    finally:
        await srv.停止()


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
