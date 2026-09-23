# HTTP-SERVER-CL005 设计 v1.2 — CL004 批遗留四项收口（输出通道 / web 退出码 / 启动锁 / 派发件）

- 件号：`documents/http-server-cl005-hardening-design-v1.2-20260923.md`（v1.0/v1.1 留档不删）
- 目标仓：`/Users/jadenli/CodeSpace/http-server.cli`（单仓闭环，禁跨仓改动）
- 评审链：v1.0 `70c7a3d` → **78/100（B）** 4🟡+9🟢 ｜ v1.1 `ecd0322` → **86/100（B+）** 2🟡（F-2a/F-4a）｜ 本版 v1.2 → 待 round-3
- 交付版本口径：**1.4.1**（D9，评审两轮确认合理）
- 模式：**独立模式 1A 全自动**（用户 2026-09-23 指令）

---

## §0 修订落点表（round-2 → 本版）

### 本版必改（round-2 新开 2 项 🟡 + 2 项增量残留）

| 级别 | round-2 要求（原文要点） | 本版落点 | 状态 |
|:--|:--|:--|:--|
| 🟡 **F-2a** | `time.monotonic()` **跨进程可比性非契约**：实测 conda py3.12 可比（119500s ≈ CLOCK_UPTIME_RAW），但系统 python3（3.9.6）三个独立进程各打印 `0.0059/0.0034/0.0047`（近零且非单调）⇒ `age < 0 ⇒ stale` 在 3.9.6 下约 50% 概率伪触发 ⇒ 活 holder 锁被误删 = 双重持有。建议改 `time.clock_gettime(CLOCK_MONOTONIC)` 并**删除 `age < 0` 规则** | §2 D3.3：计时改 **`time.clock_gettime(time.CLOCK_MONOTONIC)`**（契约上系统级、自 boot 起、免疫休眠停滞）；**删除 `age < 0 ⇒ stale`**（负龄不参与判定，跨重启遗留一律由 **pid 活性 + 命令行 token** 兜底）；§6 **T26/T27** 双解释器回归 | 闭合 |
| 🟡 **F-4a** | 测试同步清单不完整：全量 grep `captured.out` 得 8 处将红（`test_server.py:87/135/228/250/314/320/326` + `test_cli.py:365`），设计仅列 2 处；根因 = D1.3 把逐点通道归类推迟到实现 | §2.1 **完整 63 点判定表**（stdout 23 / stderr 38 / 分叉 2，逐点归类不再推迟）；§4.1 **穷举同步清单 12 条必改**（含 round-2 未列出的 `test_port_flag.py:178`、`test_port_flag.py:347`）+ 1 条可选加固 + 5 条「保持绿」显式列明 | 闭合 |
| 🟡 **N-2** | D3.4①「命中且存活」措辞会导致返回未就绪端口，应改「命中且**就绪**（复用 CL004 三态）」 | §2 D3.4① 已改：`entry_pid` / `ready`（进程活 + 端口 LISTEN）/ `others_own_port` 三态判定 | 闭合 |
| 🟡 **N-4** | 裸 `print()` 审计范围部分兑现：实测约 303 处，机器模式靠 json/url 提前 return 兜底，但 `cli.py:1798`（失败分支 "Available"）走 stdout 应改 stderr | §2 D1.3 明确范围（63 `eprint` 点 + **机器模式可达的裸 print 点**）+ 裸 print 表（`cli.py:1798` → stderr；`server.py:610-614` 保持 stdout 并说明理由）；§2 D1.4 声明结构性兜底 | 闭合 |

### 上轮已闭合项（round-2 判定，留档）

| 级别 | 项 | round-2 判定 |
|:--|:--|:--|
| 🟡 F-1① | 锁键归一（html 快捷方式同锁） | **闭合** |
| 🟡 F-1② | mid-write 读三态（新鲜不删） | **闭合**（残留 🟢：`LOCK_WRITE_GRACE=1.0s` 取值属保守参数） |
| 🟡 F-1③ | 锁放置 + busy 前语法校验保 rc=2 | **闭合** |
| 🟡 F-1④ | release 归属校验 | **闭合**（残留 🟢：读-删 TOCTOU 边界） |
| 🟡 F-2 | 计时口径与字段统一（部分闭合 → 本版 F-2a 收口） | 部分 → 本版闭合 |
| 🟡 F-3 | web 退出码分类修正 + 两分支补入 | **闭合** |
| 🟡 F-4 | 隔离方案（`lock_dir()` 派生 `DATA_DIR`） | **闭合**；清单部分 → 本版闭合 |
| 🟢 R-1~R-9 | 全部落点 | **已落点** |
| 🟢 N-1/N-3/N-5/N-6/N-7 | 无活锁 / 灰区自洽 / 回滚复用点 `_terminate_runner(server.py:87)` / D4 双模板逐字符一致 / T-A 覆盖 | **通过** |
| 🟡 SEC-3 | = F-2a 实质 | 本版闭合 |

---

## 0 范围与非目标

| 编号 | 内容 | 性质 |
|:--|:--|:--|
| O1 | `utils.eprint()` 实写 stdout（**63 调用点**） | 输出通道契约 |
| O3 | `hs web` 其余 error 分支 `return`（rc=0） | 退出码口径 |
| O5 | 无启动锁 ⇒ 同目录并发 ≥3 次仍可能残留孤儿 runner | 并发正确性 |
| O6 | 评审派发壳手工派生 ⇒ usage-file 缺失/跨轮覆盖 | 流程件 |

**非目标**：不改 `hs set port` 语义；不改 registry/services 结构与 `hs list --port`；不动保留端口 8180/8181 硬拦；**不重排 CL003 顺序链**（路径存在性 → 幂等 → `-p` 校验 → 启动）；不修复 lsof 降级路径跨地址漏判（OBS-2）；**`hs dashboard`/`hs mcp` 不纳入锁范围**；不做 PyPI 发布。

---

## 1 现状与缺陷（实测证据）

### 1.1 O1 `eprint()` 实写 stdout（63 调用点）

`utils.py:33-38`：`print(f'{emoji} {msg}')` / `print(msg)` —— 无 `file=sys.stderr`。调用点实测 `cli.py` 28 / `server.py` 32 / `utils.py` 3 = **63**。已发生事故：CL004 F-1（stale 文案污染 `--json`，`json.loads` 抛错）。

