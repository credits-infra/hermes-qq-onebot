#!/usr/bin/env python3
"""准入加固的验证:群白名单、群指令触发条件、出站目标白名单。

不是读代码判断,而是打真实的入站链路 `_处理消息事件()`(去重 → 过滤自己 →
用户白名单 → 群白名单 → 触发检测 → 分发),看哪些消息**真的进了网关**。

用法:
    python tests/test_access_control.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包, 注册napcat平台  # noqa: E402

加载包("tools", "security", "main", "llm_tools", "adapter")
注册napcat平台()
security = sys.modules["napcat_plugin.security"]
adapter模块 = sys.modules["napcat_plugin.adapter"]
llm_tools = sys.modules["napcat_plugin.llm_tools"]
tools = sys.modules["napcat_plugin.tools"]

结果 = []
_序号 = [0]


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


def _报错(函数) -> bool:
    """函数是否按预期抛了异常。"""
    try:
        函数()
    except Exception:
        return True
    return False


def 造适配器(extra):
    from gateway.config import PlatformConfig

    return adapter模块._创建适配器(PlatformConfig(enabled=True, extra=extra))


def 群事件(用户ID, 群ID, 文本, 艾特=False, 机器人QQ="90000"):
    _序号[0] += 1
    段 = []
    if 艾特:
        段.append({"type": "at", "data": {"qq": 机器人QQ}})
    段.append({"type": "text", "data": {"text": 文本}})
    return {
        "message_type": "group",
        "user_id": str(用户ID),
        "group_id": str(群ID),
        "message_id": f"m{_序号[0]}",
        "sender": {"nickname": "测试者", "card": ""},
        "message": 段,
        "raw_message": 文本,
    }


def 跑事件(适配器, 事件):
    """把事件喂进真实入站链路,返回「是否分发到了网关」。"""
    收到 = []

    async def 假分发(ev):
        收到.append(ev)

    适配器.handle_message = 假分发
    asyncio.run(适配器._处理消息事件(事件))
    return 收到


基础配置 = {"bot_self_id": "90000", "allowed_qq_ids": ["10001"]}


def 主体():
    print("① 名单解析(各种配置形态)")
    判定("字符串 '111,222'", tools.解析号码名单("111,222") == frozenset({"111", "222"}))
    判定("列表 [111,222]", tools.解析号码名单([111, 222]) == frozenset({"111", "222"}))
    判定("裸数字 111(YAML 会解析成 int)", tools.解析号码名单(111) == frozenset({"111"}))
    判定("空配置 → 空集合", tools.解析号码名单("") == frozenset())
    判定("all 被识别为全放行", tools.名单是全放行(tools.解析号码名单("all")))
    判定("数字群号不算全放行", not tools.名单是全放行(tools.解析号码名单("111")))
    判定("JSON 数组字符串(README 的写法)",
        tools.解析号码名单('["111", "222"]') == frozenset({"111", "222"}))
    判定("分号分隔也认", tools.解析号码名单("111;222") == frozenset({"111", "222"}))
    判定("非法类型仍然报错", _报错(lambda: tools.解析号码名单({"a": 1})))

    print("\n② 群白名单:默认空 = 一个群都不收")
    a = 造适配器(基础配置)
    判定("空群白名单下 群111 被拒", not a._群被允许("111"))
    判定("入站:群111 的消息没进网关", not 跑事件(a, 群事件("10001", "111", "你好", 艾特=True)))

    print("\n③ 群白名单:配了就按名单")
    a = 造适配器({**基础配置, "allowed_group_ids": [111, 222]})
    判定("群111 在白名单内", a._群被允许("111"))
    判定("群333 不在白名单内", not a._群被允许("333"))
    判定("入站:群111 + 被@ → 进网关", bool(跑事件(a, 群事件("10001", "111", "你好", 艾特=True))))
    判定("入站:群333 + 被@ → 不进网关", not 跑事件(a, 群事件("10001", "333", "你好", 艾特=True)))

    a = 造适配器({**基础配置, "allowed_group_ids": "all"})
    判定("群白名单=all 时任意群可进", bool(跑事件(a, 群事件("10001", "999", "你好", 艾特=True))))

    a = 造适配器({**基础配置, "allowed_group_ids": '["111", "222"]'})
    判定("config 里写 JSON 数组字符串也能用",
        a._群被允许("111") and a._群被允许("222"))

    os.environ["NAPCAT_ALLOWED_GROUPS"] = '["111", "222"]'
    a = 造适配器(基础配置)
    判定("环境变量 NAPCAT_ALLOWED_GROUPS 的 JSON 数组形式也能解析", a._群被允许("222"))
    del os.environ["NAPCAT_ALLOWED_GROUPS"]

    print("\n④ 群里的斜杠指令:默认也要求 @/关键词")
    a = 造适配器({**基础配置, "allowed_group_ids": [111]})
    判定("指令无@ → 不进网关(默认收紧)",
        not 跑事件(a, 群事件("10001", "111", "/reset")))
    判定("指令带@ → 进网关",
        bool(跑事件(a, 群事件("10001", "111", "/reset", 艾特=True))))
    判定("@了别人 + 指令 → 不进网关",
        not 跑事件(a, {**群事件("10001", "111", "/reset"),
                    "message": [{"type": "at", "data": {"qq": "88888"}},
                                {"type": "text", "data": {"text": "/reset"}}]}))

    a = 造适配器({**基础配置, "allowed_group_ids": [111],
                  "group_command_requires_mention": False})
    判定("显式关掉后,指令无@也进网关(保持旧行为的开关有效)",
        bool(跑事件(a, 群事件("10001", "111", "/reset"))))

    print("\n⑤ 用户白名单仍然生效")
    a = 造适配器({**基础配置, "allowed_group_ids": [111]})
    判定("白名单用户 → 进", bool(跑事件(a, 群事件("10001", "111", "你好", 艾特=True))))
    判定("非白名单用户 → 不进", not 跑事件(a, 群事件("20002", "111", "你好", 艾特=True)))

    print("\n⑥ 出站目标白名单(工具指定目标也要过)")
    class 假配置:
        def __init__(self, extra):
            self.extra = extra

    class 假适配器实例:
        def __init__(self, extra):
            self.config = 假配置(extra)
            self.发送记录 = []

        async def send(self, chat_id=None, content="", **kw):
            self.发送记录.append((chat_id, content))

            class R:
                success = True
                message_id = None
                error = None

            return R()

    假适配器 = 假适配器实例({"allowed_qq_ids": ["10001"], "allowed_group_ids": [111]})
    adapter模块._适配器实例 = 假适配器

    判定("发到白名单内的群 → 放行",
        security.检查发信目标("group", "111") is None)
    判定("发到白名单外的群 → 拒", security.检查发信目标("group", "999") is not None)
    判定("发给白名单内的用户 → 放行",
        security.检查发信目标("private", "10001") is None)
    判定("发给白名单外的用户 → 拒", security.检查发信目标("private", "88888") is not None)
    判定("空目标 → 拒", security.检查发信目标("group", "") is not None)

    假适配器.发送记录.clear()
    输出 = asyncio.run(llm_tools._handle_send_message(
        {"target_type": "group", "target_id": "999", "message": "越权测试"}))
    判定("工具端到端:发外部群被拦且没真的发", not 假适配器.发送记录, 输出[:70])

    假适配器.发送记录.clear()
    asyncio.run(llm_tools._handle_send_message(
        {"target_type": "group", "target_id": "111", "message": "正常测试"}))
    判定("工具端到端:发白名单内的群真的发了",
        len(假适配器.发送记录) == 1, str(假适配器.发送记录[:1]))

    adapter模块._适配器实例 = None

    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(主体())
