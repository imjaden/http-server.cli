# HTTP-SERVER-CL005 设计 v1.0 — CL004 批遗留四项收口（输出通道 / web 退出码 / 启动锁 / 派发件）

- 件号：`documents/http-server-cl005-hardening-design-v1.0-20260923.md`
- 目标仓：`/Users/jadenli/CodeSpace/http-server.cli`（单仓闭环，禁跨仓改动）
- 上游依据：
  - `documents/http-server-port-residual-design-v1.4-20260922.md` §13.7 观察项 O1/O3/O4/O5
  - `documents/review/http-server-cli-cl004-audit-v1.0-20260922.md`（🟢 AUD-1 / OBS-1 / OBS-2）
  - `documents/review/http-server-cli-cl004-ops-verify-v1.0-20260922.md`（13/13 PASS，残留 0）
  - draft `cache/draft/TODO-20260922.md` 条目「CL004 批遗留四项收口」（闭环: HTTP-SERVER-CL005）
- 交付版本口径：**1.4.1**（见 D9）
- 模式：**独立模式 1A 全自动**（用户 2026-09-23 指令：本件使用独立模式全自动实施整个 1A 闭环）

---

## 0 范围与非目标

**范围（四项，均为 CL004 审计/收尾登记项）**

| 编号 | 内容 | 性质 |
|:--|:--|:--|
| O1 | `utils.eprint()` 名不副实（实写 stdout）⇒ 误用即污染 `--json` 信封 | 输出通道契约 |
| O3 | `hs web` 其余 error 分支 `return`（rc=0）⇒ 脚本无法以退出码判失败 | 退出码口径 |
| O5 | 无启动锁 ⇒ 同目录并发 ≥3 次启动仍可能残留孤儿 runner | 并发正确性 |
| O6 | 评审派发壳手工派生 ⇒ usage-file 缺失/跨轮覆盖（CL004 复审轮 1/2 无用量数据） | 流程件 |

**非目标（明确不做）**

- 不改 `hs set port` 语义（起始端口 vs 锁定端口，O2 既有语义）
- 不改 registry 结构/字段、不改 `hs list --port` 语义、不改保留端口 8180/8181 硬拦
- 不重排 CL003/CL004 已定案的 `-p` 校验顺序链
- 不新增 CLI 命令面（`hs web` 仅改退出码，不加参数）
- 不修复 `is_port_in_use` 的 lsof 降级路径跨地址漏判（OBS-2 已声明为降级路径）
- 不做 PyPI 发布（Step 7 待用户放行）

---

## 1 现状与缺陷（实测证据）

### 1.1 O1 `eprint()` 实写 stdout

```
src/http_server_cli/utils.py:33
def eprint(msg: str, emoji: str = '') -> None:
    """智能打印，自动匹配 Emoji 前缀"""
    if emoji: print(f'{emoji} {msg}')     # ← 无 file= ⇒ stdout
    else:     print(msg)
```

- 调用点 **64 处**：`cli.py` 28 / `server.py` 32 / `utils.py` 4。
- 已发生的真实事故：CL004 评审 F-1 —— stale 文案经 `eprint` 写 stdout，`hs <dir> --json` 触发 stale 时 stdout 被污染，`json.loads` 抛 `JSONDecodeError`。CL004 只在**新增**文案处直写 `file=sys.stderr`，函数本身未改。
- 现状分叉：同一类「错误/警告」文案在不同命令里通道不一致（部分 `print(..., file=sys.stderr)`，部分 `eprint(...)` 到 stdout）——如 `server.py:184`（stderr）、`server.py` index_page 校验失败分支（`eprint(err, '❌')` → stdout）。
- 既有测试依赖旧行为：`tests/test_cli.py:1052` 注释「`_handle_set` 错误经 eprint 输出到 stdout（项目惯例）」。

### 1.2 O3 `hs web` 退出码

CL004 已统一 `--port` 越界与 `--port/--no-port` 互斥两处 → exit 2。其余 error 分支仍 `return`（rc=0）：

