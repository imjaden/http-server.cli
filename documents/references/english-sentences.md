# http-server-cli 源码中文内容分类翻译

> 用途：为源码国际化提供翻译对照表。
> 分类：A-用户输出 / B-文档注释 / C-行内注释 / D-帮助文本 / E-日志
> 生成日期：2026-06-20

---

## A — 用户输出消息（eprint / print）

用户直接看到的终端输出，国际化优先级最高。

### A1. 启动流程 (server.py / handler.py)

| 中文原文 | English Translation |
|:---------|:-------------------|
| 路径不存在或不是目录: {path} | Path does not exist or is not a directory: {path} |
| 发现残留注册记录，清理后重新启动 | Found stale registry entry, cleaning up and restarting |
| 端口 {default_port}-{MAX_PORT} 已全部被占用，无法启动 | Ports {default_port}-{MAX_PORT} are all occupied, cannot start |
| 端口 {default_port} 已被占用，自动分配端口 {port} | Port {default_port} is occupied, auto-allocating port {port} |
| 权限不足，无法写入日志或启动进程: {e} | Permission denied: cannot write log or start process: {e} |
| Python 解释器未找到: {e} | Python interpreter not found: {e} |
| 系统错误（端口/资源不可用）: {e} | System error (port/resource unavailable): {e} |
| 启动失败: {e} | Failed to start: {e} |
| 服务器已启动: http://{domain}:{port} | Server started: http://{domain}:{port} |
| 浏览器已打开 | Browser opened |
| 访问路径: {path} | Path: {path} |
| 日志文件: {path} | Log file: {path} |
| 按 Ctrl+C 停止日志查看，服务仍在后台运行 | Press Ctrl+C to stop log tailing; the server continues running in the background |
| 日志查看已停止，服务 http://{domain}:{port} 仍在后台运行 | Log tailing stopped. Server http://{domain}:{port} is still running |
| 前台运行模式：按 Ctrl+C 终止服务 | Foreground mode: press Ctrl+C to stop the server |
| 收到中断信号，正在终止服务... | Interrupt received, stopping server... |
| 服务已关闭 | Server stopped |
| ✅ 首页存在 index.html，正常返回 | ✅ index.html found, serving normally |
| 🔀 首页无 index.html，重定向到: {file} | 🔀 No index.html, redirecting to: {file} |
| ⚠️ 首页无 index.html 且无其他 html 文件，返回目录列表 | ⚠️ No index.html and no other HTML files, showing directory listing |

### A2. 列表与状态 (server.py)

| 中文原文 | English Translation |
|:---------|:-------------------|
| 没有正在运行的 HTTP 服务 | No HTTP services running |
| 使用 hs start [path] -o 启动一个 | Start one with `hs start [path] -o` |
| 共 {n} 个 HTTP 服务: | {n} HTTP service(s): |
| 启动时间: {time} | Started: {time} |
| 进程: 存活 | Process: alive |
| 进程: 已退出 | Process: exited |
| 端口: 占用中 | Port: in use |
| 端口: 空闲 | Port: free |
| 模式: 普通 | Mode: normal |
| 端口 {port} 已被占用 (PID: {pids})，但非本工具管理 | Port {port} is in use (PID: {pids}), but not managed by this tool |
| 端口 {port} 未注册 | Port {port} is not registered |
| 未找到匹配的服务 | No matching service found |
| http://{domain}:{port}  ✅ 运行中 | http://{domain}:{port}  ✅ Running |
| http://{domain}:{port}  ❌ 已停止 | http://{domain}:{port}  ❌ Stopped |
| 路径: {path} | Path: {path} |
| 已停止 | stopped |

### A3. 关闭服务 (server.py)

