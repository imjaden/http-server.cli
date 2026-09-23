# http-server — Features

> 零依赖 Python HTTP 服务 CLI。一键启动本地静态文件服务，忘记端口。
>
> 文件命名: 固定为 `features.md`，小写，无版本号。
>
> 适用: 风格 B 文件（无版本号，持续更新），存放在项目根目录。
>
> 功能契约事实源: `http-server.cli.spec.yaml`（OpenSpec 格式，review 审计依据）。

## CLI 命令

1. `hs start [path]` — 启动服务，选项: `-o` 打开浏览器 / `-d` 分离运行（前台 tail 日志）/ `-f` 前台 / `-i <file>` 首页 / `-p <port>` 指定端口（1024-65535；被占用即失败退出，不漂移）✅ — `documents/hs-cli-design-v1.0-20260624.md`
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
14. `hs prompt [<skill>]` — 输出技能使用说明（AI 对接）✅

## 书签系统

1. `hs bookmark add <name> [path] [-i index] [--force] [--json]` — 注册书签 ✅
2. `hs bookmark update <name> [path] [-i index] [--json]` — 更新书签 ✅
3. `hs bookmark list [--json]` — 列出所有书签 ✅
4. `hs bookmark show <name> [--json]` — 查看书签详情 ✅
5. `hs bookmark remove <name> [--json]` — 删除书签 ✅
6. (path, index_page) 组合键唯一 — 同项目不同页面可注册多个书签；`--force` 覆盖组合键冲突（不覆盖 name 冲突）✅
7. 通配符 index 解析 — `-i 'snapshots/*.html'` 存原始 pattern，运行时取 `max(mtime)` ✅
8. 损坏检测 — 非空文件 JSON 解析失败抛出 `DataCorruptionError` ✅
9. 关联文档: `documents/bookmark-feature-design-v1.1-20250715.md` / `documents/bookmark-multi-page-design-v1.1-20260819.md`

## Web 服务注册（hs web）

1. `hs web add <name> --cmd '<cmd>' [--url <url>] [--open cmd|url|both|none] [--domain]` — 注册任意 CLI 启动命令（跨项目，如 `dk server start --daemon --open`）✅ — HTTP-SERVER-CL001
2. `hs web update <name> [--cmd] [--url] [--open] [--domain|--no-domain]` — 更新（`--url ''` / `--no-domain` 清除）✅
3. `hs web list [--json]` — 列出所有注册 ✅
4. `hs web show <name> [--json]` — 查看详情 ✅
5. `hs web remove <name> [--json]` — 删除 ✅
6. `hs web <name> [--no-probe]` — 执行：url 可达→直接访问（幂等，不执行 cmd）；不可达/无 url→执行启动命令；`--no-probe` 跳过探测强制重启 ✅
7. open 策略 — `url`（默认，web 统一开浏览器）/ `cmd`（命令自带 -o）/ `both` / `none` ✅
8. url 可选 — 固定端口填 url（启动后 wait 就绪再 open）；动态端口不填（启动前未知端口，直接透传）✅
9. `--domain` 布尔 — 执行时把 config.domain 注入 cmd 末尾（`cmd ... --domain "<domain>"`，如 `dk server start --daemon --open` → 追加 `--domain "jaden.local"`）；json 输出含 `cmd_effective` ✅ — HTTP-SERVER-CL002
10. 名称校验复用 bookmark 规则 `[a-zA-Z0-9][a-zA-Z0-9._-]*` + web 子命令名（add/update/list/show/remove/help）冲突拦截 ✅ — SEC-022-1
11. 损坏检测 — 非空 JSON 语法错 / 合法 JSON 非 dict / services 非 list → `DataCorruptionError`（SEC-022-2）；bookmark 同规则 ✅
12. `hs web add/update --port <N> | --no-port` — 端口注入声明（执行期在 `--domain` 之后追加 `--port <N>`）；用法错误（越界 / 互斥）退出 2 ✅ — HTTP-SERVER-CL003 + CL004
13. 全局薄壳 `~/.local/bin/web` 转发 — 达成 `web <name>` 语法 ✅
14. 推广 — skills/hs-web（命令速查 + 其他模块接入指南 + 真实实例 daily.checker/jaden.tech/线上站点），`hs prompt hs-web` 输出，镜像 ~/.hermes/profiles/ops/skills/devops/hs-web/ ✅ — HTTP-SERVER-CL002
15. `hs web` 退出码三态 — 用法错误 2（缺必填 / 子命令名冲突 / 名已存在 / 非法 url·open / 无更新参数）/ 运行期失败 1（名不存在 / services 损坏 / 执行命令退出码非 0）/ 成功与已运行幂等 0 ✅ — HTTP-SERVER-CL005
16. 关联文档: HTTP-SERVER-CL001 review (documents/review/http-server-cli-web-registration-audit-v1.0-20260827.md) / HTTP-SERVER-CL002 review (documents/review/http-server-cli-cl002-web-domain-promo-audit-v1.0-20260827.md, documents/review/http-server-cli-cl002-sec023-1-domain-validation-rereview-v1.1-20260827.md)