| 分支 | 行 | 现有通道 | 现有 rc | 应为 |
|:--|:--|:--|:--|:--|
| `add` 缺 `--cmd` | `cli.py:1391-1397` | stderr | 0 | 2（用法） |
| `add` 名非法 / 与内置命令冲突 | 1399-1412 | stderr | 0 | 2 |
| `add` `--open` 非法 / `--url` 非法 | 1415-1428 | stderr | 0 | 2 |
| `add`/`update` services 损坏 / store 异常 | 1453-… | stderr | 0 | 1（运行期） |
| `list` services 损坏 | `_web_list` | stderr | 0 | 1 |
| `show` 名不存在 | 1572-1577 | stderr | 0 | 1 |
| `remove` 名不存在 | 1621-1633 | stderr | 0 | 1 |
| `update` 名不存在 / 校验失败 | 1665-1715 | stderr | 0 | 2 用法 / 1 运行期 |
| `web` 无子命令（`_web_help`） | `_web_run:1776` | stdout | 0 | 0（help 语义，保持） |

对照：`_web_run` 名不存在已 `sys.exit(1)`（`cli.py:1799`）⇒ 本批是**补齐一致性**，非新语义。参照口径 = CL003 D14 三态：`0` 成功/幂等 · `1` 运行期失败 · `2` 用法错误。

### 1.3 O5 无启动锁

- 现状：`ServerManager.start()` 靠「registry 查重 + ≤1.0s 宽限轮询（`START_GRACE_INTERVAL=0.2 × START_GRACE_ATTEMPTS=5`）+ R-6 归属校验 + R-7 监听者核验」收窄窗口，**进程间无互斥**。
- 实测（CL004 ops 核查 A4）：2 次并发（间隔 100ms）已达标（registry 1 条 + pid 同一性相等）；但基线（`ef125b3`）5 次双击样本中 **4 次**出现 listener 集合 ≠ registry 集合 ⇒ 竞态窗口真实存在，≥3 并发无保护。
- 影响：孤儿 runner 占端口；`hs kill` 只杀登记 pid ⇒ 孤儿需手工 `lsof`+kill；`hs list` 与真实监听不一致。

### 1.4 O6 派发件

- 现状：`cache/review-prep/dispatch-http-server.cli-cl00{3,4}-*.sh` 共 9 个手写/派生壳（每轮一个），`LOG/PROMPT/USAGE` 三行靠人肉替换。
- 已发生：CL004 复审轮 1/2 **无 usage-file** ⇒ 闭环报告该步骤用量只能归一（复盘 O6 登记）；同类风险在 skill pitfall #19 已记（派生时大小写不匹配导致 LOG/USAGE 指回上一轮）。
- 影响：跨 profile 成本/用量不可核对；多轮评审日志互相覆盖。

---

## 2 决策

### D1 输出通道：`eprint` 语义改为 stderr，正常输出走新名 `print_msg`

- `utils.eprint(msg, emoji='')` → **一律 stderr**（签名不变，语义纠正；外部未导入该函数，仓内仅 cli/server/utils 使用）。
- 新增 `utils.print_msg(msg, emoji='')` → **stdout**（人类可读正常输出）。
- 迁移规则（D1b，逐调用点判定，判定记录写进 §4.1 表）：
  | 归类 | 通道 | 例 |
  |:--|:--|:--|
  | 命令正常产物 | stdout | `hs list`/`config`/`history`/`web list` 清单、help 文本、`--url` 的 URL、启动成功信息块、`🛑 Terminated PID` 结果 |
  | 失败/警告/被忽略/清理动作 | stderr | 端口占用、路径不存在、stale 清理、未识别参数、校验失败、`eprint(err,'❌')` 各分支 |
  | JSON/URL 机器模式 | 仅 `json_output` 写 stdout；其余（含人类提示）一律 stderr | `hs <dir> --json` 只能有信封 |
- 兼容：`eprint` 名字保留（不改名以免大范围 churn），但**所有**原调点必须显式复核通道；`print_msg` 是新增名。
- 收益：`--json` 信封污染类缺陷在函数层面消失（不再依赖「新增文案记得写 file=」）。

