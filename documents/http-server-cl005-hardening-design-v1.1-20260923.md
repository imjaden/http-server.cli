# HTTP-SERVER-CL005 设计 v1.1 — CL004 批遗留四项收口（输出通道 / web 退出码 / 启动锁 / 派发件）

- 件号：`documents/http-server-cl005-hardening-design-v1.1-20260923.md`（v1.0 留档不删）
- 目标仓：`/Users/jadenli/CodeSpace/http-server.cli`（单仓闭环，禁跨仓改动）
- 上游：设计 v1.0（`70c7a3d`）→ 设计评审 v1.0 **CONDITIONAL_PASS 78/100（B）**（`documents/review/http-server-cli-cl005-design-review-v1.0-20260923.md`，4 🟡 + 9 🟢）
- 交付版本口径：**1.4.1**（D9，评审已确认合理）
- 模式：**独立模式 1A 全自动**（用户 2026-09-23 指令）

---

## §0 修订落点表（本版对评审的逐项回应）

| 级别 | 评审要求（原文要点） | 本版落点 | 状态 |
|:--|:--|:--|:--|
| 🟡 F-1① | 锁键必须按「html 提取后最终 abs_path」，否则 `hs index.html` 与 `hs <dir>` 互斥失效（实测 `1d4434…` vs `2bdca8…`） | §2 D3.1（锁键定义 = `resolve_path` + html→父目录改写 + 通配解析**之后**的 `abs_path`）；§6 T20 回归断言 | 闭合 |
| 🟡 F-1② | 「无 pid/不可解析 ⇒ 删锁」在 mid-write 窗口可致双重持有（20 线程实验：空锁文件仍阻塞但可被误判 stale） | §2 D3.3（**读三态**：可解析/不可解析-新鲜/不可解析-陈旧；新鲜 ⇒ 等待，不删）；§6 T21 | 闭合 |
| 🟡 F-1③ | 锁放置过宽会掩盖 `-p` 越界 exit 2 与路径不存在 exit 1；须收窄到「用法校验后、`registry.find` 前」 | §2 D3.2 放置点（路径存在性 + index 校验后、`registry.find` 前）+ **D3.5**（busy 路径：先只读 `registry.find` → 等待 → 释放则重试全链 → 超时前先做 `-p` 纯语法校验以保 rc=2）；§5 表注明 CL003 D5「幂等优先于 `-p` 校验」不可重排的边界与残留 | 闭合 |
| 🟡 F-1④ | `release` 增归属校验（只删自己创建的锁） | §2 D3.4（release 校验 `pid == os.getpid()`，不匹配则只记 stderr 不删） | 闭合 |
| 🟡 F-2 | `started_at` 墙钟致 TTL 失效（时钟回拨）；§2 四字段 vs §3.3 三字段不一致 | §2 D3.3（计时改用 `time.monotonic()` 存 `started_mono`，负龄 ⇒ 视为跨重启 stale；`started_at` 仅诊断）；字段统一为 **4 字段** `{path, pid, started_mono, started_at}`（去 `host`） | 闭合 |
| 🟡 F-3 | `add/update` 的 `ValueError`（名已存在/cmd 空）应 exit 2；补 `_web_run` 的 `DataCorruptionError`→1 与 cmd 失败→1；cmd 失败时信封 `success=False` | §1.2 表新增三行（`add/update` `ValueError`→2、`run` `DataCorruptionError`→1、`run` cmd 失败→1 + `json_output(False, 'web-run', error=…)`）；§6 T22 | 闭合 |
| 🟡 F-4 | 测试同步漏 `tests/test_utils.py:222`；空清单/空历史通道未定案；`LOCK_DIR` 隔离方案缺失 | §2 D1.2 灰区定案表（空态/not-found → stdout ⇒ 该三处测试不红）+ §4.1 测试同步清单（含 `test_utils.py:222` `.out`→`.err`）；§4.3 `lock_dir()` **函数**从 `DATA_DIR` 动态派生 ⇒ 复用 conftest 既有 `_isolate_data_dir`（无需新增 fixture） | 闭合 |
| 🟢 R-1 | 调用点 63（cli 28/server 32/utils 3），非 64 | §1.1 已按实测改写；§2.1 表 63 行 | 落点 |
| 🟢 R-2 | 「stdout 仅一行」与 `json_output(indent=2)` 冲突 | §3.1 措辞改「仅含**一个可 `json.loads` 的 JSON 文档**（`indent=2` 多行，本批不改）」 | 落点 |
| 🟢 R-3/R-4 | 字段数不一致；`host` 死字段 | §2 D3.3 4 字段定案（去 `host`）；§3.3 伪码同步 | 落点 |
| 🟢 R-5 | `started_at` 墙钟计时 | 并入 F-2（`started_mono` 为主判据） | 落点 |
| 🟢 R-6 | holder token `basename hs` 过松 | §2 D3.3 判据重排：**pid 活性为主判据**（无时钟、无 token），token 仅用于「pid 活但不属本工具」的 pid 复用拦截；收紧为 token 精确匹配 `http_server_cli`（模块路径片段）或 basename **恰等于** `hs`；并在 §5 声明 fail-closed 可用性边界 | 落点 |
| 🟢 R-7 | D4 路径推导：LOG/USAGE 命名不同源、`--step/--round` 与扁平文件名不符、date 格式未锁定 | §2 D4 重写：**双模板**（`LOG={CODE}-{STEP}-dispatch.log`；`USAGE={YYYYMMDD}-{PROJECT}-{CODE}-{STEP}.json`）+ **`--step` 单参数（步骤键已含轮次，如 `design-rereview2`）** + `code` 统一 `.upper()`、脚本文件名 `.lower()` + `--date` 锁定 `YYYYMMDD` | 落点 |
| 🟢 R-8 | 派发壳实为 10 个（cl003 3 + cl004 6 + cl005 1） | §1.4 已按实测改写 | 落点 |
| 🟢 R-9 | D1 审计范围漏裸 `print()` 诊断（`server.py:1798`、`607-614`） | §2 D1.3 范围扩为「63 个 `eprint` 调用点 + 裸 `print()` 诊断点」，§2.1 表含 `print()` 行 | 落点 |
| 🟢 SEC-1/SEC-2 | 与 F-1①② 同源 | 同上 | 闭合 |
| 🟢 审项19 | 覆盖缺口 7 项（daemon/foreground 释放、html 同锁、mid-write 等待、dashboard/mcp 不入锁、release 归属、cmd 失败信封、JSON 矩阵） | §6 T19–T25 + A15–A17 | 补入 |