### 1.2 O3 `hs web` 退出码（分类已修正 + 两分支补入）

| 分支 | 行 | 目标码 |
|:--|:--|:--|
| `add` 缺 `--cmd` | 1391-1397 | 2 |
| `add` 名非法/内置冲突 | 1399-1412 | 2 |
| `add` `--open`/`--url` 非法 | 1415-1428 | 2 |
| `add` `--port/--no-port` 互斥 | 1429-1435 | 2（CL004 已改） |
| `add` store `ValueError`（名已存在 / cmd 空 / 值非法） | 1466 | **2**（F-3 修正） |
| `add` `DataCorruptionError` | 1471 | 1 |
| `list` `DataCorruptionError` | 1496 | 1 |
| `show` 名不存在 | 1571-1577 | 1 |
| `remove` 名不存在 | 1621-1633 | 1 |
| `update` 名不存在 | 1667-1673 | 1 |
| `update` `ValueError` | 1750 | **2**（F-3 修正） |
| `run` `DataCorruptionError` | 1783-1788 | **1**（F-3 补入） |
| `run` 名不存在 | 1790-1799 | 1（已一致） |
| `run` cmd 退出码非 0 | 1850-1851 | **1 + 信封 `success=False`**（F-3 补入） |
| `web` 无子命令 → `_web_help` | 1776-1778 | 0 |

判据：`store.add/update` 的 `ValueError` 全为用法/校验类（`already exists`、`cmd cannot be empty`、`open_mode/url/port` 非法）⇒ 用法 2；`DataCorruptionError` 属运行期 ⇒ 1（与 CL003 D14 同口径）。

### 1.3 O5 无启动锁
现状靠「registry 查重 + ≤1.0s 宽限 + R-6 归属校验」收窄窗口，进程间无互斥；CL004 ops 实测基线 5 次双击样本中 **4 次** listener 集合 ≠ registry 集合 ⇒ 竞态真实。

### 1.4 O6 派发件
`cache/review-prep/` 派发壳实测 **10 个**；CL004 复审轮 1/2 无 usage-file。

---

## 2 决策

### D1 输出通道：`eprint` → stderr，正常产物 → `print_msg`（stdout）

**D1.1 语义**：`eprint(msg, emoji='')` 一律 stderr（签名不变，外部零导入）；新增 `print_msg(msg, emoji='')` 一律 stdout；`emoji` 前缀逻辑同构。

**D1.2 判定规则（灰区定案，两轮评审确认）**

| 归类 | 通道 | 说明 |
|:--|:--|:--|
| 命令主产物 | **stdout** | 清单/配置值/URL/history 表/search 结果/help 文本 |
| 查询类命令的空态与 not-found | **stdout** | `list`/`history`/`search`/`status` 的「No running…」「Port X not registered」= 答案；保持 `hs list \| wc -l` 语义 |
| 动作命令的「无事可做」 | **stdout** | `hs kill`（all）无服务（rc=0、无副作用），与查询空态同形 |
| 过程反馈 | **stderr** | Browser opened / Ctrl+C / tail / foreground / Interrupt / Service closed / 端口漂移 🔀 |
| 失败·警告·被忽略·清理动作 | **stderr** | 端口占用、路径不存在、stale 清理、未识别参数、校验失败、kill 告警、`Unknown command` |
| 用法提示（`set`/`search`/`kill` 缺参） | **stderr** | 退出码另行登记（O7） |
| 机器模式 | §3.1 | `--json` 仅一个 JSON 文档；`--url` 仅一行 URL；其余一律 stderr |

**同文案分叉**：`Port X not registered` 在 `hs status` = 答案（stdout）、在 `hs kill` = 失败（stderr）；`dashboard/MCP not running` 在 `status` = 答案（stdout）、在 `stop`/`restart` = 失败（stderr）⇒ 该两处**按 subcmd 分叉实现**（`cli.py:671/929`）。

**D1.3 审计范围（含裸 `print()`）**：= 63 个 `eprint` 点（§2.1 全表）**+ 机器模式可达的裸 `print()` 点**。实测裸 `print()` 约 303 处，绝大多数是人类模式专属产物路径（help/清单/dashboard/MCP/prompt 文本），机器模式由 `json`/`url_only` **提前 return** 结构性兜底；逐点过滤后需改动的仅 `cli.py:1798`（`_web_run` 名不存在分支的 "Available:" 提示 → stderr），`server.py:610-614`（status 占用诊断块）保持 stdout（status 无 json 模式、属人工诊断产物）。裸 print 表：

| 位置 | 所属函数 | 通道（本批） | 说明 |
|:--|:--|:--|:--|
| `cli.py:1798` | `_web_run` | **stderr** | 失败分支的 "Available:" 提示（N-4：机器模式可达） |
| `server.py:610` | `status` | stdout（保持） | status 占用诊断块（人工诊断，status 无 json 模式） |
| `server.py:611` | `status` | stdout（保持） | 同上（仅 status 路径，非机器模式） |
| `server.py:612` | `status` | stdout（保持） | 同上 |
| `server.py:613` | `status` | stdout（保持） | 同上 |
| `server.py:614` | `status` | stdout（保持） | 同上 |

**D1.4 范围外声明**：`--daemon` 模式 `tail -f` 日志透传属用户显式要求的产物，不经 `eprint`/`print_msg`（json/url 提前 return，不污染机器模式）；`foreground` 模式 runner 输出已重定向日志文件。

### D2 `hs web` 退出码三态统一
按 §1.2 表逐分支执行；JSON 模式一律**先 `json_output(False, cmd, error=…)` 再 `sys.exit(code)`**。

### D3 目录级启动锁（v1.2 修订；唯一新增机制）

**D3.1 锁键（F-1① 闭合）**
```
abs_path = resolve_path(path)
if isfile(abs_path) and abs_path.lower().endswith(('.html','.htm')): abs_path = dirname(abs_path)
if index_page 含 '*': index_page = relpath(latest, abs_path)     # server.py:163-178
lock_key = sha1(abs_path.encode())[:16]        # ← html 提取后最终 abs_path
```
⇒ `hs index.html` 与 `hs <dir>` 同一锁（T20）。

