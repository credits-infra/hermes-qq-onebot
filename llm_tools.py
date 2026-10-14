"""
NapCat LLM 工具 — 供 Hermes Agent 调用的 QQ 消息发送与 OneBot API 工具。

两个工具：
  - napcat_send_message: 发送 QQ 消息（群聊/私聊），支持纯文本和 CQ 码
  - napcat_call_action:  调用 OneBot v11 API 动作（默认只放行只读查询，见 security.py）

直接复用适配器实例的 WS 连接 / HTTP 调用器 / 发送逻辑（CQ码、合并转发、拆分等）。
适配器实例由 adapter.py 的 _创建适配器 工厂函数在创建时存入模块级变量。
"""

import json
import logging
from typing import Any, Optional

from tools.registry import tool_error, tool_result

from .security import 检查调用, 检查发信目标

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 适配器实例获取
# ═══════════════════════════════════════════════════════════════════════════════

def _获取适配器() -> Optional[Any]:
    """获取运行中的 NapCat适配器实例。

    实例由 adapter._创建适配器() 工厂函数在创建时存入模块级变量。
    网关未运行时返回 None。
    """
    try:
        from .adapter import _适配器实例
        return _适配器实例
    except Exception:
        return None


def _检查可用() -> bool:
    """检查 NapCat 适配器是否已实例化。"""
    return _获取适配器() is not None


# ═══════════════════════════════════════════════════════════════════════════════
# OneBot API 调用（复用适配器实例）
# ═══════════════════════════════════════════════════════════════════════════════

async def _调用OneBotAPI(动作: str, 参数: dict) -> dict:
    """通过适配器实例调用 OneBot API。

    优先用 HTTP 调用器（反向 WS 下图片等可能不返回 echo 导致超时），
    回退到 WS 通道。
    """
    适配器 = _获取适配器()
    if 适配器 is None:
        return {"status": "failed", "msg": "NapCat 适配器未初始化（网关未启动或平台未连接）"}

    # 优先 HTTP 调用器
    HTTP调用器 = getattr(适配器, "_HTTP调用器", None)
    if HTTP调用器 is not None:
        try:
            return await HTTP调用器.调用API(动作, 参数)
        except Exception as e:
            logger.warning(f"HTTP 调用「{动作}」失败，回退 WS: {e}")

    # WS 回退
    ws = getattr(适配器, "ws", None)
    if ws is not None:
        try:
            return await ws.调用API(动作, 参数)
        except Exception as e:
            return {"status": "failed", "msg": f"WS 调用失败: {e}"}

    return {"status": "failed", "msg": "适配器无可用通道（WS 和 HTTP 均未初始化）"}


# ═══════════════════════════════════════════════════════════════════════════════
# 工具 1: napcat_send_message
# ═══════════════════════════════════════════════════════════════════════════════

NAPCAT_SEND_MESSAGE_SCHEMA = {
    "name": "napcat_send_message",
    "description": (
        "通过 NapCat 向 QQ 群聊或私聊发送消息。支持纯文本和 CQ 码（图片、表情、@等）。\n"
        "CQ 码格式示例：[CQ:image,file=http://example.com/img.jpg]\n"
        "            [CQ:face,id=178]\n"
        "            [CQ:at,qq=123456]\n"
        "多条 CQ 码可拼接在消息文本中一起发送。\n"
        "限制：目标必须已在群/用户白名单内，否则拒绝发送；[CQ:file] 与 @全体 不允许；\n"
        "本地图片路径必须在运维的媒体白名单目录内。要发文件请用 MEDIA: 通道。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target_type": {
                "type": "string",
                "enum": ["group", "private"],
                "description": "消息类型：group=群聊, private=私聊",
            },
            "target_id": {
                "type": "string",
                "description": "目标 ID：群聊为群号，私聊为 QQ 号",
            },
            "message": {
                "type": "string",
                "description": "消息内容，支持纯文本和 CQ 码。CQ 码直接嵌入文本中即可。",
            },
            "auto_escape": {
                "type": "boolean",
                "description": "是否禁用 CQ 码解析（将消息作为纯文本发送）。默认 false。",
            },
        },
        "required": ["target_type", "target_id", "message"],
    },
}