| 中文原文 | English Translation |
|:---------|:-------------------|
| 请指定端口或路径: kill <port\|path> | Specify port or path: kill <port\|path> |
| 端口 {port} 未注册 | Port {port} is not registered |
| 路径 {path} 未注册 | Path {path} is not registered |
| 进程组 {pgid} 未响应 SIGTERM，发送 SIGKILL | Process group {pgid} did not respond to SIGTERM, sending SIGKILL |
| 无权限终止进程组 PID: {pid}，请手动执行 kill {pid} | Permission denied to kill process group PID: {pid}. Run `kill {pid}` manually |
| 进程 {pid} 已不存在 | Process {pid} no longer exists |
| 已终止进程 PID: {pid} | Terminated process PID: {pid} |
| 服务已关闭: http://{domain}:{port} → {path} | Server stopped: http://{domain}:{port} → {path} |
| 日志文件已删除: {path} | Log file deleted: {path} |
| 删除日志文件失败: {e} | Failed to delete log file: {e} |
| 没有正在运行的服务 | No services running |
| 已关闭 {count} 个服务 | Stopped {count} service(s) |
| 已关闭 {count} 个服务（{skipped} 个跳过） | Stopped {count} service(s) ({skipped} skipped) |

### A4. 配置管理 (config.py / cli.py)

| 中文原文 | English Translation |
|:---------|:-------------------|
| http-server-cli 配置 | http-server-cli Configuration |
| 数据目录: {path} | Data directory: {path} |
| 修改配置: | Modify configuration: |
| 用法: set <port\|domain> <值> | Usage: set <port\|domain> <value> |
| 设置默认端口 | Set default port |
| 设置绑定域名 | Set bind domain |
| 端口号应在 1024-65535 之间 | Port must be between 1024 and 65535 |
| 默认端口已设置为 {port} | Default port set to {port} |
| 无效端口号: {value} | Invalid port number: {value} |
| 默认域名已设置为 {value} | Default domain set to {value} |
| 未知配置项: {key}（支持: port, domain） | Unknown config key: {key} (supported: port, domain) |

### A5. 通用消息 (utils.py / cli.py)

| 中文原文 | English Translation |
|:---------|:-------------------|
| http-server-cli 当前仅支持 macOS（依赖 lsof 命令） | http-server-cli currently only supports macOS (requires lsof) |
| Linux/Windows 支持开发中，欢迎贡献 PR | Linux/Windows support is in development. PRs welcome! |
| 用法: kill <port\|path> | Usage: kill <port\|path> |
| 未知命令: {cmd} | Unknown command: {cmd} |
| 服务已在运行: http://{domain}:{port} → {path} | Service already running: http://{domain}:{port} → {path} |

### A6. 时长格式化 (utils.py)

| 中文原文 | English Translation |
|:---------|:-------------------|
| 1分钟 | 1 minute |
| {n}分钟 | {n} minutes |
| {h}小时{m}分钟 | {h}h {m}m |
| {h}小时 | {h}h |

---

## B — 文档注释（docstring）

### B1. 模块级 docstring