---

## 0 范围与非目标

| 编号 | 内容 | 性质 |
|:--|:--|:--|
| O1 | `utils.eprint()` 实写 stdout（**63 调用点**）⇒ 误用即污染 `--json` 信封 | 输出通道契约 |
| O3 | `hs web` 其余 error 分支 `return`（rc=0） | 退出码口径 |
| O5 | 无启动锁 ⇒ 同目录并发 ≥3 次仍可能残留孤儿 runner | 并发正确性 |
| O6 | 评审派发壳手工派生 ⇒ usage-file 缺失/跨轮覆盖 | 流程件 |

**非目标**：不改 `hs set port` 语义；不改 registry/services 结构与 `hs list --port` 语义；不动保留端口 8180/8181 硬拦；**不重排 CL003 顺序链**（路径存在性 → 幂等 → `-p` 校验 → 启动）；不修复 lsof 降级路径跨地址漏判（OBS-2）；**`hs dashboard`/`hs mcp` 不纳入锁范围**（走 ManagedRegistry 独立路径，见 §5）；不做 PyPI 发布。

---

## 1 现状与缺陷（实测证据）

### 1.1 O1 `eprint()` 实写 stdout（63 调用点，非 64）

```
src/http_server_cli/utils.py:33-38
def eprint(msg: str, emoji: str = '') -> None:
    if emoji: print(f'{emoji} {msg}')     # ← 无 file= ⇒ stdout
    else:     print(msg)
```
调用点实测：`cli.py` **28** / `server.py` **32** / `utils.py` **3** = **63**（`grep -rn "eprint(" src/` 共 64 匹配，含 `def` 行 1）。已发生事故：CL004 评审 F-1（stale 文案污染 `--json`，`json.loads` 抛错）。

### 1.2 O3 `hs web` 退出码（v1.1 修正分类 + 补两分支）

