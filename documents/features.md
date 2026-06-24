# hs — http-server-cli 功能文档

> 忘记端口，只管预览。基于 `python3 -m http.server`，零外部依赖。
>
> 项目: https://github.com/imjaden/http-server-cli

---

## 一、核心功能

所有核心 CLI 命令均支持 `--json` 标志，以统一 JSON 信封结构输出结构化数据，适合 API / MCP 消费。

### 1.1 一键预览 — `hs . -o`

- 无参 `hs` 默认等价于 `hs start .`
- `hs . -o` 先检查 registry 中该路径是否已注册且存活：
  - 已存活 → 直接打开浏览器，显示已有服务的资源占用和运行时长
  - 未注册/已停止 → 从默认端口（config.port，默认 8080）开始递增查找空闲端口，启动后自动打开浏览器
- `-d` / `--daemon`：后台守护模式，启动后 tail -f 日志，Ctrl+C 仅停止日志查看，服务继续运行
- `-f` / `--foreground`：前台运行模式，Ctrl+C 终止服务并清理 registry
- `-i` / `--index <file>`：指定自定义首页文件（如 `hs . -i app.html`）
- 端口冲突时自动递增查找空闲端口，直至 `MAX_PORT`（默认 65535）
- 启动信息展示：URL、路径、PID、CPU、内存、运行时长、日志文件路径

### 1.2 启动服务 — `hs start [path]`

- `hs start [path]` 显式启动服务，参数语义与快捷方式相同
- 支持 `.`、`/absolute/path`、`~/relative/path` 等多种路径格式
- 路径不存在/非目录时输出错误提示
- 支持三种运行模式：普通（无额外行为）、daemon、foreground
- 持久化注册：自动写入 `registry.json`，记录 port、path、pid、domain、mode、started_at、index_page

### 1.3 列出服务 — `hs list`

- 列出所有运行中的 HTTP 服务，按端口排序
- 每个服务显示：⚠ URL（域名:端口）、📁 路径、🔧 PID、启动时间、📊 CPU/内存/时长
- 当前目录服务标记 📍（current）
- Daemon 模式标记 🖥，Foreground 模式标记 ⌨
- 已停止服务标记 ❌
- **合并展示基础设施服务**：在用户服务列表之后，单独显示 🔧 基础设施服务（dashboard、MCP SSE 等），来源为 `registry-managed.json`
- 无服务运行显示 "没有正在运行的 HTTP 服务" + 使用提示
- `--json`：返回 `{ count, servers[], managed[] }`，每个服务含 url、port、path、pid、alive、mode、started_at、stats(cpu/memory/memory_percent)、duration

### 1.4 查询状态 — `hs status [port|path]`

- 按端口号查询：`hs status 8080`
- 按路径查询：`hs status ~/my-site`
- 无参数时等价于 `hs list`
- 端口被非本工具进程占用时，显示占用进程信息（USER、CMD、kill 命令）
- 输出：URL、路径、PID、进程状态、端口占用状态、运行模式、启动时间
- `--json`：返回 `{ found, url, port, path, pid, alive, port_active, mode, started_at, stats, duration }`

### 1.5 关闭服务 — `hs kill` / `hs kill-all`

- **`hs kill <port>`**：按端口号关闭服务
- **`hs kill <path>`**：按路径关闭服务（如 `hs kill ~/project-alpha`）
- 终止逻辑：先 SIGTERM 发送到进程组（`killpg`），0.5s 后未响应则 SIGKILL
- 清理：从 registry 移除记录，删除对应日志文件 `~/.http-server-cli/logs/{port}.log`
- 未注册时提示 "端口/路径未注册"
- **`hs kill-all`**：一键关闭所有用户服务（不影响基础设施服务）
- 支持 `killall` 作为 `kill-all` 的别名
- `--json`：返回 `{ port, path, pid, killed, log_removed }`（kill-all 返回 `{ total, killed, entries[] }`）

### 1.6 配置管理 — `hs config` / `hs set`

- **`hs config`**：查看当前配置（默认端口、绑定域名、数据目录路径）
- **`hs set port <value>`**：修改默认端口（范围 1024-65535），即时持久化
- **`hs set domain <value>`**：修改绑定域名（如 `0.0.0.0`），即时持久化
- `--json`：返回 `{ port, domain, data_dir }`（set 返回 `{ key, old_value, new_value }`）
- 未知配置项提示支持 `port, domain`