## HTTP 服务

1. 零外部依赖 — 仅 Python 3.12 标准库 ✅
2. Range 请求支持 — 206 Partial Content，视频拖动进度条可用 ✅ — dev skill: `~/.hermes/profiles/dev/skills/software-development/http-server-cli-dev/references/range-request-support.md`
3. MIME 类型自动识别 — 基于文件扩展名 ✅
4. 智能首页 — 无 index.html 时自动重定向到最近修改的 html ✅
5. 自定义首页 — `-i <file>` 指定任意首页文件（支持子目录路径如 `build/index.html`）✅
6. HTML 文件路径友好 — `hs /path/file.html` 自动提取目录作为服务目录 ✅

## 服务管理

1. 自动端口分配 — 默认 8080，冲突自动递增 ✅
2. 指定端口 — `hs start -p <port>`（CLI 优先于 config.port 且一次性不回写；被占用 / 保留端口 8180/8181 fail-closed 不漂移）✅ — HTTP-SERVER-CL003
3. 端口检测 — macOS 以 lsof LISTEN 集合为准（真实监听者，含 127.0.0.1 / LAN 绑定）；非 macOS 或 lsof 不可用时回退 IPv4 + IPv6 双栈 bind 探测（开 `SO_REUSEADDR`，残留态 `TIME_WAIT` 不误判）✅ — HTTP-SERVER-CL004（原 `documents/ports-detect-design-v1.1-20250716.md`）
4. 进程资源监控 — CPU%、内存 MB、运行时长 ✅
5. 进程组管理 — daemon 模式 `os.killpg` 防孤儿进程 ✅
6. 原子写入 — 防多进程并发脏读 ✅
7. 智能历史 — `hs history` 自动过滤系统临时目录 ✅
8. 文件路径 kill — `hs kill ~/my-site` 按路径关闭 ✅
9. HTML 文件 kill — `hs kill file.html` 自动解析父目录 ✅
10. 退出码三态 — 0 成功（含幂等）/ 1 运行期失败（路径不存在、端口不可用、`hs kill` 未注册端口）/ 2 用法错误 ✅ — HTTP-SERVER-CL003
11. 未识别参数告警 — stderr 提示「未识别参数（已忽略）」+ 近形引导（stdout / JSON 信封零污染）✅ — HTTP-SERVER-CL003
12. 顶层 `-p` 归位 — `hs -p 8099 [path]` 不再误报 `Unknown command` ✅ — HTTP-SERVER-CL003
13. 顶层取值型 flag 归位 — `hs -i <CWD 存在的文件> -p <N> <dir>` 按参数形态优先重组（`-i` 与 `<dir>` 均保留；`-o/-d/-f` 不受影响）✅ — HTTP-SERVER-CL004
14. 启动竞态防护 — 同目录并发启动 ≤1.0s 宽限 + 归属校验（token 精确匹配 `runner.py` + 目录）；判 stale 先终止进程组再清登记，防孤儿进程与误杀；stale 文案三态一律 stderr ✅ — HTTP-SERVER-CL004
15. 目录级启动锁 — 同目录并发启动临界区互斥（`~/.http-server.cli/locks/<sha1(路径)[:16]>.json`，O_CREAT|O_EXCL 原子获取 + finally 释放 + 归属校验仅删本进程锁）；stale 四判据（不可解析且写入龄≥1.0s / pid 死 / pid 复用 / 龄>30s）+ 负龄不判 stale；等待 ≤3.0s 就绪即幂等、超时 fail-closed；用法错误（路径不存在 / `-p` 越界）优先于锁 ✅ — HTTP-SERVER-CL005
16. 输出通道契约 — `eprint()` → stderr、`print_msg()` → stdout；63 处调用点逐点固化（stdout 23 / stderr 38 / 三态分叉 2）；机器模式 stdout 仅 JSON 信封或单行 URL ✅ — HTTP-SERVER-CL005

## 数据持久化

1. `registry.json` — 运行中服务注册（port/path/pid/domain/daemon/started_at/last_access_at/index_page）✅
2. `history.json` — 历史记录（started_at/ended_at/memory_mb）✅
3. `config.json` — 默认配置（port/domain）✅
4. `bookmarks.json` — 书签持久化 ✅
5. `services.json` — Web 服务注册持久化（name/cmd/url/open/created_at）✅
6. `logs/` — 按端口分日志文件 ✅
7. 数据目录: `~/.http-server.cli/`

