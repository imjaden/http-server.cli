# Changelog

## 1.5.1 (2026-10-15)

### Fixed
- **web --domain 注入在 hs 型 cmd 上必挂 + 启动横幅假成功**（HTTP-SERVER-CL008）— CL007 fail-closed 升级后，`hs web` 无条件注入 `--domain` 对 hs 型 cmd 成为故障源（hs 自身无 `--domain`，注入必 exit 2）；且 cmd 失败时仍打印 `✅` 成功横幅。修正：
  - **A1 横幅修正**：cmd 退出码非 0 → stderr `❌ Service '<name>' failed (exit N)`；✅ 仅 exit_code=0；JSON 信封字段零变更
  - **A2 源头防呆**：`hs web add/update` 在 `use_domain=true` + hs 型 cmd 时 fail-closed（exit 2）；`--force-domain` 逃生开关
  - **A3 存量止血**：`hs web list/show` 对 hs 型 + use_domain=true 条目打 `⚠️` 风险标记；JSON 信封新增 `domain_risk` 字段
  - **A4 文档**：--domain 语义边界补全（hs 型 cmd domain 由 config.json 统一决定）

### Fixed（round-2 复审修订，评审 HM-CL008-SEC-001/002/003）
- **SEC-001 `_is_hs_cmd` fail-open 收口** — 旧实现依赖 `shutil.which('hs')` 比对绝对路径，PATH 无 hs 即静默放行（`~/bin/hs` / `./hs` / `HS` 既不拦也不标记）。改为 `os.path.expanduser` + `basename` 判定（大小写不敏感，覆盖 `hs`/`HS`/`./hs`/`~/bin/hs`/任意绝对路径/symlink 名），不依赖 PATH；`_web_help` 与 `skills/hs-web/SKILL.md` 同步收窄「hs 型 cmd」表述（明确不识别 `env hs` / `command hs` / `sh -c 'hs …'`）
- **SEC-002 update 按有效态判定** — 旧判据只看「本次是否传 `--domain`」，`hs web update <name> --cmd '<hs …>'` 可在既有 `use_domain=true` 条目上静默重建风险态（rc=0）。改为先算 effective（`--no-domain` 清除优先 → `--domain` → 既有态）再判定；OBS-002「`--no-domain --domain` 同给提示矛盾」随之收敛
- **SEC-003 历史 harness 白名单正则化** — 版本 1.5.0→1.5.1 未同步 `scripts/*-verify.py` 版本/计数枚举 → `cl005-verify.py::a12_sync`、`port-flag-verify.py::a14`、`port-residual-verify.py::a9_sync_greps` 复跑即红（证据链断）。三处改正则（`v\d+\.\d+\.\d+` / `^version: \d+\.\d+\.\d+` / `\d{2} 个测试模块，\d{3} 个测试用例`），一次性消除此类漂移

### Changed
- **Help 打印规范化（hm-style grouped help）**— 参考治理规范 §8（hermes-manager/skills-governance/cli-architecture-patterns.md）+ `hm help` / `dk help` 实例，`hs help` 及子命令 help（web / dashboard / mcp / bookmark）统一改造：`=`-rule + `📖 名称 · 版本(发布日) · 别名` 标题 + 【功能概述】 + `── 分组 ──` 两行条目（name+usage / description 缩进）+ `── 选项 ──` + `📋 示例:`；危险命令（kill / kill-all / prune）⚠️ 标记；`hs version` 保持机器可读格式不变

### Notes
- 新增测试模块 `tests/test_cl008_web_domain_guard.py`（31 用例，含 round-2 SEC-001/002 回归）+ `tests/test_help_format.py`（10 用例）；全量 **691 passed**
- round-2 复审面复跑：`cl005-verify.py --only A12` PASS；`port-flag-verify.py` 31/31 PASS（含 A14）；`port-residual-verify.py` 13/13 PASS（含 A9）
- 兼容性：JSON 信封字段零变更（只增 `domain_risk`）；退出码语义不变
- 设计件：`documents/http-server-cl008-web-domain-guard-design-v1.0-20261015.md`；审计件：`documents/review/http-server-cli-cl008-audit-v1.0-20261015.md`

## 1.5.0 (2026-10-13)

