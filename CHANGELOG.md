# Changelog

## 1.3.0 (2026-08-27)

### Added
- `hs web` — 跨项目 Web 服务注册管理（HTTP-SERVER-CL001）：注册任意 CLI 启动命令到名称，`hs web <name>` 已运行→直接访问 / 未运行→执行启动命令
  - `hs web add <name> --cmd '<cmd>' [--url <url>] [--open cmd|url|both|none]` — 注册（open 默认 url：web 统一开浏览器；cmd：命令自带 -o；both：都试；none：不开）
  - `hs web list/show/remove/update` + 全部 `--json` 信封；url 可选——固定端口填 url（web 先探测，可达则幂等直达），动态端口不填（启动前未知端口，直接透传）
  - `hs web <name> --no-probe` — 跳过探测，强制重启
  - 存储 `~/.http-server.cli/services.json`（独立于 bookmarks.json，bookmark 管静态目录、services 管任意命令）
  - 全局薄壳 `~/.local/bin/web` 转发，达成 `web <name>` 语法
- `hs web --domain`（HTTP-SERVER-CL002）— 布尔入参，执行时把 config.domain 注入 cmd 末尾（`cmd ... --domain "<domain>"`）；update 支持 `--no-domain` 清除；json 输出含 `cmd_effective`
- 审计遗留（HTTP-SERVER-CL002 / SEC-022-1/2, OBS-3）— web 子命令名（add/update/list/show/remove/help）冲突拦截；services.json 形状校验（合法 JSON 非 dict / services 非 list → DataCorruptionError）；spec.yaml version 1.1.0→1.3.0 + version 场景输出串修正
- `hs prompt hs-web` — 跨项目 web 服务注册推广 skill（命令速查 + 其他模块接入指南 + 真实实例 daily.checker/jaden.tech/线上站点），镜像 ~/.hermes/profiles/ops/skills/devops/hs-web/（HTTP-SERVER-CL002）
- Test suite: 442 → 483 tests（+41：CL002 第一批 +17，SEC-023-1 set_domain 校验 +24）
- SEC-023-1（CL002 复核）— `hs set domain` / `Config.set_domain` 字符集校验 `[a-zA-Z0-9][a-zA-Z0-9.-]*`（拒绝空格/引号/`$`/反引号/`;`/`&` 等 shell 元字符，hs web --domain 注入 defense-in-depth）

## 1.2.0 (2026-08-25)

### Added
- `hs prompt [<skill>]` — 输出 skills/ 使用说明（AI 对接，参考 html-gen prompt）：无参列出 4 篇（hs-cli/hs-bookmark/hs-mcp/hs-dashboard）/ `<name>` 全文 / `--brief` / `--json` 信封 / 不存在报错 + 可用列表 + exit 1
- `hs mcp` 扩展 5 个数据工具（6→11）：hs_bookmark_list / hs_bookmark_add（name/path/index_page/force，布尔 flag 映射 --force）/ hs_bookmark_remove / hs_history / hs_search
- `hs mcp` MCP Resources 3 项（只读）：hs://registry / hs://bookmarks / hs://config；initialize capabilities 声明 resources；SERVER_VERSION 1.0.0→1.1.0
- `hs mcp --config` — 输出 mcpServers 接入配置片段（Claude Code / Cursor / Hermes 一行接入，stdio）+ `--json` 信封

### Notes
- 批次二暂缓：hs export / hs doctor（draft CL-SEC20 记录）
- Test suite: 378 tests（+21：test_prompt 9 / test_mcp 12）

## 1.1.0 (2026-08-23)

### Changed
- Project renamed `http-server-cli` → `http-server.cli`; GitHub repo → `imjaden/http-server.cli`
- Data directory migrated `~/.http-server-cli/` → `~/.http-server.cli/` (auto-migrate on first run, move + copy fallback)
- CLI display strings, `hs version` output, docstrings updated to `http-server.cli`
- Display name updated to `http-server` (CLI strings, `hs version` output, README h1/badges, index hero, features title); internal identifiers (repo/domain/data dir/spec/PyPI package) unchanged
- npm disambiguation note added (README + landing pages): hs is unrelated to the npm package `http-server`
- `pyproject.toml`: `readme` corrected `README.en.md` → `README.md` (file was already `README.md`)
- Spec file renamed `http-server-cli.spec.yaml` → `http-server.cli.spec.yaml`

