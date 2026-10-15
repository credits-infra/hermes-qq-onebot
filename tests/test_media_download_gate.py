#!/usr/bin/env python3
"""入站媒体下载的「大小闸门」行为验证。

背景:`_下载段媒体` 原本「没有 file_size 就跳过下载」(return None)。不是所有 OneBot
实现都带 file_size,于是那些实现上的图片/语音**永远到不了模型**,日志里只有一句
「跳过下载」。而下载函数本身有「HEAD 预检 + 边下边查」两道闸门,拿配置上限兜底是安全的。

用法:
    python tests/test_media_download_gate.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包, 注册napcat平台  # noqa: E402

加载包("tools", "main", "adapter")
注册napcat平台()
main模块 = sys.modules["napcat_plugin.main"]
adapter模块 = sys.modules["napcat_plugin.adapter"]

结果 = []
_序号 = [0]


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


真下载 = main模块.下载媒体文件


def 造适配器(extra=None):
    from gateway.config import PlatformConfig

    base = {"bot_self_id": "90000", "allowed_qq_ids": ["10001"],
            "allowed_group_ids": [123456]}
    base.update(extra or {})
    return adapter模块._创建适配器(PlatformConfig(enabled=True, extra=base))


def 装假下载():
    """替换 main 模块作用域里的 下载媒体文件(它是 `from .tools import *` 导入的)。"""
    调用 = []

    async def 假下载(地址, 媒体类型="image", 大小限制字节=0):
        调用.append({"地址": 地址, "类型": 媒体类型, "限制": 大小限制字节})
        return "/tmp/假的媒体.jpg"

    main模块.下载媒体文件 = 假下载
    return 调用


def 段(类型="image", **数据):
    基础 = {"url": "http://example.invalid/a.jpg", "file": "a.jpg"}
    基础.update(数据)
    return {"type": 类型, "data": 基础}


def 下载一个(适配器, 消息段):
    return asyncio.run(适配器._下载段媒体(消息段["type"], 消息段["data"], 消息段["data"]["url"]))


def 单元():
    print("① 有 file_size:按预报值决定")
    a = 造适配器({"download_limits": {"image": "1KB"}})
    调用 = 装假下载()
    try:
        路径, _ = 下载一个(a, 段("image", file_size="2048"))
        判定("超限 → 不下载", not 调用, f"却调用了 {调用}")
        判定("超限 → 返回 None", 路径 is None)

        调用.clear()
        路径, _ = 下载一个(a, 段("image", file_size="512"))
        判定("未超限 → 下载", len(调用) == 1 and 路径 == "/tmp/假的媒体.jpg")
        判定("传给下载函数的限制 = 该类型的配置上限(1KB)",
            调用 and 调用[0]["限制"] == 1024, str(调用[:1]))
    finally:
        main模块.下载媒体文件 = 真下载

    print("\n② 没有 file_size:不再直接放弃(修的就是这条)")
    a = 造适配器()
    调用 = 装假下载()
    try:
        路径, _ = 下载一个(a, 段("image"))
        判定("★ 未给 file_size → 仍然尝试下载", len(调用) == 1, f"调用={调用}")
        判定("下载成功时返回本地路径", 路径 == "/tmp/假的媒体.jpg")

        调用.clear()
        路径, _ = 下载一个(a, 段("record", file_size=""))
        判定("空字符串 file_size 也照样尝试", len(调用) == 1, f"调用={调用}")

        调用.clear()
        路径, _ = 下载一个(a, 段("image", file_size="不是数字"))
        判定("非数字 file_size 当作未知 → 仍然尝试", len(调用) == 1, f"调用={调用}")
        判定("且仍带配置上限(而不是 0/无限)",
            调用 and 调用[0]["限制"] > 0, str(调用[:1]))
    finally:
        main模块.下载媒体文件 = 真下载

    print("\n③ 各类型上限各自独立")
    a = 造适配器({"download_limits": {"image": "1KB", "video": "2MB"}})
    调用 = 装假下载()
    try:
        下载一个(a, 段("video"))
        判定("video 用 video 的上限(2MB)",
            调用 and 调用[0]["类型"] == "video" and 调用[0]["限制"] == 2 * 1024 * 1024,
            str(调用[:1]))
    finally:
        main模块.下载媒体文件 = 真下载


def 端到端():
    print("\n④ 端到端:无 file_size 的图片能到模型")
    a = 造适配器()
    调用 = 装假下载()
    收到 = []

    async def 假分发(ev):
        收到.append(ev)

    a.handle_message = 假分发
    _序号[0] += 1
    事件 = {
        "message_type": "group",
        "user_id": "10001",
        "group_id": "123456",
        "message_id": f"m{_序号[0]}",
        "sender": {"nickname": "测试者", "card": ""},
        "message": [{"type": "at", "data": {"qq": "90000"}},
                    {"type": "text", "data": {"text": "看看这张图"}},
                    {"type": "image", "data": {"url": "http://example.invalid/x.jpg", "file": "x.jpg"}}],
        "raw_message": "[CQ:at,qq=90000] 看看这张图",
    }
    try:
        asyncio.run(a._处理消息事件(事件))
    finally:
        main模块.下载媒体文件 = 真下载

    判定("消息进了网关", len(收到) == 1, "没进网关" if not 收到 else "")
    if 收到:
        判定("★ 无 file_size 的图片被下载并带上(media_urls 非空)",
            bool(收到[0].media_urls), f"media_urls={收到[0].media_urls}")
        判定("文本里带图片标签", "图片" in 收到[0].text, repr(收到[0].text[:60]))


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