| 分支 | 行 | 目标码 | 表内（v1.0） | v1.1 |
|:--|:--|:--|:--|:--|
| `add` 缺 `--cmd` | 1391-1397 | 2 | ✅ | 不变 |
| `add` 名非法/内置冲突 | 1399-1412 | 2 | ✅ | 不变 |
| `add` `--open`/`--url` 非法 | 1415-1428 | 2 | ✅ | 不变 |
| `add` `--port/--no-port` 互斥 | 1429-1435 | 2 | ✅（CL004） | 不变 |
| `add` store `ValueError`（名已存在 / cmd 空 / 值非法） | 1466 | **2** | ❌ 误记 1 | **F-3 修正** |
| `add` `DataCorruptionError` | 1471 | 1 | ✅ | 不变 |
| `list` `DataCorruptionError` | 1496 | 1 | ✅ | 不变 |
| `show` 名不存在 | 1571-1577 | 1 | ✅ | 不变 |
| `remove` 名不存在 | 1621-1633 | 1 | ✅ | 不变 |
| `update` 名不存在 | 1667-1673 | 1 | ✅ | 不变 |
| `update` `ValueError` | 1750 | **2** | ❌ 误记 1 | **F-3 修正** |
| `run` `DataCorruptionError` | 1783-1788 | **1** | ❌ 未列 | **F-3 补入** |
| `run` 名不存在 | 1790-1799 | 1 | ✅（已一致） | 不变 |
| `run` cmd 退出码非 0 | 1850-1851 | **1** + 信封 `success=False` | ❌ 未列 | **F-3 补入** |
| `web` 无子命令 → `_web_help` | 1776-1778 | 0 | ✅ | 不变 |

判据：`store.add/update` 抛的 `ValueError` 全为**用法/校验类**（`service '{name}' already exists`、`cmd cannot be empty`、`open_mode/url/port` 非法）⇒ 与 D2「用法错误 → 2」自洽，与 CL003 D14（`UsageError → 2`）同口径；`DataCorruptionError` 才是运行期 ⇒ 1。

### 1.3 O5 无启动锁

现状靠「registry 查重 + ≤1.0s 宽限 + R-6 归属校验」收窄窗口，进程间无互斥；CL004 ops 核查：2 并发已达标，**基线 5 次双击样本中 4 次** listener 集合 ≠ registry 集合 ⇒ 竞态真实、≥3 并发无保护。

### 1.4 O6 派发件

`cache/review-prep/` 下派发壳实测 **10 个**（cl003 3 + cl004 6 + cl005 1），`LOG/PROMPT/USAGE` 三行靠人肉替换；CL004 复审轮 1/2 **无 usage-file**（闭环报告该步骤用量只能归一）。

---

## 2 决策

### D1 输出通道：`eprint` → stderr，正常产物 → `print_msg`（stdout）

**D1.1 语义**：`eprint(msg, emoji='')` 一律 stderr（签名不变，外部零导入）；新增 `print_msg(msg, emoji='')` 一律 stdout；两者实现同构（`emoji` 前缀逻辑不变）。

**D1.2 判定规则（灰区已定案）**

| 归类 | 通道 | 说明与定案 |
|:--|:--|:--|
| 命令主产物 | **stdout** | 清单/配置值/URL/history 表/search 结果/help 文本 |
| **查询类命令的空态与 not-found** | **stdout**（定案） | `hs list`/`history`/`search`/`status`/`web show` 的「No running…」「Port X not registered」「No matching…」= **答案** ⇒ stdout。**取此定案的理由**：保持 `hs list \| wc -l`、`hs history \| grep` 语义不回退；且使 `tests/test_server.py:180/336`、`tests/test_cli.py:296` 三处断言**不红**（回归面最小） |
| 动作命令的「无事可做」 | stdout | `hs kill`（all）无运行服务 ⇒ 与查询空态同形（rc=0、无副作用），保持一致 |
| 过程反馈 | **stderr** | `Browser opened`、`Press Ctrl+C`、`Log tail stopped`、`Foreground mode`、`Interrupt received`、`Service closed`、`Port X in use, auto-assigned port Y`（🔀 漂移警告） |
| 失败/警告/被忽略/清理动作 | **stderr** | 端口占用、路径不存在、stale 清理、未识别参数、校验失败、kill 内部告警、`Unknown command` |
| 用法错误提示（`set`/`search` 缺参） | **stderr**（定案） | 其**退出码**仍为 0（CL003 未覆盖 `set`/`search`）⇒ 登记观察项 **O7**，本批不扩范围 |
| 机器模式 | 见 §3.1 | `--json` 仅一个 JSON 文档；`--url` 仅一行 URL；其余一律 stderr |

**同一条文案在不同命令语义下通道不同**（必须逐点判定，禁按文案猜）：`Port X not registered` 在 `hs status` = 答案（stdout）、在 `hs kill` = 失败（stderr）。