**D3.2 放置点（F-1③ 闭合）**：`isdir` 校验 + `index_page` 校验之后、`self.registry.find()` 之前；`-p` 校验保持在幂等判定之后（CL003 D5，不可重排）⇒ busy 路径补偿见 D3.4。

**D3.3 锁协议与 stale 判据（F-1②/F-2a/R-3/R-4/R-6 闭合）**

锁内容 **4 字段**：`{path, pid, started_mono, started_at}`（`started_at` 仅诊断；无 `host`）。
`started_mono = time.clock_gettime(time.CLOCK_MONOTONIC)` —— **契约上系统级自 boot 起的时钟**（round-2 实测三独立进程一致：`235526/235559/235584`），**不用** `time.monotonic()`（py3.9.6 实测跨进程近零且非单调：`0.0059/0.0034/0.0047`）。

```
acquire(abs_path):
  try: fd = os.open(lock_file, O_CREAT|O_EXCL|O_WRONLY, 0o644)     # 原子, 唯一赢家
       write({path,pid,started_mono,started_at}); flush; fsync; close
       return HIT
  except FileExistsError:
     raw, mtime = read_lock(lock_file)
     ① raw 不可解析/无 pid  → age_mtime = time.time() - mtime
          age_mtime < LOCK_WRITE_GRACE(1.0s) → return WAIT          # mid-write: 不删
          否则 → unlink; retry-once
     ② pid 不存活 → unlink; retry-once                              # 主判据（无时钟依赖）
     ③ pid 活但命令行非本 CLI（token 精确匹配）→ unlink; retry-once   # pid 复用拦截
     ④ age = now_mono - started_mono；**仅当 0 ≤ age 且 age > LOCK_TTL(30.0) 才判 stale**
        负龄（跨重启/时钟异常）**不参与判定**，不删锁（F-2a 关键修正）
        否则 → return BUSY(holder)
```
- **token 收紧（R-6）**：`ps -o args=` 按空白切分 token 精确匹配，任一 token 含 `http_server_cli`（`…/http_server_cli/cli.py`、`-m http_server_cli.cli`）或 `basename(token) == 'hs'`（恰等）；仅用于 pid 复用拦截。
- **release 归属校验（F-1④）**：读回锁内容 `pid == os.getpid()` 才 unlink，否则只 stderr 记一行。
- **负龄的兜底链（F-2a 的替代保障）**：跨重启遗留锁 ⇒ 旧 pid 非活（⇒②清）或 pid 被复用但命令行非本 CLI（⇒③清）；两者皆不命的概率极低，且失败方向是 fail-closed（等待→rc=1，不重复启动），**不产生双持有**。

**D3.4 等待路径（F-1③ 补偿 + N-2 修正）**
```
BUSY(holder):
  ① 只读 registry.find(path=abs_path) —— **命中且就绪**（复用 CL004 三态：entry_pid 非空 + 进程活 + 端口 LISTEN ⇒ ready；他方占端口 ⇒ others_own_port）
       ready → 幂等返回 rc=0（复用既有端口/URL 分支）；未就绪 → 不进幂等
  ② 轮询 ≤ LOCK_WAIT(3.0s)/LOCK_POLL(0.2s)：
       registry 就绪 → rc=0
       锁被释放 → 回 acquire 重试**整链**（含本进程 `-p` 校验）⇒ 本进程用法错误仍 rc=2 ✓
       仍持锁 → 继续
  ③ 超时 → **先做 `-p` 纯语法校验（1024-65535，无副作用）**：越界 ⇒ UsageError ⇒ **rc=2**；
       合法 ⇒ stderr「另一实例正在启动（pid …, 路径 …），请稍后重试或 `hs kill <path>`」+ **rc=1**（fail-closed）
```
残留边界：holder 卡死 >3.0s 且请求合法 ⇒ rc=1（预期 fail-closed；不重复启动是不变量）。

**D3.5 try/finally 范围与长期持锁声明**
- `try` 起 = acquire HIT，终 = 启动流程结束（含 `registry.add` 成败）；`finally: release()` 覆盖 6 处 `return False`、`UsageError`、`SystemExit`、异常；早于 acquire 的 return 无锁可释放。
- `registry.add` 抛异常 ⇒ 释放锁前**先 `_terminate_runner`（`server.py:87` 复用点，N-5 确认存在）**终止本次 runner ⇒ 不产生孤儿。
- `--daemon`（前台 tail）与 `foreground`（`proc.wait()`）期间锁长期持有，语义 = 启动锁 + 会话锁，非缺陷（幂等兜底）。
- `hs dashboard`/`hs mcp` 不入锁范围。

**D3.6 常量与隔离**
- 模块级：`LOCK_TTL=30.0` / `LOCK_WAIT=3.0` / `LOCK_POLL=0.2` / `LOCK_WRITE_GRACE=1.0`（可 monkeypatch）。
- `lock_dir()` 为**函数** `return DATA_DIR / 'locks'`（动态读模块全局 ⇒ conftest autouse `_isolate_data_dir` 自动隔离；不新增 fixture）。`ensure_storage()` 幂等建 `locks/`。

### D4 派发件模板（R-7/R-8 已闭合，round-2 N-6 逐字符一致 ✅）
`scripts/review-dispatch.sh --target <repo> --code HTTP-SERVER-CL005 --project http-server.cli --step design-rereview2 --date 20260923 --prompt <file> [--role review] [--dry-run]`：
- `LOG = cache/closed-loop/{CODE}-{STEP}-dispatch.log`；`USAGE = cache/closed-loop/{YYYYMMDD}-{PROJECT}-{CODE}-{STEP}.json`（**双模板**，与既有文件逐字符一致）
- 步骤键**已含轮次**；`CODE.upper()` / 脚本名 `.lower()`；`--date` 缺省 `YYYYMMDD`
- 分层：`--dry-run` 可测三路径 + 非法参数 rc≠0（pytest T25）；真实派发 usage 非空核对由 ops harness A9 承担
- 自校验：usage 缺失/空 ⇒ 诊断 + exit 2

### D9 版本口径：1.4.1（2026-09-23）
五处同步：`__init__.__version__` / `__release_date__` / CHANGELOG / `hs version` / features.md / `spec.yaml`。

---

## 2.1 D1 通道归属完整判定表（63 点，逐点定案，**不再推迟到实现**）