### Changed
- **参数面加固 — 未知 flag 不再「告警后照常执行」**（HTTP-SERVER-CL007 / 转交自 script-miner ops）— 12 分钟内两次真实触发：`hs prune --help` 被当「未知参数（已忽略）」后**照删** registry 沉积记录；裸 `hs`（想读用法）在 cwd **凭空起服务**。收紧规则：
  - **A1 fail-closed**：写 / 破坏性命令（`start` / `kill` / `kill-all` / `prune` / `web add·update·remove·<name>` / `mcp` / `dashboard` / `bookmark add·update·remove` / `set`）遇未知 flag 或多余位置参数 → stderr 报错 + **exit 2，不执行任何副作用**（`hs <dir> --prot 8080` 这类近形 typo 不再静默起服务）
  - **`-h/--help`、`-v/--version` 在任意位置识别**：`hs prune --help` 现打印用法 exit 0（原实现因顶层 `REMAINDER` 把 `--help` 吞进子命令 args，既不走全局 help 分支、又被当未知参数忽略而照常执行）
  - **A2**：裸 `hs`（无路径 / 无命令 / 无参数）→ 打印用法 **exit 2**，不再默认在当前目录起服务；显式 `hs .` / `hs <dir>` 行为不变
  - **A4 只读命令不变**：`list` / `status` / `history` / `config` / `search` / `bookmark list·show` / `web list·show` 遇未知 flag 仍告警放行（rc 不变，D6 口径）；`--json` 既有字段与退出码语义不变
  - 写命令 + `--json` 遇未知 flag：stdout 输出 `{"success": false, "command": ..., "error": "unrecognized arguments: ..."}` 信封，exit 2

### Added
- **`hs prune` 汇总行**（A3）— 输出末尾新增 `📦 Kept N registry record(s)`（已删 N / 保留 N）；`hs prune --json` 新增 additive 字段 `kept`
- 复跑 harness `scripts/cl007-verify.py`（AC A1–A4，10 断言，`HS_DATA_DIR` 沙箱）

### Notes
- 新增测试模块 `tests/test_cl007_argsurface.py`（20 用例）；全量 **650 passed**（+20）
- 兼容性：本次只收紧**异常输入**路径；合法调用与既有 JSON 字段、退出码语义均不变。历史 harness 版本断言放宽至 1.5.0（`cl005-verify.py` / `port-flag-verify.py` A14 / `port-residual-verify.py`），`port-flag-verify.py` A6 期望随 A1 收紧更新为 rc=2
- 设计件：`documents/http-server-cl007-argsurface-hardening-design-v1.0-20261013.md`
- 本仓**未 push**（用户放行后再推）

## 1.4.2 (2026-10-13)

### Fixed
- **`hs status <port>` 口径缺陷 — 陈旧 registry 记录压过存活实例**（HTTP-SERVER-CL006）— 同端口存在多条登记（历史沉积）时，`hs status` 按端口取**首条**命中、而 `hs list` 做存活过滤，导致同一端口结论自相矛盾（`hs status` 报 `❌ stopped`（陈旧 pid / 错拼 path）却又 `Port: in use`，使用者据此会误判「服务已停」）：
  - **D1 选条口径**：`Registry.find(port=)` 现按「存活优先 + 最近 `started_at`」选择，`hs status` / `hs kill` / dashboard 与 `hs list` 结论一致（`prefer_alive=False` 保留旧「首个命中」语义作逃生口）
  - **D2 记账目标**：`Registry.touch(port)` 与 60s 批量刷盘 `_flush_access_cache()` 均写入**存活实例**记录，不再把 `last_access_at` 刷到同端口陈旧沉积条上

### Added
- **`hs prune [-n|--dry-run] [--json]`**（HTTP-SERVER-CL006 / A4）— 显式清理 `registry.json` 中 pid 已不存活的沉积登记；`list` / `status` / `start` 等默认命令**不删记录**。`history.json` 为独立文件，语义不受影响
- **`hs status --json` 新增字段** `record_status`（`live` / `stale-record`）；陈旧记录且端口被他人占用时附 `occupants`（占用者 pid 列表）—— additive
- **`hs list --json` 新增字段** `stale_count`（被过滤的沉积条数）—— additive
- 复跑 harness `scripts/cl006-verify.py`（AC A1–A4，16 断言）

### Changed
- `hs list` / `hs status <port>` 输出：不再出现「`❌ stopped` + `Port: in use`」矛盾组合 —— 陈旧记录显式标注 `Status:  stale-record`；端口被他人占用时 `Port:  occupied by PID <n>（非本记录）`，端口空闲则 `Port:  free`
- 同端口多条时展示层按「存活优先 + 最近 `started_at`」保留一条；非 JSON `hs list` 末尾附沉积条数提示（`N stale registry record(s) hidden — run hs prune to clean`）
- `registry.json` 结构 `{"servers":[...]}` 不变（旧文件可读；未新增/删除字段）

### Notes
- 新增测试模块 `tests/test_cl006_status_registry.py`（25 用例）；全量 **629 passed**（+25）
- 已知环境相关红 1（修前既有，与本次改动无关）：`test_cl005_hardening.py::test_t26` 断言 `CLOCK_MONOTONIC > 1e4`（uptime 量级），本机 uptime 不足 1e4 秒
- 设计件：`documents/http-server-cl006-registry-stale-design-v1.0-20261013.md`
- 本仓**未 push**（用户放行后再推）

## 1.4.1 (2026-09-23)