### Added
- bookmark: unique key is now `(path, index_page)` composite; same path with different index pages can coexist
- `hs bookmark add --force`: overwrite existing bookmark with same `(path, index_page)` key
- `hs bookmark list` / `show` / `add` / `update` / `remove` support `--json` envelope output
- `hs mcp status|stop|restart` and `hs dashboard status|stop|restart` support `--json`
- Data dir migration unit tests (5 cases: migrate, skip, no-legacy, copy fallback, full failure)

### Fixed
- PyPI project description missing ("The author of this package has not provided a project description"): v1.0.8 was built with `readme = "README.en.md"` (nonexistent file) → long_description empty; now `readme = "README.md"` produces a non-empty description with GitHub + PyPI links

### Index (landing page)
- `index.html` / `index.zh.html` two-screen redesign (pages-index pattern): screen 1 = hero + install + quick start (4 core commands, each copyable) + scroll-hint; screen 2 = 5 scenario groups with per-command copy buttons + comparison table
- Dynamic two-screen hero height (`minHeight = innerHeight - 110` + resize), scroll-hint fixed bottom with fade-out
- Footer links now use platform favicons (GitHub / PyPI / site), `rel="noopener"` on all external links
- github-corner light-theme colors (dark triangle + white octocat), theme mechanism unchanged (`[data-theme=light]` + `hs-theme`)
- README badges (GitHub / PyPI favicon icons) + PyPI↔GitHub cross links
- Test suite: 352 tests (index sync +2: cmd-row count, two-screen elements)

## 1.0.8 (2026-07-01)

### Added
- `--index` wildcard (glob) support: auto-select most recently modified file
- `hs /path/to/*.html` path glob support: same most-recent-file resolution
- `hs kill /path/to/file.html`: automatically resolves to parent directory
- Dashboard URL column includes `index_page` path when non-default
- Re-open (`hs . -o`) reuses registry `index_page` in URL
- `scripts/release-local.sh` and `release-pypi.sh`: `--versions` shows editable status
- Test suite: 227 tests (added reopen with index_page, dashboard URL with index)
- `hs list` now only shows running/alive servers (filtered by `_alive` flag)
- `hs search` now only searches running/alive servers
- `hs history` filters out system temp directory entries (`/tmp/`, `/private/var/folders/`)
- `/?lang=zh` query parameter support — language toggle now works regardless of browser `Accept-Language`
- `hs dashboard -d` daemon mode logs to `~/.http-server-cli/logs/dashboard.log`
- `hs dashboard status` now prints log path in output
- GitHub CI/CD workflow: `.github/workflows/release.yml` — auto Release + PyPI on tag push
- CI/CD recommendation document: `documents/github-ci-cd-recommendation.md`

### Changed
- CLI output unified to English — all ~108 `print()`/`eprint()` calls across 5 files
- Emoji formatting: 1 space after emoji, ` -> ` arrow spacing, ` | ` pipe spacing
- README restructured: `README.md` (English) → default, `README.zh.md` (Chinese)
- Dashboard auto-language detection: `Accept-Language` header with URL query param override

### Fixed
- Language toggle BUG: clicking 🇨🇳 with English browser now correctly switches to Chinese
- `/?lang=zh` route returning 404 — `do_GET` now strips query params before routing
- Test suite expanded from 182 → 224 tests

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
  - 底部可折叠版本号（Version: 1.0.x）+ hs help 命令参考（通过 `/api/info` 获取）
  - 测试用例从 18 → 20 个（新增 footer + EN columns 测试）
  - 健康检查探活：新增 `/api/ping/{port}` HEAD 请求（2s 超时），前端 🟢/🟡/🔴 圆点
  - 搜索过滤框：表格上方 input 实时按端口/路径关键字过滤（纯前端）
  - 一键复制 URL：每行 URL 右侧 📋 按钮，clipboard.writeText + toast
  - 日志尾部查看：新增 `/api/log/{port}` tail 50 行，集成至 Status 弹框
  - 测试用例：224 个（新增 9 个：ping/log API + copy/search/health/log HTML 元素）
  - 搜索框默认隐藏，>10 个实例时自动显示
  - Footer summary 文字居中 + 宽度对齐表格
  - 自动语言检测：根据浏览器 Accept-Language 头切换 CN/EN（_detect_lang）
  - 语言切换 BUG 修复：/?lang=zh 显式参数覆盖自动检测，非英文浏览器必切中文
  - CI/CD 推荐文档 → documents/ci-cd-recommendation.md
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
