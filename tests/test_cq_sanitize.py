#!/usr/bin/env python3
"""CQ 码净化的验证。

分两层:
  ① 单元 —— 直接打 净化CQ码() 的策略判定;
  ② 端到端 —— 构造真适配器、把 ws 换成记录器,打真 send(),断言最终**发出去的
     字符串**里没有该剥的码、留着该留的码。①只证明函数对,②证明接线对。

用法:
    python tests/test_cq_sanitize.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import 加载包, 建立临时媒体策略, 注册napcat平台  # noqa: E402

加载包("tools", "security", "main", "adapter")
注册napcat平台()
security = sys.modules["napcat_plugin.security"]
adapter模块 = sys.modules["napcat_plugin.adapter"]

结果 = []


def 判定(名, 通过, 详情=""):
    结果.append((名, 通过))
    print(f"  {'✅ PASS' if 通过 else '❌ FAIL'}  {名}" + (f"   {详情}" if 详情 else ""))


class 假配置:
    def __init__(self, extra):
        self.extra = extra


class 假适配器配置源:
    def __init__(self, extra):
        self.config = 假配置(extra)


def 设插件配置(extra):
    adapter模块._适配器实例 = 假适配器配置源(extra)


class 假WS:
    """替掉真 WS:只记录被要求发出去的内容。"""

    def __init__(self):
        self.记录 = []

    async def 发送群聊消息(self, 目标ID, 消息内容):
        self.记录.append((目标ID, 消息内容))
        return {"status": "ok", "retcode": 0}

    async def 发送私聊消息(self, 目标ID, 消息内容):
        self.记录.append((目标ID, 消息内容))
        return {"status": "ok", "retcode": 0}

    async def 发送群合并转发(self, 目标ID, 节点列表):
        self.记录.append((目标ID, 节点列表))
        return {"status": "ok", "retcode": 0}

    async def 发送私聊合并转发(self, 目标ID, 节点列表):
        self.记录.append((目标ID, 节点列表))
        return {"status": "ok", "retcode": 0}


def 造适配器(extra=None):
    """默认给本例用到的群 123456 开白名单。

    本测试考的是 CQ 净化,不是出站 ACL;空名单时核心发送会 fail-closed(见
    test_outbound_acl.py),那样这里根本发不出东西、断言的就不是净化了。
    """
    from gateway.config import PlatformConfig

    cfg = PlatformConfig(enabled=True, extra=extra or {"allowed_group_ids": ["123456"]})
    a = adapter模块._创建适配器(cfg)
    a.ws = 假WS()
    return a


def 发一条(适配器, 内容, 会话="napcat_group_123456"):
    asyncio.run(适配器.send(会话, 内容))
    return 适配器.ws.记录[-1][1] if 适配器.ws.记录 else None


def 单元():
    print("① CQ 码策略(单元)")
    设插件配置({})

    文本, 丢 = security.净化CQ码("[CQ:face,id=178] 好看")
    判定("[CQ:face] 保留", 文本 == "[CQ:face,id=178] 好看" and not 丢)

    文本, 丢 = security.净化CQ码("[CQ:at,qq=12345] 你好")
    判定("[CQ:at,qq=12345] 保留", "[CQ:at" in 文本 and not 丢)

    文本, 丢 = security.净化CQ码("[CQ:at,qq=all] 全体注意")
    判定("[CQ:at,qq=all] 默认剥掉", "CQ:at" not in 文本 and 丢, 丢[:1])

    文本, 丢 = security.净化CQ码("[CQ:file,file=file:///home/leemina/.hermes/profiles/qq/.env]")
    判定("[CQ:file] 剥掉(外泄路)", 文本.strip() == "" and 丢, 丢[:1])

    文本, 丢 = security.净化CQ码("[CQ:image,file=/etc/passwd]")
    判定("[CQ:image] 指向白名单外路径 → 剥掉", 文本.strip() == "", 丢[:1])

    文本, 丢 = security.净化CQ码("[CQ:image,file=http://example.com/a.png]")
    判定("[CQ:image] 远程 URL → 保留(不读本机文件)", "[CQ:image" in 文本 and not 丢)

    文本, 丢 = security.净化CQ码("[CQ:unknown_type,x=1]")
    判定("未知 CQ 类型 → 剥掉", 文本.strip() == "", 丢[:1])

    文本, 丢 = security.净化CQ码("[CQ:image]")
    判定("[CQ:image] 缺 file 参数 → 剥掉", 文本.strip() == "", 丢[:1])

    文本, 丢 = security.净化CQ码("前[CQ:file,file=/etc/passwd]后")
    判定("剥掉码但保留两侧文本", 文本 == "前后" and 丢, repr(文本))

    文本, 丢 = security.净化CQ码("这不是码 [CQ 只是文字] 结束")
    判定("非 CQ 文本原样保留", 文本 == "这不是码 [CQ 只是文字] 结束" and not 丢)

    设插件配置({"allow_at_all": True})
    文本, 丢 = security.净化CQ码("[CQ:at,qq=all]")
    判定("allow_at_all=true 时放行 @全体", "CQ:at" in 文本 and not 丢)
    设插件配置({})

    设插件配置({"allowed_cq_types": "all"})
    文本, 丢 = security.净化CQ码("[CQ:unknown_type,x=1]")
    判定("allowed_cq_types=all 放行未知类型", "[CQ:unknown_type" in 文本)
    文本, 丢 = security.净化CQ码("[CQ:file,file=file:///etc/passwd]")
    判定("但 all 仍拦 [CQ:file](永不放过)", 文本.strip() == "", 丢[:1])
    文本, 丢 = security.净化CQ码("[CQ:file2,file=/etc/passwd]")
    判定("all 下未知类型带路径参数也要查白名单", 文本.strip() == "" and bool(丢), 丢[:1])
    文本, 丢 = security.净化CQ码("[CQ:weird_type,url=/etc/passwd]")
    判定("all 下任何类型带路径参数都查白名单", 文本.strip() == "" and bool(丢), 丢[:1])
    文本, 丢 = security.净化CQ码("[CQ:face,id=178]")
    判定("all 下正常 face 照常放行", "[CQ:face" in 文本 and not 丢)
    设插件配置({})

    # 解析失败的形状 → fail-closed(交叉评审 M3:原来原样放行)
    for 码 in ("[CQ:file2,file=/etc/passwd]", "[CQ:file2.5,file=/etc/passwd]",
               "[CQ:file-x,file=/etc/passwd]", "[CQ:image2,path=/etc/passwd]"):
        文本, 丢 = security.净化CQ码(f"前{码}后")
        判定(f"解析失败的 {码[:22]} 剥掉", 文本 == "前后" and bool(丢), f"→ {文本!r}")
    文本, 丢 = security.净化CQ码("[CQ:FILE,file=file:///etc/passwd]")
    判定("[CQ:FILE] 大写也剥掉(小写化后命中永不放过)", 文本.strip() == "" and bool(丢), 丢[:1])

    # 重复键 → fail-closed(第二轮评审:接收端取哪个键没有统一规定,我们只能校验看到的那一个)
    文本, 丢 = security.净化CQ码(
        "[CQ:image,file=https://a.example/x.png,url=https://a.example/b.png,url=/etc/passwd]")
    判定("重复的 url 键 → 整条剥掉", 文本.strip() == "" and bool(丢), 丢[:1])
    文本, 丢 = security.净化CQ码("[CQ:at,qq=all,qq=1]")
    判定("重复的 qq 键 → 整条剥掉(不能绕过 @全体 检查)", 文本.strip() == "" and bool(丢), 丢[:1])
    文本, 丢 = security.净化CQ码("[CQ:image,file=/etc/passwd,file=https://a.example/x.png]")
    判定("重复的 file 键 → 整条剥掉", 文本.strip() == "" and bool(丢), 丢[:1])

    # 非 file 键里的本地路径也要拦(交叉评审 M4:LLOneBot 取 url || file)
    for 码, 说明 in (("[CQ:image,file=https://a.example/x.png,url=/etc/passwd]", ",url="),
                     ("[CQ:image,file=https://a.example/x.png,src=/etc/passwd]", ",src="),
                     ("[CQ:image,path=/etc/passwd]", "只有 path="),
                     ("[CQ:record,file=https://a.example/x.mp3,dest=/etc/passwd]", ",dest=")):
        文本, 丢 = security.净化CQ码(码)
        判定(f"承载键 {说明} 指向本机文件 → 剥掉", 文本.strip() == "" and bool(丢), 丢[:1])
    文本, 丢 = security.净化CQ码(
        "[CQ:image,file=https://a.example/x.png,url=https://a.example/b.png]")
    判定("file 与 url 都是远程 URL → 保留", "[CQ:image" in 文本 and not 丢, repr(文本))


def 端到端(好文件: Path):
    print("\n② 端到端:打真 send(),看最终发出去的字符串")
    适配器 = 造适配器()

    发出 = 发一条(适配器, "看这个 [CQ:file,file=file:///home/leemina/.hermes/profiles/qq/.env] 完了")
    判定("send():[CQ:file] 没发出去", 发出 is not None and "[CQ:file" not in 发出, repr(发出))
    判定("send():两侧文本保留", 发出 is not None and "看这个" in 发出 and "完了" in 发出)

    发出 = 发一条(适配器, "看这个 [CQ:image,file=/etc/passwd] 完了")
    判定("send():白名单外的图片路径没发出去", 发出 is not None and "/etc/passwd" not in 发出, repr(发出))

    发出 = 发一条(适配器, f"看这个 [CQ:image,file={好文件}] 完了")
    判定("send():白名单内的图片路径正常发出",
        发出 is not None and "[CQ:image" in 发出 and "ok.png" in 发出, repr(发出))

    发出 = 发一条(适配器, "[CQ:at,qq=all] 都来看看")
    判定("send():@全体 没发出去", 发出 is not None and "qq=all" not in 发出, repr(发出))

    # ```CQ 代码块路径:块里全是被剥掉的码 → 整条不发,返回失败
    记录数之前 = len(适配器.ws.记录)
    结果 = asyncio.run(适配器.send("napcat_group_123456", "```CQ\n[CQ:file,file=file:///etc/passwd]\n```"))
    新记录 = 适配器.ws.记录[记录数之前:]
    判定("send():```CQ 块里全是非法码 → 一条都没发出去",
        not 新记录 and not 结果.success, f"新增={新记录} 结果={结果.error}")

    发出 = 发一条(适配器, "```CQ\n[CQ:face,id=178]\n```")
    判定("send():```CQ 块里的合法码照常发出",
        发出 is not None and "[CQ:face" in str(发出), repr(发出))

    # 长消息路径(超过合并转发阈值)也要过闸门
    长文本 = "开头\n" * 400 + "[CQ:file,file=file:///etc/passwd]\n" + "结尾\n" * 400
    记录数之前 = len(适配器.ws.记录)
    asyncio.run(适配器.send("napcat_group_123456", 长文本))
    for _, 内容 in 适配器.ws.记录[记录数之前:]:
        if isinstance(内容, str) and "[CQ:file" in 内容:
            判定("send():长消息路径也过闸门", False, "长消息里漏出了 [CQ:file]")
            break
    else:
        判定("send():长消息路径也过闸门", True, f"检查了 {len(适配器.ws.记录) - 记录数之前} 条出站内容")


def 主体():
    临时 = Path(tempfile.mkdtemp(prefix="napcat_cq_"))
    允许目录 = 临时 / "allow"
    允许目录.mkdir()
    好文件 = 允许目录 / "ok.png"
    好文件.write_bytes(b"\x89PNG\r\n\x1a\n")
    建立临时媒体策略(允许目录)

    单元()
    端到端(好文件)

    print("\n================ 汇总 ================")
    通过 = sum(1 for _, p in 结果 if p)
    print(f"{通过}/{len(结果)} 通过")
    for 名, p in 结果:
        if not p:
            print("  ❌", 名)
    return 0 if 通过 == len(结果) else 1


if __name__ == "__main__":
    sys.exit(主体())
