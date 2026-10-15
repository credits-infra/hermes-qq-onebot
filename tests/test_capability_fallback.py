#!/usr/bin/env python3
"""扩展动作的能力探测与优雅降级的验证。

背景:`set_msg_emoji_like` / `friend_poke` 是 NapCat/Lagrange/LLOneBot 的扩展动作,
不是 OneBot v11 标准。LLOneBot/LuckyLilliaBot 对没有的动作返
`retcode 1404` + `"<action> API 不存在"`。原实现把这个失败直接抛给上层,而上层是
「每次失败打一条 warning」——不支持该动作的实现于是**每条消息刷一行日志,功能永远
不工作**。

用法:
    python tests/test_capability_fallback.py
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包, 注册napcat平台  # noqa: E402

加载包("tools", "ws", "main", "adapter")
注册napcat平台()
ws模块 = sys.modules["napcat_plugin.ws"]
adapter模块 = sys.modules["napcat_plugin.adapter"]

结果 = []


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


def 造WS():
    return ws模块.WS(lambda d: None, "127.0.0.1", 16999, "")


def 装接口(ws, 响应表):
    """把 调用API 换成按动作查表的假实现,并记录调用过的动作。"""
    调用 = []

    async def 假调用API(动作, 参数, **kwargs):
        调用.append(动作)
        值 = 响应表.get(动作, {"status": "ok", "retcode": 0, "data": {}})
        return 值 if not callable(值) else 值(动作, 参数)

    ws.调用API = 假调用API
    return 调用


不支持 = {"status": "failed", "retcode": 1404, "msg": "friend_poke API 不存在"}
正常 = {"status": "ok", "retcode": 0, "data": {}}


# ══════════════════════════════════════════════════════════════════════════════
def 单元():
    print("① 「不支持」的识别")
    f = ws模块._是不支持
    判定("retcode 1404 → 不支持", f({"retcode": 1404}) is True)
    判定("'xxx API 不存在' → 不支持", f({"msg": "friend_poke API 不存在"}) is True)
    判定("'不支持的 API' → 不支持", f({"msg": "不支持的 API"}) is True)
    判定("英文 unsupported → 不支持", f({"message": "Unsupported action"}) is True)
    判定("普通错误(retcode 100 参数错误)→ 不算不支持",
        f({"retcode": 100, "msg": "参数错误"}) is False)
    判定("正常响应 → 不算不支持", f({"status": "ok", "retcode": 0}) is False)
    判定("非 dict → 不算不支持", f("boom") is False)

    print("\n② 戳一戳:标准动作优先,被拒退专有动作")
    ws = 造WS()
    调用 = 装接口(ws, {"send_poke": 不支持, "friend_poke": 正常})
    结果1 = asyncio.run(ws.戳一戳好友("10001"))
    判定("先试 send_poke 再试 friend_poke", 调用 == ["send_poke", "friend_poke"], str(调用))
    判定("最终返回成功", 结果1.get("status") == "ok")
    判定("只把不支持的那个记下来", ws._不支持的动作 == {"send_poke"}, str(ws._不支持的动作))

    print("\n③ 两个都不支持 → 停用且不再重试")
    ws = 造WS()
    调用 = 装接口(ws, {"send_poke": 不支持, "friend_poke": 不支持})
    结果1 = asyncio.run(ws.戳一戳好友("10001"))
    判定("返回 skipped(不是 failed)", 结果1.get("status") == "skipped", str(结果1))
    判定("两个动作都被记住", ws._不支持的动作 == {"send_poke", "friend_poke"})
    调用.clear()
    结果2 = asyncio.run(ws.戳一戳好友("10001"))
    判定("第二次调用一次 API 都不发(不再重试)", 调用 == [], str(调用))
    判定("第二次仍返回 skipped", 结果2.get("status") == "skipped")

    print("\n④ 表情回应:不支持则停用")
    ws = 造WS()
    调用 = 装接口(ws, {"set_msg_emoji_like": {"status": "failed", "retcode": 1404,
                                            "msg": "set_msg_emoji_like API 不存在"}})
    结果1 = asyncio.run(ws.设置表情回应("123", 12))
    判定("返回 skipped", 结果1.get("status") == "skipped", str(结果1))
    调用.clear()
    asyncio.run(ws.设置表情回应("124", 12))
    判定("第二次不再发 API", 调用 == [], str(调用))

    ws = 造WS()
    调用 = 装接口(ws, {"set_msg_emoji_like": 正常})
    结果1 = asyncio.run(ws.设置表情回应("123", 12))
    判定("实现支持时正常放行", 结果1.get("status") == "ok" and not ws._不支持的动作)


# ══════════════════════════════════════════════════════════════════════════════
class 日志捕获(logging.Handler):
    def __init__(self):
        super().__init__()
        self.记录 = []

    def emit(self, record):
        if record.name.startswith("napcat_plugin"):
            self.记录.append((record.levelno, record.getMessage()))


def 端到端():
    """原始症状:不支持时每条消息刷一行 warning。这里数日志条数。"""
    print("\n⑤ 端到端:不再每条消息刷日志(原始症状)")
    from gateway.config import PlatformConfig

    a = adapter模块._创建适配器(PlatformConfig(
        enabled=True, extra={"bot_self_id": "90000", "allowed_qq_ids": ["10001"],
                             "allowed_group_ids": [123456], "emoji_react": True}))
    ws = a.ws
    调用 = 装接口(ws, {"set_msg_emoji_like": {"status": "failed", "retcode": 1404,
                                            "msg": "set_msg_emoji_like API 不存在"},
                      "send_poke": {"status": "failed", "retcode": 1404, "msg": "send_poke API 不存在"},
                      "friend_poke": {"status": "failed", "retcode": 1404, "msg": "friend_poke API 不存在"}})

    捕获 = 日志捕获()
    logging.getLogger().addHandler(捕获)
    try:
        for i in range(5):
            asyncio.run(a._表情回应(str(1000 + i), 12))
        for i in range(5):
            asyncio.run(a._戳一戳("10001"))
    finally:
        logging.getLogger().removeHandler(捕获)

    警告 = [m for lv, m in 捕获.记录 if lv >= logging.WARNING]
    停用提示 = [m for m in 警告 if "不支持" in m]
    失败提示 = [m for m in 警告 if "失败" in m or "异常" in m]
    判定("5 次表情回应只发了 1 次 API(之后走缓存)",
        len([x for x in 调用 if x == "set_msg_emoji_like"]) == 1, str(调用))
    # 三个动作各一条停用提示,且不重复 —— 关键是没有「每条消息一条」
    判定("停用提示每个动作恰好一条、无重复",
        len(停用提示) == 3 and len(set(停用提示)) == 3, f"{len(停用提示)} 条: {停用提示}")
    判定("没有『表情回应失败』『戳一戳失败』这类告警刷屏",
        not 失败提示, f"{len(失败提示)} 条: {失败提示[:3]}")

    print("\n⑥ 实现支持时行为不变")
    a = adapter模块._创建适配器(PlatformConfig(
        enabled=True, extra={"bot_self_id": "90000", "allowed_qq_ids": ["10001"],
                             "allowed_group_ids": [123456], "emoji_react": True}))
    调用 = 装接口(a.ws, {"set_msg_emoji_like": 正常, "send_poke": 正常})
    捕获 = 日志捕获()
    logging.getLogger().addHandler(捕获)
    try:
        for i in range(3):
            asyncio.run(a._表情回应(str(2000 + i), 12))
        asyncio.run(a._戳一戳("10001"))
    finally:
        logging.getLogger().removeHandler(捕获)
    判定("每次都真的调了 API(没有误判成不支持)",
        len([x for x in 调用 if x == "set_msg_emoji_like"]) == 3, str(调用))
    判定("戳一戳用的是标准 send_poke", 调用[-1] == "send_poke", str(调用))


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