### D2 `hs web` 退出码三态统一

- 用法错误（缺参、非法值、互斥、名非法、冲突、不知名子命令）→ `sys.exit(2)`。
- 运行期失败（services 损坏、store 读写异常、名不存在、探测失败且 cmd 失败）→ `sys.exit(1)`。
- 成功/幂等 → 0。`hs web` 无子命令 → 打印 help + 0（保持）。
- JSON 模式：先 `json_output(False, cmd, error=...)` 再 `sys.exit(code)` ⇒ 机器可读 + 退出码可判。
- 与 `hs start` 口径一致（CL003 D14）；README/spec 增补「退出码」小节。

### D3 目录级启动锁（新增机制）

- 目的：同目录并发启动**至多一个赢家**，其余要么幂等返回既有服务、要么 fail-closed 报「正在启动」。
- 锁文件：`~/.http-server.cli/locks/<sha1(abs_path)[:16]>.json`，内容 `{path, pid, started_at, host}`；目录 `locks/` 随 `ensure_storage()` 建立。
- 获取：`os.open(lock, O_CREAT|O_EXCL|O_WRONLY)` 原子创建 → 写内容 → 关闭 fd（文件保留为锁）。
  - 成功 ⇒ 进入既有启动流程；**`finally` 释放**（删除锁文件，best-effort）。
- 失败 ⇒ 读锁文件判 stale：
  | 判据 | 结论 |
  |:--|:--|
  | 锁文件不可解析 / 无 pid | stale ⇒ 删锁重试 1 次 |
  | holder pid 不存活（`is_process_alive`） | stale ⇒ 删锁重试 1 次 |
  | 锁龄 > `LOCK_TTL=30s` | stale ⇒ 删锁重试 1 次 |
  | holder pid 存活且命令行**不含**本 CLI 特征（`http_server_cli` 或 basename `hs`，token 精确匹配，R-6 同口径） | stale ⇒ 删锁重试 1 次 |
  | holder pid 存活 + 命令行命中 + 未过期 | **有效锁** ⇒ 等待路径 |
- 等待路径（有效锁）：轮询 ≤ `LOCK_WAIT=3.0s`（0.2s×15）：
  - 期间 registry 出现该 `abs_path` 条目且端口监听 ⇒ **幂等命中**（复用 CL004 幂等分支，rc=0）
  - 超时仍无 ⇒ stderr「另一实例正在启动（pid …, 路径 …），请稍后重试或先 `hs kill <path>`」+ `return False` ⇒ CLI `exit 1`（fail-closed，**不**重复启动）
- 崩溃遗留：TTL + pid 活性双兜底（无 pid 复用风险时 pid 判据即命中；pid 复用由 token 校验拦截）。
- 与既有机制的关系：锁在 `start()` **最前**（路径解析后、index_page 校验前）获取，`finally` 释放；不改变既有顺序链语义（锁是横切保护层）。`--json`/`--url`/`daemon`/`foreground` 各模式共用同一锁。

### D4 派发件模板化（versioned 脚本 + 自校验）

- 新增版本化脚本 `scripts/review-dispatch.sh`，用法：
  ```
  scripts/review-dispatch.sh --target <repo> --code <编号> --step <步骤键> --round <轮次词> \
      --prompt <prompt 文件> [--role review] [--dry-run]
  ```
  行为：由 `--code/--step/--round` **唯一推导** `LOG`/`USAGE` 路径（`cache/closed-loop/{date}-{project}-{code}-{step}{-round}.log/.json`），`--dry-run` 只打印三路径 + 校验 prompt 存在；真实执行走「review 通道串行等待（pgrep 守卫）→ `hermes -p <role> --in <target> -z "$(cat prompt)" --usage-file <usage>` → 退出码写日志尾 `..._EXIT=$rc`」。
  执行后**自校验**：usage 文件存在且非空（缺 ⇒ 打印诊断 + exit 2，日志尾部标注），杜绝「轮次串号/漏传 usage-file」。
