# Changelog

## 1.0.7 (2026-06-24)

### Added
- `hs dashboard` — Web dashboard for GUI management of HTTP services
  - REST API: list, status, kill, kill-all, restart
  - Dark-themed inline HTML/CSS/JS, 5s auto-refresh, favicon 📊
  - `--json` one-shot query mode, `-o` auto-daemon + open browser
  - Duplicate run detection: shows status or opens browser if already running
  - Dashboard API includes managed infrastructure services (MCP SSE)
  - Managed registry integration (registry-managed.json)
- `hs dashboard` subcommands:
  - `hs dashboard stop` — stop running dashboard via managed registry
  - `hs dashboard status` — query dashboard status (port/PID/duration/CPU/memory)
  - `hs dashboard restart` — stop + restart
  - `hs dashboard help` — dashboard-specific usage
- **Dashboard v2** — Web UI 增强
  - 中英文语言切换（🇨🇳 `/` ↔ 🇺🇸 `/en`），右上角悬浮 pill
  - 工具栏 60s 倒计时自动刷新 + 🔄 Refresh 按钮 + 🛑 Kill All 按钮
  - 表格重构：URL(Port) | Status | CPU | Memory | Last Access | Action（移除 PATH/PID/STARTED）
  - URL 列用 `url` 字段渲染为 `<a target="_blank">` 超链接
  - Status 点击弹出详情弹框：端口/路径/PID/内存/启动时间/日志路径/最近访问
  - `window.onerror` + `unhandledrejection` 全局异常捕捉覆盖层
  - API `_get_server_list` 增加 `url` + `log_path` 字段
  - API `_handle_get_status` 增加 `log_path` + `last_access_at` 字段
  - 测试用例从 7 → 18 个（覆盖中英文加载/error handler/列头/API 字段）
  - 仅显示 Running 实例（`render()` 中 `servers.filter(alive)`）
  - H1 标题右侧添加 GitHub 图标，链接至 https://github.com/imjaden/http-server-cli
  - 中英文各自使用母语：CN 全中文（列标题/按钮/状态文字）、EN 全英文
  - 底部可折叠版本号（Version: 1.0.7）+ hs help 命令参考（通过 `/api/info` 获取）
  - 测试用例从 18 → 20 个（新增 footer + EN columns 测试）
  - 健康检查探活：新增 `/api/ping/{port}` HEAD 请求（2s 超时），前端 🟢/🟡/🔴 圆点
  - 搜索过滤框：表格上方 input 实时按端口/路径关键字过滤（纯前端）
  - 一键复制 URL：每行 URL 右侧 📋 按钮，clipboard.writeText + toast
  - 日志尾部查看：新增 `/api/log/{port}` tail 50 行，集成至 Status 弹框
  - 测试用例：224 个（新增 9 个：ping/log API + copy/search/health/log HTML 元素）
  - 搜索框默认隐藏，>10 个实例时自动显示
  - Footer summary 文字居中 + 宽度对齐表格
  - 自动语言检测：根据浏览器 Accept-Language 头切换 CN/EN（_detect_lang）
- `hs mcp` — MCP Server for AI Agent integration
  - JSON-RPC 2.0 over SSE (default, auto-daemon) or stdio transport
  - 6 tools: hs_list, hs_status, hs_start, hs_kill, hs_kill_all, hs_config
  - SSE mode registers to managed registry; stdio mode does not
  - Duplicate run detection for SSE mode
  - Init sequence validation (rejects tools before initialize)
  - Package CLI via subprocess (方案A), zero external dependencies
- `hs mcp` subcommands:
  - `hs mcp stop` — stop MCP SSE service via managed registry
  - `hs mcp status` — query MCP status (port/PID/duration)
  - `hs mcp restart` — stop + restart
  - `hs mcp help` — mcp-specific usage
- `hs list` now merges both registries, managed services marked with 🔧
- `registry-managed.json` — separate registry for infrastructure services
  - Dashboard and MCP SSE services tracked here
  - `hs kill-all` does NOT affect managed services
- `scripts/hs-mcp-demo.py` — reusable MCP integration verification script
  - Subcommand mode: help/status/init/tools/hs_list/hs_config/all
  - Zero third-party deps, no auto-start (shows manual commands)
  - Includes AI Agent config examples (Claude Desktop, Cursor, VS Code)
- Test suite: 182 tests (registry_managed, dashboard, MCP, CLI, server)

### Changed
- `hs mcp` default transport changed from stdio to SSE (auto-daemon)
- `hs dashboard -o` now auto-daemons (no need for `-d`)
- Dashboard web layout: h1 + stats + toolbar on same line (compact flexbox)
- `_execute_hs()`: parses full JSON output first, handles multi-line `indent=2` output
- `__version__` bumped to 1.0.7

### Fixed
- Dashboard API returning empty user services (Registry cached at server start;
  now creates fresh ServerManager per API request)
- MCP `_execute_hs()` failing on multi-line JSON output from `json_output()`
- Dashboard frontend JS reading `data.servers` instead of `data.data.servers`
- `hs dashboard -o` not opening browser in daemon mode (parent now opens browser)
- `hs mcp` daemon infinite subprocess chain (HS_MCP_WORKER env var)

## 1.0.6 (2026-06-23)

### Added
- `--json` flag for all commands (start/list/status/kill/kill-all/config/set/version)
  - Unified response envelope: `{ success, command, data, error }`
  - Designed for API/MCP consumption
- `-i`/`--index` flag for `hs start` to specify custom index HTML page
  - Persisted to registry, shown in `list --json` and `status --json`
- Cross-platform port detection (socket-based, no longer macOS-only)
- `CHANGELOG.md` for project version history

### Changed
- All JSON output now uses unified `json_output()` envelope function
- `hs config --json`, `hs list --json`, `hs status --json` improved format
- `hs start --json` returns `stats`, `duration`, `index_page` fields
- `hs status --json` now returns `stats` and `duration` fields

### Fixed
- Duplicate `index` variable assignment in `server.py:start()`
- Missing `include LICENSE` in MANIFEST.in
- Hardcoded TestPyPI token in release scripts

### Security
- Removed hardcoded API token from release scripts; now loaded via `.env`
