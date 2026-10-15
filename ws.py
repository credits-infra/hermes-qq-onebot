import asyncio
import hmac
import ipaddress
import json
import logging
import os
import time
from typing import Optional
from urllib.parse import parse_qs, urlparse
import websockets
from websockets.asyncio.server import ServerConnection

from .tools import 打印

logger = logging.getLogger(__name__)

# 只在回环上绑定时才算「本机」。
_回环主机名 = {"localhost"}


def _是回环地址(地址: str) -> bool:
    """地址是否只在本机可达。

    绑非回环地址却不设访问令牌，等于把「伪造 QQ 事件的入口」敞开：任何能访问
    该端口的人都可以冒充任意用户/群（直接绕过用户白名单）、伪造 API 响应，或
    借事件里的路径字段让 bot 去读本机文件。
    """
    值 = str(地址 or "").strip().strip("[]").lower()
    if not 值:
        return False
    if 值 in _回环主机名:
        return True
    try:
        return ipaddress.ip_address(值).is_loopback
    except ValueError:
        return False


# 实现「我没有这个动作」的几种说法。LLOneBot/LuckyLilliaBot 对未实现的动作返
# retcode 1404 + "<action> API 不存在"(src/onebot11/connect/ws.ts 的 handleAction);
# go-cqhttp / NapCat 措辞类似。认出来才能优雅降级,而不是每次失败刷一行日志。
_不支持关键词 = ("api 不存在", "不支持的", "不支持该", "未实现", "unsupported",
               "not implemented", "not support", "no such api")


def _是不支持(结果: dict) -> bool:
    """实现是否明确表示「没有这个动作」。"""
    if not isinstance(结果, dict):
        return False
    if 结果.get("retcode") == 1404:
        return True
    文本 = " ".join(str(结果.get(键, "")) for 键 in ("msg", "message", "wording")).lower()
    return any(词 in 文本 for 词 in _不支持关键词)