| # | 位置 | 所属函数 | 通道（本批） | 归类 | 依据/备注 |
|:--|:--|:--|:--|:--|:--|
| 1 | `cli.py:172` | `_handle_set` | **stderr** (`eprint`) | 用法提示 | set 缺参 usage |
| 2 | `cli.py:173` | `_handle_set` | **stderr** (`eprint`) | 用法提示 | set 示例行 |
| 3 | `cli.py:174` | `_handle_set` | **stderr** (`eprint`) | 用法提示 | set 示例行 |
| 4 | `cli.py:188` | `_handle_set` | **stderr** (`eprint`) | 错误 | set 区间 |
| 5 | `cli.py:196` | `_handle_set` | **stdout** (`print_msg`) | 产物 | set port 成功 |
| 6 | `cli.py:202` | `_handle_set` | **stderr** (`eprint`) | 错误 | set 非法端口 |
| 7 | `cli.py:212` | `_handle_set` | **stderr** (`eprint`) | 错误 | set 写盘失败 |
| 8 | `cli.py:218` | `_handle_set` | **stdout** (`print_msg`) | 产物 | set domain 成功 |
| 9 | `cli.py:224` | `_handle_set` | **stderr** (`eprint`) | 错误 | 未知配置键 |
| 10 | `cli.py:363` | `_list_servers` | **stdout** (`print_msg`) | 查询空态 | list 空态 |
| 11 | `cli.py:364` | `_list_servers` | **stdout** (`print_msg`) | 查询空态 | list 空态提示行 |
| 12 | `cli.py:382` | `_list_servers` | **stdout** (`print_msg`) | 产物 | list 表头 |
| 13 | `cli.py:410` | `_list_servers` | **stdout** (`print_msg`) | 产物 | 基础设施服务表头 |
| 14 | `cli.py:515` | `_cmd_history` | **stdout** (`print_msg`) | 查询空态 | history 空态 |
| 15 | `cli.py:519` | `_cmd_history` | **stdout** (`print_msg`) | 查询空态 | history 空态 |
| 16 | `cli.py:521` | `_cmd_history` | **stdout** (`print_msg`) | 产物 | history 表头 |
| 17 | `cli.py:523` | `_cmd_history` | **stdout** (`print_msg`) | 产物 | history 过滤说明 |
| 18 | `cli.py:551` | `_cmd_search` | **stderr** (`eprint`) | 用法提示 | search 缺参 |
| 19 | `cli.py:575` | `_cmd_search` | **stdout** (`print_msg`) | 查询空态 | search 无匹配 |
| 20 | `cli.py:578` | `_cmd_search` | **stdout** (`print_msg`) | 产物 | search 表头 |
| 21 | `cli.py:623` | `_cmd_dashboard` | **stderr** (`eprint`) | 错误 | dashboard -p 区间 |
| 22 | `cli.py:671` | `_manage_dashboard` | **分叉**（status stdout / stop·restart stderr） | 分叉 | status→stdout / stop·restart→stderr |
| 23 | `cli.py:730` | `_manage_dashboard` | **stdout** (`print_msg`) | 产物 | dashboard stop 结果 |
| 24 | `cli.py:736` | `_manage_dashboard` | **stderr** (`eprint`) | 错误 | 8181 保留端口 |
| 25 | `cli.py:739` | `_manage_dashboard` | **stderr** (`eprint`) | 错误 | 端口被占用 |
| 26 | `cli.py:929` | `_manage_mcp` | **分叉**（status stdout / stop·restart stderr） | 分叉 | status→stdout / stop·restart→stderr |
| 27 | `cli.py:971` | `_manage_mcp` | **stdout** (`print_msg`) | 产物 | mcp stop 结果 |
| 28 | `cli.py:1911` | `main` | **stderr** (`eprint`) | 错误 | Unknown command |
| 29 | `server.py:189` | `start` | **stderr** (`eprint`) | 错误 | index_page 校验失败 |
| 30 | `server.py:204` | `start` | **stderr** (`eprint`) | 错误 | 路径不存在 |
| 31 | `server.py:354` | `start` | **stderr** (`eprint`) | 错误 | 端口段全占用 |
| 32 | `server.py:357` | `start` | **stderr** (`eprint`) | 警告 | 端口漂移通知 |
| 33 | `server.py:379` | `start` | **stderr** (`eprint`) | 错误 | 权限失败 |
| 34 | `server.py:388` | `start` | **stderr** (`eprint`) | 错误 | 解释器缺失 |
| 35 | `server.py:397` | `start` | **stderr** (`eprint`) | 错误 | 系统资源错误 |
| 36 | `server.py:406` | `start` | **stderr** (`eprint`) | 错误 | 启动失败 |
| 37 | `server.py:464` | `start` | **stderr** (`eprint`) | 过程反馈 | Browser opened |
| 38 | `server.py:473` | `start` | **stderr** (`eprint`) | 过程反馈 | Ctrl+C 提示 |
| 39 | `server.py:478` | `start` | **stderr** (`eprint`) | 过程反馈 | log tail 停止 |
| 40 | `server.py:481` | `start` | **stderr** (`eprint`) | 过程反馈 | foreground 提示 |
| 41 | `server.py:486` | `start` | **stderr** (`eprint`) | 过程反馈 | 中断接收 |
| 42 | `server.py:496` | `start` | **stderr** (`eprint`) | 过程反馈 | 服务关闭 |
| 43 | `server.py:519` | `list` | **stdout** (`print_msg`) | 查询空态 | list 空态（定案 stdout） |
| 44 | `server.py:520` | `list` | **stdout** (`print_msg`) | 查询空态 | list 空态提示行 |
| 45 | `server.py:545` | `list` | **stdout** (`print_msg`) | 产物 | list 表头 |
| 46 | `server.py:607` | `status` | **stderr** (`eprint`) | 诊断警告 | 端口被非本工具占用 |
| 47 | `server.py:616` | `status` | **stdout** (`print_msg`) | 查询答案 | status 未注册 = 答案 |
| 48 | `server.py:626` | `status` | **stdout** (`print_msg`) | 查询空态 | 无匹配服务 |
| 49 | `server.py:657` | `status` | **stdout** (`print_msg`) | 查询答案 | status running |
| 50 | `server.py:659` | `status` | **stdout** (`print_msg`) | 查询答案 | status stopped |
| 51 | `server.py:680` | `kill` | **stderr** (`eprint`) | 用法提示 | kill 缺参数 |
| 52 | `server.py:692` | `kill` | **stderr** (`eprint`) | 失败 | kill 端口未注册 |
| 53 | `server.py:704` | `kill` | **stderr** (`eprint`) | 失败 | kill 路径未注册 |
| 54 | `server.py:724` | `kill` | **stderr** (`eprint`) | 警告 | SIGTERM 无响应 |
| 55 | `server.py:741` | `kill` | **stderr** (`eprint`) | 警告 | 无权限 kill |
| 56 | `server.py:745` | `kill` | **stderr** (`eprint`) | 过程反馈 | 进程已不存在 |
| 57 | `server.py:761` | `kill` | **stderr** (`eprint`) | 清理动作 | 日志已删 |
| 58 | `server.py:764` | `kill` | **stderr** (`eprint`) | 警告 | 日志删除失败 |
| 59 | `server.py:785` | `kill_all` | **stdout** (`print_msg`) | 动作无操作 | kill all 无服务（定案 stdout） |
| 60 | `server.py:814` | `kill_all` | **stdout** (`print_msg`) | 产物 | kill all 结果 |
| 61 | `utils.py:64` | `_migrate_legacy_data` | **stderr** (`eprint`) | 过程反馈 | 数据目录迁移通知 |
| 62 | `utils.py:68` | `_migrate_legacy_data` | **stderr** (`eprint`) | 警告 | 迁移降级（copy 成功） |
| 63 | `utils.py:73` | `_migrate_legacy_data` | **stderr** (`eprint`) | 错误 | 迁移失败 |