async def _handle_send_message(args: dict, **kw) -> str:
    """发送 QQ 消息，复用适配器的完整发送链路（CQ码检测、合并转发、拆分等）。"""
    目标类型 = str(args.get("target_type") or "").strip().lower()
    目标ID = str(args.get("target_id") or "").strip()
    消息内容 = args.get("message") or ""

    if 目标类型 not in ("group", "private"):
        return tool_error("target_type 必须是 'group' 或 'private'")
    if not 目标ID:
        return tool_error("target_id 不能为空")
    if not 消息内容:
        return tool_error("message 不能为空")

    # 出站目标也要过白名单:否则被允许的人(或提示注入)可以指挥机器人把消息发到
    # 白名单之外的任意群 / 任意 QQ 用户。
    拒绝理由 = 检查发信目标(目标类型, 目标ID)
    if 拒绝理由:
        logger.warning(f"拒绝发送到 {目标类型}:{目标ID}: {拒绝理由}")
        return tool_error(拒绝理由)

    适配器 = _获取适配器()
    if 适配器 is None:
        return tool_error("NapCat 适配器未初始化（网关未启动或平台未连接）")

    # 构建适配器能识别的 chat_id 格式
    if 目标类型 == "group":
        chat_id = f"napcat_group_{目标ID}"
    else:
        chat_id = f"napcat_private_{目标ID}"

    try:
        result = await 适配器.send(chat_id=chat_id, content=消息内容)
        if result.success:
            return tool_result({
                "success": True,
                "target_type": 目标类型,
                "target_id": 目标ID,
                "message_id": result.message_id,
            })
        return tool_error(f"发送失败: {result.error}")
    except Exception as e:
        return tool_error(f"发送异常: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 工具 2: napcat_call_action
# ═══════════════════════════════════════════════════════════════════════════════

NAPCAT_CALL_ACTION_SCHEMA = {
    "name": "napcat_call_action",
    "description": (
        "调用 NapCat / OneBot v11 API 动作。默认只放行只读查询类动作，例如：\n"
        "  get_group_list — 群列表\n"
        "  get_group_info — 群信息（params: group_id）\n"
        "  get_group_member_info / get_group_member_list — 群成员（params: group_id）\n"
        "  get_friend_list — 好友列表\n"
        "  get_msg — 获取单条消息（params: message_id）\n"
        "  get_group_msg_history — 群历史消息（params: group_id）\n"
        "  get_login_info / get_status / get_version_info — 账号与运行状态\n"
        "改动状态、撤回删除、发送消息、上传文件等动作不在默认白名单内，调用会被拒绝。\n"
        "需要用文件时请走 MEDIA: 通道（受运维的媒体白名单管理），不要试图用 API 绕过：\n"
        "上传类动作的路径参数同样要过媒体白名单，绕不过去。\n"
        "运维可在插件配置 allowed_actions 里放开更多动作。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "OneBot API 动作名（如 get_group_list, get_login_info）",
            },
            "params": {
                "type": "object",
                "description": "动作参数对象。不同动作需要不同参数，见 action 描述。",
                "additionalProperties": True,
            },
        },
        "required": ["action"],
    },
}


async def _handle_call_action(args: dict, **kw) -> str:
    """调用 OneBot API 动作（经 security.py 的动作白名单 + 路径校验）。"""
    动作 = str(args.get("action") or "").strip()
    参数 = args.get("params") or {}

    if not 动作:
        return tool_error("action 不能为空")
    if not isinstance(参数, dict):
        return tool_error("params 必须是对象")

    # 闸门在调用之前:不让动作白名单外的调用摸到 API,也不让路径白名单外的文件出去。
    拒绝理由 = 检查调用(动作, 参数)
    if 拒绝理由:
        logger.warning(f"拒绝 OneBot 动作「{动作}」: {拒绝理由}")
        return tool_error(拒绝理由)

    结果 = await _调用OneBotAPI(动作, 参数)

    if isinstance(结果, dict):
        if 结果.get("status") == "ok":
            return tool_result({
                "success": True,
                "action": 动作,
                "data": 结果.get("data"),
                "retcode": 结果.get("retcode"),
            })
        else:
            错误信息 = 结果.get("msg") or 结果.get("wording") or 结果.get("message") or str(结果)
            return tool_error(f"动作「{动作}」调用失败: {错误信息}")
    else:
        return tool_error(f"动作「{动作}」返回异常: {结果}")


# ═══════════════════════════════════════════════════════════════════════════════
# 工具注册表
# ═══════════════════════════════════════════════════════════════════════════════

# (工具名, schema, handler, emoji)
工具列表 = (
    ("napcat_send_message", NAPCAT_SEND_MESSAGE_SCHEMA, _handle_send_message, "💬"),
    ("napcat_call_action", NAPCAT_CALL_ACTION_SCHEMA, _handle_call_action, "🔧"),
)
