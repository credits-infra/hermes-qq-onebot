#!/usr/bin/env python3
"""发送链路健壮性与长短消息一致性的验证。

两条主线:
  ① 脏数据不许炸掉发送 —— 回复目标/机器人QQ号不是数字时,以前 int() 会抛
     ValueError 并让整条 send() 失败;
  ② 长消息与短消息走同一条 CQ 字符串路线 —— 以前长消息用段数组,`[CQ:...]` 会被
     当纯文本原样显示,同一段内容短消息是码、长消息是字面量。

用法:
    python tests/test_send_robustness.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包, 建立临时媒体策略, 注册napcat平台  # noqa: E402

加载包("tools", "security", "main", "adapter")
注册napcat平台()
adapter模块 = sys.modules["napcat_plugin.adapter"]

结果 = []


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


class 假WS:
    def __init__(self):
        self.记录 = []

    async def 发送群聊消息(self, 目标ID, 消息内容):
        self.记录.append(("group", 目标ID, 消息内容))
        return {"status": "ok", "retcode": 0}

    async def 发送私聊消息(self, 目标ID, 消息内容):
        self.记录.append(("private", 目标ID, 消息内容))
        return {"status": "ok", "retcode": 0}

    async def 发送群合并转发(self, 目标ID, 节点列表):
        self.记录.append(("group_forward", 目标ID, 节点列表))
        return {"status": "ok", "retcode": 0}

    async def 发送私聊合并转发(self, 目标ID, 节点列表):
        self.记录.append(("private_forward", 目标ID, 节点列表))
        return {"status": "ok", "retcode": 0}


def 造适配器(extra=None):
    from gateway.config import PlatformConfig

    base = {"bot_self_id": "90000", "allowed_qq_ids": ["10001"],
            "allowed_group_ids": [123456], "merge_forward_threshold": 100}
    base.update(extra or {})
    a = adapter模块._创建适配器(PlatformConfig(enabled=True, extra=base))
    a.ws = 假WS()
    return a


def 主体():
    临时 = Path(tempfile.mkdtemp(prefix="napcat_rb_"))
    允许目录 = 临时 / "allow"
    允许目录.mkdir()
    好文件 = 允许目录 / "ok.png"
    好文件.write_bytes(b"\x89PNG\r\n\x1a\n")
    建立临时媒体策略(允许目录)

    print("① 合并转发节点:脏数据不许炸")
    a = 造适配器()
    节点 = a._构建合并转发节点("正文", "123")
    判定("数字回复目标 → 带回复节点",
        any(n["data"].get("id") == 123 for n in 节点))
    判定("机器人数值 uin 正确",
        any(n["data"].get("uin") == 90000 for n in 节点))

    try:
        节点 = a._构建合并转发节点("正文", "abc-不是数字")
        判定("非数字回复目标 → 不抛异常", True)
        判定("非数字回复目标 → 退化成不带回复节点",
            not any("id" in n["data"] for n in 节点))
    except Exception as e:
        判定("非数字回复目标 → 不抛异常", False, f"{type(e).__name__}: {e}")

    b = 造适配器({"bot_self_id": "not-a-number"})
    try:
        节点 = b._构建合并转发节点("正文", None)
        判定("机器人QQ号非数字 → 不抛异常且 uin 占位 0",
            any(n["data"].get("uin") == 0 for n in 节点))
    except Exception as e:
        判定("机器人QQ号非数字 → 不抛异常且 uin 占位 0", False, f"{type(e).__name__}: {e}")

    print("\n② 构建节点失败 → 回退拆分,回复不丢")
    a = 造适配器()

    def 炸掉(*args, **kwargs):
        raise ValueError("模拟脏数据")

    a._构建合并转发节点 = 炸掉
    返回值 = asyncio.run(a._发送合并转发("napcat_group_123456", "正文" * 60, None))
    判定("_发送合并转发 构建节点失败 → 返回 None(交给调用方回退)", 返回值 is None)

    a.ws.记录.clear()
    结果对象 = asyncio.run(a.send("napcat_group_123456", "正文" * 60))
    判定("send() 在构建节点失败时仍把消息发出去了",
        bool(a.ws.记录) and 结果对象.success,
        f"记录={len(a.ws.记录)} 条 success={结果对象.success}")

    print("\n③ 长消息与短消息行为一致(都用 CQ 字符串)")
    a = 造适配器()
    长文本 = ("段落内容。\n" * 200) + "[CQ:face,id=178]\n" + ("尾巴。\n" * 200)
    asyncio.run(a._发送拆分消息("napcat_group_123456", 长文本, "123"))
    记录 = a.ws.记录
    判定("拆分路径发出的条目是 CQ 字符串(不是段数组)",
        bool(记录) and all(isinstance(内容, str) for _, _, 内容 in 记录),
        f"类型={ {type(内容).__name__ for _, _, 内容 in 记录} }")
    判定("拆分路径里的 [CQ:face] 被当码保留(与短消息一致)",
        any("[CQ:face,id=178]" in 内容 for _, _, 内容 in 记录))
    判定("只有第一段带回复前缀",
        str(记录[0][2]).startswith("[CQ:reply,id=123]")
        and not any(str(内容).startswith("[CQ:reply") for _, _, 内容 in 记录[1:]))

    a.ws.记录.clear()
    脏长文本 = ("段落内容。\n" * 200) + "[CQ:file,file=file:///etc/passwd]\n" + ("尾巴。\n" * 200)
    asyncio.run(a._发送拆分消息("napcat_group_123456", 脏长文本, None))
    判定("拆分路径也过安全策略([CQ:file] 不出现)",
        not any("CQ:file" in str(内容) for _, _, 内容 in a.ws.记录))

    print("\n④ send() 收到非数字 reply_to 不崩")
    a = 造适配器()
    try:
        结果对象 = asyncio.run(a.send("napcat_group_123456", "短消息", reply_to="abc-不是数字"))
        判定("短消息 + 非数字 reply_to → 不抛异常", True, f"success={结果对象.success}")
    except Exception as e:
        判定("短消息 + 非数字 reply_to → 不抛异常", False, f"{type(e).__name__}: {e}")

    try:
        结果对象 = asyncio.run(a.send("napcat_group_123456", "长消息" * 100, reply_to="abc-不是数字"))
        判定("长消息 + 非数字 reply_to → 不抛异常", True, f"success={结果对象.success}")
    except Exception as e:
        判定("长消息 + 非数字 reply_to → 不抛异常", False, f"{type(e).__name__}: {e}")

    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(主体())