**D1.3 审计范围（R-9 修正）**：= 63 个 `eprint` 调用点 **+ 裸 `print()` 诊断点**（`grep -rn "print(" src/` 逐点过滤），已识别至少：`server.py:1798`（"Available" 提示）、`server.py:607-614`（status 占用诊断块）。逐点定案写入实现 commit 的「调用点清单表」。

**D1.4 范围外声明**：`--daemon` 模式 `subprocess.run(['tail','-f',log_path])` 的**日志透传属用户显式要求的产物**，不经 `eprint`/`print_msg`，不在本函数级审计范围；因 `json`/`url` 提前 return（`server.py:466/469`），该路径不会污染机器模式。`foreground` 模式 runner 输出已重定向日志文件（`server.py:369`），无 stdout 污染。

### D2 `hs web` 退出码三态统一

按 §1.2 表逐分支：用法/校验类 `ValueError` → `sys.exit(2)`；`DataCorruptionError` → `sys.exit(1)`；名不存在 → 1；`run` cmd 退出码非 0 → 1 且 JSON 信封 `json_output(False, 'web-run', error=…)`（不再 `success=True`）；`web` 无子命令 → help + 0。JSON 模式一律**先出信封再退出**。

### D3 目录级启动锁（v1.1 修订；唯一新增机制）

**D3.1 锁键（F-1① 闭合）**
```
abs_path  = resolve_path(path)
if os.path.isfile(abs_path) and abs_path.lower().endswith(('.html','.htm')): abs_path = dirname(abs_path)
if index_page 含 '*': index_page = relpath(latest, abs_path)          # server.py:163-178
lock_key  = sha1(abs_path.encode())[:16]      # ← 以「html 提取后最终 abs_path」为输入
lock_file = lock_dir() / f'{lock_key}.json'
```
⇒ `hs index.html` 与 `hs <dir>` **同一锁**（T20 回归断言）。

**D3.2 放置点（F-1③ 闭合）**：`路径存在性（isdir）` 与 `index_page 校验` 之后、`self.registry.find()` 之前。
- 路径不存在 ⇒ 早于锁 ⇒ 仍 rc=1 ✓
- `-p` 校验（区间/保留/占用）**保持在幂等判定之后**（CL003 D5「幂等优先于 `-p` 校验」，spec `cli-05` 已固化，**不可重排**）⇒ 见 D3.5 的 busy 路径补偿。

**D3.3 锁协议与 stale 判据（F-1②/F-2/R-3/R-4/R-6 闭合）**

锁内容 **4 字段**：`{path, pid, started_mono, started_at}`（`started_at` 仅诊断用 ISO 字串；**去 `host`**）。

```
acquire(abs_path):
  try: fd = os.open(lock_file, O_CREAT|O_EXCL|O_WRONLY, 0o644)      # 原子, 唯一赢家
       os.write(fd, json.dumps({...})); os.fsync(fd); os.close(fd)  # 立即写内容
       return HIT
  except FileExistsError:
     raw, mtime = read_lock(lock_file)
     if raw 不可解析/无 pid:                                        # mid-write 窗口
         if time.time() - mtime < LOCK_WRITE_GRACE(=1.0s): return WAIT   # ← 不删!
         else: unlink; retry-once
     holder = parsed
     if not is_process_alive(holder.pid): unlink; retry-once         # 主判据: pid 活性
     if holder.pid != os.getpid() and not _cmdline_is_this_cli(holder.pid): unlink; retry-once   # pid 复用
     age = time.monotonic() - holder.started_mono
     if age < 0 or age > LOCK_TTL(=30.0): unlink; retry-once         # 负龄 = 跨重启 ⇒ stale
     return BUSY(holder)
```
- **计时口径（F-2）**：`started_mono = time.monotonic()`（同机跨进程可比；重启后新 monotonic 更小 ⇒ `age < 0` ⇒ 视为 stale ✓）；墙钟 `started_at` 不参与判定。
- **token 收紧（R-6）**：`_cmdline_is_this_cli(pid)` 取 `ps -o args=`，**按空白切分 token 精确匹配**：任一 token 含 `http_server_cli`（如 `…/http_server_cli/cli.py`、`-m http_server_cli.cli`）**或** `basename(token) == 'hs'`（恰等，非子串）。仅用于 pid 复用拦截；**主判据是 pid 活性**（无时钟、无 token）。
- **release 归属校验（F-1④）**：`release()` 读回锁内容，`pid == os.getpid()` 才 unlink；不匹配只 stderr 记一行不删（防误删他人锁）。