| 文件 | 中文原文 | English Translation |
|:-----|:---------|:-------------------|
| `__init__.py` | http-server-cli — 本地 HTTP 服务管理器 | http-server-cli — Local HTTP Server Manager |
| `__init__.py` | 基于 python3 -m http.server，自动检测可用端口、记录项目映射、管理服务生命周期。 | Based on python3 -m http.server. Auto-detect free ports, track project mappings, manage service lifecycle. |
| `__init__.py` | Karpathy Principles - AI编程四大原则 | Karpathy Principles |
| `__init__.py` | 1. 先思考 - 不假设... | 1. Think first - no assumptions... |
| `__init__.py` | 2. 保持简单 - 最小代码解决问题 → 无多余抽象 | 2. Keep it simple - minimal code, no over-abstraction |
| `__init__.py` | 3. 精准修改 - 只改必须改的 → 不"顺便"改进邻接代码 | 3. Precise edits - change only what's needed, no scope creep |
| `__init__.py` | 4. 目标驱动 - 测试先行，验证闭环 | 4. Goal-driven - tests first, verify the loop |
| `cli.py` | CLI 入口：argparse 解析 + 命令分派。 | CLI entry point: argparse parsing + command dispatch. |
| `config.py` | 配置管理：默认端口、绑定域名。 | Configuration: default port, bind domain. |
| `config.py` | 持久化至 ~/.http-server-cli/config.json。 | Persisted to ~/.http-server-cli/config.json. |
| `handler.py` | 自定义 HTTP 请求处理器：首页智能跳转。 | Custom HTTP request handler: smart homepage redirect. |
| `handler.py` | 当访问根路径 `/` 时： | When accessing root `/`: |
| `handler.py` | 1. 若存在 index.html，正常返回 | 1. If index.html exists, serve normally |
| `handler.py` | 2. 若不存在，查找目录下所有 *.html 文件，按修改时间排序 | 2. Otherwise, find all *.html files, sort by modification time |
| `handler.py` | 3. 返回最近修改的 html 文件（HTTP 302 重定向） | 3. Return the most recently modified HTML file (HTTP 302 redirect) |
| `server.py` | 服务管理核心：启动/停止/列表/状态。 | Core service management: start/stop/list/status. |
| `server.py` | HTTP 服务全生命周期管理。 | Full lifecycle management for HTTP services. |
| `server.py` | 启动 HTTP 服务。 | Start an HTTP service. |
| `server.py` | 1. 检查 registry 中该路径是否已注册且存活... | 1. Check if the path is already registered and alive... |
| `server.py` | 2. 从默认端口递增查找空闲端口 | 2. Find the next available port from default |
| `server.py` | 3. 启动后台进程 | 3. Start background process |
| `server.py` | 4. 写入 registry | 4. Write to registry |
| `server.py` | 5. 可选打开浏览器 | 5. Optionally open browser |
| `server.py` | 6. daemon 模式：前台 tail -f 日志，Ctrl+C 仅停止日志查看 | 6. Daemon mode: foreground log tail; Ctrl+C stops tail only |
| `server.py` | 7. foreground 模式：前台运行服务，Ctrl+C 终止服务进程 | 7. Foreground mode: run in foreground; Ctrl+C stops the server |
| `server.py` | 列出所有已注册服务及其存活状态 | List all registered services and their status |
| `server.py` | 查询单个服务状态 | Query a single service status |
| `server.py` | 关闭指定服务（按端口或路径） | Stop a service (by port or path) |
| `server.py` | 关闭所有已注册服务 | Stop all registered services |
| `utils.py` | 工具函数集：路径、端口检测、JSON I/O、进程存活检查。 | Utility functions: path, port detection, JSON I/O, process alive check. |
| `utils.py` | 所有操作基于 Python 标准库，零外部依赖。 | All operations based on Python stdlib, zero external dependencies. |

### B2. 函数/方法 docstring

| 中文原文 | English Translation |
|:---------|:-------------------|
| 智能打印，自动匹配 Emoji 前缀 | Smart print, auto-matches emoji prefix |
| 路径格式化：HOME 替换为 ~ | Format path: replace HOME with ~ |
| 确保数据目录和初始文件存在 | Ensure data directory and initial files exist |
| 安全读 JSON，失败返回空 dict | Safe JSON read, returns empty dict on failure |
| 原子写 JSON（write + newline + rename），防多进程并发脏读 | Atomic JSON write (write + newline + rename), prevents concurrent read corruption |
| 非 macOS 平台给出 pending 提示 | Show pending hint on non-macOS platforms |
| 用 lsof 检测端口是否被占用（仅 macOS） | Check if port is in use via lsof (macOS only) |
| 一次性获取所有 LISTEN 状态的端口号，减少 lsof 调用次数 | Get all LISTEN ports in one call, reducing lsof invocations |
| 从 start_port 递增查找空闲端口，MAX_PORT 封顶（批量 lsof 检测） | Find available port incrementally from start_port, capped at MAX_PORT (batch lsof) |
| 通过 lsof 获取占用端口的 PID 列表（仅 macOS） | Get PIDs occupying a port via lsof (macOS only) |
| 信号 0 检测 PID 是否存活 | Check if PID is alive using signal 0 |
| 获取进程资源使用情况（CPU、内存） | Get process resource usage (CPU, memory) |
| 解析路径为绝对路径（展开 ~ 并解析符号链接） | Resolve path to absolute (expand ~ and resolve symlinks) |
| 当前 ISO 时间戳（到秒） | Current ISO timestamp (second precision) |
| 计算并格式化运行时长 | Calculate and format running duration |
| 当前 Python 解释器路径 | Current Python interpreter path |
| 配置读写，字段变更即时持久化。 | Config read/write, field changes persist immediately. |
| 合并磁盘配置，不覆盖缺失字段 | Merge disk config without overwriting missing fields |
| 默认起始端口 | Default start port |
| 绑定域名 | Bind domain |
| 设置默认端口（1024-65535），持久化 | Set default port (1024-65535), persists |
| 设置绑定域名，持久化 | Set bind domain, persists |
| 打印配置，或返回 JSON 格式 | Print config, or return as JSON |
| 添加新条目 | Add a new entry |
| 删除匹配的条目 | Remove matched entries |
| 清空所有条目 | Clear all entries |
| 返回所有条目（引用，修改需调用 save） | Return all entries (reference, call save to persist) |
| 查找条目，支持 port 或 path | Find an entry, supports port or path |
| 返回存活状态装饰后的条目列表 | Return entries decorated with alive status |
| 处理 GET 请求，首页智能跳转 | Handle GET request, smart homepage redirect |
| 查找目录下最近修改的 html 文件 | Find the most recently modified HTML file in directory |
| 自定义日志格式，输出到 stderr | Custom log format, output to stderr |
| 创建绑定指定目录的处理器类 | Create handler class bound to a specific directory |
| 装饰器：注册命令处理函数 | Decorator: register command handler |
| HTTP 服务启动脚本：使用自定义处理器启动服务。 | HTTP service bootstrap script: start with custom handler. |

