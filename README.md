<div align="center">

# Hermes-QQ-OneBot

**Hermes Agent × QQ — 让 AI 在 QQ 里活起来**

[![Hermes Plugin](https://img.shields.io/badge/Hermes-Platform%20Plugin-7c3aed?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiPjxwYXRoIGQ9Ik0xMiAyTDIuNSA3djEwTDEyIDIybDkuNS0yVjciLz48L3N2Zz4=)](https://hermes-agent.nousresearch.com/docs)
[![OneBot v11](https://img.shields.io/badge/OneBot-v11-1677ff?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiPjxjaXJjbGUgY3g9IjEyIiBjeT0iMTIiIHI9IjEwIi8+PC9zdmc+)](https://github.com/botuniverse/onebot)
[![Version](https://img.shields.io/badge/version-3.4.0-green)](./plugin.yaml)
[![License](https://img.shields.io/badge/license-MIT-blue)](./LICENSE)

**语言 / Language：** [中文](README.md) | [English](README_EN.md)

*基于 OneBot v11 协议的 QQ 平台适配器，为 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 接入 QQ 生态*

</div>

---

## ✨ 亮点

<table>
<tr>
<td width="50%">

### 🔌 即装即用
一行命令安装启用，反向 WebSocket 零配置连接，NapCat 主动连过来

</td>
<td width="50%">

### 🧩 纯插件设计
不动 Hermes 一行源码，安装即生效，卸载即干净，零侵入

</td>
</tr>
<tr>
<td width="50%">

### 📦 CQ 码原生支持
Agent 直接在文本里写 `[CQ:image,file=...]` 发送复杂消息，无需额外 API

</td>
<td width="50%">

### 🛡️ 按需下载媒体
只在被唤醒时下载媒体，闲聊消息不碰磁盘，超限只保留 URL 由 Agent 按需取用

</td>
</tr>
<tr>
<td width="50%">

### ✂️ 长消息合并转发
群聊超长回复自动合并转发，CQ 码智能拆分为独立消息节点

</td>
<td width="50%">

### 🔑 关键词触发
正则匹配群聊消息自动响应，不用 @ 也能唤醒 Agent

</td>
</tr>
</table>

---

## 🏗️ 架构

```
📱 QQ 客户端
      ↕
🌊 NapCat / Lagrange / go-cqhttp / LLOneBot  (OneBot v11 实现)
      ↓ 反向 WebSocket (主动连接适配器)
🔌 hermes-qq-onebot
      ↓
🤖 Hermes Agent (完整 AI 能力: 终端/浏览器/文件/搜索/...)
```

> **反向 WebSocket** — 适配器起 Server，OneBot 实现主动连过来，无需公网 IP，无需开放端口。
>
> **HTTP API** — 可选但推荐，解决图片发送超时、文件获取等问题。

---

## 🚀 安装

```bash
hermes plugins install landamao/hermes-qq-onebot --enable
```

搞定！现在配置 NapCat 连接过来就行。

<details>
<summary>🔧 手动安装</summary>

```bash
# 克隆到 Hermes 插件目录
git clone https://github.com/landamao/hermes-qq-onebot.git ~/.hermes/plugins/napcat

# 安装依赖
pip install websockets

# 重启网关
hermes gateway restart
```
</details>

---

## 📋 兼容的 OneBot 实现

| 实现 | 状态 | 说明 |
|:-----|:----:|:-----|
| [NapCat](https://github.com/NapNeko/NapCatQQ) | ✅ 首选 | 推荐使用，功能最全面 |
| [Lagrange.OneBot](https://github.com/LagrangeDev/Lagrange.Core) | ✅ 兼容 | 正常工作 |
| [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) | ⚠️ 旧版 | 可用但已停止维护 |
| [LuckyLilliaBot](https://github.com/LLOneBot/LuckyLilliaBot)（原 LLOneBot） | ✅ 兼容 | 已改名并迁到新仓库；逐项核对过，见下 |

> 只要符合 OneBot v11 标准的实现都能用～

### 实测细节（2026-10，对着实现源码逐项核对）

以 LuckyLilliaBot 为基准，核对了本插件用到的每个动作与协议细节：

| 本插件的调用 | 实现情况 | 备注 |
|:---|:---:|:---|
| `send_group_msg` / `send_private_msg` | ✅ | |
| `get_group_info` / `get_msg` / `get_file` | ✅ | |
| `upload_group_file` / `upload_private_file` | ✅ | |
| `send_group_forward_msg` / `send_private_forward_msg` | ✅ | 合并转发 |
| `send_poke`（标准）/ `friend_poke`（其扩展） | ✅ 都有 | 插件**先试标准的**，被拒才退专有的 |
| `set_msg_emoji_like`（表情回应） | ✅ 在其扩展命名空间 | 实现没有时会优雅降级 |

- **令牌**：它连接时发 `Authorization: Bearer <token>`，正是插件读取的格式（无 token 时发空
  Bearer，插件在不校验模式下也正常）。非 ASCII 令牌也能正确判等。
- **握手头**：它还会发 `X-Self-ID`（机器人 QQ 号）。插件连接时就读它并打进日志
  （`反向WS客户端已连接：… 机器人QQ=…`），所以刚接上、还没收到消息时也知道连的是哪个号；
  机器人 QQ 号仍以事件里的 `self_id` 为准，缺了才用这个兜底。
- **消息格式**：`messageFormat` 可配 `array`（默认）或 `string`。**两种都能用**——`string`
  时 `message` 是 CQ 码字符串，插件会拆成段数组（见 `tools.规范化消息段`）。
- **未实现的动作**：返 `retcode 1404` + `"<action> API 不存在"`。插件据此识别并**优雅降级**：
  首次提示一次、之后停用该功能，不会每条消息刷一行日志。换实现时不必担心扩展动作缺失。
- **媒体段**：`transform/message/incoming.ts` 会给 image/video/file/record 段带 `file_size`，
  下载闸门能预判；即使某个实现不带，插件也按配置上限尝试下载（下载本身有 HEAD 预检 +
  边下边查两道闸门）。

> NapCat / Lagrange.OneBot / go-cqhttp 未逐个核对源码，但插件的策略是「标准动作优先、
> 不支持就降级」，不依赖某一家的实现细节。

---

## 📁 模块结构

```
napcat/
├── plugin.yaml        # 插件元数据
├── adapter.py         # 注册入口（register 函数 + _创建适配器 工厂）
├── main.py            # 适配器主体（NapCat适配器 类）
├── ws.py              # 反向 WS 服务端（WS 类）
├── napcat_http.py     # HTTP API 调用器（NapcatHttp 类）
├── llm_tools.py       # LLM 工具（napcat_send_message + napcat_call_action）
├── security.py        # 出站安全策略（动作白名单 / CQ 码净化 / 出站目标校验）
├── tools.py           # 常量、LRU缓存、媒体下载、消息段构建/解析、CQ 码解析
└── tests/             # 回归测试（13 个脚本，共 299 条断言）
```

---

## 🎯 功能一览

### 💬 消息能力

| 功能 | 说明 |
|:-----|:-----|
| 私聊 / 群聊 | 双模式消息收发 |
| @ 提及检测 | 被 @ 自动响应 |
| 关键词触发 | 正则匹配，不 @ 也能唤醒 |
| 引用回复 | 解析被引用的原文并截断，保留完整媒体标签 |
| 长消息合并转发 | 群聊超阈值自动合并，CQ 码拆分为独立节点 |
| 表情回应 / 戳一戳 | 默认关闭，按需开启 |
| LLM 工具 | Agent 可主动发消息、调用 OneBot API（见下方 LLM 工具） |

### 📎 媒体支持

| 类型 | 接收 | 发送 | 消息标签 |
|:-----|:----:|:----:|:---------|
| 🖼️ 图片 | ✅ | ✅ | `[图片:file=/tmp/xxx.jpg]` 或 `[图片:url=https://...]` |
| 🎤 语音 | ✅ | ✅ | `[语音:file=/tmp/xxx.ogg]` 或 `[语音:url=https://...]` |
| 🎬 视频 | ✅ | ✅ | `[视频:url=https://...]` 或 `[视频:file=/tmp/xxx.mp4]` |
| 📄 文件 | ✅ | ✅ | `[文件:name=report.pdf,file=/tmp/xxx]` |
| 😊 表情 | ✅ | ✅ | `[表情:id=123]` |
| 📢 @ 提及 | ✅ | ✅ | `@昵称(QQ:123456)` → `[CQ:at,qq=123]` |

> Agent 看到的是带路径/URL 的结构化标签，不需要额外处理就能拿到文件。

### 📤 CQ 码发送

Agent 直接在回复文本里写 CQ 码，适配器自动解析发送：

```
看看这个 [CQ:image,file=/tmp/test.jpg]
这是你要的文件 [CQ:file,file=/tmp/document.pdf,name=文档.pdf]
```

**支持的 CQ 码：** `[CQ:at]` · `[CQ:image]` · `[CQ:record]` · `[CQ:video]` · `[CQ:file]` · `[CQ:face]` · 以及更多 OneBot v11 标准 CQ 码

---

## 🤖 LLM 工具

v3.1.0 新增两个 LLM 工具，注册到 `napcat` toolset。网关运行时 Agent 可主动调用，直接复用适配器实例的 WS 连接和发送逻辑：

| 工具 | 说明 |
|:-----|:-----|
| `napcat_send_message` | 向群聊/私聊发送消息，支持 CQ 码，复用适配器的合并转发/拆分逻辑 |
| `napcat_call_action` | 调用 OneBot API：群历史消息、私聊历史消息、撤回消息、发文件、群成员列表等 |

工具通过适配器工厂函数存入模块级变量 `_适配器实例`，直接复用已建立的连接，无需通过框架获取。`check_fn` 检查适配器是否已初始化——网关未运行时工具不出现。

---

## ⚙️ 配置

在 `~/.hermes/config.yaml` 中添加：

```yaml
platforms:
  napcat:
    enabled: true
    extra:
      # ── 反向 WS 配置 ──
      reverse_host: "127.0.0.1"          # 监听地址（默认 127.0.0.1，仅本地）。以 / 开头 = Unix socket 路径
      reverse_port: 6700                  # 监听端口（默认 6700）；socket 模式下不用
      access_token: ""                    # 访问令牌（可选，用于认证 NapCat 连接）
      socket_group: ""                    # 仅 socket 模式：把 socket 属组改成该组（如 caddy）
      # reverse_token 可作为 access_token 的别名

      # ── HTTP API（推荐开启）──
      http_api_url: "http://127.0.0.1:5700"  # OneBot HTTP API 地址
      http_api_token: ""                      # HTTP 令牌（默认同 access_token）

      # ── 机器人信息 ──
      bot_self_id: ""                     # 机器人 QQ 号（可选，会从消息中自动学习）

      # ── 媒体下载限制 ──
      # 有 file_size 时超限不下载，只保留 URL
      # 支持 B/KB/MB/GB（不区分大小写）
      download_limits:
        image: 10MB                     # 图片限制（默认 10MB）
        record: 10MB                    # 语音限制（默认 10MB）
        video: 10MB                     # 视频限制（默认 10MB）
        file: 10MB                      # 文件限制（默认 10MB）

      # ── 长消息处理 ──
      merge_forward_threshold: 800      # 群聊超过此字数触发合并转发（默认 800，私聊不触发）
      forward_name: "纳西妲"            # 合并转发显示的名字（默认 纳西妲）

      # ── 引用回复 ──
      reply_text_max_length: 50         # 解析引用回复消息的最大字数，超出截断用省略号（默认 50）
                                         # 截断时会保留完整的媒体标签（如 [图片:file=...]），不会在标签中间截断

      # ── 关键词触发 ──
      # 群聊中匹配这些正则时自动响应（不区分大小写）
      mention_patterns:
        - "纳猫"
        - "帮我"

      # ── 用户白名单 ──
      # 为空或不设置则拒绝所有用户
      # 设置为 "all" 或 "*" 则允许所有用户
      allowed_qq_ids: "123456,789012"   # 逗号分隔、列表、裸数字均可

      # ── 表情回应 ──
      emoji_react: false                # 收到消息后随机回应表情（默认 false）
```

<details>
<summary>🌍 环境变量覆盖</summary>

所有配置项都可通过环境变量覆盖。变量名 = `NAPCAT_` + 配置键名大写。

优先级：环境变量 > config.yaml > 默认值

值的解析：先尝试 JSON（数字、布尔、列表、字典均支持），再识别布尔关键词（`off/false/no` → False，`on/true/yes` → True），其余原样返回字符串。

```bash
# 基本配置
NAPCAT_REVERSE_HOST=127.0.0.1
NAPCAT_REVERSE_PORT=6700
NAPCAT_ACCESS_TOKEN=your_token
NAPCAT_HTTP_API_URL=http://127.0.0.1:5700
NAPCAT_HTTP_API_TOKEN=your_http_token
NAPCAT_BOT_SELF_ID=123456789

# 布尔值（以下写法等价）
NAPCAT_EMOJI_REACT=false
NAPCAT_EMOJI_REACT=off
NAPCAT_EMOJI_REACT=no

# 整数
NAPCAT_MERGE_FORWARD_THRESHOLD=1000

# JSON 字典（复杂值用 JSON）
NAPCAT_DOWNLOAD_LIMITS='{"image":"20MB","video":"100MB"}'

# JSON 数组或逗号分隔
NAPCAT_MENTION_PATTERNS='["纳猫","帮我"]'
NAPCAT_MENTION_PATTERNS=纳猫,帮我

# 白名单
NAPCAT_ALLOWED_QQ_IDS=123456,789012
NAPCAT_ALLOWED_QQ_IDS='[123, 456]'        # JSON 数组也行
NAPCAT_ALLOWED_QQ_IDS=123456              # 单个裸数字也行

# 白名单别名（仅在 config 未设 allowed_qq_ids 时生效）
NAPCAT_ALLOWED_USERS=123456,789012

# 允许所有用户（设置为 true 时跳过白名单）
NAPCAT_ALLOW_ALL_USERS=false

# 群白名单（默认空 = 一个群都不收；写 all 表示不限制群）
NAPCAT_ALLOWED_GROUPS=123456,789012
NAPCAT_ALLOWED_GROUPS='[123, 456]'        # JSON 数组也行

# 群里的斜杠指令是否也要求 @机器人/关键词（默认 true）
NAPCAT_GROUP_COMMAND_REQUIRES_MENTION=true

# 出站安全：额外放行的 OneBot 动作 / CQ 码类型（追加在默认白名单之上）
NAPCAT_ALLOWED_ACTIONS='["upload_group_file"]'    # 默认只放行只读查询动作
NAPCAT_ALLOWED_CQ_TYPES=shake                     # 默认已有 face/at/image/record/video/reply
NAPCAT_ALLOW_AT_ALL=false                         # 是否允许 @全体成员
```
</details>

---

## 🛡️ 出站安全策略

这个插件能让 LLM 直接调 OneBot API，也能在回复里写 CQ 码 —— 两条路都能把**服务器上的文件发出去**。
把它放进自己的小号群无所谓，放进别人的群就必须有闸门。以下是内置的四道（默认全开，不需要额外配置）：

### 1. API 动作白名单（`napcat_call_action`）

默认只放行**只读查询**动作（`get_group_list` / `get_group_info` / `get_msg` / `get_group_msg_history` 等）。

`upload_group_file`（按路径把服务器文件发进群）、`download_file`（按给定 URL 写到给定路径）、
`delete_msg`、`set_group_*`、`send_*` 等一律拒绝，需要运维在 `allowed_actions` 里点名（或写 `all`）。
`get_cookies` / `get_csrf_token` 这类**交出账号凭据**的动作写 `all` 也不放行。

点名是**追加**在默认白名单之上 —— 放开一个动作不会把只读查询一起锁死。

### 2. CQ 码净化

`[CQ:file,file=file:///任意路径]` 与 `upload_group_file` 是同一条外泄路，所以：

- `[CQ:file]` 永不放过；
- `[CQ:image]` / `[CQ:record]` / `[CQ:video]` 里**任何承载路径的参数**（`file` / `url` / `path` /
  `src` / `dest` …）只要指向**本机路径**，就必须过 Hermes 的媒体白名单
  （`gateway.media_delivery_allow_dirs`）—— 复用 Hermes 自己的策略，不另造一套，"哪些文件能出去"只有一个事实来源。
  之所以不能只看 `file`：LLOneBot 发送时取 `url || file`，一个 `file=https://x/a.png,url=/本机文件`
  就能把本机文件塞进 `url`；
- `[CQ:at,qq=all]`（@全体）默认不放行，要放开设 `allow_at_all: true`；
- 未知 CQ 类型一律剥掉（默认拒绝）；**解析不出来的 CQ 形状也剥掉**（fail-closed）——
  `[CQ:file2,...]`、`[CQ:FILE,...]` 这类"净化判不出来、接收端却可能按 `file` 语义处理"的写法原来会被原样放行；
- **重复参数键直接剥掉**：`[CQ:image,file=https://x/a.png,url=https://安全,url=/本机文件]` 里各家接收端取哪个
  键没有统一规定，而我们只能校验我们看到的那一个 → 判不了就不放行；
- **CQ 前缀大小写不敏感**：`[cq:file,...]` 同样会被抓到；
- 任何类型只要带**承载路径的参数**都查白名单（不再只 `image`/`record`/`video` ——
  否则 `allowed_cq_types: all` 时 `[CQ:file2,file=/etc/passwd]` 会溜过去）。

净化的位置是**收口**的：所有出站消息都经过 `_WS发送` / `_HTTP发送` 两个薄封装，净化写在里面 ——
而不是让每条发送路径自己记得调（加固前正是"5 处调了、3 处忘了"，`send_image` 的 URL、
`send_image_file` 的路径、`send_document` 的 caption 都漏了闸门）。
被剥掉的码会打警告日志，不会变成字面量发出去。

另外，**拼进 CQ 参数的动态值会先做 CQ 转义**（图片 URL、本机路径、reply id）：
值里的逗号会让接收端多解析出一个参数键，值里的方括号会凭空长出一个新 CQ 码 ——
这两种都不含 `[CQ:` 子串，净化看不见，只能靠转义挡住（`&#44;` / `&#91;` / `&#93;`，接收端会还原）。

> 走 `MEDIA:` 通道的附件不受影响：那条路由 Hermes 先过媒体白名单，再由 adapter 的
> `send_image_file` / `send_document` 发出。

### 3. 准入（默认全拒）

| 配置 | 默认 | 说明 |
|---|---|---|
| `allowed_qq_ids` | 空 = 谁都不收 | 谁能触发机器人 |
| `allowed_group_ids` | 空 = 一个群都不收 | 机器人能在哪些群工作 |
| `group_command_requires_mention` | `true` | 群里的 `/xxx` 指令是否也要求 @机器人/关键词 |

群白名单默认空是个**行为变更**：升级后不配置就收不到任何群消息（启动日志会明确提示）。
要恢复旧行为可以写 `allowed_group_ids: all`，但那等于任何群都能用 —— 放进别人群时不建议。

另外 `napcat_send_message` 指定目标时也会校验目标在白名单内，否则被允许的人（或提示注入）
可以指挥机器人把消息发到白名单之外的任意群 / 任意 QQ 用户。

**核心发送路径同样校验**：`send()` / `send_image()` / `send_image_file()` / `send_voice()` /
`send_document()` 全部经过 `_解析投递目标()`，那里统一做一次目标白名单校验；`napcat_call_action`
放行了的动作（如 `send_group_msg`）其参数里的 `group_id` / `user_id` 也一并校验（**读取类动作也不例外** ——
否则白名单群里的成员就能让机器人把别的群 / 别人的私聊历史读回来）；发消息类动作的 `message` /
`messages` 载荷同样要过 CQ 净化，命中禁止项就**拒绝整个调用**并把原因回给模型。

> 取值阶梯（与核心发送路径一致）：**主键环境变量 → 插件配置 → 别名环境变量**。
> 所以用 `NAPCAT_ALLOWED_GROUP_IDS` 收窄时，工具层的那条路也会同步收窄。

> 启动时会读 `gateway.strict`，未开启则打一条醒目提示 —— 非严格模式下的媒体白名单几乎不设防
> （除凭据目录黑名单外都能出站），而本插件是直接委托给它的。

> 与准入同一姿态：**白名单为空时出站也一律拒绝**（fail-closed）。空名单本来就收不到任何群消息，
> 谈不上"本来能回"；要放开必须显式写 `all`。

### 传输层

反向 WS 绑**非回环地址**时**必须**同时设置 `access_token`，否则拒绝启动 —— 否则任何能访问该端口的人
都能伪造 QQ 事件（冒充任意用户/群，直接绕过用户白名单）、伪造 API 响应。

---

## 部署与网络暴露

插件只有反向 WS 一种模式：插件监听，OneBot 实现主动连过来。默认绑 `127.0.0.1:6700`。LLOneBot 跑在另一台机器上时，这段连接要穿过公网，暴露面取决于你把监听放在哪里。

### 监听位置

| `reverse_host` | 谁能连上 | 说明 |
|---|---|---|
| `127.0.0.1`（默认） | 本机任何进程 | 不占公网端口。本机用户之间没有隔离，只能靠令牌区分 |
| `0.0.0.0` 或公网地址 | 任何能访问该端口的人 | 必须同时设 `access_token`，否则插件拒绝启动 |
| `/dev/shm/napcat.sock` | 只有文件属主与属组 | 不占端口，不经过 TCP 栈。访问控制由内核按文件权限判定 |

### 优先选 Unix socket 的原因

socket 文件把访问控制交给内核，而不是交给一个令牌。插件启动时把权限设成 `0660`（不依赖 umask，否则默认是 `0755`，本机谁都能连），再用 `socket_group` 把属组交给运行反向代理的那个用户。别的用户知道路径也连不上。

它也省掉一个端口：反向代理直接连 socket，插件侧不监听任何 TCP 地址，`ss -ltnp` 里看不到它。

### socket 该放在哪里

`/dev/shm` 是 tmpfs，内容全在内存里。socket 文件本身不落盘，内核也不为它保留磁盘块，所以 `bind` 和 `unlink` 不产生文件系统 I/O。

两个实测出来的约束决定了它不能放别处：

- 不能放 `/tmp` 或 `/var/tmp`。Caddy 的服务单元带 `PrivateTmp=true`，它有独立的临时目录命名空间，看不到你放在 `/tmp` 里的 socket。
- 不能放家目录。Caddy 以 `caddy` 用户运行；家目录如果是 `0700`（本机 `/home/leemina` 就是），它连路径都走不进去。

说清楚一点：对一个聊天机器人来说，tmpfs 相对磁盘目录省下的那点 I/O 量不出来。选 `/dev/shm` 是因为上面两条把 `/tmp` 和家目录排除了，而它既在内存里，又对所有进程可见。

### Caddy 反代

```caddyfile
# 放在现有站点块里,末尾的 fallback handle 之前
@napcat host napcat.example.com
handle @napcat {
	@不是设备 not remote_ip 203.0.113.45
	respond @不是设备 "forbidden" 403

	reverse_proxy unix//dev/shm/napcat.sock
}
```

`unix//<路径>` 承载 WebSocket 的 Upgrade，可以直接用。`unix+h2c//<路径>` 不行：实测返回 502，Caddy 日志写的是 `http2: invalid Upgrade request header: ["websocket"]`。那个传输是给 HTTP/2 型后端（gRPC 之类）用的。

反代不会绕过插件侧的鉴权。没带令牌的连接照样被插件拒掉，这一条也实测过。

### 配置

插件侧：

```yaml
reverse_host: /dev/shm/napcat.sock
socket_group: caddy
access_token: ACCESS_TOKEN
```

运行 Hermes 的用户要先进入 `caddy` 组，否则插件改不了 socket 属组（会打一条告警，Caddy 也连不上）：

```bash
sudo usermod -aG caddy HERMES_USER
```

两个占位符：`HERMES_USER` 是运行 Hermes 的账号，`ACCESS_TOKEN` 是两端填同一个的随机串。

客户端侧把反向 WS 地址指向 `wss://napcat.example.com/`，令牌填同一个值。

### 安全边界

- 这条链路的访问控制就是 socket 权限。忘了配 `socket_group` 时，插件打告警，Caddy 连不上。
- 插件的 WS 服务端不支持 TLS。公网那一段必须由反向代理终止 TLS（Caddy 自动签证书）。不要用明文 `ws://` 穿过公网，也不要把插件端口直接暴露出去。
- `access_token` 在 socket 模式下不强制，但建议设：它仍然能拦住任何连到反代却没带令牌的人。
- SELinux 不参与这条链路的判定。本机策略是 enforcing，但 caddy 和 Hermes 都跑在 unconfined 域，类型强制管不到它们。要让 SELinux 覆盖它，得给 caddy 单独写策略。

---

## 🔗 NapCat 端配置

在 NapCat 配置文件中设置反向 WS 连接：

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

> 如果配置了 `access_token`，NapCat 端也需要设置相同的 token。

---

## 📟 启动信息

Hermes 默认日志级别为 WARNING，`logger.info()` 用户看不到，容易误以为插件没加载。因此不频繁的重要 info 日志（连接/断开/启动/异常）同时 `print()` 到终端；频繁的（收发消息）不加 print。

启动时会输出配置摘要，便于排查：

```
[NapCat插件] 反向WS模式启动，等待 NapCat 连接 端口 6700
[NapCat插件] HTTP接口已启用: http://127.0.0.1:5700
[NapCat插件] 配置: 监听地址=127.0.0.1 端口=6700 令牌=已设置
[NapCat插件] 配置: HTTP接口=已启用 表情回应=未启用
[NapCat插件] 配置: 机器人QQ号=未设置(自动学习) 合并转发阈值=800 引用文本最大字数=50
[NapCat插件] 配置: 允许所有用户=否 白名单用户(2): 123456, 789012
[NapCat插件] 配置: 群白名单(1): 123456
[NapCat插件] 配置: 群指令需@/关键词=是
[NapCat插件] 配置: 下载限制={'image': '10MB', 'record': '10MB', 'video': '10MB', 'file': '10MB'}
[NapCat插件] 配置: 关键词触发模式数=2
```

---

## 🗑️ 卸载

```bash
rm -rf ~/.hermes/plugins/napcat
hermes gateway restart
```

---

## 🧪 测试

安全策略与发送链路有回归测试（断言式，全绿时退出码 0）：

```bash
python tests/test_ws_hardening.py        # 反向 WS：绑定性 / 认证顺序 / 连接顶替
python tests/test_action_policy.py       # API 动作白名单 + 路径校验
python tests/test_cq_sanitize.py         # CQ 码净化（端到端打真 send()）
python tests/test_access_control.py      # 群/用户白名单、群指令触发、出站目标
python tests/test_send_robustness.py     # 脏数据不炸 / 长短消息行为一致
python tests/test_inbound_formats.py     # 入站 message 的段数组 / CQ 字符串两种格式
python tests/test_capability_fallback.py # 扩展动作缺失时的能力探测与优雅降级
python tests/test_media_download_gate.py # 媒体下载的大小闸门（含无 file_size 的情形）
python tests/test_self_id_handshake.py   # 握手头 X-Self-ID（含大小写不敏感、未授权不写入）
python tests/test_bot_qq_learning.py     # 机器人 QQ 号的学习来源与 @ 触发
python tests/test_auth_edge_cases.py     # 认证边界：非 ASCII 令牌、URL 令牌、无头
```

需要一个装了 Hermes 依赖的 python（`websockets`、`gateway` 等）。脚本会自动在
`~/.hermes/installs/*/environments/*/workspace` 里找，找不到就用环境变量
`HERMES_WORKSPACE` 指定。

> ⚠️ `hermes plugins validate` 请在**插件目录之外**用绝对路径跑：
> `cd ~ && hermes plugins validate /path/to/hermes-qq-onebot`。
> 在插件目录里跑时探针子进程的 `sys.path[0]` 就是本目录，`import tools` 会命中本插件的
> `tools.py` 而不是 Hermes 的 `tools/` 包，capability probe 会报
> `No module named 'tools.xxx'; 'tools' is not a package` —— 那是假失败，不是插件的问题。

---

## 🧩 作为 Hermes 插件

本项目是一个 Hermes Agent 平台适配器插件，注册到 Hermes 插件系统后自动生效：

- **插件名：** `napcat`
- **类型：** `platform`
- **注册平台：** `napcat` (NapCat QQ)
- **依赖：** `websockets`

插件入口自动注册平台适配器到 Hermes 网关，无需手动干预。

---

<details>
<summary><b>📖 与 v2.x 旧版的差异（点击展开）</b></summary>

v3.0.0 是对 v2.1.x 的重构升级，功能逻辑一致，以下为详细差异：

### 代码结构

| 项目 | v2.1.x (旧) | v3.0.0 (新) |
|------|-------------|-------------|
| 文件组织 | 单体文件 `napcat_adapter.py` (1530行) | 模块化拆分为 5 个文件 |
| WS 服务端 | 内嵌在主文件 | 独立 `ws.py`（WS 类） |
| HTTP 调用器 | 内嵌在适配器中 | 独立 `napcat_http.py`（NapcatHttp 类） |
| 工具函数 | 内嵌在主文件 | 独立 `tools.py`，有 `__all__` 导出列表 |
| API 边界 | 无，所有代码互相依赖 | 清晰的模块边界 |

### 配置类型校验

- **旧**：`extra_config.get()` + `os.getenv()` 简单回退，无类型检查，错误输入静默通过
- **新**：`获取配置()` 辅助函数，每个字段做 `isinstance` 类型校验，不合法时抛 `ValueError` 并给出详细错误信息

### 环境变量读取

- **旧**：直接从 `os.getenv()` 取值，只处理字符串，环境变量和配置文件两套独立逻辑
- **新**：统一走 `获取配置()` 函数，支持 JSON 解析 + 布尔关键词识别 + 字符串回退

### 安全性

| 项目 | v2.1.x | v3.0.0 |
|------|--------|--------|
| 默认监听地址 | `0.0.0.0`（所有接口） | `127.0.0.1`（仅本地） |
| 白名单为空 | 隐式允许所有用户 | 拒绝所有用户，启动时打印警告 |
| 允许所有用户 | 无显式机制 | 需设置 `"all"` 或 `"*"` 才放行 |

### 其他变更

- **私聊会话ID**：`napcat_{用户ID}` → `napcat_private_{用户ID}`
- **全局状态**：移除 `_全局接口调用器` 全局变量，WS 实例由适配器持有
- **WS API 超时**：60s → 120s（适配大文件获取等慢操作）
- **WS 事件过滤**：`post_type == "meta"` → `"meta_event"`（OneBot v11 标准字段名）
- **白名单解析**：新增 `int`/`float` 支持（YAML 裸数字自动转字符串）
- **HTTP API 令牌**：新增 `http_api_token`，默认回退到 `access_token`
- **启动信息**：不频繁的重要 info 日志同时 `print()` 到终端（Hermes 默认 WARNING 级，info 不可见）
- **消息段解析**：`构建完整文本()` 拆分为 `_格式化媒体标签()`、`_格式化文件标签()`、`_追加详细艾特文本()`
- **show_qq_id**：移除该选项，显示名称固定为 `昵称(QQ号)` 格式
- **配置项别名**：`reverse_token` 作为 `access_token` 别名；`NAPCAT_ALLOWED_USERS` 作为白名单备用环境变量

</details>

---

## 📋 更新日志

### v3.1.0

- 新增 LLM 工具 `napcat_send_message`：Agent 可主动向群聊/私聊发送消息，复用适配器的 CQ 码处理、合并转发、长消息拆分逻辑
- 新增 LLM 工具 `napcat_call_action`：调用 OneBot API（群历史消息、私聊历史消息、撤回消息、发文件、群成员列表等）
- 工具直接复用适配器实例的 WS 连接和 HTTP 调用器，通过工厂函数存入模块级变量 `_适配器实例`，无需通过框架获取
- `check_fn` 检查适配器是否已初始化——网关未运行时工具不出现

### v3.0.0

- 重构适配器架构，模块化拆分为 adapter/main/ws/napcat_http/tools 五个文件
- 反向 WS 监听地址默认 127.0.0.1（仅本地），白名单为空时拒绝所有用户
- 配置类型校验、环境变量 JSON 解析、合并转发阈值、引用文本截断等改进

MIT License © [懒大猫](https://github.com/landamao)