### Added
- **目录级启动锁**（HTTP-SERVER-CL005）— 同一目录并发启动（含 `hs index.html` 与 `hs <dir>` 混用）在临界区互斥，杜绝「先 Popen 后登记」窗口内的重复启动与孤儿 runner：
  - 锁文件 `~/.http-server.cli/locks/<sha1(abs_path)[:16]>.json`（`O_CREAT|O_EXCL` 原子获取，`finally` 释放 + 归属校验仅删本进程锁）
  - stale 四判据：内容不可解析且写入龄 ≥1.0s · pid 非活 · pid 活但命令行非本 CLI（pid 复用）· 持锁龄 > `LOCK_TTL=30s`；**负龄不判 stale**（跨重启/时钟异常交 pid 活性兜底）
  - 等待路径 `LOCK_WAIT=3s` / `LOCK_POLL=0.2s`：期间该目录登记就绪 ⇒ 幂等命中退出 0；锁已释放 ⇒ 重试整链；超时 ⇒ fail-closed 退出 1（提示持锁 pid）
  - 用法错误优先：路径不存在 / index 非法 / `-p` 越界仍按原语义 exit 1 / 2，不被锁等待掩盖
  - 计时基准 `time.clock_gettime(CLOCK_MONOTONIC)`（跨进程可比；`time.monotonic()` 在 py3.9 实测跨进程近零且非单调，会导致活锁被误判 stale）
- **`HS_DATA_DIR` 数据目录覆盖**（HTTP-SERVER-CL005 收口 / O11）— 数据目录可用环境变量指向任意路径（测试 / CI 隔离）；子进程继承该变量，daemon 子进程的登记不再回写真实 `~/.http-server.cli`（未设时行为不变）
- **锁常量环境变量覆盖**（HTTP-SERVER-CL005 收口 / O10）— `HS_LOCK_TTL` / `HS_LOCK_WAIT` / `HS_LOCK_POLL` / `HS_LOCK_WRITE_GRACE` 可覆盖默认值（重负载 / 慢盘场景调参）；未设或非法值一律退回默认（默认行为不变）
- **派发件模板** `scripts/review-dispatch.sh`（HTTP-SERVER-CL005 / D4）— 由「编号 + 项目 + 步骤 + 日期」唯一推导 派发壳/日志/用量 三路径；派发前校验提示词非空、派发后校验 usage-file 非空，生成物先过 `bash -n`

### Fixed
- **`eprint()` 实际写 stdout**（HTTP-SERVER-CL005）— 内部打印函数名为 stderr 系列却写 stdout，导致错误/警告文案污染 `--json` 输出与下游管道；现 `eprint()` 写 stderr、查询类结果走新增的 `print_msg()`（stdout），并逐调用点固化通道契约（63 处：stdout 23 / stderr 38 / 三态分叉 2）
- **`hs web` 错误分支退出 0**（HTTP-SERVER-CL005）— `hs web add/list/show/remove/update/<name>` 的用法错误与运行期失败此前一律退出 0（假成功）；现用法错误（缺必填 / 子命令名冲突 / 名已存在 / 非法 url·open / 无更新参数）退出 2，运行期失败（名不存在 / services 文件损坏 / 执行命令退出码非 0）退出 1；并补 `hs web <name>` 的命令失败分支（修前 rc=0 且 JSON `success=true`）

- **`hs set` / `hs search` 用法错误退出 0**（HTTP-SERVER-CL005 收口 / O7）— 缺参 / 端口越界 / 端口非数字 / domain 字符集非法 / 未知配置键 / `hs search` 缺 keyword 现统一退出 `2`（`--json` 下仍先输出可解析失败信封再退出）
- **`hs dashboard` / `hs mcp` 的 `stop`・`restart` 未运行退出 0**（HTTP-SERVER-CL005 收口 / O8）— 现退出 `1`（运行期失败）；`status` 作为查询保持 `0`（文案仍在 stdout）；`--json` 失败信封不变
- **`tests/test_dashboard.py::TestDaemonMode` 泄漏 dashboard 守护进程**（HTTP-SERVER-CL005 收口 / O11）— 用例的 daemon 子进程（独立会话）在测试结束后残留为孤儿，且会在真实 `~/.http-server.cli/registry-managed.json` 留下 stale 登记；现用例 ① 就绪确认后自行回收（SIGTERM → SIGKILL 进程组）② 通过 `HS_DATA_DIR` 把子进程数据目录指向临时目录（登记写入临时目录）③ 断言「无存活进程 + 端口已释放 + 子进程登记落在临时目录」

### Changed
- 锁语义：`--daemon` tail / `foreground` 长驻期间由首实例持有锁，第二实例在该期间命中「已就绪」快径 ⇒ 幂等退出 0（不判忙、不重复启动）
- **依赖 stderr 捕获的脚本请注意**：错误/警告文案通道由 stdout 改为 stderr（stdout 仅剩命令主产物：URL、清单、JSON 信封）

### Notes
- 1.4.0（CL003 + CL004）与 1.4.1（CL005）均**尚未发布 PyPI**，可按同批发布
- 新增测试模块 `tests/test_cl005_hardening.py`（47 用例：T1–T28b + O7/O8/O9/O10 收口组）；`tests/test_dashboard.py` daemon 用例补回收 + 数据目录隔离断言；全量 **605 passed**
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
