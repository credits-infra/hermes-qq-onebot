#!/usr/bin/env python3
"""入站消息格式兼容的验证。

背景:OneBot 的 `message` 字段有两种形态 —— 段数组,或 `message_format=string` 时的
CQ 码字符串(LLOneBot/LuckyLilliaBot 的 messageFormat 可配 'string')。原实现
「不是 list 就置空」会把整条消息静默丢掉。

用法:
    python tests/test_inbound_formats.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包, 注册napcat平台  # noqa: E402

加载包("tools", "main", "adapter")
注册napcat平台()
tools = sys.modules["napcat_plugin.tools"]
adapter模块 = sys.modules["napcat_plugin.adapter"]

结果 = []
_序号 = [0]


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


# ══════════════════════════════════════════════════════════════════════════════
# ① 单元:规范化消息段
# ══════════════════════════════════════════════════════════════════════════════

def 单元():
    print("① 规范化消息段")
    数组 = [{"type": "text", "data": {"text": "原样"}}]
    判定("段数组原样通过", tools.规范化消息段(数组) == 数组)
    判定("数组里的非 dict 项被剔除",
        tools.规范化消息段([{"type": "text", "data": {"text": "a"}}, "垃圾", 42])
        == [{"type": "text", "data": {"text": "a"}}])

    段 = tools.规范化消息段("[CQ:at,qq=90000] 你好")
    判定("CQ 字符串 → 段数组(2 段)",
        len(段) == 2 and 段[0]["type"] == "at" and 段[0]["data"]["qq"] == "90000",
        str(段))
    判定("CQ 码后的文本保留", 段[1]["type"] == "text" and "你好" in 段[1]["data"]["text"])

    段 = tools.规范化消息段("就是一句普通话")
    判定("纯文本 → 单段", len(段) == 1 and 段[0]["data"]["text"] == "就是一句普通话")

    段 = tools.规范化消息段("前[CQ:face,id=178]后")
    判定("码夹在文本中间也拆对",
        [s["type"] for s in 段] == ["text", "face", "text"], str(段))
    判定("表情 id 正确", 段[1]["data"]["id"] == "178")

    段 = tools.规范化消息段("[CQ:image,file=a&#44;b.png]")
    判定("逗号转义 &#44; 被还原", 段[0]["data"]["file"] == "a,b.png", str(段[0]))

    段 = tools.规范化消息段("[CQ:image,file=br&#91;1&#93;.png]")
    判定("方括号转义 &#91;/&#93; 被还原", 段[0]["data"]["file"] == "br[1].png", str(段[0]))

    段 = tools.规范化消息段("[CQ:at,qq=123,name=A&amp;B]")
    判定("与号转义 &amp; 被还原", 段[0]["data"]["name"] == "A&B", str(段[0]))

    判定("None → 空", tools.规范化消息段(None) == [])
    判定("空串 → 空", tools.规范化消息段("") == [])
    判定("数字(脏数据)→ 空", tools.规范化消息段(12345) == [])

    段 = tools.规范化消息段("[CQ:broken")
    判定("没闭合的码原样当文本(不崩、不丢)",
        len(段) == 1 and 段[0]["type"] == "text", str(段))

    段 = tools.规范化消息段("[CQ:weird_type,x=1]")
    判定("入站不过滤类型(过滤是出站方向的事)",
        len(段) == 1 and 段[0]["type"] == "weird_type", str(段))

    段 = tools.规范化消息段("[CQ:image,file=x.png][CQ:image,file=y.png]")
    判定("连续两个码都不丢",
        [s["data"]["file"] for s in 段] == ["x.png", "y.png"], str(段))

    解析 = tools.解析CQ码("[CQ:image,file=/a/b.png,type=flash]")
    判定("解析CQ码:类型小写化 + 多参数",
        解析 is not None and 解析[0] == "image" and 解析[1] == {"file": "/a/b.png", "type": "flash"},
        str(解析))
    判定("解析CQ码:非 CQ 文本返回 None", tools.解析CQ码("随便一句话") is None)


# ══════════════════════════════════════════════════════════════════════════════
# ② 端到端:字符串格式的群消息能进网关
# ══════════════════════════════════════════════════════════════════════════════

def 造适配器(extra=None):
    from gateway.config import PlatformConfig

    base = {"bot_self_id": "90000", "allowed_qq_ids": ["10001"],
            "allowed_group_ids": [123456]}
    base.update(extra or {})
    return adapter模块._创建适配器(PlatformConfig(enabled=True, extra=base))


def 群事件(文本, 消息ID, 原始=None):
    return {
        "message_type": "group",
        "user_id": "10001",
        "group_id": "123456",
        "message_id": str(消息ID),
        "sender": {"nickname": "测试者", "card": ""},
        "message": 文本,
        "raw_message": 原始 if 原始 is not None else 文本,
    }


def 跑事件(适配器, 事件):
    收到 = []

    async def 假分发(ev):
        收到.append(ev)

    适配器.handle_message = 假分发
    asyncio.run(适配器._处理消息事件(事件))
    return 收到


def 端到端():
    print("\n② 端到端:message 是 CQ 字符串时不再被丢空")
    a = 造适配器()

    收到 = 跑事件(a, 群事件("[CQ:at,qq=90000] 请解释一下糖酵解", 501))
    判定("字符串格式的群消息进了网关", len(收到) == 1,
         "没进网关(原 bug:内容被丢空)" if not 收到 else "")
    if 收到:
        文本 = 收到[0].text
        判定("消息正文完整到达", "糖酵解" in 文本, repr(文本[:60]))
        判定("at 被渲染成可读文本", "@" in 文本, repr(文本[:60]))

    收到 = 跑事件(a, 群事件([{"type": "at", "data": {"qq": "90000"}},
                          {"type": "text", "data": {"text": "数组格式仍然正常"}}], 502))
    判定("段数组格式不受影响", len(收到) == 1 and "数组格式仍然正常" in 收到[0].text)

    收到 = 跑事件(a, 群事件("[CQ:at,qq=90000] 带表情 [CQ:face,id=178]", 503))
    判定("字符串里的表情段被解析", len(收到) == 1 and "表情" in 收到[0].text,
         repr(收到[0].text[:60]) if 收到 else "没进网关")

    收到 = 跑事件(a, 群事件(None, 504, 原始="[CQ:at,qq=90000] 只给了 raw_message"))
    判定("message 为空时回落到 raw_message", len(收到) == 1 and "raw_message" in 收到[0].text,
         "没进网关" if not 收到 else "")

    print("\n③ 被回复消息的 message 也可能是字符串")
    a = 造适配器()

    class 假WS:
        async def 获取消息(self, 消息ID):
            return {"status": "ok", "data": {"message": "[CQ:face,id=1] 这是被引用的原话"}}

    a.ws = 假WS()
    回复ID, 回复文本, 媒体映射 = asyncio.run(
        a._解析回复消息([{"type": "reply", "data": {"id": "999"}}]))
    判定("引用的字符串格式消息被解析出文本",
        回复文本 is not None and "被引用的原话" in 回复文本, repr(回复文本))

    class 假WS2:
        async def 获取消息(self, 消息ID):
            return {"status": "ok", "data": {"message": [{"type": "text", "data": {"text": "数组格式的原话"}}]}}

    a.ws = 假WS2()
    _, 回复文本, _ = asyncio.run(a._解析回复消息([{"type": "reply", "data": {"id": "998"}}]))
    判定("引用的数组格式仍正常", 回复文本 is not None and "数组格式的原话" in 回复文本)


def 主体():
    单元()
    端到端()
    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(主体())