- 收尾口径增补：闭环收尾核对「每轮评审各有独立非空 usage-file」（写入本件 §8.4 与 skill）。
- 边界：脚本只做「派发 + 记账」，不含业务判断；既有手写壳保留（历史留档），新批一律用模板。

---

## 3 行为契约汇总

### 3.1 输出通道（三态）

| 模式 | stdout | stderr |
|:--|:--|:--|
| 默认（人类） | 命令正常产物 + help + 启动信息块 | 失败/警告/未识别参数/stale/清理动作 |
| `--url` | 仅 URL 一行 | 同上 |
| `--json` | 仅 JSON 信封一行 | 同上 |

### 3.2 退出码

| 码 | 语义 | 适用 |
|:--|:--|:--|
| 0 | 成功 / 幂等命中 / help / status 未注册 | 全命令 |
| 1 | 运行期失败（路径不存在、端口不可用、端口被他人占、正在启动超时、kill 未注册、web 运行期失败、名不存在） | 全命令 |
| 2 | 用法错误（非法值、越界、互斥、缺必填、名非法） | 全命令 |

### 3.3 启动锁协议

```
acquire(abs_path):
  try O_CREAT|O_EXCL → 写 {path,pid,started_at} → HIT(持有)
  except EEXIST:
     holder = parse(lock)
     if holder stale (无 pid/pid 死/超 TTL 30s/命令行非本 CLI) → 删锁 → 重试 1 次
     else → WAIT(≤3.0s 轮询 registry 就绪) → 就绪: 幂等返回 / 超时: fail-closed(exit 1)
finally: release(删除锁文件)
```

---

## 4 实施点（文件 / 函数）

### 4.1 O1（`utils.py` / `cli.py` / `server.py`）

| 位置 | 改动 |
|:--|:--|
| `utils.py:33` | `eprint` → `print(..., file=sys.stderr)`；新增 `print_msg`（stdout） |
| `cli.py` 28 处 / `server.py` 32 处 / `utils.py` 4 处 | 逐点判定：产物类 → `print_msg`；错误/警告/清理类 → `eprint`。判定在实现 commit 内以「调用点清单表」记录（文件:行 → 归类） |
| 已知必须改判的点 | `server.py` index_page 校验失败（`eprint(err,'❌')`，错误 → stderr ✓ 已随函数语义自动纠正）；`server.py:184` 既有 stderr ✓ 不变；`cli.py:1052` 对应 `_handle_set` 错误（测试注释将同步） |
| `tests/test_cli.py:1052` 附近 | 断言通道由 stdout 改为 stderr（对应 D1 有意变更） |

### 4.2 O3（`cli.py` web 段）

- `_web_add/_web_list/_web_show/_web_remove/_web_update/_web_run`：按 §1.2 表逐分支补 `sys.exit(1|2)`；`--json` 先出信封。
- `_web_help()` 路径不加退出码。

### 4.3 O5（`server.py` / `utils.py`）

- `utils.py`：新增 `LOCK_DIR`（`~/.http-server.cli/locks`）、`lock_path(abs_path)`、`acquire_start_lock(abs_path)`（返回 `('hit', lockpath) | ('stale_retry', …) | ('busy', holder)`）、`release_start_lock(lockpath)`；`LOCK_TTL=30.0`、`LOCK_WAIT=3.0`、`LOCK_POLL=0.2` 模块级常量（便于测试替换）。
- `server.py:start()`：`abs_path = resolve_path(path)` 之后 acquire；`try/finally` 释放；`busy` 分支：轮询幂等 → 超时 stderr + `return False`。
- `ensure_storage()` 建 `locks/` 目录（幂等 `mkdir(parents=True, exist_ok=True)`）。

### 4.4 O6

- 新增 `scripts/review-dispatch.sh`（可执行位）；`scripts/` 内已有 `port-flag-verify.py`/`port-residual-verify.py` 先例。
- 文档：`documents/` 本件 §8.4 口径 + `skills/hs-cli`（若含发布/流程段）与 ops skill 同步。