### 1.7 结构化 JSON 输出

- 所有命令追加 `--json` 均可获得结构化 JSON 输出
- 统一信封格式：`{ "success": true/false, "command": "...", "data": {...}, "error": "..." }`
- 专为 API / MCP 消费设计，方便 AI Agent 解析
- 版本查询也支持 `hs version --json`

### 1.8 其他命令

- **`hs version`**：显示版本号（如 `http-server-cli v1.0.7`）
- **`hs help`**：显示所有命令帮助文本，含用法示例

---

## 二、Dashboard 面板 — `hs dashboard`

Web 图形化管理界面，基于 Python 标准库 `http.server` 实现，零外部依赖。

### 2.1 启动方式

```bash
hs dashboard              # 默认端口 8180，前台运行
hs dashboard -p 9200      # 指定端口
hs dashboard -o           # 启动并自动打开浏览器
hs dashboard -d           # 后台守护模式
hs dashboard --json       # 一次性查询模式（非 Web 模式）
```

### 2.2 REST API 接口

| 端点 | 方法 | 说明 |
|:-----|:-----|:------|
| `/` | GET | 返回 Web UI 页面（内联 HTML/CSS/JS） |
| `/api/servers` | GET | 获取所有服务列表（含用户服务 + 基础设施服务） |
| `/api/status/{port}` | GET | 查询单个服务状态 |
| `/api/kill/{port}` | POST | 关闭指定端口服务（SIGTERM → SIGKILL，清理 registry + 日志） |
| `/api/kill-all` | POST | 关闭所有用户服务 |
| `/api/restart/{port}` | POST | 重启指定端口服务 |

### 2.3 Web UI 特性

- **深色主题**（GitHub Dark 风格）：`#0d1117` 背景底色
- **响应式布局**，最大宽度 1200px
- **统计卡片**：运行中（绿色）、已停止（红色）、总端口（蓝色）
- **一键关闭全部**：带确认弹窗，按钮禁用防重复
- **服务表格**：URL、路径、PID、状态徽章（🟢 运行中 / 🔴 已停止）、CPU、内存、操作按钮
- **基础设施服务**：在用户服务上方单独显示 🔧 基础设施服务行
- **实时刷新**：每 5 秒自动轮询 `/api/servers` 更新状态
- **Toast 通知**：操作后显示成功/失败提示，3 秒自动消失
- **空状态**：无服务时显示 "没有正在运行的 HTTP 服务" + `hs . -o` 使用提示

### 2.4 重复运行检测

- 启动 dashboard 时检测该端口是否已运行 dashboard 实例
- 如果已运行则展示状态信息并退出，避免端口冲突

### 2.5 日志与注册

- Dashboard 服务注册到 `registry-managed.json`（name: `dashboard`）
- 在 `hs list` 中作为基础设施服务展示
- `hs kill-all` 不影响 dashboard

---

## 三、MCP Server — `hs mcp`

基于 Model Context Protocol (MCP) 的 AI Agent 集成层，支持 JSON-RPC 2.0 协议。

### 3.1 传输模式

#### SSE 模式（默认）

```bash
hs mcp                              # 默认 SSE + daemon，端口 8181
hs mcp --transport sse -p 8182      # 指定端口
```

- 通过 HTTP SSE (Server-Sent Events) 传输 JSON-RPC 消息
- 自动后台守护模式启动（不占用终端）
- SSE endpoint: `http://127.0.0.1:{port}/sse`
- POST endpoint: `http://127.0.0.1:{port}/messages`
- 注册到 `registry-managed.json`（name: `mcp`，type: `sse`）
- 重复运行检测：如果 MCP 已在运行，显示状态信息并退出

#### Stdio 模式

```bash
hs mcp --transport stdio
```

- 通过标准输入/输出流传输 JSON-RPC 消息
- 适合嵌入到 AI Agent 的子进程中（如 Claude Code、Cursor）
- 不注册到 managed registry
- 从 stdin 读取请求，响应写到 stdout

### 3.2 协议实现

- 协议版本: `2025-03-26`
- 基础方法：`initialize`（握手）、`notifications/initialized`、`tools/list`、`tools/call`
- 工具调用通过子进程执行 `hs` CLI 命令 + `--json`，获取结构化结果
- hs_start 工具自动注入 `--daemon` 参数，确保服务后台运行

