#!/usr/bin/env python3
"""反向 WS 加固的验证:绑定性、认证顺序、连接顶替。

不是读代码判断,而是真的起服务端、用 websockets 客户端连上去打。

用法(需要一个装了 Hermes 依赖的 python,因为要 import websockets):

    HERMES_WORKSPACE=~/.hermes/installs/*/environments/*/workspace \
        python tests/test_ws_hardening.py

不设 HERMES_WORKSPACE 时会自动在 ~/.hermes/installs 下找一个含 gateway/ 的 workspace。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包  # noqa: E402

加载包("tools", "ws")

import websockets  # noqa: E402

WS = sys.modules["napcat_plugin.ws"].WS
是回环 = sys.modules["napcat_plugin.ws"]._是回环地址

结果 = []


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


async def 主体():
    print("① 地址判定")
    for addr, want in (("127.0.0.1", True), ("localhost", True), ("::1", True),
                       ("[::1]", True), ("127.0.0.5", True),
                       ("0.0.0.0", False), ("::", False), ("192.168.1.5", False),
                       ("example.com", False)):
        判定(f"_是回环地址({addr!r}) == {want}", 是回环(addr) is want)

    print("\n② 非回环 + 无令牌 → 必须拒绝启动")
    bad = WS(lambda d: None, "0.0.0.0", 16811, "")
    try:
        await bad.启动()
        await bad.停止()
        判定("0.0.0.0 + 无令牌 被拒绝", False, "竟然启动成功了!")
    except ValueError as e:
        判定("0.0.0.0 + 无令牌 被拒绝", True, str(e)[:46] + "…")

    print("\n③ 非回环 + 有令牌 → 允许(令牌补上就行)")
    ok_remote = WS(lambda d: None, "192.0.2.1", 16812, "tok")  # TEST-NET,绑不上但应过守卫
    try:
        await ok_remote.启动()
        await ok_remote.停止()
        判定("非回环 + 有令牌 通过守卫", True)
    except ValueError as e:
        判定("非回环 + 有令牌 通过守卫", False, f"被守卫拦了: {e}")
    except OSError:
        判定("非回环 + 有令牌 通过守卫", True, "守卫放行,绑定失败属预期(TEST-NET 地址)")

    print("\n④ 回环 + 无令牌 → 仍允许(默认配置不能被搞坏)")
    ok_local = WS(lambda d: None, "127.0.0.1", 16813, "")
    try:
        await ok_local.启动()
        await ok_local.停止()
        判定("127.0.0.1 + 无令牌 可用", True)
    except Exception as e:
        判定("127.0.0.1 + 无令牌 可用", False, f"{type(e).__name__}: {e}")

    print("\n⑤ 核心回归:坏令牌连接不得污染发送通道")
    srv = WS(lambda d: None, "127.0.0.1", 16814, "good-token")
    await srv.启动()
    try:
        # 先让合法客户端接上,建立正常的发送通道
        legit = await websockets.connect("ws://127.0.0.1:16814/?access_token=good-token")
        await asyncio.sleep(0.3)
        第一任 = srv._ws连接实例
        判定("合法客户端已成为当前连接", 第一任 is not None)

        # 攻击者用坏令牌连一次,然后断开
        try:
            async with websockets.connect("ws://127.0.0.1:16814/?access_token=wrong"):
                await asyncio.sleep(0.3)
        except Exception:
            pass
        await asyncio.sleep(0.3)
        判定("坏令牌之后,当前连接未被改写(DoS 已修)", srv._ws连接实例 is 第一任,
             f"当前={type(srv._ws连接实例).__name__ if srv._ws连接实例 else None}")

        # 合法通道仍可用:发一个动作,应能真的收发
        # 注意:假响应器必须读【客户端】那头 —— 服务端 ServerConnection 的迭代器
        # 已被 _认证并处理连接 自己的 async for 占着,再挂一个读不到东西。
        async def 假响应():
            try:
                async for msg in legit:
                    import json as _j
                    d = _j.loads(msg)
                    if d.get("echo"):
                        await legit.send(_j.dumps({"status": "ok", "retcode": 0,
                                                 "echo": d["echo"], "data": {"ok": 1}}))
            except Exception:
                pass

        任务 = asyncio.create_task(假响应())
        调用 = await srv.调用API("get_login_info", {}, 超时秒数=3)
        任务.cancel()
        判定("坏令牌之后,合法通道仍能收发", 调用.get("status") == "ok", str(调用)[:60])

        # 新合法客户端顶替旧连接
        第二任客户端 = await websockets.connect("ws://127.0.0.1:16814/?access_token=good-token")
        await asyncio.sleep(0.4)
        判定("新客户端顶替旧连接", srv._ws连接实例 is not 第一任)
        try:
            # 从【旧客户端】那侧看它有没有被服务端断开 —— 这才是「旧连接已关闭」的真判据
            await asyncio.wait_for(legit.recv(), timeout=2)
            判定("旧连接被服务端关闭", False, "旧客户端还能收到数据")
        except Exception as e:
            判定("旧连接被服务端关闭", True, type(e).__name__)
        await 第二任客户端.close()
        await asyncio.sleep(0.3)
        判定("当前连接断开后置空,不会留下死 socket", srv._ws连接实例 is None)
    finally:
        await srv.停止()

    print("\n⑥ 监听位置判定(Unix socket 也算本地)")
    是本地 = sys.modules["napcat_plugin.ws"]._是本地监听
    for addr, want in (("/dev/shm/napcat.sock", True), ("/run/napcat.sock", True),
                       ("127.0.0.1", True), ("localhost", True),
                       ("0.0.0.0", False), ("192.168.1.5", False)):
        判定(f"_是本地监听({addr!r}) == {want}", 是本地(addr) is want)

    print("\n⑦ Unix socket 模式:起服务、权限、认证、残留清理")
    import os as _os
    import socket as _socket
    import stat as _stat
    import tempfile as _tempfile

    from websockets.asyncio.client import unix_connect

    根 = Path(_tempfile.mkdtemp(prefix="napcat_uds_"))
    sock路径 = str(根 / "napcat.sock")
    收到的事件 = []

    async def 收事件(数据):
        收到的事件.append(数据)

    # 无令牌也能起:本地监听不受「非回环必须带令牌」那条约束
    服务 = WS(收事件, sock路径, 0, "")
    await 服务.启动()
    判定("socket 文件已创建", _os.path.exists(sock路径), sock路径)
    权限位 = oct(_stat.S_IMODE(_os.stat(sock路径).st_mode))
    判定("权限被显式收紧到 0660(不靠 umask)", 权限位 == "0o660", 权限位)

    async with unix_connect(sock路径, additional_headers={"X-Self-ID": "80001"}) as 客户端:
        await asyncio.sleep(0.4)
        判定("客户端经 socket 连上并被采纳", 服务._ws连接实例 is not None)
        判定("socket 模式下握手头 X-Self-ID 同样生效",
            服务._对端SelfID == "80001", repr(服务._对端SelfID))
    await asyncio.sleep(0.4)
    判定("断开后置空,不留死引用", 服务._ws连接实例 is None)
    await 服务.停止()
    判定("停止后 socket 文件被删除", not _os.path.exists(sock路径))

    # 残留的死 socket(上次没退干净)要能清掉并重新绑定
    死socket = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    死socket.bind(sock路径)
    死socket.close()
    判定("(已造出一个残留 socket 文件)", _os.path.exists(sock路径))
    服务2 = WS(收事件, sock路径, 0, "good-token")
    await 服务2.启动()
    判定("残留 socket 被清掉后能重新绑定", _os.path.exists(sock路径))
    try:
        async with unix_connect(sock路径, "ws://localhost/?access_token=good-token"):
            await asyncio.sleep(0.4)
            判定("socket 模式下令牌认证照常生效", 服务2._ws连接实例 is not None)
    except Exception as e:
        判定("socket 模式下令牌认证照常生效", False, f"{type(e).__name__}: {e}")
    try:
        async with unix_connect(sock路径, "ws://localhost/?access_token=坏的") as 坏客户端:
            await asyncio.sleep(0.4)
            await asyncio.wait_for(坏客户端.recv(), timeout=1)
        判定("socket 模式下坏令牌被拒", False, "坏令牌居然保持连接")
    except Exception as e:
        判定("socket 模式下坏令牌被拒", True, type(e).__name__)
    await 服务2.停止()

    # 同名普通文件:拒绝启动,而不是删掉别人的东西
    占位文件 = 根 / "占用"
    占位文件.write_text("x")
    服务3 = WS(收事件, str(占位文件), 0, "")
    try:
        await 服务3.启动()
        await 服务3.停止()
        判定("同名普通文件 → 拒绝启动(不删别人的文件)", False, "竟然启动了")
    except ValueError as e:
        判定("同名普通文件 → 拒绝启动(不删别人的文件)", True, str(e)[:38] + "…")
    判定("那个文件还在", 占位文件.exists())

    # 属组配置:给了不存在的组名只告警,不该拦住启动
    服务4 = WS(收事件, sock路径, 0, "", "不存在的组名_xyz")
    await 服务4.启动()
    判定("属组名不存在时仍能启动(只告警)", _os.path.exists(sock路径))
    await 服务4.停止()

    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(主体()))
