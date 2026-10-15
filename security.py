"""出站安全策略:OneBot 动作白名单 + 本地文件路径校验。

为什么需要这一层:Hermes 的 media_policy(`validate_media_delivery_path`)只管
`MEDIA:` 那条出站通道,管不到模型自己拼出来的 OneBot API 调用。而
`napcat_call_action` 能调到 `upload_group_file` 这类「把服务器上任意文件发进群」
的动作,参数又完全由模型(可能已被群里的提示注入操纵)决定。所以工具层需要一道
自己的闸门。

策略分三层:
  1. 默认只放行只读动作;
  2. 改动状态 / 破坏性 / 能把文件外传的动作,要运维显式点名(或写 `all`)才放行;
  3. 会交出账号凭据的动作永不放过,写 `all` 也不行。

此外,任何带本地路径参数的动作,路径都必须过 Hermes 的媒体白名单 —— 复用它而不是
另造一套,保证「哪些文件能出去」只有一个事实来源,运维改一处两边都生效。
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Iterable, Optional
from urllib.parse import unquote, urlparse

# tools 不 import 本模块,所以这里不存在循环导入
from .tools import 解析CQ码

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 动作策略
# ═══════════════════════════════════════════════════════════════════════════════

# 默认放行:只读、不改状态、不读文件。
默认允许的动作 = frozenset({
    # 账号 / 状态
    "get_login_info", "get_version_info", "get_status", "get_self_info",
    "get_robot_uin_range",
    # 群 / 好友 / 成员
    "get_group_list", "get_group_info", "get_group_info_ex",
    "get_group_member_info", "get_group_member_list", "get_group_honor_info",
    "get_group_at_all_remain", "get_group_system_msg", "get_group_file_system_info",
    "get_friend_list", "get_stranger_info", "get_recent_contact",
    # 消息(只读)
    "get_msg", "get_forward_msg",
    "get_group_msg_history", "get_friend_msg_history",
    # 能力查询
    "can_send_image", "can_send_record",
})

# 需要运维点名才放行:改状态、破坏性、或能把文件送出去。
# 尤其 upload_* / download_file:前者是文件外泄通道,后者是「按给定 URL 写到给定
# 路径」的任意写。想发文件请走 MEDIA: 通道,那条受 Hermes media_policy 管。
需显式授权的动作 = frozenset({
    # 文件外传与任意写
    "upload_group_file", "upload_private_file", "upload_file",
    "upload_group_file_by_url", "download_file",
    # 撤回 / 删除
    "delete_msg", "delete_friend",
    # 独立发送口(绕过 napcat_send_message 的链路)
    "send_msg", "send_group_msg", "send_private_msg",
    "send_group_forward_msg", "send_private_forward_msg", "send_like",
    # 群 / 好友状态变更
    "set_group_name", "set_group_card", "set_group_kick", "set_group_ban",
    "set_group_whole_ban", "set_group_admin", "set_group_leave",
    "set_group_portrait", "set_group_remark", "set_friend_remark",
    "set_friend_add_request", "set_group_add_request", "set_restart",
    # 按 id / 路径取本机文件
    "get_file", "get_image", "get_record", "get_group_file_url",
})

# 永不放过:直接交出账号凭据。拿到这些等于拿到账号本身,没有「显式授权」这一说。
永不放过 = frozenset({
    "get_cookies", "get_csrf_token", "get_credentials", "get_clientkey",
    "get_qq_sig", "get_session_token",
})

# 参数里可能承载本地路径的键名(小写比较)。
路径参数键 = frozenset({
    "file", "path", "file_path", "filepath", "image", "record", "video",
    "cover", "dest", "target_path", "local_path",
})


def 解析动作策略(原始: Any) -> tuple[frozenset, bool]:
    """把配置值解析成 (允许的动作集, 是否全放行)。

    None / 空 → 默认白名单; "all" 或 "*" → 全放行(凭据类仍拦); 其余按逗号分隔,
    并**追加在默认白名单之上** —— 点名一个动作不该把只读查询一起锁死,那是配置
    陷阱而不是加固(实测:`allowed_actions: [upload_group_file]` 若按替换处理,
    `get_group_list` 这类查询会全部失效)。
    """
    if 原始 is None or (isinstance(原始, str) and not 原始.strip()):
        return 默认允许的动作, False
    from .tools import 解析列表配置

    # 走公共解析:环境变量可能写成 JSON 数组('["a","b"]'),只按逗号切会切错。
    项 = 解析列表配置(原始) or []
    if any(x.lower() in ("all", "*") for x in 项):
        return frozenset(), True
    return frozenset(默认允许的动作 | frozenset(项)), False


def 当前额外配置() -> dict:
    """读取本插件的 config.extra。

    延迟 import:llm_tools 要 import 本模块,模块级互相 import 会成环。
    """
    try:
        from .llm_tools import _获取适配器
    except Exception:
        return {}
    适配器 = _获取适配器()
    if 适配器 is None:
        return {}
    额外 = getattr(getattr(适配器, "config", None), "extra", None)
    return 额外 if isinstance(额外, dict) else {}


def 当前动作策略() -> tuple[frozenset, bool]:
    """按「配置 > 环境变量 > 默认」取生效的动作策略。"""
    原始 = 当前额外配置().get("allowed_actions")
    if 原始 is None or (isinstance(原始, str) and not 原始.strip()):
        原始 = os.getenv("NAPCAT_ALLOWED_ACTIONS")
    return 解析动作策略(原始)


def 检查动作(动作: str) -> Optional[str]:
    """检查动作是否允许。None=放行,否则返回给模型看的拒绝说明。"""
    名 = str(动作 or "").strip()
    if not 名:
        return "action 不能为空"
    if 名 in 永不放过:
        return f"动作「{名}」会交出账号凭据,本插件永不放行。"

    允许, 全放 = 当前动作策略()
    if 名 in 允许 or 全放:
        return None
    if 名 in 需显式授权的动作:
        return (
            f"动作「{名}」会改动账号/服务器状态,或能把服务器上的文件发出去,"
            f"不在默认白名单内 —— 这不是权限故障,是运维的安全设置。"
            f"要发文件请用 MEDIA: 通道(它受运维的媒体白名单管理);"
            f"确实需要该动作,请运维在插件配置里加 allowed_actions。"
        )
    return (
        f"动作「{名}」不在允许列表内 —— 这不是权限故障,是运维的安全设置。"
        f"默认只放行只读查询动作;要放开需运维在插件配置 allowed_actions 里点名。"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 路径校验
# ═══════════════════════════════════════════════════════════════════════════════

_非本机前缀 = ("http://", "https://", "base64://", "data:", "file://", "ftp://")


def _本机路径(值: str) -> Optional[str]:
    """把参数值归约成本机绝对路径;不是本机路径(URL/base64)则返回 None。"""
    文本 = str(值 or "").strip()
    if not 文本:
        return None
    if 文本.startswith("file://"):
        try:
            解析 = urlparse(文本)
            路径 = unquote(解析.path)
            if not 路径 and 解析.netloc:
                路径 = unquote(解析.netloc)
            return 路径 or None
        except Exception:
            return 文本
    if 文本.startswith(("http://", "https://", "base64://", "data:", "ftp://")):
        return None
    return 文本


def 校验本地路径(路径: str) -> Optional[str]:
    """本机路径是否过了 Hermes 的媒体白名单。None=放行,否则返回拒绝说明。

    刻意复用 `validate_media_delivery_path`:它是 Hermes 判断「这个文件能不能出站」
    的唯一权威。白名单没配就一律拒绝(失败即拒),不在这里自作主张放行。
    """
    候选 = _本机路径(路径)
    if 候选 is None:
        return None  # URL / base64,不存在读本机文件的问题

    try:
        from gateway.platforms.base import validate_media_delivery_path
    except Exception as e:  # 拿不到策略就不放行,宁可少一个功能
        logger.warning(f"无法加载媒体白名单校验,按安全默认拒绝: {e}")
        return f"路径「{路径}」:无法加载媒体白名单校验({e}),按安全默认拒绝。"

    安全路径 = validate_media_delivery_path(候选)
    if not 安全路径:
        return (
            f"路径「{路径}」不在媒体白名单内(media_policy),拒绝发出。"
            f"这是运维的策略设置,不是权限故障。"
        )
    return None


def 遍历参数里的路径(参数: Any, 前缀: str = "") -> Iterable[tuple[str, str]]:
    """递归找出参数里所有像路径的字符串。"""
    if not isinstance(参数, dict):
        return
    for 键, 值 in 参数.items():
        全名 = f"{前缀}{键}"
        if isinstance(值, str):
            if str(键).lower() in 路径参数键:
                yield 全名, 值
        elif isinstance(值, dict):
            yield from 遍历参数里的路径(值, f"{全名}.")
        elif isinstance(值, (list, tuple)):
            for 序号, 子项 in enumerate(值):
                if isinstance(子项, str) and str(键).lower() in 路径参数键:
                    yield f"{全名}[{序号}]", 子项
                elif isinstance(子项, dict):
                    yield from 遍历参数里的路径(子项, f"{全名}[{序号}].")


def 检查调用(动作: str, 参数: Any) -> Optional[str]:
    """动作 + 参数的整体检查。None=放行,否则返回拒绝说明。"""
    错误 = 检查动作(动作)
    if 错误:
        return 错误
    for 键, 值 in 遍历参数里的路径(参数 or {}):
        错误 = 校验本地路径(值)
        if 错误:
            return f"参数 {键}:{错误}"
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 出站目标校验
# ═══════════════════════════════════════════════════════════════════════════════

def _名单(键: str, 环境变量: str) -> frozenset[str]:
    from .tools import 解析号码名单

    原始 = 当前额外配置().get(键)
    if 原始 is None or 原始 == "":
        原始 = os.getenv(环境变量, "")
    return 解析号码名单(原始)


def 检查发信目标(目标类型: str, 目标ID: str) -> Optional[str]:
    """工具指定目标的发送也要过白名单。None=放行,否则返回拒绝说明。

    入站白名单只决定「谁能让机器人干活」;如果没有这道出站校验,被允许的人(或
    提示注入)可以指挥机器人把消息发到白名单之外任意群/任意 QQ 用户去。
    """
    from .tools import 名单是全放行

    类型 = str(目标类型 or "").strip().lower()
    ID = str(目标ID or "").strip()
    if not ID:
        return "目标 ID 不能为空"

    if 类型 == "group":
        允许集 = _名单("allowed_group_ids", "NAPCAT_ALLOWED_GROUPS")
        if 名单是全放行(允许集) or ID in 允许集:
            return None
        return (
            f"群「{ID}」不在群白名单(allowed_group_ids)内,拒绝发送。"
            f"这不是权限故障,是运维的设置。"
        )
    if 类型 == "private":
        允许集 = _名单("allowed_qq_ids", "NAPCAT_ALLOWED_USERS")
        if 名单是全放行(允许集) or ID in 允许集:
            return None
        return (
            f"QQ「{ID}」不在用户白名单(allowed_qq_ids)内,拒绝发送。"
            f"这不是权限故障,是运维的设置。"
        )
    return f"未知的 target_type「{目标类型}」"


# ═══════════════════════════════════════════════════════════════════════════════
# CQ 码净化
# ═══════════════════════════════════════════════════════════════════════════════

# 默认允许的 CQ 类型。file 刻意不在其中:[CQ:file,...] 是「服务器按这个路径取文件
# 发出去」,和 upload_group_file 是同一条外泄路。要发文件请走 MEDIA: 通道 ——
# 那条由 Hermes 先过媒体白名单,再由 adapter 的 send_document 送。
默认允许的CQ类型 = frozenset({"face", "at", "image", "record", "video", "reply"})
永不放过的CQ类型 = frozenset({"file", "onlinefile", "flash"})
需校验路径的CQ类型 = frozenset({"image", "record", "video"})

# 只用来「找出」CQ 码;解析(含参数反转义)交给 tools.解析CQ码 ——
# 收发两个方向共用同一套解析,免得两处逻辑各自漂移。
CQ码正则 = re.compile(r"\[CQ:[^\]]+\]")


def 解析CQ类型策略(原始: Any) -> tuple[frozenset, bool]:
    """解析 allowed_cq_types。语义与动作白名单一致:点名是【追加】在默认之上。"""
    if 原始 is None or (isinstance(原始, str) and not 原始.strip()):
        return 默认允许的CQ类型, False
    from .tools import 解析列表配置

    项 = [x.lower() for x in (解析列表配置(原始) or [])]
    if any(x in ("all", "*") for x in 项):
        return frozenset(), True
    return frozenset(默认允许的CQ类型 | frozenset(项)), False


def 当前CQ类型策略() -> tuple[frozenset, bool]:
    原始 = 当前额外配置().get("allowed_cq_types")
    if 原始 is None or (isinstance(原始, str) and not 原始.strip()):
        原始 = os.getenv("NAPCAT_ALLOWED_CQ_TYPES")
    return 解析CQ类型策略(原始)


def 允许艾特全体() -> bool:
    """`[CQ:at,qq=all]`(群里 @全体成员)默认不放行。"""
    原始 = 当前额外配置().get("allow_at_all")
    if 原始 is None:
        原始 = os.getenv("NAPCAT_ALLOW_AT_ALL", "")
    return str(原始).strip().lower() in ("1", "true", "yes", "on")


def 净化CQ码(文本: str) -> tuple[str, list[str]]:
    """剥掉策略不允许的 CQ 码,返回 (净化后文本, 丢弃说明列表)。

    只处理**模型自己拼出来**的文本。走 MEDIA: 通道的附件由 Hermes 先校验、再由
    adapter 的 send_image_file / send_document 发出,不经过这里 —— 所以这里严格
    按策略剥掉,不会误伤合法附件。

    选择「剥掉」而不是「转义成纯文本」:目的是让它发不出去,同时日志里留下痕迹
    (转义会让攻击者看到自己拼的码原样显示,也给不出安全日志)。
    """
    if not 文本 or "[CQ:" not in 文本:
        return 文本, []

    允许集, 全放 = 当前CQ类型策略()
    允许全体 = 允许艾特全体()
    丢弃: list[str] = []

    def _替换(匹配: "re.Match[str]") -> str:
        解析 = 解析CQ码(匹配.group())
        if 解析 is None:
            return 匹配.group()
        类型, 原始参数 = 解析
        # 参数名大小写不敏感(原实现统一转小写);值已由 解析CQ码 反转义
        参数 = {键.lower(): 值 for 键, 值 in 原始参数.items()}
        if 类型 in 永不放过的CQ类型:
            丢弃.append(f"[CQ:{类型}] 会按路径读取服务器文件并发出,不放行")
            return ""
        if not 全放 and 类型 not in 允许集:
            丢弃.append(f"[CQ:{类型}] 不在允许的 CQ 类型内")
            return ""

        if 类型 == "at" and 参数.get("qq", "").strip().lower() == "all" and not 允许全体:
            丢弃.append("[CQ:at,qq=all] 是 @全体成员,默认不放行(要放开设 allow_at_all: true)")
            return ""

        if 类型 in 需校验路径的CQ类型:
            文件 = 参数.get("file", "")
            if not 文件:
                丢弃.append(f"[CQ:{类型}] 缺少 file 参数")
                return ""
            错误 = 校验本地路径(文件)
            if 错误:
                丢弃.append(f"[CQ:{类型}] {错误}")
                return ""

        return 匹配.group()

    return CQ码正则.sub(_替换, 文本), 丢弃