---

## 5 兼容与风险

| 风险 | 评估 | 缓解 |
|:--|:--|:--|
| `eprint` 通道变化影响既有脚本/管道（`hs list \| grep`） | 产物类改走 stdout（`print_msg`）⇒ 管道语义不变；错误类改走 stderr ⇒ 更规范（`2>/dev/null` 可静音） | 逐点判定表 + 全量测试 + 三态 stdout 契约测试 |
| 退出码变化影响既有调用方 | 仅为「原本 rc=0 的失败路径」改为 1/2；成功路径不变 | CHANGELOG `### Changed` 明写；README 退出码小节 |
| 锁引入启动延迟 | 无竞争时 1 次 `open(O_EXCL)`（<1ms）；有竞争时 ≤3.0s 等待（fail-closed） | 常量可调；`--url`/`--json` 同路径不特殊化 |
| 锁文件遗留 | 崩溃时靠 TTL 30s + pid 活性 → 最坏 30s 后自愈 | 测试覆盖 stale 三态 |
| 锁在 NFS/网络盘不原子 | 本仓场景为本地盘；`ensure_storage()` 目录固定在 `~/.http-server.cli` | 设计文档声明边界 |
| `print_msg` 新增名改变 import 面 | 仅仓内使用；`utils` 非公开 API | 无需兼容层 |

---

## 6 测试计划（T1–T18）与断言表（A1–A14）

### 6.1 测试（`tests/test_cl005_hardening.py` + 既有文件同步）

| # | 用例 | 断言要点 |
|:--|:--|:--|
| T1 | `eprint()` 写 stderr、不写 stdout | capsys 两通道分离 |
| T2 | `print_msg()` 写 stdout | 同上 |
| T3 | `hs config`（默认模式）stdout 含配置内容 | 产物类走 stdout |
| T4 | `hs set port abc`（错误）stdout 为空 + stderr 有错误 | 通道纠正 |
| T5 | `hs <dir> --json` 全流程 stdout 仅一行可解析 JSON | 信封契约 |
| T6 | `hs web add` 缺 `--cmd` → rc=2 | 用法错误 |
| T7 | `hs web add` 名非法 / 与内置命令冲突 → rc=2 | 同上 |
| T8 | `hs web show <不存在>` → rc=1 | 运行期失败 |
| T9 | `hs web remove <不存在>` → rc=1 | 同上 |
| T10 | `hs web list`（services 损坏注入）→ rc=1 | 同上 |
| T11 | `hs web` 无子命令 → rc=0 + help | 保持 |
| T12 | 并发 5 次同目录 `hs <dir> -d --url` | registry 该 path **1 条**；`listener pid 集合 == registry pid 集合`（pid 同一性）；无孤儿 |
| T13 | 有效锁存在（模拟 holder=当前测试进程）→ 第二次 start rc=1 + stderr「正在启动」 | fail-closed |
| T14 | stale 锁（pid 死）→ 自动清理并成功启动 | 自愈 |
| T15 | stale 锁（超 TTL）→ 同上 | 自愈 |
| T16 | 锁在成功/失败路径均被释放 | 启动后 `locks/` 无残留 |
| T17 | `scripts/review-dispatch.sh --dry-run` 三路径推导正确 + 非法参数 rc≠0 | 派发件 |
| T18 | 全量回归 `pytest tests/ -q` 0 failed | 回归 |

### 6.2 断言表（ops harness `scripts/cl005-verify.py`）