**D3.4 等待路径与重试（F-1③ 补偿）**
```
BUSY(holder):
  ① 只读 registry.find(path=abs_path) 命中且存活 → 幂等返回（rc=0, 复用既有端口/URL 分支）
  ② 否则轮询 ≤ LOCK_WAIT(=3.0s)/LOCK_POLL(=0.2s):
       - registry 出现该 abs_path 且就绪 → 幂等返回 rc=0
       - 锁被释放（holder 结束/失败）→ 回到 acquire 重试**整链**（含本进程自己的 `-p` 校验）
          ⇒ 本进程的 `-p` 越界等用法错误仍以 rc=2 报出 ✓
       - 锁仍在（holder 存活）→ 继续轮询
  ③ 超时仍持锁 → **先做 `-p` 纯语法校验（区间 1024-65535，无副作用）**：
       越界 ⇒ UsageError ⇒ rc=2（**不**被「正在启动」掩盖）✓
       合法 ⇒ stderr「另一实例正在启动（pid …, 路径 …），请稍后重试或 `hs kill <path>`」+ rc=1（fail-closed）
```
- 残留边界（§5 声明）：holder 卡死 >3.0s 且请求合法 ⇒ rc=1，属 fail-closed 预期；不重复启动是不变量。

**D3.5 try/finally 精确范围与长期持锁声明**
- `try` 块起 = acquire HIT；终 = 启动流程结束（含 `registry.add` 成功或失败）；`finally: release()`（覆盖 6 处 `return False`、`UsageError`、`SystemExit`、异常）。
- 早于 acquire 的 return（index 校验 / 路径不存在）**无锁可释放**，天然安全。
- `registry.add` 抛异常 ⇒ `finally` 释放锁前**先终止本次已 Popen 的 runner**（与 CL004 既有「判 stale 先终止进程组再清登记」同口径回滚）⇒ 不产生孤儿。
- **声明**：`--daemon`（前台 `tail -f`）与 `foreground`（`proc.wait()`）期间锁被长期持有，语义为**启动锁 + 会话锁**，非缺陷（幂等兜底）；文档按此措辞。
- `hs dashboard`/`hs mcp` **不获取该锁**（独立 ManagedRegistry 路径）。

**D3.6 常量与隔离（F-4 部分）**
- 模块级常量：`LOCK_TTL=30.0` / `LOCK_WAIT=3.0` / `LOCK_POLL=0.2` / `LOCK_WRITE_GRACE=1.0`（均可 monkeypatch）。
- `lock_dir()` 为**函数**：`return DATA_DIR / 'locks'`（动态读模块全局 ⇒ conftest 既有 `_isolate_data_dir`（autouse，`monkeypatch.setattr('http_server_cli.utils.DATA_DIR', tmp)`）**自动隔离** ⇒ 测试不污染真实 `~/.http-server.cli/locks`，无需新增 fixture）。`ensure_storage()` 增 `locks/` 幂等创建。

### D4 派发件模板（v1.1 重写，R-7/R-8/审项15 闭合）

- 新增版本化 `scripts/review-dispatch.sh`：
  ```
  scripts/review-dispatch.sh --target <repo> --code HTTP-SERVER-CL005 --project http-server.cli \
      --step design-rereview2 --date 20260923 --prompt <file> [--role review] [--dry-run]
  ```
- **双模板（同源不同名，各由参数唯一推导）**：
  - `LOG  = cache/closed-loop/{CODE}-{STEP}-dispatch.log`（与既有实测命名一致：无 date/project 前缀、`-dispatch.log` 后缀）
  - `USAGE= cache/closed-loop/{YYYYMMDD}-{PROJECT}-{CODE}-{STEP}.json`（与既有 usage 命名一致）