class WS:
    """反向 WebSocket 服务端（OneBot v11），配置在初始化时传入，启动时直接监听。"""

    def __init__(
        self,
        事件处理器,
        监听地址: str = "127.0.0.1",
        监听端口: int = 6700,
        访问令牌: str = "",
    ):
        """
        参数:
            事件处理器: 异步回调，处理收到的 OneBot 事件。
            监听地址: 绑定地址（如 "0.0.0.0" 或 "127.0.0.1"）。
            监听端口: 绑定端口（如 6700）。
            访问令牌: 可选 Bearer token，用于认证 NapCat 等客户端。
        """
        self._事件处理器 = 事件处理器
        self._监听地址 = 监听地址
        self._监听端口 = 监听端口
        self._访问令牌 = 访问令牌

        self._ws连接实例: Optional[ServerConnection] = None
        self._待响应映射表: dict[str, asyncio.Future] = {}
        self._自增计数器: int = 0
        self._服务端 = None  # asyncio 服务器对象，由启动() 创建
        # 能力探测:被实现明确拒绝(1404 / "API 不存在")的扩展动作记在这里,之后不再重试。
        self._不支持的动作: set[str] = set()
        # 握手头里声明的东西:反连的 OneBot 实现会发 X-Self-ID(机器人 QQ 号)。
        # 认证通过后才写入 —— 未授权的连接不该能影响我们的状态(见 _认证并处理连接)。
        self._对端SelfID: str = ""

    async def 启动(self) -> None:
        """启动反向 WS 服务端（使用 __init__ 中保存的配置）。"""
        # 失败即拒：非回环地址 + 无令牌 = 谁都能伪造事件。宁可启动不了，也不要
        # 一个看起来正常、实际对全网敞开的入口。
        if not _是回环地址(self._监听地址) and not self._访问令牌:
            raise ValueError(
                f"拒绝启动：监听地址「{self._监听地址}」不是回环地址，却没有设置访问令牌。"
                "请把 reverse_host 改回 127.0.0.1，或同时设置 access_token。"
            )

        async def _处理连接(ws连接: ServerConnection):
            await self._认证并处理连接(ws连接) # type: ignore[attr-defined]

        self._服务端 = await websockets.serve(
            _处理连接,
            self._监听地址,
            self._监听端口,
            ping_interval=20,
            ping_timeout=20,
        )
        logger.info(f"反向WS服务端启动：ws://{self._监听地址}:{self._监听端口}，等待连接")
        打印(f"反向WS服务端启动：ws://{self._监听地址}:{self._监听端口}，等待连接")

    async def 停止(self) -> None:
        """停止服务端并清理资源。"""
        if self._ws连接实例:
            try:
                await self._ws连接实例.close()
            except Exception:
                pass
        if self._服务端:
            self._服务端.close()
            await self._服务端.wait_closed()

    # ── 内部方法 ──────────────────────────────────────────────────────────

    async def _认证并处理连接(self, ws连接) -> None:
        """认证 NapCat 连接，认证通过后才接管发送通道，然后进入消息接收循环。

        ⚠️ 顺序很要紧：认证通过之前绝不能把 `self._ws连接实例` 指过去。原实现
        「先接管、再认证」，认证失败只 close + return —— 而那条路径**不会走
        finally**，于是 `_ws连接实例` 永久停在已关闭的 socket 上，出站消息全部
        失败。任何人对端口发一次坏令牌的连接即可触发（连令牌都不需要知道）。
        """
        if self._访问令牌:
            认证头 = ws连接.request.headers.get("Authorization", "")
            提取的令牌 = 认证头.removeprefix("Bearer ").strip()

            if not 提取的令牌:
                try:
                    查询参数 = parse_qs(urlparse(ws连接.request.path).query)
                    提取的令牌 = 查询参数.get("access_token", [""])[0]
                except Exception:
                    提取的令牌 = ""

            # 按字节比较,且用 surrogateescape:HTTP 头里的非 ASCII 字节会被 websockets 以
            # surrogateescape 解出来(实测:含代理字符),直接 encode("utf-8") 会抛
            # UnicodeEncodeError —— 而这段不在 try 里,连接就会带着 traceback 断开,日志被
            # 噪音污染,任何人都能发非 ASCII 令牌来刷。surrogateescape 把代理字符还原成原始
            # 字节,常数时间比较语义不变,任意字节序列都能正常判「不匹配」走干净路径。
            try:
                令牌匹配 = hmac.compare_digest(
                    提取的令牌.encode("utf-8", "surrogateescape"),
                    self._访问令牌.encode("utf-8", "surrogateescape"),
                )
            except (UnicodeError, TypeError, ValueError):
                令牌匹配 = False

            if not 令牌匹配:
                logger.warning(f"反向WS认证失败，拒绝连接：{ws连接.remote_address}")
                打印(f"反向WS认证失败，拒绝连接：{ws连接.remote_address}")
                await ws连接.close(1008, "认证失败")
                return

        # 认证通过才接管。已有连接时先关掉旧的，避免两条连接同时收事件、
        # 而发送只走新连接，造成串台。
        旧连接 = self._ws连接实例
        if 旧连接 is not None and 旧连接 is not ws连接:
            logger.info("反向WS：新客户端接入，顶替旧连接")
            打印("反向WS：新客户端接入，顶替旧连接")
            try:
                await 旧连接.close(1008, "连接已被新客户端顶替")
            except Exception:
                pass
        self._ws连接实例 = ws连接
        # 握手头里的机器人 QQ 号:连上来就能知道是谁,不必等第一条事件。
        # websockets 的 headers 大小写不敏感,写 "X-Self-ID" 即可。
        self._对端SelfID = str(ws连接.request.headers.get("X-Self-ID", "") or "").strip()

        logger.info(f"反向WS客户端已连接：{ws连接.remote_address}")
        打印(f"反向WS客户端已连接：{ws连接.remote_address}"
             + (f" 机器人QQ={self._对端SelfID}" if self._对端SelfID else ""))

        try:
            async for 原始消息 in ws连接:
                await self._处理消息(原始消息)
        except websockets.ConnectionClosed as e:
            logger.warning(f"反向WS连接关闭: rcvd={e.rcvd} sent={e.sent}")
            打印(f"反向WS连接关闭: rcvd={e.rcvd} sent={e.sent}")
        except Exception as e:
            logger.error(f"反向WS处理错误: {e}", exc_info=True)
            打印(f"反向WS处理错误: {e}")
        finally:
            # 只有「自己仍是当前连接」才清理共享状态：被顶替的旧连接收尾时若清空
            # 待响应表，会把新连接正在等待的 API 响应一起打掉。
            if self._ws连接实例 is ws连接:
                self._ws连接实例 = None
                logger.info("反向WS客户端已断开")
                打印("反向WS客户端已断开")
                for 正在等待 in self._待响应映射表.values():
                    if not 正在等待.done():
                        正在等待.set_exception(ConnectionError("WebSocket 已断开"))
                self._待响应映射表.clear()

    async def _处理消息(self, 原始消息: str) -> None:
        """解析并分发 WebSocket 消息。"""
        try:
            数据 = json.loads(原始消息)

            if "echo" in 数据:
                self.处理echo响应(数据)
            elif 数据.get("post_type") == "meta_event":
                pass
            else:
                await self._事件处理器(数据)

        except json.JSONDecodeError:
            logger.debug(f"反向WS: 非JSON消息: {原始消息[:200]}")
        except Exception as e:
            logger.error(f"反向WS事件处理错误: {e}", exc_info=True)

    async def 调用API(self, 动作: str, 参数: dict, 超时秒数: float = 120.0) -> dict:
        """调用 OneBot API 并等待响应。"""
        if not self._ws连接实例:
            return {"status": "failed", "msg": "WebSocket 未连接"}

        self._自增计数器 += 1
        回显标识 = f"napcat_{self._自增计数器}_{int(time.time() * 1000)}"

        数据包 = json.dumps({
            "action": 动作,
            "params": 参数,
            "echo": 回显标识,
        })

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._待响应映射表[回显标识] = future

        try:
            await self._ws连接实例.send(数据包)
            return await asyncio.wait_for(future, timeout=超时秒数)
        except asyncio.TimeoutError:
            return {"status": "failed", "msg": f"WebSocket 调用「{动作}」超时未响应"}
        except websockets.exceptions.ConnectionClosed as e:
            return {"status": "failed", "msg": f"连接已关闭: {e}"}
        except ConnectionError as e:
            return {"status": "failed", "msg": str(e)}
        finally:
            self._待响应映射表.pop(回显标识, None)

    def 处理echo响应(self, 数据: dict) -> None:
        """处理 WebSocket 返回的带 echo 的响应。"""
        回显标识 = 数据.get("echo")
        if not 回显标识:
            return
        future = self._待响应映射表.pop(回显标识, None)
        if future and not future.done():
            future.set_result(数据)

    # ── 常用 API 封装（保持不变）──────────────────────────────────────────

    async def 发送私聊消息(self, 用户ID: str, 消息内容) -> dict:
        return await self.调用API("send_private_msg", {
            "user_id": int(用户ID),
            "message": 消息内容,
        })

    async def 发送群聊消息(self, 群ID: str, 消息内容) -> dict:
        return await self.调用API("send_group_msg", {
            "group_id": int(群ID),
            "message": 消息内容,
        })

    async def 获取群信息(self, 群ID: str) -> dict:
        return await self.调用API("get_group_info", {"group_id": int(群ID)})

    async def 获取文件(self, 文件ID: str) -> dict:
        return await self.调用API("get_file", {"file_id": 文件ID})

    async def 获取消息(self, 消息ID: str) -> dict:
        return await self.调用API("get_msg", {"message_id": int(消息ID)})

    async def 上传群文件(self, 群ID: str, 文件路径: str, 文件名: str = "") -> dict:
        return await self.调用API("upload_group_file", {
            "group_id": int(群ID),
            "file": 文件路径,
            "name": 文件名 or os.path.basename(文件路径),
        })

    async def 上传私聊文件(self, 用户ID: str, 文件路径: str, 文件名: str = "") -> dict:
        return await self.调用API("upload_private_file", {
            "user_id": int(用户ID),
            "file": 文件路径,
            "name": 文件名 or os.path.basename(文件路径),
        })

    async def 发送群合并转发(self, 群ID: str, 消息节点列表: list) -> dict:
        return await self.调用API("send_group_forward_msg", {
            "group_id": int(群ID),
            "messages": 消息节点列表,
        })

    async def 发送私聊合并转发(self, 用户ID: str, 消息节点列表: list) -> dict:
        return await self.调用API("send_private_forward_msg", {
            "user_id": int(用户ID),
            "messages": 消息节点列表,
        })

    def _记不支持(self, 动作: str, 结果: dict, 功能名: str) -> bool:
        """首次发现某动作为「不支持」时记下来并提示一次。返回是否属于这种情况。"""
        if not _是不支持(结果):
            return False
        if 动作 not in self._不支持的动作:
            self._不支持的动作.add(动作)
            logger.warning(f"当前 OneBot 实现不支持「{动作}」，已停用{功能名}（不再重试）")
            打印(f"注意：当前实现不支持「{动作}」，已停用{功能名}")
        return True

    async def 设置表情回应(self, 消息ID: str, 表情ID: int = 12) -> dict:
        """给消息加表情回应。

        `set_msg_emoji_like` 是 NapCat/Lagrange/LLOneBot 的扩展动作,不是 OneBot v11
        标准;实现没有它时返回「已跳过」而不是失败 —— 上层每次失败都打 warning,那样
        每条消息都会刷一行日志,而功能本来就不存在。
        """
        if "set_msg_emoji_like" in self._不支持的动作:
            return {"status": "skipped", "retcode": 0, "msg": "表情回应：实现不支持，已停用"}
        结果 = await self.调用API("set_msg_emoji_like", {
            "message_id": int(消息ID),
            "emoji_id": 表情ID,
            "set": True,
        })
        if self._记不支持("set_msg_emoji_like", 结果, "表情回应"):
            return {"status": "skipped", "retcode": 0, "msg": "表情回应：实现不支持，已停用"}
        return 结果

    async def 戳一戳好友(self, 用户ID: str) -> dict:
        """戳一戳好友。

        标准动作是 `send_poke`;go-cqhttp 系实现常用 `friend_poke`(NapCat/LLOneBot 两个
        都有)。先试标准的,被拒再试专有的;都试完仍不支持就记下来停用。
        """
        候选 = [动作 for 动作 in ("send_poke", "friend_poke")
                if 动作 not in self._不支持的动作]
        if not 候选:
            return {"status": "skipped", "retcode": 0, "msg": "戳一戳：实现不支持，已停用"}

        for 动作 in 候选:
            结果 = await self.调用API(动作, {"user_id": int(用户ID)})
            if not self._记不支持(动作, 结果, "戳一戳"):
                return 结果
        return {"status": "skipped", "retcode": 0, "msg": "戳一戳：实现不支持，已停用"}