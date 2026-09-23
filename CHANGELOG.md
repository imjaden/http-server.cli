# Changelog

## 1.4.1 (2026-09-23)

### Added
- **目录级启动锁**（HTTP-SERVER-CL005）— 同一目录并发启动（含 `hs index.html` 与 `hs <dir>` 混用）在临界区互斥，杜绝「先 Popen 后登记」窗口内的重复启动与孤儿 runner：
  - 锁文件 `~/.http-server.cli/locks/<sha1(abs_path)[:16]>.json`（`O_CREAT|O_EXCL` 原子获取，`finally` 释放 + 归属校验仅删本进程锁）
  - stale 四判据：内容不可解析且写入龄 ≥1.0s · pid 非活 · pid 活但命令行非本 CLI（pid 复用）· 持锁龄 > `LOCK_TTL=30s`；**负龄不判 stale**（跨重启/时钟异常交 pid 活性兜底）
  - 等待路径 `LOCK_WAIT=3s` / `LOCK_POLL=0.2s`：期间该目录登记就绪 ⇒ 幂等命中退出 0；锁已释放 ⇒ 重试整链；超时 ⇒ fail-closed 退出 1（提示持锁 pid）
  - 用法错误优先：路径不存在 / index 非法 / `-p` 越界仍按原语义 exit 1 / 2，不被锁等待掩盖
  - 计时基准 `time.clock_gettime(CLOCK_MONOTONIC)`（跨进程可比；`time.monotonic()` 在 py3.9 实测跨进程近零且非单调，会导致活锁被误判 stale）
- **派发件模板** `scripts/review-dispatch.sh`（HTTP-SERVER-CL005 / D4）— 由「编号 + 项目 + 步骤 + 日期」唯一推导 派发壳/日志/用量 三路径；派发前校验提示词非空、派发后校验 usage-file 非空，生成物先过 `bash -n`

### Fixed
- **`eprint()` 实际写 stdout**（HTTP-SERVER-CL005）— 内部打印函数名为 stderr 系列却写 stdout，导致错误/警告文案污染 `--json` 输出与下游管道；现 `eprint()` 写 stderr、查询类结果走新增的 `print_msg()`（stdout），并逐调用点固化通道契约（63 处：stdout 23 / stderr 38 / 三态分叉 2）
- **`hs web` 错误分支退出 0**（HTTP-SERVER-CL005）— `hs web add/list/show/remove/update/<name>` 的用法错误与运行期失败此前一律退出 0（假成功）；现用法错误（缺必填 / 子命令名冲突 / 名已存在 / 非法 url·open / 无更新参数）退出 2，运行期失败（名不存在 / services 文件损坏 / 执行命令退出码非 0）退出 1；并补 `hs web <name>` 的命令失败分支（修前 rc=0 且 JSON `success=true`）

### Changed
- 锁语义：`--daemon` tail / `foreground` 长驻期间由首实例持有锁，第二实例在该期间命中「已就绪」快径 ⇒ 幂等退出 0（不判忙、不重复启动）
- **依赖 stderr 捕获的脚本请注意**：错误/警告文案通道由 stdout 改为 stderr（stdout 仅剩命令主产物：URL、清单、JSON 信封）

### Notes
- 1.4.0（CL003 + CL004）与 1.4.1（CL005）均**尚未发布 PyPI**，可按同批发布
- 新增测试模块 `tests/test_cl005_hardening.py`（33 用例，T1–T27）；全量 590 passed
- 设计件：`documents/http-server-cl005-hardening-design-v1.2-20260923.md`（v1.0 / v1.1 留档）

## 1.4.0 (2026-09-22)

### Added
- `hs start -p/--port <N>`（HTTP-SERVER-CL003）— 指定启动端口，CLI 优先于 `config.port`（一次性，不回写配置）
  - fail-closed：端口被占用即报占用者（PID/路径）+ 换端口提示并退出 1，不再静默漂移
  - 保留端口 8180（dashboard）/ 8181（mcp）硬拦 + 双态提示（被占用报「正在使用，PID …」；空闲提示 `hs dashboard -p 8180`）
  - 区间 1024-65535（越界退出 2）；`-p` 直绑不受自动漂移上限 `MAX_PORT=10000` 约束
  - 已运行路径 + `-p` → 幂等命中（忽略 `-p`，stderr 注记；换端口先 `hs kill <port>`）
