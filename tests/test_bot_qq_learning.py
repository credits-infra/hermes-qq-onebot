#!/usr/bin/env python3
"""机器人 QQ 号的学习来源。

两处来源,优先级明确:
  ① 事件里的 `self_id`(各实现都会带);
  ② 握手里的 `X-Self-ID`(见 ws._对端SelfID)—— 实现漏给 self_id 时兜底。
最后一条用例是端到端的:没有 self_id、只有握手头时,群里 @ 机器人仍然认得出「@的是自己」。

用法:
    python tests/test_bot_qq_learning.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包, 注册napcat平台  # noqa: E402

加载包("tools", "main", "adapter")
注册napcat平台()
adapter模块 = sys.modules["napcat_plugin.adapter"]

结果 = []
_序号 = [0]


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


def 造适配器(extra=None):
    from gateway.config import PlatformConfig

    base = {"allowed_qq_ids": ["10001"], "allowed_group_ids": [123456]}
    base.update(extra or {})
    return adapter模块._创建适配器(PlatformConfig(enabled=True, extra=base))


class 假WS:
    """只用于提供 _对端SelfID(主适配器的活动连接在测试里不存在)。"""

    def __init__(self, self_id=""):
        self._对端SelfID = self_id

    async def 获取消息(self, 消息ID):
        return {"status": "ok", "data": {"message": []}}


def 群事件(文本, self_id=None, 艾特="90000"):
    段 = [{"type": "at", "data": {"qq": 艾特}},
          {"type": "text", "data": {"text": 文本}}]
    事件 = {
        "post_type": "message",
        "message_type": "group",
        "user_id": "10001",
        "group_id": "123456",
        "message_id": f"m{_序号[0]}",
        "sender": {"nickname": "测试者", "card": ""},
        "message": 段,
        "raw_message": f"[CQ:at,qq={艾特}] {文本}",
    }
    _序号[0] += 1
    if self_id is not None:
        事件["self_id"] = str(self_id)
    return 事件


def 跑(适配器, 事件):
    收到 = []

    async def 假分发(ev):
        收到.append(ev)

    适配器.handle_message = 假分发
    asyncio.run(适配器._处理WS事件(事件))
    return 收到


def 主体():
    print("① 事件里的 self_id 优先")
    a = 造适配器()
    a.ws = 假WS("123456789")
    跑(a, 群事件("你好", self_id=90000))
    判定("用事件的 self_id(不是握手值)", a.机器人QQ号 == "90000", a.机器人QQ号)

    print("\n② 事件没给 self_id → 用握手头声明的")
    a = 造适配器()
    a.ws = 假WS("123456789")
    跑(a, 群事件("你好"))            # 不带 self_id
    判定("落到握手头的值", a.机器人QQ号 == "123456789", a.机器人QQ号)

    print("\n③ 两边都没有 → 保持空(不瞎填)")
    a = 造适配器()
    a.ws = 假WS("")
    跑(a, 群事件("你好"))
    判定("仍是空", a.机器人QQ号 == "", repr(a.机器人QQ号))

    print("\n④ 端到端:只有握手头时,群里的 @ 触发仍认得出自己")
    a = 造适配器()
    a.ws = 假WS("90000")             # 只有握手头声明
    收到 = 跑(a, 群事件("这句话会进网关吗"))   # @ 的是 90000,事件不带 self_id
    判定("被 @ 的消息进了网关", len(收到) == 1,
         "没进网关 —— 说明没认出手握头里的机器人号" if not 收到 else "")

    a = 造适配器()
    a.ws = 假WS("90000")
    收到 = 跑(a, 群事件("这句不该进网关", 艾特="88888"))   # @ 的是别人
    判定("@ 别人时仍然不触发", not 收到)


def run():
    主体()
    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(run())
