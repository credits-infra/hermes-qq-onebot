<div align="center">

# Hermes-QQ-OneBot

**Hermes Agent × QQ — Bringing AI to Life on QQ**

[![Hermes Plugin](https://img.shields.io/badge/Hermes-Platform%20Plugin-7c3aed?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiPjxwYXRoIGQ9Ik0xMiAyTDIuNSA3djEwTDEyIDIybDkuNS0yVjciLz48L3N2Zz4=)](https://hermes-agent.nousresearch.com/docs)
[![OneBot v11](https://img.shields.io/badge/OneBot-v11-1677ff?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiPjxjaXJjbGUgY3g9IjEyIiBjeT0iMTIiIHI9IjEwIi8+PC9zdmc+)](https://github.com/botuniverse/onebot)
[![Version](https://img.shields.io/badge/version-3.5.0-green)](./plugin.yaml)
[![License](https://img.shields.io/badge/license-MIT-blue)](./LICENSE)

**Language / 语言：** [中文](README.md) | [English](README_EN.md)

*A QQ platform adapter based on the OneBot v11 protocol, bringing QQ connectivity to [Hermes Agent](https://github.com/NousResearch/hermes-agent)*

</div>

---

## ✨ Highlights

<table>
<tr>
<td width="50%">

### 🔌 Plug & Play
One command to install and enable. Reverse WebSocket needs zero config — NapCat connects to you

</td>
<td width="50%">

### 🧩 Pure Plugin Design
Doesn't touch a line of Hermes source. Install to activate, remove to clean up — zero intrusion

</td>
</tr>
<tr>
<td width="50%">

### 📦 Native CQ Code Support
Agent writes `[CQ:image,file=...]` directly in text to send complex messages — no extra API needed

</td>
<td width="50%">

### 🛡️ On-Demand Media Download
Media is only downloaded when the Agent is invoked. Idle messages never touch disk. Oversized items keep URL only for Agent to fetch as needed

</td>
</tr>
<tr>
<td width="50%">

### ✂️ Long Message Merged Forwarding
Group chat replies exceeding the threshold are auto-merged. CQ codes are smartly split into independent message nodes

</td>
<td width="50%">

### 🔑 Keyword Triggers
Regex matching auto-responds to group chat messages — no @mention needed to wake the Agent

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
📱 QQ Client
      ↕
🌊 NapCat / Lagrange / go-cqhttp / LLOneBot  (OneBot v11 implementations)
      ↓ Reverse WebSocket (connects to adapter)
🔌 hermes-qq-onebot
      ↓
🤖 Hermes Agent (full AI capabilities: terminal/browser/files/search/...)
```

> **Reverse WebSocket** — The adapter runs a server; OneBot implementations connect to it. No public IP or open ports needed.
>
> **HTTP API** — Optional but recommended, resolves image send timeouts, file retrieval, etc.

---

## 🚀 Installation

```bash
hermes plugins install landamao/hermes-qq-onebot --enable
```

Done! Now just configure NapCat to connect.

<details>
<summary>🔧 Manual Installation</summary>

```bash
# Clone into Hermes plugins directory
git clone https://github.com/landamao/hermes-qq-onebot.git ~/.hermes/plugins/napcat

# Install dependencies
pip install websockets

# Restart gateway
hermes gateway restart
```
</details>

---

## 📋 Compatible OneBot Implementations

| Implementation | Status | Notes |
|:---------------|:------:|:------|
| [NapCat](https://github.com/NapNeko/NapCatQQ) | ✅ Recommended | Best feature support |
| [Lagrange.OneBot](https://github.com/LagrangeDev/Lagrange.Core) | ✅ Compatible | Works fine |
| [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) | ⚠️ Legacy | Usable but no longer maintained |
| [LuckyLilliaBot](https://github.com/LLOneBot/LuckyLilliaBot) (formerly LLOneBot) | ✅ Compatible | Renamed, new repo; verified action-by-action (below) |

> Any implementation conforming to the OneBot v11 standard works!

### Verification details (2026-10, checked against the implementation's source)

Verified against LuckyLilliaBot — every action this plugin calls, plus the protocol details:

| Called by this plugin | Supported | Notes |
|:---|:---:|:---|
| `send_group_msg` / `send_private_msg` | ✅ | |
| `get_group_info` / `get_msg` / `get_file` | ✅ | |
| `upload_group_file` / `upload_private_file` | ✅ | |
| `send_group_forward_msg` / `send_private_forward_msg` | ✅ | merged forwarding |
| `send_poke` (standard) / `friend_poke` (its extension) | ✅ both | the plugin tries the **standard one first** |
| `set_msg_emoji_like` (emoji reaction) | ✅ in its extension namespace | degrades gracefully when missing |

- **Token**: it connects with `Authorization: Bearer <token>` — exactly the header this plugin
  reads (an empty Bearer when no token is set is also fine). Non-ASCII tokens compare correctly.
- **Handshake header**: it also sends `X-Self-ID` (the bot's QQ number). The plugin reads it at
  connect time and logs it (`反向WS客户端已连接：… 机器人QQ=…`), so you can tell which account
  connected before the first event arrives; the event's `self_id` still wins — this is the fallback.
- **Message format**: `messageFormat` may be `array` (default) or `string`. **Both work** — under
  `string` the `message` field is a CQ-code string, which the plugin splits into segments.
- **Missing actions**: it answers `retcode 1404` + `"<action> API 不存在"`. The plugin detects that
  and **degrades gracefully** (announced once, then the feature is disabled — no per-message log spam).
- **Media segments**: `transform/message/incoming.ts` includes `file_size` for image/video/file/record,
  so the download gate can pre-check; if an implementation omits it, the plugin still attempts the
  download under the configured limit (the download itself enforces HEAD pre-check + streaming abort).

---

## 📁 Module Structure

```
napcat/
├── plugin.yaml        # Plugin metadata
├── adapter.py         # Registration entry (register function)
├── main.py            # Adapter body (NapCat适配器 class)
├── ws.py              # Reverse WS server (WS class)
├── napcat_http.py     # HTTP API caller (NapcatHttp class)
└── tools.py           # Constants, LRU cache, media download, message segment build/parse
```

---

## 🎯 Feature Overview

### 💬 Messaging

| Feature | Description |
|:--------|:------------|
| Private / Group chat | Dual-mode message send & receive |
| @Mention detection | Auto-respond when mentioned |
| Keyword triggers | Regex matching — no @mention needed to wake Agent |
| Reply quoting | Parses quoted original text with smart truncation, preserves full media tags |
| Long message merged forwarding | Group chat auto-merges above threshold; CQ codes split into independent nodes |
| Emoji reactions / poke | Disabled by default, enable on demand |

### 📎 Media Support

| Type | Receive | Send | Message Tag |
|:-----|:-------:|:----:|:------------|
| 🖼️ Image | ✅ | ✅ | `[图片:file=/tmp/xxx.jpg]` or `[图片:url=https://...]` |
| 🎤 Voice | ✅ | ✅ | `[语音:file=/tmp/xxx.ogg]` or `[语音:url=https://...]` |
| 🎬 Video | ✅ | ✅ | `[视频:url=https://...]` or `[视频:file=/tmp/xxx.mp4]` |
| 📄 File | ✅ | ✅ | `[文件:name=report.pdf,file=/tmp/xxx]` |
| 😊 Emoji | ✅ | ✅ | `[表情:id=123]` |
| 📢 @Mention | ✅ | ✅ | `@Nickname(QQ:123456)` → `[CQ:at,qq=123]` |

> The Agent sees structured tags with paths/URLs — no extra processing needed to access files.

### 📤 CQ Code Sending

The Agent writes CQ codes directly in reply text; the adapter auto-parses and sends:

```
Check this out [CQ:image,file=/tmp/test.jpg]
Here's the file you wanted [CQ:file,file=/tmp/document.pdf,name=文档.pdf]
```

**Supported CQ codes:** `[CQ:at]` · `[CQ:image]` · `[CQ:record]` · `[CQ:video]` · `[CQ:file]` · `[CQ:face]` · and more OneBot v11 standard CQ codes

---

## ⚙️ Configuration

Add to `~/.hermes/config.yaml`:

```yaml
platforms:
  napcat:
    enabled: true
    extra:
      # ── Reverse WS config ──
      reverse_host: "127.0.0.1"          # Listen address (default 127.0.0.1, localhost only)
      reverse_port: 6700                  # Listen port (default 6700)
      access_token: ""                    # Access token (optional, authenticates NapCat connection)
      # reverse_token works as an alias for access_token

      # ── HTTP API (recommended) ──
      http_api_url: "http://127.0.0.1:5700"  # OneBot HTTP API address
      http_api_token: ""                      # HTTP token (defaults to access_token)

      # ── Bot info ──
      bot_self_id: ""                     # Bot QQ number (optional, auto-learned from messages)

      # ── Media download limits ──
      # When file_size is available, items exceeding the limit are not downloaded; only URL kept
      # Supports B/KB/MB/GB (case-insensitive)
      download_limits:
        image: 10MB                     # Image limit (default 10MB)
        record: 10MB                    # Voice limit (default 10MB)
        video: 10MB                     # Video limit (default 10MB)
        file: 10MB                      # File limit (default 10MB)

      # ── Long message handling ──
      merge_forward_threshold: 800      # Group chat messages exceeding this length trigger merged forwarding (default 800, private chat not affected)
      forward_name: "纳西妲"            # Name shown in merged forwarding (default 纳西妲)

      # ── Reply quoting ──
      reply_text_max_length: 50         # Max chars when parsing reply-quoted messages; truncate with ellipsis beyond this (default 50)
                                         # Truncation preserves full media tags (e.g. [图片:file=...]) — won't cut mid-tag

      # ── Keyword triggers ──
      # Auto-respond when these regexes match in group chat (case-insensitive)
      mention_patterns:
        - "纳猫"
        - "帮我"

      # ── User whitelist ──
      # Empty/unset → reject all users
      # Set to "all" or "*" → allow all users
      allowed_qq_ids: "123456,789012"   # Comma-separated, list, or bare numbers all work

      # ── Emoji reactions ──
      emoji_react: false                # Random emoji reaction on message receive (default false)
```

<details>
<summary>🌍 Environment Variable Overrides</summary>

All config items can be overridden via environment variables. Variable name = `NAPCAT_` + config key uppercased.

Priority: environment variable > config.yaml > default value

Value parsing: try JSON first (numbers, booleans, lists, dicts all supported), then recognize boolean keywords (`off/false/no` → False, `on/true/yes` → True), otherwise return string as-is.

```bash
# Basic config
NAPCAT_REVERSE_HOST=127.0.0.1
NAPCAT_REVERSE_PORT=6700
NAPCAT_ACCESS_TOKEN=your_token
NAPCAT_HTTP_API_URL=http://127.0.0.1:5700
NAPCAT_HTTP_API_TOKEN=your_http_token
NAPCAT_BOT_SELF_ID=123456789

# Boolean (these are equivalent)
NAPCAT_EMOJI_REACT=false
NAPCAT_EMOJI_REACT=off
NAPCAT_EMOJI_REACT=no

# Integer
NAPCAT_MERGE_FORWARD_THRESHOLD=1000

# JSON dict (complex values use JSON)
NAPCAT_DOWNLOAD_LIMITS='{"image":"20MB","video":"100MB"}'

# JSON array or comma-separated
NAPCAT_MENTION_PATTERNS='["纳猫","帮我"]'
NAPCAT_MENTION_PATTERNS=纳猫,帮我

# Whitelist
NAPCAT_ALLOWED_QQ_IDS=123456,789012
NAPCAT_ALLOWED_QQ_IDS='[123, 456]'        # JSON array works too
NAPCAT_ALLOWED_QQ_IDS=123456              # Single bare number works too

# Whitelist alias (only effective when config doesn't set allowed_qq_ids)
NAPCAT_ALLOWED_USERS=123456,789012

# Allow all users (set to true to skip whitelist)
NAPCAT_ALLOW_ALL_USERS=false

# Group allowlist (default empty = no group is served; `all` disables the check)
NAPCAT_ALLOWED_GROUPS=123456,789012
NAPCAT_ALLOWED_GROUPS='[123, 456]'        # JSON array also accepted

# Do slash commands in groups also require an @mention/keyword? (default true)
NAPCAT_GROUP_COMMAND_REQUIRES_MENTION=true

# Outbound security: extra OneBot actions / CQ types (added on top of the defaults)
NAPCAT_ALLOWED_ACTIONS='["upload_group_file"]'    # default: read-only actions only
NAPCAT_ALLOWED_CQ_TYPES=shake                     # face/at/image/record/video/reply by default
NAPCAT_ALLOW_AT_ALL=false                         # allow @everyone
```
</details>

---

## 🛡️ Outbound Security Policy

This plugin lets the LLM call OneBot APIs and write CQ codes in replies — **both can exfiltrate files from
the host**. That is fine for a bot in your own group, not fine for a bot in someone else's. Four gates ship
on by default:

**1. API action allowlist (`napcat_call_action`)** — only read-only queries are allowed by default
(`get_group_list`, `get_group_info`, `get_msg`, `get_group_msg_history`, …). Actions like
`upload_group_file` (send an arbitrary host file into a group), `download_file` (write an arbitrary URL to an
arbitrary path), `delete_msg`, `set_group_*` and `send_*` are refused unless the operator names them in
`allowed_actions` (or `all`). Credential-revealing actions (`get_cookies`, `get_csrf_token`) are refused even
under `all`. Naming actions **extends** the default read-only set — enabling one action never locks out queries.

**2. CQ code sanitization** — `[CQ:file,file=file:///any/path]` is the same exfiltration route as
`upload_group_file`, so it is never allowed; `[CQ:image]`/`[CQ:record]`/`[CQ:video]` must pass Hermes' own
media allowlist (`gateway.media_delivery_allow_dirs`) for **every parameter that can carry a path**
(`file`, `url`, `path`, `src`, `dest`, …), not just `file` — LLOneBot sends `url || file`, so
`file=https://x/a.png,url=/host/file` would smuggle a host path through `url`. `[CQ:at,qq=all]` requires
`allow_at_all: true`. Unknown CQ types are dropped, and so is **anything that fails to parse** (fail-closed):
`[CQ:file2,…]` / `[CQ:FILE,…]` used to slip through as "unjudgeable but maybe file-like". **Duplicate
parameter keys are dropped too** (receivers disagree on whether the first or last wins, and we can only
validate the one we see), the CQ prefix is **case-insensitive**, and path validation applies to **any type**
carrying a path parameter (not just `image`/`record`/`video`).

Sanitization happens at a single **choke point**: every outbound message goes through `_WS发送` / `_HTTP发送`,
which sanitize inside — instead of each send path having to remember (before this, 5 call sites remembered and
3 forgot: `send_image`'s URL, `send_image_file`'s path, `send_document`'s caption). Dropped codes are logged as
warnings, never sent as literals.

Dynamic values interpolated into a CQ parameter (image URL, local path, reply id) are **CQ-escaped** first: a
comma inside a value would otherwise become an extra parameter key, and brackets would grow a brand-new CQ code —
neither contains `[CQ:`, so the sanitizer cannot see them (`&#44;` / `&#91;` / `&#93;`, unescaped by receivers).
Attachments sent through the `MEDIA:` route are unaffected — Hermes validates those first.

**3. Admission control (default deny)** — `allowed_qq_ids` (empty = nobody) and `allowed_group_ids`
(empty = no group, a **behavior change**: configure it or the bot ignores all group messages).
`group_command_requires_mention` (default `true`) also requires an @mention for `/commands` in groups.
`napcat_send_message` validates that the target is inside the allowlists, and so do **the core send paths**:
`send()` / `send_image()` / `send_image_file()` / `send_voice()` / `send_document()` all route through
`_解析投递目标()`, which checks the same allowlists; actions allowed by `napcat_call_action` (e.g.
`send_group_msg`) also get their `group_id`/`user_id` checked — **including read-only ones**, otherwise any
member of an allowed group could have the bot read another group's (or someone's private) history back into
the chat. Message-carrying actions additionally have their `message` / `messages` payload sanitized: a
disallowed CQ code makes the whole call **refuse with a reason** instead of being silently rewritten.
Like admission, this is **fail-closed**: with an empty allowlist nothing can be sent either.

Value resolution follows one ladder everywhere — **primary env var → plugin config → alias env var** — so
narrowing via `NAPCAT_ALLOWED_GROUP_IDS` also narrows the tool-layer path. At startup the plugin reads
`gateway.strict` and prints a warning when it is off, because the media allowlist is nearly open in
non-strict mode and the plugin delegates to it.

**Transport** — binding the reverse WebSocket to a non-loopback address **requires** `access_token`;
otherwise the plugin refuses to start, because anyone reaching that port could forge QQ events (impersonating
any user/group and bypassing the user allowlist) or forge API responses.

---

## Deployment and network exposure

The plugin runs in reverse WebSocket mode only: it listens, and the OneBot implementation connects to it. The default bind is `127.0.0.1:6700`. When LLOneBot runs on another machine, that connection crosses the public internet, so what you expose depends on where you bind.

### Where the plugin can listen

| `reverse_host` | Who can connect | Notes |
|---|---|---|
| `127.0.0.1` (default) | Any process on the host | No public port. Local users are not isolated from each other, so the token is the only gate |
| `0.0.0.0` or a public address | Anyone who can reach the port | Requires `access_token`. Without it the plugin refuses to start |
| `/dev/shm/napcat.sock` | Only the file owner and its group | No port, no TCP stack. The kernel enforces the file permissions |

### Why a Unix socket beats loopback TCP

A socket file hands access control to the kernel instead of to a shared secret. The plugin sets the mode to `0660` at startup. Without that, umask would leave `0755` and any local user could connect. Set `socket_group` to move the socket into the group that runs your reverse proxy; a user who knows the path still cannot connect.

It also removes a port from your host. The reverse proxy dials the socket, so the plugin listens on no TCP address at all and does not appear in `ss -ltnp`.

### Socket placement

Put it in `/dev/shm`, a tmpfs whose contents live in memory. The socket file never touches disk and the kernel allocates no disk blocks for it, so `bind` and `unlink` cause no file system I/O.

Two measured constraints rule out the alternatives:

- Not `/tmp` or `/var/tmp`. The Caddy unit sets `PrivateTmp=true`, so Caddy has its own temporary directory namespace and cannot see a socket you place in `/tmp`.
- Not your home directory. Caddy runs as the `caddy` user, and a home directory with mode `0700` (as on this host: `/home/leemina`) blocks it from even traversing the path.

For a chat bot's message rate, the I/O saved by using tmpfs instead of a directory on disk does not show up in any measurement. `/dev/shm` wins because the two constraints above rule out `/tmp` and your home directory, and tmpfs is both in memory and visible to every process.

### Caddy reverse proxy

```caddyfile
# Inside your existing site block, before the final fallback handle
@napcat host napcat.example.com
handle @napcat {
	@not_the_device not remote_ip 203.0.113.45
	respond @not_the_device "forbidden" 403

	reverse_proxy unix//dev/shm/napcat.sock
}
```

Use `unix//<path>`. It carries the WebSocket upgrade. Do not use `unix+h2c//<path>`: it returns 502 in testing, and the Caddy log says `http2: invalid Upgrade request header: ["websocket"]`. That transport targets HTTP/2 backends such as gRPC services.

The proxy does not bypass the plugin's own authentication. A connection with no token is still rejected by the plugin. An end-to-end test through Caddy confirmed the token check.

### Configuration

Plugin settings:

```yaml
reverse_host: /dev/shm/napcat.sock
socket_group: caddy
access_token: ACCESS_TOKEN
```

The user that runs Hermes must belong to the `caddy` group. Otherwise the plugin cannot change the socket group, it logs a warning, and Caddy cannot connect:

```bash
sudo usermod -aG caddy HERMES_USER
```

Two placeholders appear here. `HERMES_USER` is the account that runs Hermes, and `ACCESS_TOKEN` is a random string that both sides share.

On the client side, point the reverse WebSocket URL at `wss://napcat.example.com/` and use the same token.

### Limits

- The socket permissions are the access control for this link. If `socket_group` is missing, the plugin warns and Caddy cannot connect.
- The plugin's WebSocket server does not support TLS. Terminate TLS at the reverse proxy (Caddy provisions certificates for you). Do not send plain `ws://` across the public internet, and do not expose the plugin's port directly.
- `access_token` is optional in socket mode. Set it anyway: it still stops anyone who reaches the proxy without it.
- SELinux does not take part in this link. The host policy is enforcing, but caddy and Hermes both run in unconfined domains, so type enforcement never applies to them. Covering caddy would require writing a policy for it.

---

## 🔗 NapCat Side Configuration

Set up reverse WS connection in NapCat's config:

```json
{
  "ws_reverse": {
    "enable": true,
    "url": "ws://127.0.0.1:6700",
    "reconnect_interval": 3000,
    "token": ""
  }
}
```

> If you configured `access_token`, NapCat must also set the same token.

---

## 📟 Startup Output

Hermes' default log level is WARNING; `logger.info()` output is invisible to users, which can cause the false impression that the plugin isn't loaded. Therefore infrequent important info logs (connect/disconnect/startup/exception) also `print()` to the terminal; frequent ones (message send/receive) don't print.

A config summary is printed at startup for easy troubleshooting:

```
[NapCat插件] 反向WS模式启动，等待 NapCat 连接 端口 6700
[NapCat插件] HTTP接口已启用: http://127.0.0.1:5700
[NapCat插件] 配置: 监听地址=127.0.0.1 端口=6700 令牌=已设置
[NapCat插件] 配置: HTTP接口=已启用 表情回应=未启用
[NapCat插件] 配置: 机器人QQ号=未设置(自动学习) 合并转发阈值=800 引用文本最大字数=50
[NapCat插件] 配置: 允许所有用户=否 白名单用户(2): 123456, 789012
[NapCat插件] 配置: 下载限制={'image': '10MB', 'record': '10MB', 'video': '10MB', 'file': '10MB'}
[NapCat插件] 配置: 关键词触发模式数=2
```

---

## 🗑️ Uninstall

```bash
rm -rf ~/.hermes/plugins/napcat
hermes gateway restart
```

---

## 🧩 As a Hermes Plugin

This project is a Hermes Agent platform adapter plugin. Once registered with the Hermes plugin system, it activates automatically:

- **Plugin name:** `napcat`
- **Kind:** `platform`
- **Registered platform:** `napcat` (NapCat QQ)
- **Dependencies:** `websockets`

The plugin entry auto-registers the platform adapter with the Hermes gateway — no manual intervention needed.

---

<details>
<summary><b>📖 Differences from v2.x (click to expand)</b></summary>

v3.0.0 is a refactored upgrade from v2.1.x with identical functionality. Details below:

### Code Structure

| Item | v2.1.x (old) | v3.0.0 (new) |
|------|-------------|-------------|
| File organization | Monolithic `napcat_adapter.py` (1530 lines) | Modular split into 5 files |
| WS server | Embedded in main file | Standalone `ws.py` (WS class) |
| HTTP caller | Embedded in adapter | Standalone `napcat_http.py` (NapcatHttp class) |
| Utility functions | Embedded in main file | Standalone `tools.py` with `__all__` export list |
| API boundaries | None, all code interdependent | Clear module boundaries |

### Config Type Validation

- **Old**: `extra_config.get()` + `os.getenv()` simple fallback, no type checking, invalid input silently passes
- **New**: `获取配置()` helper function, each field validated with `isinstance`; invalid values raise `ValueError` with detailed error info

### Environment Variable Reading

- **Old**: Config items read directly from `os.getenv()`, only handles strings; env vars and config file are two independent logic paths
- **New**: Unified through `获取配置()` function, supports JSON parse + boolean keyword recognition + string fallback

### Security

| Item | v2.1.x | v3.0.0 |
|------|--------|--------|
| Default listen address | `0.0.0.0` (all interfaces) | `127.0.0.1` (localhost only) |
| Empty whitelist | Implicitly allows all users | Rejects all users, prints warning at startup |
| Allow all users | No explicit mechanism | Must set `"all"` or `"*"` to allow |

### Other Changes

- **Private chat session ID**: `napcat_{userID}` → `napcat_private_{userID}`
- **Global state**: Removed `_全局接口调用器` global variable; WS instance held by adapter
- **WS API timeout**: 60s → 120s (accommodates slow operations like large file retrieval)
- **WS event filtering**: `post_type == "meta"` → `"meta_event"` (OneBot v11 standard field name)
- **Whitelist parsing**: Added `int`/`float` support (YAML bare numbers auto-converted to string)
- **HTTP API token**: Added `http_api_token`, defaults to `access_token`
- **Startup output**: Infrequent important info logs also `print()` to terminal (Hermes defaults to WARNING level, info invisible)
- **Message segment parsing**: `构建完整文本()` split into `_格式化媒体标签()`, `_格式化文件标签()`, `_追加详细艾特文本()`
- **show_qq_id**: Removed; display name fixed as `nickname(QQnumber)` format
- **Config aliases**: `reverse_token` as alias for `access_token`; `NAPCAT_ALLOWED_USERS` as fallback env var for whitelist

</details>

---

## 📄 License

MIT License © [懒大猫](https://github.com/landamao)
