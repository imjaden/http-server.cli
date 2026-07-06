<p align="center">
  <a href="README.zh.md">🇨🇳</a> · <a href="README.md">🇬🇧</a>
</p>

<h1 align="center">
  <svg viewBox="0 0 16 16" width="28" height="28" style="vertical-align:middle;margin-right:6px;"><circle cx="8" cy="8" r="7.5" fill="#e0e0e0"/><text x="8" y="11.5" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="900" font-size="9" fill="#333">hs</text></svg>
  http-server-cli
</h1>

> 忘记端口，只管预览 — Forget ports. Just preview.
>
> 基于 `python3 -m http.server`，零外部依赖。项目目录下 `hs . -o` 一键预览。

- [x] **零外部依赖** — 仅需 Python 3.7+，macOS/Linux/Windows（`pip install http-server-cli`）
- [x] **自动端口 + 智能首页** — 默认 8080，冲突自动递增；无 index.html 时自动打开最近修改的 html；支持 `-i` 指定（`hs . -o`）
- [x] **项目管理** — 追踪路径↔端口映射、监控 CPU/内存、JSON 输出（`hs list`）
- [x] **多种启动模式** — daemon 后台或 foreground 前台（`-d`/`-f`）
- [x] **Web 仪表盘** — `hs dashboard -o` 图形化管理（中英文切换 / 60s 倒计时 / Kill All / 异常捕捉）
- [x] **AI Agent 集成** — `hs mcp` MCP Server（SSE/stdio，6 个工具），托管服务隔离管理

## 为什么用 `hs`

同时开发多个前端项目时，总在记 "A 用了几号端口" 和 "8080 被谁占了" 之间切换。

`hs` 把**启动 → 追踪 → 列出 → 关闭**闭环了。

## 对比一览

| 场景 | 以前 | 用 `hs` |
|:---------|:-----|:--------|
| 启动服务 | `python3 -m http.server 8080` + 手动开浏览器 | `hs . -o` — 自动找空闲端口，打开浏览器 |
| 查看服务 | `lsof -i :8080`，再 `ps` 看路径 | `hs list` |
| 切换项目 | 先关旧的，再开新的（或冲突） | `hs ../project-b` |
| 关掉服务 | `lsof` 查 PID → `kill` | `hs kill 8080` |

## 安装

```bash
pip install http-server-cli
# 或：pip install --upgrade http-server-cli
```

验证：
```
hs version     # → http-server-cli v1.0.x
hs . -o        # 当前目录启动 + 打开浏览器
```

## 用法

### 日常三件事

```bash
# 1. 到项目下无脑预览
cd ~/project-alpha
hs . -o                     # 自动找端口 + 打开浏览器

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

### Dashboard

| 命令 | 说明 |
|:--------|:------------|
| `hs dashboard [-p PORT] [-o] [--json]` | Web 仪表盘（默认 8180） |
| `hs dashboard stop|status|restart|help` | 子命令 |

### MCP（AI Agent 集成）

| 命令 | 说明 |
|:--------|:------------|
| `hs mcp [--transport stdio|sse] [--port PORT]` | MCP Server |
| `hs mcp stop|status|restart|help` | 子命令 |

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
~/.http-server-cli/
├── config.json            # 默认端口/域名配置
├── registry.json          # port → {path, pid, domain, started_at, index_page}
├── registry-managed.json  # 基础设施服务（dashboard、MCP SSE）
└── logs/{port}.log        # http.server 日志
```

## 本地开发

```bash
git clone git@github.com:imjaden/http-server-cli.git
cd http-server-cli
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
| **`http-server-cli`** | **✅** | **✅** | **✅** | **✅** | **✅** | **✅** |