## Web Dashboard

1. 图形化管理面板 — 端口 8180，`hs dashboard -o` 打开 ✅ — `documents/hs-dashboard-design-v2.0-20260629.md`
2. `hs dashboard [stop|status|restart] [--json]` — 管理仪表盘 ✅
3. 中英文语言切换 — 🇨🇳 `/?lang=zh` ↔ 🇺🇸 `/en`，右上角悬浮 pill ✅
4. 工具栏 — 60s 倒计时自动刷新 / 刷新按钮 / Kill All 一键关闭 ✅
5. 服务器表格 — URL(Port) | Health | Status | CPU | Memory | Last Access | Action ✅
6. 健康检查探活 — 🟢/🟡/🔴 圆点标识 HTTP 响应状态 ✅
7. 搜索过滤框 — 实例 >10 时自动显示，实时按端口/路径关键字过滤 ✅
8. 状态弹框 — 端口/路径/PID/内存/启动时间/日志路径/最近访问 + 最近 50 行日志 ✅
9. 一键复制 URL — 📋 按钮 ✅
10. 全局异常捕捉 — `window.onerror` 覆盖层弹框显示完整 stack trace ✅
11. REST API — list / status / kill / kill-all / ping / log / info ✅

## MCP 集成

1. `hs mcp` — 启动 MCP Server（后台 SSE），AI Agent 集成 ✅ — `documents/hs-mcp-design-v1.0-20260624.md`
2. `hs mcp stop [--json]` — 停止 MCP 服务 ✅
3. `hs mcp status [--json]` — 查看 MCP 状态 ✅
4. `hs mcp --config` — 输出 mcpServers 接入配置（stdio，Claude Code/Cursor/Hermes 一行接入）✅
5. JSON-RPC 2.0 协议 — stdio/SSE 传输，11 个工具（6 管理：hs_list/status/start/kill/kill_all/config；5 数据：hs_bookmark_list/add/remove、hs_history、hs_search）✅
6. MCP Resources 3 项（只读）— hs://registry / hs://bookmarks / hs://config ✅
7. 零外部依赖 — 纯标准库实现 MCP 协议 ✅

## AI 对接

1. `hs prompt [<skill>]` — 输出 skills/ 使用说明（hs-cli/hs-bookmark/hs-mcp/hs-dashboard/ai-interchange/hs-web，--brief/--json）✅ — `documents/hs-ai-integration-design-v1.0-20260825.md`
2. skills/ai-interchange — AI 互通数据对接方法论（三通道框架 + hs 实证 + 验收清单），供其他项目核对复用 ✅ — CL-SEC21
3. skills/hs-web — 跨项目 web 服务注册推广（命令速查 + 其他模块接入指南 + 真实实例），`hs prompt hs-web` 输出，镜像 ~/.hermes/profiles/ops/skills/devops/hs-web/ ✅ — HTTP-SERVER-CL002
4. 批次二（暂缓）— hs export / hs doctor 🚧

## 配置管理

1. `hs config [--json]` — 查看当前配置 ✅
2. `hs set port <value>` — 修改默认端口（1024-65535）✅
3. `hs set domain <value>` — 修改绑定域名 ✅

## 测试

1. 17 个测试模块，590 个测试用例 ✅ — `documents/test-design-spec-v1.2-20260702.md`
2. `conftest.py` — autouse 数据隔离 + monkeypatch 路径注入 ✅
3. 集成测试模式 — mock `_COMMANDS` / `ensure_storage`，set `sys.argv`，catch `SystemExit` ✅

## 构建 & 发布

1. `release-local.sh` — 本地安装（`--editable` / `--versions`）✅
2. `release-pypi.sh` — PyPI 发布（`--production` / `--versions`）✅
3. `scripts/review-dispatch.sh` — 审查/审计派发件模板（编号+项目+步骤+日期 → 派发壳/日志/用量三路径唯一推导；提示词非空 + usage-file 非空自校验；生成物过 `bash -n`）✅ — HTTP-SERVER-CL005
4. `setup.py` — 入口点 `hs = http_server_cli.cli:main` ✅

## 待定/规划

1. `hs mcp` 支持更多传输协议（如 Streamable HTTP）🚧
2. `hs dashboard` 暗色/亮色主题切换 🚧 — `documents/light-dark-theme-design-v1.0-20260706.md`
3. `hs dashboard` GitHub Corner 链接 🚧 — `documents/github-corner-link-design-v1.0-20260706.md`
4. GitHub CI/CD 流水线 🚧 — `documents/github-ci-cd-design-v1.1-20260701.md`