统计：**stdout（`print_msg`）23 点 / stderr（`eprint`）38 点 / 分叉 2 点**（`cli.py:671`、`cli.py:929` 按 subcmd 分叉）。
迁移影响面：产物类 23 点**换名不改通道**（零行为变化）；错误/警告/过程类 38 点 + 分叉 2 点**真换通道** ⇒ 既有断言影响见 §4.1。

---

## 3 行为契约汇总

### 3.1 输出通道

| 模式 | stdout | stderr |
|:--|:--|:--|
| 默认 | 命令主产物（含查询空态/not-found）+ help + 启动信息块 | 过程反馈/警告/错误/清理/用法提示 |
| `--url` | 仅 URL 一行 | 同上 |
| `--json` | 仅含**一个可 `json.loads` 的 JSON 文档**（`indent=2` 多行，本批不改） | 同上 |
| `--daemon` | `tail -f` 透传日志流（范围外，D1.4） | 同上 |
| `foreground` | 无（runner 输出重定向日志） | 同上 |

### 3.2 退出码

| 码 | 语义 |
|:--|:--|
| 0 | 成功 / 幂等命中 / help / 查询类未注册（`hs status`）/ `kill all` 无服务 |
| 1 | 运行期失败（路径不存在、端口不可用/被他人占、正在启动超时、kill 未注册、store 损坏、web 名不存在、web cmd 失败） |
| 2 | 用法错误（非法值、越界、互斥、缺必填、名非法/冲突、web `ValueError` 类） |

### 3.3 启动锁状态机

```
lock_file = lock_dir()/sha1(最终 abs_path)[:16].json   # {path,pid,started_mono,started_at}
HIT → 启动流程 → finally: release(pid 归属校验)
FileExists:
  不可解析 & mtime 新鲜(<1.0s) → WAIT（不删）
  不可解析 & 陈旧 | pid 死 | 命令行非本 CLI | 0 ≤ age > 30s → 清锁 retry-once
  其它（含 age < 0）→ BUSY:
      registry 就绪 → rc=0 ／ 轮询 ≤3.0s：就绪→0、锁释放→重试整链、超时→[-p 语法校验 ⇒ 2] 否则 1
```

---

## 4 实施点

### 4.1 测试同步清单（F-4a 穷举；全量 grep `captured.out` 逐条核对）

**必改（12 条：错误/警告/过程反馈类文案由 stdout → stderr）**

| # | 测试位置 | 断言片段 | 对应调用点 | 改法 |
|:--|:--|:--|:--|:--|
| 1 | `tests/test_utils.py:222` | `'migration failed' in captured.out` | `utils.py:73` | `.out`→`.err` |
| 2 | `tests/test_cli.py:365` | `'Usage' in captured.out` | `cli.py:172`（set usage） | `.out`→`.err` |
| 3 | `tests/test_cli.py:1053` | `'domain must match' in …out`（注释行在 1052） | `cli.py:212` | `.out`→`.err` |
| 4 | `tests/test_server.py:87` | `'all in use, cannot start' in captured.out` | `server.py:354` | `.out`→`.err` |
| 5 | `tests/test_server.py:135` | `'Path does not exist' in captured.out` | `server.py:204` | `.out`→`.err` |
| 6 | `tests/test_server.py:228` | `'not managed by this tool' in captured.out` | `server.py:607` | `.out`→`.err` |
| 7 | `tests/test_server.py:250` | `'still running in background' in captured.out` | `server.py:478` | `.out`→`.err` |
| 8 | `tests/test_server.py:314` | `'not registered' in captured.out` | `server.py:692`（kill） | `.out`→`.err` |
| 9 | `tests/test_server.py:320` | `'not registered' in captured.out` | `server.py:704`（kill path） | `.out`→`.err` |
| 10 | `tests/test_server.py:326` | `'Please specify' in captured.out` | `server.py:680` | `.out`→`.err` |
| 11 | `tests/test_port_flag.py:178` | `'not registered' in capsys…out` | `server.py:692`（直调 `kill()`） | `.out`→`.err` |
| 12 | `tests/test_port_flag.py:347` | `'not running' in capsys…out` | `cli.py:671`（`restart` 分支 ⇒ 分叉后 stderr） | `.out`→`.err` |

> 第 11/12 条为 round-2 清单未列出、本版全量 grep 补出（`test_port_flag.py:178` 直调 `ServerManager.kill` 走 `server.py:692`；`:347` 走 `_manage_dashboard('restart')` ⇒ 分叉取 stderr）。

**可选加固（1 条，不断言失败但语义更准）**