- **步骤键已含轮次**（`design-review` / `design-rereview` / `design-rereview2` / `audit`）⇒ 取消独立 `--round`（避免与扁平命名不符）；
- **大小写规范化**：LOG/USAGE 用 `CODE` 的 `.upper()`，脚本文件名用 `.lower()`；`--date` 缺省 `YYYYMMDD` 锁定；
- **分层（审项15）**：脚本核心（路径推导 + 校验）抽为 `--dry-run` 可打印的纯逻辑，**pytest 只测 `--dry-run` 三路径 + 非法参数 rc≠0**；「真实派发产生非空 usage-file」由 ops harness A9 断言（依赖 `hermes`/`pgrep`，pytest 内不可复现）；
- 真实执行：review 通道串行等待（既有 `guard_wait` 语义）→ `hermes -p <role> --in <target> -z "$(cat prompt)" --usage-file <USAGE>` → 日志尾 `…_EXIT=$rc` → **自校验** usage 存在且非空（缺 ⇒ 打印诊断 + exit 2）。
- 收尾口径：闭环收尾核对「每轮评审各有独立非空 usage-file」（写入 §8.4）。

### D9 版本口径：1.4.1（2026-09-23）

理由同 v1.0（1.4.0 已审计冻结、可独立发布；本批含行为变更 + 新机制），评审已确认合理。五处同步：`__init__.__version__`/`__release_date__`/CHANGELOG/`hs version`/features.md/`spec.yaml`。

---

## 3 行为契约汇总

### 3.1 输出通道（三态 + 两特殊模式）

| 模式 | stdout | stderr |
|:--|:--|:--|
| 默认（人类） | 命令主产物（含查询空态/not-found）+ help + 启动信息块 | 过程反馈/警告/错误/清理/用法提示 |
| `--url` | 仅 URL 一行 | 同上 |
| `--json` | 仅含**一个可 `json.loads` 的 JSON 文档**（`indent=2` 多行，本批不改） | 同上 |
| `--daemon`（前台 tail） | `tail -f` 透传的日志流（范围外，见 D1.4） | 同上 |
| `foreground` | 无（runner 输出重定向日志） | 同上 |

### 3.2 退出码

| 码 | 语义 |
|:--|:--|
| 0 | 成功 / 幂等命中 / help / 查询类未注册（`hs status`）/ `kill all` 无服务 |
| 1 | 运行期失败（路径不存在、端口不可用/被他人占、正在启动超时、kill 未注册、store 损坏、web 名不存在、web cmd 失败） |
| 2 | 用法错误（非法值、越界、互斥、缺必填、名非法/冲突、web `ValueError` 类） |

### 3.3 启动锁状态机（与 D3.3/D3.4 同源）

```
lock_file = lock_dir()/sha1(最终 abs_path)[:16].json      # 4 字段: path/pid/started_mono/started_at
HIT      → 启动流程 → finally: release(含 pid 归属校验)
FileExists:
  读三态 → 不可解析且 mtime 新鲜(<1.0s) → WAIT（不删）
        → 不可解析且陈旧 / pid 死 / pid 复用(命令行非本 CLI) / 龄>30s / 龄<0 → 清锁 retry-once
        → 有效 holder → BUSY：
              registry.find 命中 → 幂等 rc=0
              否 → 轮询 ≤3.0s：就绪→rc=0 ／ 锁释放→重试整链 ／ 超时→[`-p` 语法校验 ⇒ 2] 否则 rc=1
```

---

## 4 实施点

| 件 | 改动 |
|:--|:--|
| `utils.py:33-38` | `eprint` → stderr；新增 `print_msg`；新增 `lock_dir()`/`lock_path()`/`acquire_start_lock()`/`release_start_lock()`/`_cmdline_is_this_cli()` + 4 常量 |
| `utils.py` 其余 3 调点 | migration 提示/警告 → stderr（`eprint` 保持，通道随函数语义自动纠正） |
| `cli.py` 28 调点 | 产物类 → `print_msg`（通道不变）；错误/警告类保持 `eprint`（通道转 stderr）；usage 提示（172-174/551）→ stderr |
| `server.py` 32 调点 + 裸 `print()` 诊断点 | 同上；`519/520/545/607/616/626/657/659/785/814` 逐点按 §2.1 定案 |
| `cli.py` web 段 | §1.2 表逐分支补 `sys.exit(1|2)`；`_web_run` cmd 失败 → 1 + 信封 `success=False`（1850 附近） |
| `server.py:start()` | 锁 acquire 置于 isdir/index 校验后、`registry.find` 前；busy 路径按 D3.4；`try/finally` 按 D3.5；`registry.add` 失败回滚 runner |
| `ensure_storage()` | 增 `locks/` 幂等创建 |
| `scripts/review-dispatch.sh` | 新增（D4） |
| `tests/test_utils.py:222` | 断言 `.out`→`.err`（migration full-failure） |
| `tests/test_cli.py:1052` | 断言 `.out`→`.err`（`set` 错误通道纠正） |
| `tests/test_cl005_hardening.py` | 新增（§6） |