- `hs web add/update --port <N> | --no-port`（HTTP-SERVER-CL003）— 注册命令可声明端口注入，执行时在 `--domain` 之后追加 `--port <N>`；`services.json` 增 `use_port`/`port` 字段（旧数据缺字段按未启用兼容）
- `hs dashboard restart --port <N>`（HTTP-SERVER-CL003）— 指定端口重启面板；未给则沿用当前 entry 端口（修 1.3.x 硬编码 8180）
- `hs start --json` 信封增 `data.port`（HTTP-SERVER-CL003，additive）
- 未识别参数显式告警（HTTP-SERVER-CL003）— 全命令统一 stderr 提示「未识别参数（已忽略）」+ 近形引导（stdout / JSON 信封零污染，退出码不变）

### Fixed
- 端口探测「假占用」（HTTP-SERVER-CL004）— `is_port_in_use` 不再被残留态端口（`TIME_WAIT` / `FIN_WAIT_2`，如刚 `hs kill` 的服务）误判为占用：
  - `hs start` 未给 `-p` 时不再无提示漂移到下一端口（修复前实测：8084 被 kill 后 3 秒重启落到 8085）
  - `hs . -p <N>` 对刚释放的端口不再假拒绝；`registry._alive` / dashboard / mcp 端口判定同源修复
  - 实现：macOS 以 lsof 的 LISTEN 集合为准（只反映真实监听者，天然不受残留连接影响）；非 macOS 或 lsof 不可用时回退 socket 探测（开 `SO_REUSEADDR`）
- 顶层 `-i` 值泄漏走「路径快捷方式」（HTTP-SERVER-CL004）— `hs -i <CWD 存在的文件> -p <N> <dir>` 此前被当作目录快捷方式处理，导致 `-i` 被丢弃、`<dir>` 被当未识别参数忽略、服务落到当前目录；现取值型 flag（`-p/--port/-i/--index`）在场时优先按参数形态重组（`-o/-d/-f` 不受影响）
- `hs web add/update` 用法错误软拒绝（HTTP-SERVER-CL004）— `--port` 越界与 `--port/--no-port` 互斥此前打印错误却退出 0，现统一退出 2（对齐 CL003 退出码三态）
- 启动竞态下的孤儿 `runner` 进程（HTTP-SERVER-CL004）— 同目录 100ms 内连续两次 `hs <dir>` 时，后一次会把「已 `Popen` 但尚未 LISTEN」的前一次判为 stale 并删登记，导致进程仍在跑却无登记；现引入 ≤1.0s 启动宽限 + 归属校验（命令行 token 精确匹配 `runner.py` 与该目录，防 pid 复用误杀），判 stale 时先终止该进程组再清登记；宽限内若端口被其他进程占用则不误杀
- stale 提示污染 `--json` 输出（HTTP-SERVER-CL004）— stale 文案此前经 `eprint` 写入 stdout，`hs <dir> --json` 触发 stale 时 JSON 信封被污染（`JSONDecodeError`）；现 stale/宽限/终止三类文案在 url / json / 默认三态一律写入 stderr

### Changed
- **退出码语义收敛为三态**（HTTP-SERVER-CL003）：`0` 成功（含幂等命中）· `1` 运行期失败（路径不存在 / 端口不可用 / `hs kill <未注册端口>`）· `2` 用法错误（非法取值 / 越界 / 互斥参数）。此前「路径不存在」与 `hs kill <未注册端口>` 均返回 0（假成功），围绕 hs 写脚本时请改判退出码
  - `hs status <未注册端口>` 仍为 0（查询本身成功）
  - argparse 报错不再被吞掉：`hs dashboard -p abc` 等此前打印错误却退出 0，现退出 2
- 顶层 `-p` 归位（HTTP-SERVER-CL003）：`hs -p 8099 [path]` 不再误报 `Unknown command: 8099`，按原顺序重组给 `start`
- help / skills/hs-cli / README 中 `-d` 文案改为如实描述（服务已分离，CLI 随后**前台 tail 日志**；真正非阻塞用 `--url` 或 `--json`）

### Notes
- 1.3.1（2026-09-04）为展示名 patch 发布，**未单列 CHANGELOG 条目**（版本链承认既有漂移，F-12）
- `hs list --port` 语义不变（布尔开关，仅打印端口号）；指定启动端口请用 `hs start -p <N>`
- 端口探测「假占用」（`is_port_in_use` 裸 bind 无 SO_REUSEADDR，CL003 观察项 O1）**已在 1.4.0 内修复**（见 `### Fixed` 第一条）；实现口径由「纯 socket 探测」调整为「macOS 以 lsof LISTEN 为准 + socket 回退」（CL004 实施偏差，理由见设计件 §13）

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