| # | 位置 | 现状 | 建议 |
|:--|:--|:--|:--|
| 13 | `tests/test_server.py:76` | `'auto-assigned port' in captured.out or '8081' in captured.out` | 漂移文案已转 stderr；改为 `'auto-assigned port' in captured.err or '8081' in captured.out`（现形式因 `or` 短路仍绿，可不改） |

**保持绿（设计结论，非侥幸 —— 5 条关键项显式列明）**

| # | 位置 | 断言 | 依据 |
|:--|:--|:--|:--|
| G1 | `tests/test_server.py:180` | `'No running HTTP services' in captured.out` | `server.py:519` 查询空态 → **stdout**（D1.2 定案） |
| G2 | `tests/test_server.py:336` | `'No running services' in captured.out` | `server.py:785` 动作无操作 → **stdout** |
| G3 | `tests/test_server.py:220` | `'not registered' in captured.out` | `server.py:616` **status 答案** → stdout（与 `kill` 的 692 分属不同调用点） |
| G4 | `tests/test_cli.py:296` | `'No history records' in captured.out` | `cli.py:519` 查询空态 → stdout |
| G5 | `tests/test_cli.py:1046` | `'Default domain set to jaden.local' in …out` | `cli.py:218` set 成功产物 → stdout（换 `print_msg`，通道不变） |

**新增**：`tests/test_cl005_hardening.py`（§6）。

### 4.2 其余实施点

| 件 | 改动 |
|:--|:--|
| `utils.py:33-38` | `eprint`→stderr；新增 `print_msg`；新增 `lock_dir()/lock_path()/acquire_start_lock()/release_start_lock()/_cmdline_is_this_cli()` + 4 常量（`CLOCK_MONOTONIC` 计时） |
| `utils.py` 其余 3 点 | 迁移提示/警告/失败 → stderr（随函数语义自动） |
| `cli.py` 28 点 / `server.py` 32 点 | 按 §2.1 表逐点改（产物 → `print_msg`；错误/警告 → `eprint`；671/929 分叉） |
| `cli.py:1798` | "Available:" 提示 → stderr（N-4） |
| `cli.py` web 段 | §1.2 表逐分支 `sys.exit(1|2)`；`run` cmd 失败 → 1 + 信封 `success=False` |
| `server.py:start()` | 锁 acquire 置于 isdir/index 后、`registry.find` 前；busy 路径按 D3.4；`try/finally` 按 D3.5；`registry.add` 失败 `_terminate_runner` 回滚 |
| `ensure_storage()` | 幂等建 `locks/` |
| `scripts/review-dispatch.sh` | 新增（D4） |

---

## 5 兼容与风险

| 风险 | 评估 | 缓解 |
|:--|:--|:--|
| `eprint` 通道变化 | 产物 23 点换名保 stdout；错误 38 点 + 2 分叉转 stderr | §2.1 逐点表 + §4.1 穷举同步 + 全量回归 |
| 退出码变化 | 仅「原 rc=0 的失败路径」改 1/2 | CHANGELOG `### Changed` + README |
| **时钟口径（F-2a）** | `time.monotonic()` 跨进程可比性非契约（py3.9.6 实测不可比）⇒ 改 `clock_gettime(CLOCK_MONOTONIC)` + 删负龄规则 | §6 T26/T27 双解释器回归 |
| 负龄兜底缺口 | 跨重启遗留锁若 pid 恰好被本 CLI 复用且 age<0 ⇒ fail-closed 等待 3s 后 rc=1 | 方向安全（不双持有）；stderr 指引 `hs kill` |
| 锁引入延迟 | 无竞争 <1ms；有竞争 ≤3.0s | 常量可调 |
| busy 掩盖 `-p` 越界 | D3.4③ abort 前语法校验 ⇒ rc=2 | T22b/A4 |
| `lock_dir()` 派生 `DATA_DIR` | 测试自动隔离；真实目录仅新增 `locks/` | conftest autouse |
| NFS 原子性 | 本地盘场景，锁目录固定 | 文档声明 |
| `dashboard`/`mcp` 未加锁 | 独立路径、非目标 | §0 声明 |
| 裸 print 机器模式 | 结构上由 json/url 提前 return 兜底（非函数级保证） | D1.3/D1.4 声明 + A3 三态契约断言 |

---

## 6 测试计划（T1–T27）与断言表（A1–A17）

### 6.1 测试

| # | 用例 | 断言要点 |
|:--|:--|:--|
| T1/T2 | `eprint` / `print_msg` 通道 | capsys 两通道分离 |
| T3 | `hs config`（默认） | stdout 含配置（产物） |
| T4 | `hs set port abc` | stdout 空 + stderr 有错误 |
| T5 | `hs <dir> --json` 全流程 | stdout 仅一个可 `json.loads` 文档 |
| T6–T14 | web 退出码矩阵 | 缺参/名非法→2；名已存在→**2**；`update --cmd ''`→**2**；show/remove 不存在→1；list 损坏→1；**run cmd 失败→1 + 信封 `success=False`**；run 损坏→1 |
| T15 | `hs web` 无子命令 | rc=0 + help |
| T16 | 并发 5 次同目录 start | registry 1 条 + **pid 同一性** + 无孤儿 |
| T17 | 有效锁 → 第二次 start | rc=1 + stderr「正在启动」 |
| T18 | stale 锁三态（无 pid / pid 死 / 超 TTL） | 各一次自愈 + 成功启动 |
| T19 | release 归属校验 | 他人锁不删；成功/失败/异常路径无残留 |
| T20 | **html 快捷方式同锁**（F-1①） | `lock_path()` 相等 |
| T21 | **mid-write 等待**（F-1②） | 空锁 + mtime 新 ⇒ 等待不删；mtime 陈旧 ⇒ 清锁重试 |
| T22a | `hs <dir> -p 70000`（无竞争） | rc=2（CL003 回归） |
| T22b | 持有效锁时 `-p 70000` | **rc=2**（F-1③） |
| T23 | 持有效锁时 `-p 8080` | rc=1 + 「正在启动」 |
| T24 | daemon tail / foreground 结束 | 锁释放 |
| T25 | `review-dispatch.sh --dry-run` | 双模板三路径 + 非法参数 rc≠0 |
| **T26** | **`CLOCK_MONOTONIC` 跨进程可比（F-2a）** | 两个独立子进程各打印 `clock_gettime(CLOCK_MONOTONIC)`：断言两者量级一致（差 < 60s）且 > 1e4（uptime 量级）；**同时**在系统 py3.9.6 解释器下复跑同一断言（防回退到 `time.monotonic()`） |
| **T27** | **负龄不删锁（F-2a）** | 伪造锁 `started_mono = now + 1e6`（负龄）且 pid 活/命令行命中 ⇒ **不删**、走 BUSY（等待→rc=1），不产生第二实例 |