---

## C — 行内注释（# 开头）

### C1. 分隔线 / 章节标记

| 中文原文 | English Translation |
|:---------|:-------------------|
| # ── 帮助文本 ── | # ── Help text ── |
| # ── Set 子命令 ── | # ── Set subcommand ── |
| # ── 命令分派 ── | # ── Command dispatch ── |
| # ── 打印 ── | # ── Printing ── |
| # ── 存储 ── | # ── Storage ── |
| # ── 端口检测 ── | # ── Port detection ── |
| # ── 进程 ── | # ── Process ── |
| # ── 路径 / 时间 ── | # ── Path / Time ── |
| # ── 属性读取 ── | # ── Property reads ── |
| # ── 属性写入（自动保存） ── | # ── Property writes (auto-save) ── |
| # ── 序列化 ── | # ── Serialization ── |
| # ── 查询 ── | # ── Query ── |
| # ── 修改 ── | # ── Mutation ── |
| # ── 检查是否已注册且存活 ── | # ── Check if registered and alive ── |
| # ── 查找可用端口 ── | # ── Find available port ── |
| # ── 启动后台进程 ── | # ── Start background process ── |
| # ── 注册 ── | # ── Register ── |

### C2. 业务逻辑注释

| 中文原文 | English Translation |
|:---------|:-------------------|
| 可写字段白名单 | Settable field whitelist |
| 写临时文件，再原子 rename，防止写入中途崩溃留下半成品 | Write to temp file, then atomic rename to prevent partial writes |
| 添加包路径（上一级目录，使 http_server_cli 包可被导入） | Add package path so http_server_cli can be imported |
| 创建处理器 | Create handler |
| 启动服务 | Start server |
| 确保 directory 参数正确设置 | Ensure directory parameter is set correctly |
| 解析 URL，获取纯路径（忽略查询参数） | Parse URL, get clean path (ignore query params) |
| 仅处理根路径请求 | Only handle root path requests |
| 检查是否存在 index.html | Check if index.html exists |
| 存在 index.html，正常返回 | index.html exists, serve normally |
| 不存在 index.html，查找最近修改的 html 文件 | No index.html, find most recently modified HTML file |
| 重定向到最近修改的 html 文件 | Redirect to most recently modified HTML file |
| 其他路径，使用默认处理（包括静态资源） | Other paths, use default handler (including static assets) |
| 按修改时间排序，获取最近修改的文件 | Sort by modification time, get most recent |
| 按端口排序 | Sort by port |
| 获取当前目录 | Get current directory |
| 当前目录服务使用 📍 标记 | Current directory service marked with 📍 |
| 计算时长 | Calculate duration |
| 进程资源使用情况 | Process resource usage |
| daemon 模式启动时 preexec_fn=os.setsid 创建了新进程组 | daemon mode uses preexec_fn=os.setsid to create new process group |
| 使用 killpg 确保整个进程组（包括可能产生的子进程）被终止 | Use killpg to ensure the entire process group is terminated |
| 删除日志文件 | Delete log file |
| 等待服务完全启动 | Wait for server to fully start |
| 解析输出: CPU%, MEM%, RSS | Parse output: CPU%, MEM%, RSS |
| 转换 RSS 为 MB | Convert RSS to MB |
| 尝试解析 ISO 格式或空格分隔格式 | Try to parse ISO format or space-separated format |