| # | 断言 | 判据 |
|:--|:--|:--|
| A1 | `eprint` 通道 | `python3 -c "...eprint('x')"`：stdout 空、stderr 含 x |
| A2 | `print_msg` 通道 | 反向断言 |
| A3 | 三态 stdout 契约 | 默认/`--url`/`--json` 三模式下 stdout 逐字符比对期望形状（json 可 `json.loads`；url 单行 URL） |
| A4 | web 退出码矩阵 | 逐分支实测 rc（含 JSON 模式信封可解析） |
| A5 | 并发 5 次 | registry 1 条 + pid 同一性 + 无孤儿（**修前反证**：worktree `4679ee8` 同法 ≥3 次样本出现不一致） |
| A6 | 有效锁 fail-closed | 伪造锁文件（holder=活 pid 且命令行含 `http_server_cli`）→ rc=1 |
| A7 | stale 锁自愈 | 三种 stale（无 pid / pid 死 / 超 TTL）各一次 → rc=0 + 锁被清理 |
| A8 | 锁无残留 | 全部用例后 `locks/` 无该 path 文件 |
| A9 | 派发件 | `--dry-run` 三路径 + 非法参数；真实派发产生非空 usage-file |
| A10 | CL003/CL004 回归 | `scripts/port-flag-verify.py` 31/31 + `scripts/port-residual-verify.py` 13/13 |
| A11 | 全量回归 | `pytest tests/ -q` 0 failed（期望 ≥575） |
| A12 | 四同步实测 | `hs version` = v1.4.1；CHANGELOG `### Changed/Fixed`；features 计数；spec `version` + 新场景；README 退出码小节 |
| A13 | 残留 0 | registry/services 前后快照一致；无主 runner listener 0；`locks/` 清理 |
| A14 | 未越界 | `git diff` 复核：`hs set port` 语义/registry 字段/8180-8181 硬拦/`-p` 顺序链零变更 |

---

## 7 版本口径 D9

- **1.4.1（2026-09-23）**，理由：
  1. 1.4.0（CL003+CL004）已完成实现审计（PASS 99/100）且随时可发布；并入新内容会使「已审计产物的范围」在发布前再次变动。
  2. 本批含行为变更（输出通道、退出码）与新增机制（启动锁），独立小版本更利于回溯与回滚。
  3. 用户 2026-09-23 指令为「独立模式全自动实施」 ⇒ 与 1.4.0 发布解耦（发布另待放行）。
- 五处同步：`__init__.__version__` / `__release_date__` / CHANGELOG `## 1.4.1 (2026-09-23)` / `hs version` / features.md / `http-server.cli.spec.yaml`。

---

## 8 文档同步计划

1. `CHANGELOG.md`：新增 `## 1.4.1 (2026-09-23)`，`### Changed`（eprint 通道 / web 退出码）+ `### Fixed`（并发孤儿 / 派发件）+ `### Notes`（锁协议边界）。
2. `features.md`：新增条目（输出通道契约 / 退出码三态 / 目录级启动锁 / 派发件模板）+ 测试计数更新。
3. `http-server.cli.spec.yaml`：`version: 1.4.1`；新增 requirement `cli-06`（输出通道与退出码）、`lifecycle-07`（启动锁）场景。
4. `README.md` / `README.zh.md`：退出码小节 + 并发启动说明。
5. `skills/hs-cli`（若涉并发/退出码）+ ops skill `http-server-ops`（派发件模板 + 锁协议 + 收尾 usage 核对口径）。
6. 本设计件 §13 实施记录与偏差（Step 3 回填）。

---

## 9 闭环计划（独立模式全自动）

| 步骤 | 内容 | 产出 |
|:--|:--|:--|
| [1/6] 方案 | 本件（v1.0） | `docs@design:` commit |
| [2/6] 设计评审 | `hermes -p review -z`（用 D4 新派发脚本） | 报告 + review-log + `.review-level.yaml`；PASS → review 侧 push |
| [3/6] dev 实施 | 源码 3 笔 + 测试 1 笔 + 四同步 1 笔 | `fix@cli:` / `tests@cli:` / `docs@sync:` |
| [4/6] ops 核查 | `scripts/cl005-verify.py`（A1–A14，含修前反证） | `test@verify:` + 报告 `documents/review/http-server-cli-cl005-ops-verify-v1.0-20260923.md` |
| [5/6] 实现审计 | `hermes -p review -z` | PASS → `audit@review:` + push（仅 github） |
| [6/6] 收尾 | 复盘 + 清单 + 四件套 + 观察项 + `hm loop` 六步登记 + draft 更新 | 收尾 commit + push |