### 6.2 断言表（ops harness `scripts/cl005-verify.py`）

| # | 断言 | 判据 |
|:--|:--|:--|
| A1/A2 | `eprint`/`print_msg` 通道 | 子进程实测分离 |
| A3 | 三态 stdout 契约 | 默认/`--url`/`--json` 形状（json 可 `json.loads`） |
| A4 | web 退出码矩阵 | §1.2 表逐行实测（含 `ValueError`→2、cmd 失败→1 + 信封 `success=False`） |
| A5 | 并发 5 次 | registry 1 条 + pid 同一性 + 无孤儿；**修前反证** worktree `4679ee8` ≥3 有效样本出现不一致 |
| A6 | 有效锁 fail-closed | 伪造锁（活 pid + 命令行含 `http_server_cli`）⇒ rc=1 |
| A7 | stale 锁三态自愈 | 无 pid / pid 死 / 超 TTL ⇒ rc=0 + 锁清理 |
| A8 | 锁无残留 | 注入目录无该 path 锁文件 |
| A9 | 派发件 | `--dry-run` 双模板三路径 + **真实派发产生非空 usage-file** |
| A10 | CL003/CL004 回归 | `port-flag-verify.py` 31/31 + `port-residual-verify.py` 13/13 |
| A11 | 全量回归 | `pytest tests/ -q` 0 failed（期望 ≥582：557 + 新增 ≥25） |
| A12 | 四同步 | `hs version`=v1.4.1；CHANGELOG；features 计数（`git ls-files tests/test_*.py \| wc -l`）；spec 1.4.1 + 新场景；README 退出码小节 |
| A13 | 残留 0 | registry/services 前后一致；无主 runner listener 0；`locks/` 清理 |
| A14 | 未越界 | `git diff` 复核：`hs set port` 语义/registry 字段/8180-8181/CL003 顺序链零变更 |
| A15 | html 同锁 + mid-write | T20/T21 真机版 |
| A16 | 归属/回滚 | release 不删他人锁；`registry.add` 失败无孤儿 |
| A17 | daemon/foreground 释放 + **时钟跨解释器** | T24 + T26（部署解释器与系统 py3.9.6 双跑） |

**并发/时序纪律**：就绪等待 ≤2s 轮询到 LISTEN；剔除幂等样本；≥3 有效样本；pid 同一性（禁计数相等、禁 `hs list --json`、禁 `in` 子串）；修前反证基线 `4679ee8`。

---

## 7 观察项（本批登记，不扩范围）

| # | 内容 | 处置 |
|:--|:--|:--|
| O7 | `hs set` / `hs search` 缺参用法提示走 stderr 但 **rc 仍 0**（CL003 未覆盖） | 登记，另批 |
| O8 | `hs dashboard`/`hs mcp` 的 `stop`/`restart` 在未运行时 **rc=0**、`--json` 信封 `success=False`（与 web 三态不一致） | 登记，另批 |
| O9 | 裸 `print()` 约 303 处，机器模式仅靠 `json`/`url` 提前 return 结构性兜底（无函数级保证） | 登记；本批仅收 `cli.py:1798` |
| O10 | `LOCK_WRITE_GRACE=1.0s` 取值保守（写内容 + fsync 超过 1s 的极端情形会误判 stale） | 登记；重负载下可调 |

---

## 8 闭环计划（独立模式全自动）

| 步骤 | 内容 | 产出 |
|:--|:--|:--|
| [1/6] 方案 | v1.0 `70c7a3d` / v1.1 `ecd0322` / 本版 v1.2 | `docs@design:` ×3 |
| [2/6] 设计评审 | 78 → 86 → 本版 round-3（**限定只审 F-2a/F-4a/N-2/N-4 闭合 + 本版增量**） | 报告 + 评分链 |
| [3/6] dev | 按 §2.1 表迁移 + web 退出码 + 启动锁 + 派发件 + §4.1 同步 + 四同步 | `fix@cli:` / `tests@cli:` / `docs@sync:` |
| [4/6] ops 核查 | `scripts/cl005-verify.py`（A1–A17，含修前反证 + 双解释器时钟） | `test@verify:` + 报告 |
| [5/6] 实现审计 | 用 D4 新派发模板（A9 实战验证） | `audit@review:` + push |
| [6/6] 收尾 | 复盘 + 清单 + 四件套 + 观察项 O7–O10 + `hm loop` 六步登记 | 收尾 commit + push |

---

## 9 实施记录与偏差（[3/6] dev 回填，2026-09-23）

### 9.1 D1 输出通道（落地与设计一致）

- `utils.eprint()` 语义纠正为 **stderr**；新增 `utils.print_msg()`（stdout），二者由 utils 顶部「通道契约」注释块定案。
- 63 处调用点按 §2.1 表迁移：产物/查询类 → `print_msg`（stdout 23 处），过程反馈/警告/错误/清理/用法 → `eprint`（stderr 38 处），三态分叉 2 处按分支各走各的通道。
- 机器模式（`--json`）stdout 仅信封；`--url` 仅单行 URL；`cli.py:1798`（web 运行失败提示）随本批归 stderr。
- 存量断言同步 12 处（§4.1）+ 可选加固 1 处（`test_server.py:76` 改为 `captured.err or captured.out`）。

### 9.2 D2 `hs web` 退出码三态（落地与设计一致 + 1 处实现期修正）