---

## D — 帮助文本（HELP）

| 中文原文 | English Translation |
|:---------|:-------------------|
| 忘记端口，只管预览 | Forget ports. Just preview. |
| 用法: hs [command] [args] | Usage: hs [command] [args] |
| 快捷方式: | Shortcuts: |
| 等价 hs start . | Equivalent to `hs start .` |
| 等价 hs start .（当前目录启动） | Equivalent to `hs start .` (start with current directory) |
| 命令: | Commands: |
| 启动服务 | Start server |
| path 默认 .；-o 打开浏览器；-d daemon；-f foreground | path defaults to `.`; `-o` open browser; `-d` daemon mode; `-f` foreground |
| 列出所有运行中的服务 | List all running services |
| 列出所有运行中的服务（--json 输出 JSON） | List all running services (--json for JSON output) |
| 查询单个服务状态（--json 输出 JSON） | Query a single service (--json for JSON output) |
| 关闭指定服务 | Stop a service |
| 关闭所有服务 | Stop all services |
| 显示当前配置（--json 输出 JSON） | Show current config (--json for JSON output) |
| 修改默认端口 | Modify default port |
| 修改绑定域名 | Modify bind domain |
| 显示此帮助 | Show this help |
| 显示版本号 | Show version |
| 示例: | Examples: |
| 当前目录启动 + 打开浏览器 | Start in current directory + open browser |
| 指定目录启动 | Start in specified directory |
| daemon 模式 | daemon mode |
| JSON 格式列出所有服务 | List all services as JSON |
| JSON 格式查询端口 8080 状态 | Query status of port 8080 as JSON |
| JSON 格式显示配置 | Show config as JSON |
| 关闭端口 8081 的服务 | Stop service on port 8081 |
| 修改默认端口为 3000 | Set default port to 3000 |
| 数据目录: ~/.http-server-cli/ | Data directory: ~/.http-server-cli/ |
| 启动服务（path 默认 .；-o 打开浏览器；-d daemon 模式；-f 前台模式） | Start server (path defaults to `.`; `-o` open browser; `-d` daemon; `-f` foreground) |
| 列出所有运行中的服务（--json 输出 JSON） | List all running services (--json for JSON output) |
| 查询单个服务状态（--json 输出 JSON） | Query service status (--json for JSON output) |
| 显示当前配置（--json 输出 JSON） | Show current configuration (--json for JSON output) |
| 修改默认端口 | Set default port |
| 修改绑定域名 | Set bind domain |

---

## E — 日志消息（handler.py log_message）

| 中文原文 | English Translation |
|:---------|:-------------------|
| ✅ 首页存在 index.html，正常返回 | ✅ index.html found at root, serving normally |
| 🔀 首页无 index.html，重定向到: {file} | 🔀 No index.html found, redirecting to: {file} |
| ⚠️ 首页无 index.html 且无其他 html 文件，返回目录列表 | ⚠️ No index.html and no other HTML files, showing directory listing |

---

## 附录：翻译优先级

| 优先级 | 分类 | 说明 |
|:------:|:-----|:------|
| 🔴 P0 | **A 用户输出** | 用户看到的终端消息，最影响国际化体验 |
| 🟡 P1 | **D 帮助文本** | `hs help` 的输出 |
| 🟢 P2 | **B 文档注释** | 开发者看的 docstring，不直接影响用户 |
| 🔵 P3 | **C 行内注释** | 仅维护者看，可最后处理 |
