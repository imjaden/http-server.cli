# http-server-cli — Features

> 零依赖 Python HTTP 服务 CLI。一键启动本地静态文件服务，忘记端口。
>
> 文件命名: 固定为 `features.md`，小写，无版本号。
>
> 适用: 风格 B 文件（无版本号，持续更新），存放在项目根目录。

## CLI 命令

1. `hs start [path]` — 启动服务，选项: `-o` 打开浏览器 / `-d` 后台 / `-f` 前台 / `-i <file>` 首页 ✅ — `documents/hs-cli-design.md`
2. `hs .` — 快捷启动当前目录（等价 `hs start .`）✅
3. `hs <name>` — 书签名称启动（自动解析为 `hs start <path>`）✅
4. `hs list [--port|--path|--short] [--json]` — 列出运行中服务 ✅
5. `hs status <port|path> [--json]` — 查询单服务状态 ✅
6. `hs kill <port|path|name> [--json]` — 关闭服务 ✅
7. `hs kill-all [--json]` — 一键关闭所有 ✅
8. `hs history [--json]` — 历史启动记录 ✅
9. `hs search <keyword> [--json]` — 模糊搜索实例 ✅
10. `hs version [--json]` — 版本号 ✅
11. `hs help` — 帮助信息 ✅
12. `hs --url` — 启动后仅输出完整 URL（与 --json 互斥）✅ — `documents/url-flag-design-v2.0-20250715.md`
13. 全局 `--json` 标志 — 所有管理命令（list/status/kill/kill-all/history/search/config/set/version）均支持 ✅

## 书签系统

1. `hs bookmark add <name> [path] [-i index]` — 注册书签 ✅
2. `hs bookmark update <name> [path] [-i index]` — 更新书签 ✅
3. `hs bookmark list [--json]` — 列出所有书签 ✅
4. `hs bookmark show <name> [--json]` — 查看书签详情 ✅
5. `hs bookmark remove <name>` — 删除书签 ✅
6. 路径唯一约束 — 不同 name 不可指向同一 path ✅
7. 通配符 index 解析 — `-i 'snapshots/*.html'` 存原始 pattern，运行时取 `max(mtime)` ✅
8. 损坏检测 — 非空文件 JSON 解析失败抛出 `DataCorruptionError` ✅
9. 关联文档: `documents/bookmark-feature-design-v1.1-20250715.md`

## HTTP 服务

1. 零外部依赖 — 仅 Python 3.12 标准库 ✅
2. Range 请求支持 — 206 Partial Content，视频拖动进度条可用 ✅ — `documents/../references/range-request-support.md`
3. MIME 类型自动识别 — 基于文件扩展名 ✅
4. 智能首页 — 无 index.html 时自动重定向到最近修改的 html ✅
5. 自定义首页 — `-i <file>` 指定任意首页文件（支持子目录路径如 `build/index.html`）✅
6. HTML 文件路径友好 — `hs /path/file.html` 自动提取目录作为服务目录 ✅

## 服务管理

1. 自动端口分配 — 默认 8080，冲突自动递增 ✅
2. 端口检测 — IPv4 + IPv6 双栈 bind 检测（macOS 兼容）✅ — `documents/ports-detect-design-v1.1-20250716.md`
3. 进程资源监控 — CPU%、内存 MB、运行时长 ✅
4. 进程组管理 — daemon 模式 `os.killpg` 防孤儿进程 ✅
5. 原子写入 — 防多进程并发脏读 ✅
6. 智能历史 — `hs history` 自动过滤系统临时目录 ✅
7. 文件路径 kill — `hs kill ~/my-site` 按路径关闭 ✅
8. HTML 文件 kill — `hs kill file.html` 自动解析父目录 ✅

## 数据持久化

1. `registry.json` — 运行中服务注册（port/path/pid/domain/daemon/started_at/last_access_at/index_page）✅
2. `history.json` — 历史记录（started_at/ended_at/memory_mb）✅
3. `config.json` — 默认配置（port/domain）✅
4. `bookmarks.json` — 书签持久化 ✅
5. `logs/` — 按端口分日志文件 ✅
6. 数据目录: `~/.http-server-cli/`

## Web Dashboard

1. 图形化管理面板 — 端口 8180，`hs dashboard -o` 打开 ✅ — `documents/hs-dashboard-design.md`
2. 中英文语言切换 — 🇨🇳 `/?lang=zh` ↔ 🇺🇸 `/en`，右上角悬浮 pill ✅
3. 工具栏 — 60s 倒计时自动刷新 / 刷新按钮 / Kill All 一键关闭 ✅
4. 服务器表格 — URL(Port) | Health | Status | CPU | Memory | Last Access | Action ✅
5. 健康检查探活 — 🟢/🟡/🔴 圆点标识 HTTP 响应状态 ✅
6. 搜索过滤框 — 实例 >10 时自动显示，实时按端口/路径关键字过滤 ✅
7. 状态弹框 — 端口/路径/PID/内存/启动时间/日志路径/最近访问 + 最近 50 行日志 ✅
8. 一键复制 URL — 📋 按钮 ✅
9. 全局异常捕捉 — `window.onerror` 覆盖层弹框显示完整 stack trace ✅
10. REST API — list / status / kill / kill-all / ping / log / info ✅

## MCP 集成

1. `hs mcp` — 启动 MCP Server（后台 SSE），AI Agent 集成 ✅ — `documents/hs-mcp-design.md`
2. `hs mcp stop` — 停止 MCP 服务 ✅
3. `hs mcp status` — 查看 MCP 状态 ✅
4. JSON-RPC 2.0 协议 — stdio/SSE 传输，6 个工具（hs_list/hs_status/hs_kill/hs_kill_all/hs_start/hs_search）✅
5. 零外部依赖 — 纯标准库实现 MCP 协议 ✅

## 配置管理

1. `hs config [--json]` — 查看当前配置 ✅
2. `hs set port <value>` — 修改默认端口（1024-65535）✅
3. `hs set domain <value>` — 修改绑定域名 ✅

## 测试

1. 11 个测试模块，293 个测试用例 ✅ — `tests/test_cli.py` 等
2. `conftest.py` — autouse 数据隔离 + monkeypatch 路径注入 ✅
3. 集成测试模式 — mock `_COMMANDS` / `ensure_storage`，set `sys.argv`，catch `SystemExit` ✅

## 构建 & 发布

1. `release-local.sh` — 本地安装（`--editable` / `--versions`）✅
2. `release-pypi.sh` — PyPI 发布（`--production` / `--versions`）✅
3. `setup.py` — 入口点 `hs = http_server_cli.cli:main` ✅

## 待定/规划

1. `hs mcp` 支持更多传输协议（如 Streamable HTTP）🚧
2. `hs dashboard` 暗色/亮色主题切换 🚧 — `documents/skill-light-dark-theme-toggle.md`
3. `hs dashboard` GitHub Corner 链接 🚧 — `documents/skill-github-corner-link.md`
4. GitHub CI/CD 流水线 🚧 — `documents/github-ci-cd-recommendation.md`