### 3.3 暴露的 6 个工具

| 工具名 | 描述 | 参数 |
|:-------|:-----|:------|
| `hs_list` | 列出所有运行中的 HTTP 服务 | 无参数 |
| `hs_status` | 查询单个 HTTP 服务状态 | `port: number`（必填） |
| `hs_start` | 启动 HTTP 服务（默认 daemon 模式） | `path: string`（可选，默认当前目录）、`open: boolean`、`index: string` |
| `hs_kill` | 关闭指定端口或路径的 HTTP 服务 | `port: number` 或 `path: string`（二选一） |
| `hs_kill_all` | 关闭所有运行中的 HTTP 服务 | 无参数 |
| `hs_config` | 显示当前 hs 配置 | 无参数 |

### 3.4 工具执行流程

1. AI Agent 调用 `tools/call`，传入工具名和参数
2. MCP Server 将参数映射为 `hs` CLI 参数（如 `hs_list` → `hs list --json`）
3. 通过 `subprocess.run` 执行 `hs` CLI，附加 `--json` 标志
4. 解析 stdout 中的 JSON 行，返回结构化结果
5. 工具调用失败时以 `isError: true` 方式返回

---

## 四、架构设计

### 4.1 零外部依赖

- 核心依赖：仅需 Python 3.7+ 标准库
- 系统工具（macOS）：`lsof`（用于端口进程查询）、`open`（用于打开浏览器）
- 跨平台端口检测：使用 socket 测试而非 `lsof`，支持 Linux/macOS
- HTTP 服务进程：基于 `python3 -m http.server`（Python 内置）

### 4.2 用户服务注册表 — `registry.json`

- 路径：`~/.http-server-cli/registry.json`
- 记录所有用户启动的 HTTP 服务
- 每个条目包含：`port`、`path`、`pid`、`domain`、`daemon`、`foreground`、`started_at`、`index_page`
- 支持查询（按 port 或 path）、添加、移除、全量列表
- `active_servers()` 方法自动装饰 `_alive` 存活状态
- `hs kill-all` 仅影响此注册表中的服务

### 4.3 基础设施服务注册表 — `registry-managed.json`

- 路径：`~/.http-server-cli/registry-managed.json`
- 记录工具自身的基础设施服务（dashboard、MCP SSE 等）
- 每个条目包含：`name`、`type`、`port`、`pid`、`transport`、`started_at`
- `hs list` 合并展示用户服务 + 基础设施服务
- **hs kill-all 不影响基础设施服务** — 保持工具自身服务持续运行
- 变更即时持久化

### 4.4 配置存储 — `config.json`

- 路径：`~/.http-server-cli/config.json`
- 可配置字段：`port`（默认 8080）、`domain`（默认 `localhost`）
- 启动时自动读取，修改即时持久化
- 写入字段白名单校验

### 4.5 数据目录结构

```
~/.http-server-cli/
├── config.json             # 默认端口/域名配置
├── registry.json           # port → {path, pid, domain, daemon, foreground, started_at, index_page}
├── registry-managed.json   # 基础设施服务注册表（dashboard, MCP）
└── logs/
    └── {port}.log          # http.server 日志文件（按端口命名）
```

### 4.6 进程管理

- 通过 `subprocess.Popen` 启动 `runner.py` 作为子进程
- `preexec_fn=os.setsid` 创建独立进程组
- 终止时使用 `os.killpg(pgid, signal.SIGTERM)` 确保整个进程组被终止
- 未响应时降级为 `SIGKILL`
- 进程存活检测：`os.kill(pid, 0)` 无异常判断

### 4.7 智能首页重定向

- 目录无 `index.html` 时自动重定向到最近修改的 `.html` 文件
- 通过 `runner.py` 中的自定义 HTTP handler 实现
- 通过 `-i`/`--index` 参数可指定任意文件作为首页

### 4.8 跨平台兼容

- 端口可用性检测基于 socket 而非 `lsof`，支持 macOS / Linux
- macOS 专有功能：`lsof` 用于查询非本工具管理的端口占用进程信息
- `open` 命令用于 macOS 浏览器打开（跨平台浏览器打开通过 `webbrowser` 模块实现）