---

## 5 兼容与风险

| 风险 | 评估 | 缓解 |
|:--|:--|:--|
| `eprint` 通道变化影响管道 | 产物类换名保 stdout ⇒ `hs list \| grep` 语义不变；错误类转 stderr ⇒ 更规范 | 逐点判定表 + 全量回归 |
| 退出码变化 | 仅「原 rc=0 的失败路径」改 1/2；成功路径与「查询类未注册」保持 0 | CHANGELOG `### Changed` + README 退出码小节 |
| 锁引入延迟 | 无竞争 <1ms；有竞争 ≤3.0s fail-closed | 常量可调 |
| **busy 超时掩盖 `-p` 越界** | D3.4③ 在 abort 前先做纯语法校验 ⇒ 越界仍 rc=2；CL003 D5「幂等优先」不重排 | §6 T22b 断言 |
| holder 卡死 >3.0s | 请求方 rc=1（可用性损失，安全方向） | 文档声明 + stderr 指引 `hs kill` |
| `lock_dir()` 派生自 `DATA_DIR` | 测试自动隔离；真实目录仅新增 `locks/` 子目录 | conftest autouse 已覆盖 |
| NFS 原子性 | 本地盘场景；锁目录固定在 `~/.http-server.cli/locks` | 文档声明边界 |
| `dashboard`/`mcp` 未加锁 | 独立路径、非本批目标 | §0 非目标显式声明 |

---

## 6 测试计划（T1–T25）与断言表（A1–A17）

### 6.1 测试（`tests/test_cl005_hardening.py` 新增 + 既有同步）

| # | 用例 | 断言要点 |
|:--|:--|:--|
| T1 | `eprint()` 通道 | capsys：stdout 空、stderr 含文案 |
| T2 | `print_msg()` 通道 | 反向 |
| T3 | `hs config`（默认） | stdout 含配置内容（产物） |
| T4 | `hs set port abc` | stdout 空 + stderr 有错误 |
| T5 | `hs <dir> --json` 全流程 | stdout 仅一个可 `json.loads` 文档（`indent=2` 允许） |
| T6 | `hs web add` 缺 `--cmd` | rc=2 |
| T7 | `hs web add` 名非法/内置冲突 | rc=2 |
| T8 | `hs web add` 名已存在（`ValueError`） | **rc=2**（F-3） |
| T9 | `hs web update` `--cmd ''`（`ValueError`） | **rc=2**（F-3） |
| T10 | `hs web show <不存在>` | rc=1 |
| T11 | `hs web remove <不存在>` | rc=1 |
| T12 | `hs web list`（services 损坏） | rc=1 |
| T13 | `hs web run <名>` cmd 失败 | **rc=1** + JSON 信封 `success=False`（F-3） |
| T14 | `hs web run`（services 损坏） | rc=1 |
| T15 | `hs web` 无子命令 | rc=0 + help |
| T16 | 并发 5 次同目录 `hs <dir> -d --url` | registry 该 path **1 条**；`listener pid 集合 == registry pid 集合`；无孤儿 |
| T17 | 有效锁（holder=本测试进程伪造）→ 第二次 start | rc=1 + stderr「正在启动」 |
| T18 | stale 锁三态（无 pid / pid 死 / 超 TTL） | 各一次：自动清理 + 成功启动 |
| T19 | 锁成功/失败/异常路径 | `locks/` 无该 path 残留；release 归属校验（他人锁不删） |
| T20 | **html 快捷方式同锁**（F-1①） | `hs <dir>/index.html` 与 `hs <dir>` 的 `lock_path()` 相等 |
| T21 | **mid-write 等待**（F-1②） | 伪造空锁文件 + mtime 极新 ⇒ 走等待、**不删**；mtime 陈旧 ⇒ 清理重试 |
| T22a | `hs <dir> -p 70000`（无竞争） | rc=2（CL003 回归） |
| T22b | 持有效锁时 `hs <dir> -p 70000` | **rc=2**（超时前语法校验，F-1③） |
| T23 | `hs <dir> -p 8080`（另一实例持锁、合法端口） | rc=1 + stderr「正在启动」 |
| T24 | daemon tail / foreground 结束后 | 锁释放（无残留） |
| T25 | `scripts/review-dispatch.sh --dry-run` | 三路径（LOG/USAGE 双模板）推导正确 + 非法参数 rc≠0 |

