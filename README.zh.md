<p align="center">
  <a href="README.zh.md">🇨🇳</a> · <a href="README.md">🇬🇧</a>
</p>

<h1 align="center">
  <svg viewBox="0 0 16 16" width="28" height="28" style="vertical-align:middle;margin-right:6px;"><circle cx="8" cy="8" r="7.5" fill="#e0e0e0"/><text x="8" y="11.5" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="900" font-size="9" fill="#333">hs</text></svg>
  http-server
</h1>

<p align="center">
  <a href="https://github.com/imjaden/http-server.cli"><img src="https://github.com/favicon.ico" width="16" height="16" alt="GitHub"> GitHub</a>
  <span> · </span>
  <a href="https://pypi.org/project/http-server-cli"><img src="https://pypi.org/static/images/favicon.35549fe8.ico" width="16" height="16" alt="PyPI"> PyPI</a>
</p>

> 忘记端口，只管预览 — Forget ports. Just preview.
>
> 基于 `python3 -m http.server`，零外部依赖。项目目录下 `hs -o` 一键预览。
>
> hs 是独立工具，与 npm 的 http-server 包无关。

- [x] **零外部依赖** — 仅需 Python 3.7+，macOS/Linux/Windows（`pip install http-server-cli`）
- [x] **自动端口 + 智能首页** — 默认 8080，冲突自动递增；无 index.html 时自动打开最近修改的 html；支持 `-i` 指定（`hs -o`）
- [x] **项目管理** — 追踪路径↔端口映射、监控 CPU/内存、JSON 输出（`hs list`）
- [x] **多种启动模式** — daemon 后台或 foreground 前台（`-d`/`-f`）
- [x] **Web 仪表盘** — `hs dashboard -o` 图形化管理（中英文切换 / 60s 倒计时 / Kill All / 异常捕捉）
- [x] **AI Agent 集成** — `hs mcp` MCP Server（SSE/stdio，11 工具 + 3 Resources），`hs prompt` 使用说明、`hs mcp --config` 一行接入

## 为什么用 `hs`

同时开发多个前端项目时，总在记 "A 用了几号端口" 和 "8080 被谁占了" 之间切换。

`hs` 把**启动 → 追踪 → 列出 → 关闭**闭环了。

- 启动服务：`hs -o` — 自动找空闲端口、打开浏览器（替代 `python3 -m http.server 8080` + 手动开）
- 查看服务：`hs list`（替代 `lsof -i :8080` + `ps`）
- 切换项目：`hs ../project-b`（无需先关旧的）
- 关掉服务：`hs kill 8080`（替代 `lsof` 查 PID → `kill`）

## AI 互通

`hs` 与 AI agent 有三条互通通道：**文档、数据、一行接入**。

### 1. 文档 — `hs prompt`

```bash
hs prompt                # 列出全部 skills（name + description）
hs prompt hs-cli         # 输出单篇完整使用说明
hs prompt hs-mcp --brief # 摘要
hs prompt --json         # 机器可读信封
```

内置 6 篇 skills：`hs-cli` / `hs-bookmark` / `hs-mcp` / `hs-dashboard` / `ai-interchange` / `hs-web`。

### 2. 数据与操作 — MCP Server

```bash
hs mcp                    # 后台 SSE → http://127.0.0.1:8181/sse
hs mcp --transport stdio  # 前台 stdio 模式（供 Claude Code / Cursor / Hermes）
hs mcp stop|status|restart
```

11 个工具（6 管理：`hs_list` / `status` / `start` / `kill` / `kill_all` / `config`；5 数据：`hs_bookmark_list` / `add` / `remove`、`hs_history`、`hs_search`）+ 3 个只读 Resources（`hs://registry` / `hs://bookmarks` / `hs://config`）。零外部依赖 — 纯标准库。

### 3. 一行接入 — `hs mcp --config`

```bash
hs mcp --config
```

输出可直接粘贴到 Claude Code / Cursor / Hermes 的 `mcpServers` 配置片段：

```yaml
mcpServers:
  hs:
    command: hs
    args: ["mcp", "--transport", "stdio"]
    transport: stdio
```

粘贴到 AI 工具的 MCP 配置并重启，agent 即可列出服务、读取书签/历史、搜索运行实例并执行管理操作。

> AI agent 建议先 `hs prompt hs-cli` — 零依赖拿完整用法，不用猜参数。

## 安装

```bash
pip install http-server-cli
# 或：pip install --upgrade http-server-cli
```

验证：
```
hs version     # → http-server v1.2.x
hs -o        # 当前目录启动 + 打开浏览器
```

## 用法

### 日常三件事

```bash
# 1. 到项目下无脑预览
cd ~/project-alpha
hs -o                     # 自动找端口 + 打开浏览器

# 2. 看看都起了哪些
hs list
# ✅  http://localhost:8080   →  ~/project-alpha
# ✅  http://localhost:8081   →  ~/project-beta  (daemon)

# 3. 关掉不需要的
hs kill 8080                # 按端口
hs kill ~/project-alpha     # 按路径
hs kill-all                 # 一键全关
```

### 启动

| 命令 | 说明 |
|:--------|:------------|
| `hs . [-o] [-d] [-f]` | 当前目录，自动找空闲端口 |
| `hs /path [-o] [-d] [-f]` | 指定目录 |
| `hs . -i app.html [-o]` | 指定首页文件 |
| `hs . -i './snapshots/*.html' [-o]` | 通配符 → 取最近修改的文件 |
| `hs /path/to/file.html [-o]` | HTML 文件 → 自动提取目录 + 设 index |
| `hs /path/snapshots/*.html [-o]` | 路径通配符 → 取最近文件 |
| `hs start [path] [-o] [-d] [-f] [-i <file>]` | `hs .` 的完整形式 |

