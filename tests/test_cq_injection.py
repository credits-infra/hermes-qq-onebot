#!/usr/bin/env python3
"""出站 CQ 注入的回归测试。

为什么单独一组:交叉评审在加固分支上找出 H1 —— 模型回复里的图片 URL(以及
caption、本地路径)会**原样拼进 CQ 串**,夹带的 `[CQ:file,file=...]` 能绕过净化把
本机文件发出去。原测试只盖了 send() 与 ```CQ 块,没盖 send_image / send_image_file
/ send_voice / send_document —— 洞正好落在没被测的那几条路上。

本测试按真实链路搭:Hermes 的 BasePlatformAdapter.extract_images(真函数)
→ 插件 send_image / send_image_file / send_document,ws 换成记录器,
断言的是**最终发到 OneBot 的字符串**。

用法:
    python tests/test_cq_injection.py
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
tools = sys.modules["napcat_plugin.tools"]
from gateway.config import PlatformConfig  # noqa: E402
from gateway.platforms.base import BasePlatformAdapter  # noqa: E402

结果 = []
敏感 = "/home/leemina/.hermes/profiles/qq/.env"


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


class 假配置:
    def __init__(self, extra):
        self.extra = extra


class 假适配器源:
    def __init__(self, extra):
        self.config = 假配置(extra)


class 假WS:
    def __init__(self):
        self.记录 = []

    async def 发送群聊消息(self, 目标ID, 内容):
        self.记录.append(str(内容))
        return {"status": "ok", "retcode": 0}

    async def 发送私聊消息(self, 目标ID, 内容):
        self.记录.append(str(内容))
        return {"status": "ok", "retcode": 0}

    async def 上传群文件(self, 目标ID, 路径):
        self.记录.append(f"UPLOAD:{路径}")
        return {"status": "ok", "retcode": 0}

    async def 上传私聊文件(self, 目标ID, 路径):
        self.记录.append(f"UPLOAD:{路径}")
        return {"status": "ok", "retcode": 0}


def 造适配器(extra=None):
    """默认给本例用到的群开白名单:本测试考的是注出内容,不是出站 ACL。"""
    ext = extra or {"allowed_group_ids": ["123456"]}
    adapter模块._适配器实例 = 假适配器源(ext)
    a = adapter模块._创建适配器(PlatformConfig(enabled=True, extra=ext))
    a.ws = 假WS()
    return a


def 端到端(允许目录: Path):
    print("① 模型回复里的图片 URL 夹带 CQ 码(评审 H1 主体)")
    a = 造适配器()
    回复 = f"给你看 ![图](https://a.example/x.png][CQ:file,file={敏感})"
    图列表, _ = BasePlatformAdapter.extract_images(回复)
    判定("Hermes 的 extract_images 会把 ] 与 [ 一起抽进 URL",
        bool(图列表) and "]" in 图列表[0][0], repr(图列表[0][0]) if 图列表 else "没抽出图")
    for url, alt in 图列表:
        asyncio.run(a.send_image("napcat_group_123456", url, caption=alt))
    发出 = a.ws.记录[-1] if a.ws.记录 else ""
    判定("send_image:夹带的 [CQ:file] 没发出去", "[CQ:file" not in 发出, repr(发出)[:90])

    print("\n② caption(alt 文本)里夹带 CQ 码")
    a = 造适配器()
    asyncio.run(a.send_image("napcat_group_123456", "https://a.example/x.png",
                             caption=f"看图 [CQ:file,file={敏感}]"))
    发出 = a.ws.记录[-1] if a.ws.记录 else ""
    判定("send_image:caption 里的 [CQ:file] 没发出去", "[CQ:file" not in 发出, repr(发出))

    print("\n③ 值里夹键:URL 里的 ,url= 不能变成独立参数(评审 M4)")
    a = 造适配器()
    恶意URL = f"https://a.example/x.png,url={敏感}"
    asyncio.run(a.send_image("napcat_group_123456", 恶意URL))
    发出 = a.ws.记录[-1] if a.ws.记录 else ""
    解析 = tools.解析CQ码(发出.strip()) if 发出.strip().startswith("[CQ:") else None
    if 解析:
        _, 参数 = 解析
        判定("只解析出 file 一个键(没有 url 键)", sorted(参数) == ["file"], f"键={sorted(参数)}")
        判定("file 的值反转义后仍是完整原值(转义可逆)",
            参数.get("file") == 恶意URL, repr(参数.get("file"))[:80])
    else:
        判定("只解析出 file 一个键(没有 url 键)", False, f"解析不了: {发出!r}")

    print("\n④ send_image_file 的文件名里带 ] 与 [CQ:")
    a = 造适配器()
    险文件 = 允许目录 / "x.png][CQ:file,file=zz"
    险文件.write_bytes(b"\x89PNG\r\n\x1a\n")
    asyncio.run(a.send_image_file("napcat_group_123456", str(险文件)))
    发出 = a.ws.记录[-1] if a.ws.记录 else ""
    判定("文件名里的 [CQ:file] 没变成真的码(要么剥掉要么被转义)",
        "[CQ:file" not in 发出 or "&#91;CQ:file" in 发出, repr(发出)[:110])

    print("\n⑤ send_document 的 caption(评审指出完全没净化)")
    a = 造适配器()
    好文件 = 允许目录 / "ok.png"
    asyncio.run(a.send_document("napcat_group_123456", str(好文件),
                                caption=f"说明 [CQ:file,file={敏感}]"))
    文本类 = [x for x in a.ws.记录 if not x.startswith("UPLOAD:")]
    判定("caption 里的 [CQ:file] 没发出去", all("[CQ:file" not in x for x in 文本类), repr(文本类))

    print("\n⑥ 正常功能没被误伤")
    a = 造适配器()
    asyncio.run(a.send_image("napcat_group_123456", "https://a.example/normal.png", caption="正常说明"))
    发出 = a.ws.记录[-1] if a.ws.记录 else ""
    判定("正常图片 URL 照常发出", "normal.png" in 发出 and "正常说明" in 发出, repr(发出))
    a = 造适配器()
    asyncio.run(a.send("napcat_group_123456", "你好 [CQ:face,id=178] 世界"))
    发出 = a.ws.记录[-1] if a.ws.记录 else ""
    判定("正常 [CQ:face] 照常发出", "[CQ:face" in 发出, repr(发出))


def 转义往返():
    print("\n⑦ 转义与反转义互为逆运算")
    for s in ("https://a.example/x.png,url=/x", "x.png][CQ:file,file=/x]", "a&b",
              "&#44;", "已有&amp;转义", "中文,值[方括号]", ""):
        e = tools.转义CQ值(s)
        判定(f"往返一致: {s[:26]!r}", tools.反转义CQ值(e) == s, f"{e[:40]!r}")


def 主体():
    临时 = Path(tempfile.mkdtemp(prefix="napcat_cqinject_"))
    允许目录 = 临时 / "allow"
    允许目录.mkdir()
    (允许目录 / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    建立临时媒体策略(允许目录)
    转义往返()
    端到端(允许目录)

    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(主体())