### 6.2 断言表（ops harness `scripts/cl005-verify.py`）

| # | 断言 | 判据 |
|:--|:--|:--|
| A1/A2 | `eprint`/`print_msg` 通道 | 子进程实测两通道分离 |
| A3 | 三态 stdout 契约 | 默认/`--url`/`--json` 逐字符形状（json 可 `json.loads`） |
| A4 | web 退出码矩阵 | §1.2 表逐行实测 rc（含 `ValueError`→2、cmd 失败→1 与信封 `success=False`、JSON 模式） |
| A5 | 并发 5 次 | registry 1 条 + **pid 同一性** + 无孤儿；**修前反证** worktree `4679ee8` 同法 ≥3 有效样本出现不一致 |
| A6 | 有效锁 fail-closed | 伪造锁（活 pid + 命令行含 `http_server_cli`）⇒ rc=1 |
| A7 | stale 锁三态自愈 | 无 pid / pid 死 / 超 TTL ⇒ rc=0 + 锁清理 |
| A8 | 锁无残留 | 全部用例后注入目录无该 path 锁文件 |
| A9 | 派发件 | `--dry-run` 双模板三路径 + **真实派发产生非空 usage-file** |
| A10 | CL003/CL004 回归 | `port-flag-verify.py` 31/31 + `port-residual-verify.py` 13/13 |
| A11 | 全量回归 | `pytest tests/ -q` 0 failed（期望 ≥580） |
| A12 | 四同步 | `hs version`=v1.4.1；CHANGELOG `### Changed/Fixed`；features 计数（模块数用 `git ls-files`）；spec 1.4.1 + 新场景；README 退出码小节 |
| A13 | 残留 0 | registry/services 前后快照一致；无主 runner listener 0；`locks/` 清理 |
| A14 | 未越界 | `git diff` 复核：`hs set port` 语义/registry 字段/8180-8181 硬拦/**CL003 顺序链**零变更 |
| A15 | html 同锁 + mid-write | T20/T21 的真机版（`lsof` 无关） |
| A16 | 归属/回滚 | release 不删他人锁；`registry.add` 失败无孤儿 |
| A17 | daemon/foreground 释放 | 两模式结束后锁无残留 |

**并发/时序纪律（评审确认沿用）**：就绪等待 ≤2s 轮询到 LISTEN；剔除幂等样本；≥3 有效样本；pid 同一性（禁计数相等、禁 `hs list --json` 当数据源、禁 `in` 子串）；修前反证基线 `4679ee8`。

---

## 7 版本文档同步计划

1. `CHANGELOG.md`：新增 `## 1.4.1 (2026-09-23)`（`### Changed`：输出通道 / web 退出码；`### Fixed`：并发孤儿 / 派发件；`### Notes`：锁协议边界与长期持锁声明）。
2. `features.md`：新增输出通道契约 / 退出码三态 / 目录级启动锁 / 派发件模板四条目 + 测试计数（现场实测）。
3. `http-server.cli.spec.yaml`：`version: 1.4.1` + `cli-06`（输出通道与退出码）+ `lifecycle-07`（启动锁）。
4. `README.md`/`README.zh.md`：退出码小节 + 并发启动说明。
5. `skills/hs-cli`（并发/退出码段）+ ops skill `http-server-ops`（锁协议 v1.1 口径 + 派发模板 + 收尾 usage 核对）。
6. 本设计件 §13 实施记录与偏差（Step 3 回填）。

---

## 8 闭环计划（独立模式全自动）

| 步骤 | 内容 | 产出 |
|:--|:--|:--|
| [1/6] 方案 | v1.0 `70c7a3d` + 本版 v1.1 | `docs@design:` ×2 |
| [2/6] 设计评审 | round-1 CONDITIONAL 78 → 本版 → round-2 rerereview（**限定只审未闭合项 + 本版增量**） | 报告 + 评分链 78 → ? |
| [3/6] dev | 源码 + 测试 + 四同步 | `fix@cli:` / `tests@cli:` / `docs@sync:` |
| [4/6] ops 核查 | `scripts/cl005-verify.py`（A1–A17，含修前反证） | `test@verify:` + 报告 |
| [5/6] 实现审计 | 用 D4 新派发模板（A9 的实战验证） | `audit@review:` + push |
| [6/6] 收尾 | 复盘 + 清单 + 四件套 + 观察项（含 O7）+ `hm loop` 六步登记 | 收尾 commit + push |