### 查看

| 命令 | 说明 |
|:--------|:------------|
| `hs list` | 列出运行中的服务（仅存活实例） |
| `hs list --port` | 仅端口号 |
| `hs list --path` | 仅路径 |
| `hs list --short` | `端口:路径` 格式 |
| `hs list --json` | JSON 输出 |
| `hs search <keyword> [--json]` | 按端口或路径搜索 |
| `hs status <port|path> [--json]` | 单个服务状态（CPU/内存/日志） |

### 关闭

| 命令 | 说明 |
|:--------|:------------|
| `hs kill 8080` | 按端口 |
| `hs kill ~/project` | 按路径 |
| `hs kill /path/to/file.html` | HTML 文件 → 自动解析到父目录 |
| `hs kill /path/*.html` | 通配符 → 取最近文件 |
| `hs kill-all` | 关闭所有用户服务 |
| `hs kill-all --json` | JSON 输出 |

### 书签

| 命令 | 说明 |
|:--------|:------------|
| `hs bookmark add <name> [path] [-i index] [--force]` | 注册书签（path 默认当前目录） |
| `hs bookmark update <name> [path] [-i index]` | 更新书签路径或首页 |
| `hs bookmark list` | 列出所有书签 |
| `hs bookmark show <name>` | 查看书签详情 |
| `hs bookmark remove <name>` | 删除书签 |
| `hs <name> [-o]` | 从书签启动服务 |
| `hs kill <name>` | 按书签名关闭服务 |

### Web 服务注册

注册任意 web 服务启动命令（跨项目）到名称，快速启动/访问:

| 命令 | 说明 |
|:--------|:------------|
| `hs web add <name> --cmd '<cmd>' [--url <url>] [--open cmd\|url\|both\|none] [--domain]` | 注册服务（open 默认 url） |
| `hs web update <name> [--cmd] [--url] [--open] [--domain\|--no-domain]` | 更新服务（`--url ''` / `--no-domain` 清除） |
| `hs web list [--json]` | 列出所有注册 |
| `hs web show <name>` / `hs web remove <name>` | 详情 / 删除 |
| `hs web <name> [--no-probe]` | 执行：url 可达→直接打开（幂等）；否则执行启动命令 |
| `web <name>` | 全局薄壳（`~/.local/bin/web`）转发到 hs web |

```bash
hs web add daily.checker --cmd 'dk server start --daemon --open' --url http://127.0.0.1:5001
hs web daily.checker     # 5001 存活→直接打开；否则启动
hs web jaden.tech        # 动态端口：无 url → 直接透传
hs web jaden.tech --no-probe   # 跳过探测，强制重启
hs web add dk --cmd 'dk server start --daemon --open' --domain   # 注入 config.domain → ... --domain "jaden.local"
```

> `services.json` 独立于 bookmarks.json：bookmark 把名称映射到静态目录；`hs web` 把名称映射到任意命令。
> 推广：`hs prompt hs-web` — 跨项目 web 服务注册指南（daily-checker / llm-radar / html-gen / jaden.tech 等模块接入）。

### Dashboard

| 命令 | 说明 |
|:--------|:------------|
| `hs dashboard [-p PORT] [-o] [--json]` | Web 仪表盘（默认 8180） |
| `hs dashboard stop\|status\|restart\|help` | 子命令 |

> 托管服务（dashboard、MCP SSE）登记在 `registry-managed.json`；`hs kill-all` 不会关闭它们。

### MCP（AI Agent 集成）

| 命令 | 说明 |
|:--------|:------------|
| `hs mcp [--transport stdio|sse] [--port PORT]` | MCP Server |
| `hs mcp stop|status|restart|help` | 子命令 |
| `hs mcp --config` | 输出 `mcpServers` 配置片段（见 AI 互通） |
| `hs prompt [<skill>]` | 输出 skills/ 使用说明（列表 / 详情 / --brief / --json） |

### 历史与配置

| 命令 | 说明 |
|:--------|:------------|
| `hs history [--json]` | 查看历史记录（排除临时目录） |
| `hs config [--json]` | 显示配置 |
| `hs set port|domain <value>` | 修改配置 |
| `hs version [--json]` | 版本号 |
| `hs help` | 帮助 |

### 小贴士

- **`hs`** 不带参数 = `hs start .`（当前目录启动）
- **`hs . -i app.html`**：以 `app.html` 为首页

## 数据目录

```
~/.http-server.cli/
├── config.json            # 默认端口/域名配置
├── registry.json          # port → {path, pid, domain, started_at, index_page}
├── registry-managed.json  # 基础设施服务（dashboard、MCP SSE）
└── logs/{port}.log        # http.server 日志
```

## 本地开发

```bash
git clone git@github.com:imjaden/http-server.cli.git
cd http-server.cli
pip install -e .
python3 -m pytest tests/
```

## 这是在造轮子么

| 工具 | 启动服务 | 自动分配端口 | 追踪项目↔端口 | 列出所有 | 按名杀死 | 打开浏览器 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `python3 -m http.server` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `http-server` (npm) | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `serve` (npm) | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `live-server` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `portless` (npm) | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `kill-port-cli` (npm) | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| `lsof` / `netstat` | ❌ | ❌ | ❌ | 手动 | 手动 | ❌ |
| **`http-server`** | **✅** | **✅** | **✅** | **✅** | **✅** | **✅** |