- 用法错误 → `sys.exit(2)`；运行期失败 → `sys.exit(1)`；成功/幂等 → 正常 return（rc=0）。
- **实现期修正（P1）**：`remove --json` 分支的 `return` 一度被改成 `sys.exit(1)`，会把**成功**也变成 rc=1（`test_remove_json` 立即变红）。已改回：成功 `json_output(True…)` + `return`，仅「名不存在」`sys.exit(1)`。
- **实施面补充（§4.1 未列）**：14 处 web 单测直接调用 `_COMMANDS['web']` 且不含 SystemExit 期望，本批按新三态改为 `pytest.raises(SystemExit)` + `code` 断言（`test_web.py` 13 处 + `test_port_flag.py` 1 处）。根因：§4.1 穷举口径是「`.out` 断言 grep」，覆盖不到这一类「直接调函数、默认不退出」的用例。
- 打桩纪律：web 单测统一 `monkeypatch.setattr('http_server_cli.cli.subprocess', SimpleNamespace(run=…))`——只替换模块内绑定，不用 `setattr('…subprocess.run')`（后者改到 stdlib 全局，会让 `utils.get_process_info` 拿到 `None` 而崩）。同一理由适用于新用例的锁打桩。

### 9.3 D3 目录级启动锁（落地 + 2 处偏差）

**偏差 D3-1（实质缺陷，已修）——等待路径必须新建 `Registry` 实例**

- 现象：T16（5 线程并发同目录启动）在 xdist 下偶发 **2–3 次真实 `Popen`**；`-n 0` 单跑常绿 ⇒ 时序依赖。
- 根因：`Registry.__init__` 把 `_get_cached_data()` 结果**快照**进 `self._data`（P2 mtime 懒加载缓存）。比「他人写入登记」更早创建的实例永远看不到新条目 ⇒ `_await_start_lock` 的 `find()` 恒为 `None` ⇒ 判「锁已释放且非就绪」⇒ 重试整链后**再启动一个 runner**。实测 trace：t0 popen → t2/t3/t4 `find` 命中 → t1 `find` 连续 `None` 直至超时并 popen（第 2 个 runner）。
- 修法：`_await_start_lock` 每轮轮询新建 `Registry()`（重新 stat + 必要时重读）；`start()` 在「等待结束、重试获取/幂等快径之前」`self.registry = Registry()` 刷新自身快照。
- 实证：修后同用例连续 3 轮 **5/5 True、`Popen` 恰 1 次、登记恰 1 条**；真机 5 进程并发 `hs <dir> -p 8097 --url` ⇒ 5/5 rc=0 + 同一 URL + 登记 1 条（pid 82744）+ `lsof -sTCP:LISTEN` 恰 1 个且 pid 一致 + 锁目录 0 残留。
- 边界：生产形态（一次调用一进程）不受影响（无长驻多实例共用内存快照），故未改 `Registry` 本体（避免扩散到 CL004 面），仅在本批新增的等待路径内收敛。

**偏差 D3-2（口径说明，非缺陷）——就绪快径不持锁**

- 等待路径判「另一实例已就绪」时第二实例并不持锁（首实例在 `--daemon` tail / `foreground` 期间仍持锁），直接走只读幂等快径（`idempotent_only=True`）返回 rc=0；该路径**不执行** `release_start_lock`（未获取 ⇒ 不释放，避免误删他人锁）。
- 残留窗口：快径校验通过后、`_start_locked` 内 `find` 之前条目消失（µs 级）⇒ 由 `idempotent_only` 分支返回 False（不启动、不清理），不产生第二个 runner。
- `finally` 只在本进程确实取得锁时释放；`release_start_lock` 的归属校验（仅删本进程锁）在快径不被触发。

### 9.4 D4 派发件模板（落地；本批 [5/6] 起自身即实战验证）

- 新增 `scripts/review-dispatch.sh`：`--target/--code/--project/--step/--date/--prompt` 唯一推导 派发壳/日志/用量 三路径；编号大小写归一；① 派发前校验提示词非空（缺失/空 ⇒ exit 2）② 生成物过 `bash -n` ③ 派发后校验 usage-file 非空（缺失/空 ⇒ 日志告警）。
- 步骤名由「编号 + 步骤」直接派生 ⇒ 复审轮次不再可能漏文件（CL004 复审轮 usage 缺失即 O6 根因）。
- 实测：`--dry-run` 三路径打印、缺参 exit 2、大小写归一、`--no-run` 生成物三行内容与 `bash -n` 由 pytest 用例 T25/T25b/T25c/T25d/T25e 守卫。

### 9.5 同步清单实际执行（§4.1 覆盖核对）

| 面 | 设计 §4.1 | 实际 | 差异说明 |
|:--|:--|:--|:--|
| 存量断言通道同步 | 12 必改 + 1 可选 | 13 | 逐条一致（`test_utils:222` / `test_cli:365,1053` / `test_server:76,87,135,228,250,314,320,326` / `test_port_flag:178,347`） |
| web 单测 SystemExit | 未列 | +15 | 见 9.2（口径缺口，本批补上并留档） |
| 版本三处 | `__init__` / CHANGELOG / spec | 3 + harness 2 | `scripts/port-{flag,residual}-verify.py` 的 1.4.0 断言改为「1.4.0/1.4.1 兼容」⇒ CL003/CL004 harness 保持可复跑 |
| 四同步 | CHANGELOG/features/README/spec | 4（+ README.zh） | README.zh 与 README 同步（退出码 + 启动锁 + stderr 口径） |
| 测试计数 | — | 557 → **590**（17 模块） | 新增 `tests/test_cl005_hardening.py` 33 用例 |

### 9.6 commit 分组（§8 计划 vs 实际）

| 组 | 内容 | 类型 |
|:--|:--|:--|
| 1 | `src/http_server_cli/{utils,cli,server}.py` | `fix@cli:` |
| 2 | `tests/**`（存量同步 + 新用例） | `tests@cli:` |
| 3 | `scripts/review-dispatch.sh` | `feat@tool:` |
| 4 | CHANGELOG/features/README×2/spec/`__init__` + 本 §9 + harness 兼容 | `docs@sync:` |

### 9.7 实测基线（dev 收口）

- 全量：`python3 -m pytest tests/ -q -n 4` ⇒ **590 passed**（连续 3 轮，~2.5s/轮），零回归。
- `hs version` ⇒ `http-server v1.4.1`；`hs web show <不存在>` ⇒ rc=1 且错误文案在 stderr。
- 真机并发（5 进程同目录同 `-p`）⇒ 1 登记 / 1 listener（pid 同一）/ 锁目录 0 残留；`hs kill 8097` rc=0。
- 修前反证基线：`4679ee8`（CL004 收尾）。
