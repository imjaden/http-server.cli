# HTTP-SERVER-CL005 设计复审 — review 报告 v1.0（round-3 design-rereview2）

- 件号：`documents/review/http-server-cli-cl005-design-rereview2-v1.0-20260923.md`
- 被审对象：`documents/http-server-cl005-hardening-design-v1.2-20260923.md`（commit `502a114`，449 行，含 §0 修订落点表 + §2.1 63 点判定表）
- 上轮：v1.1（`ecd0322`）→ CONDITIONAL_PASS 86/100（B+），2 🟡（F-2a/F-4a）+ 6 🟢（R-10~R-15）+ O7
- 范围限定（按指令）：只审 round-2 的 2 项 🟡 必改（F-2a 计时时钟 / F-4a 测试同步穷举）+ 2 项增量残留（N-2 措辞 / N-4 裸 print 范围）；只审本版增量是否引入新问题（§2.1 表自洽 / T26·T27 可复现 / O7–O10 恰当 / 负龄兜底链反例）；上轮已闭合项只在 §0 表核对转录
- 性质：设计复审（审闭合度 + 增量是否引入新问题），非实现审计

---

## 首段方向性判定（阻断检查）

**无阻断。** 两个方向性风险点经双解释器实测与全时序推演，均排除：

1. **CLOCK_MONOTONIC 可用且跨进程/跨解释器可比**：实测 conda py3.12 三进程 `236356.99 / 236357.00 / 236357.008`，系统 py3.9.6 三进程 `236357.04 / 236357.05 / 236357.06`，两解释器互差仅 ~0.07s（详见 §一）。
2. **负龄不删锁不引入双重持有**：全部可构造时序（跨重启 / pid 复用 / 伪造未来 started_mono）均 fail-closed，无「活 holder 锁被误删 → 双持有」反例（详见 §一 要求 2）。

---

## 四项闭合判定表（F-2a / F-4a / N-2 / N-4）

| 项 | round-2 要求 | 本版落点 | 判定 | 证据摘要 |
|:--|:--|:--|:--|:--|
| 🟡 F-2a 计时时钟 | `time.monotonic()` 跨进程可比性非契约（3.9.6 近零），`age<0⇒stale` 伪触发 | §2 D3.3：`clock_gettime(CLOCK_MONOTONIC)` + 删负龄规则 + T26/T27 | ✅ 闭合 | 双解释器 CLOCK_MONOTONIC 均跨进程可比（差 <0.07s）；负龄全时序 fail-closed；T26/T27 可复现（3×🟢 残留 R-16/R-17/R-18 见 §六） |
| 🟡 F-4a 测试同步穷举 | 漏 8 处将红断言 | §2.1 63 点判定表 + §4.1 穷举 12 必改 + 5 保持绿 | ✅ 闭合 | 全量 grep 与 12 条逐条对上、无遗漏；5 条保持绿实测成立；§2.1 抽查 ≥10 点全自洽（1×🟢 残留 R-22 标签） |
| 🟡 N-2 措辞 | D3.4①「命中且存活」致返回未就绪端口 | §2 D3.4① 改「命中且就绪（CL004 三态）」 | ✅ 闭合 | 「就绪」含端口活性判据，排除「pid 活但端口未 LISTEN」；（1×🟢 措辞级 R-23 见 §三） |
| 🟡 N-4 裸 print 范围 | 范围部分兑现、1798 走 stdout | §2 D1.3 范围 + 1798→stderr + D1.4 结构性兜底 + O9 | ✅ 闭合 | grep 裸 print=303 与设计一致；json/url 提前 return 兜底成立；仍漏机器模式点 = 无（2×🟢 措辞级 R-19 见 §四） |

---

## 基线核验（评审前提）

- `git status --porcelain` → 仅 review 侧三件套改动（`.review-level.yaml` / `review-log.md` 已修改 + 未跟踪 round-1/round-2 两份报告）。**源码零改动**（`git diff --stat HEAD -- src/` 为空），与指令「本轮源码仍未改动」一致，评审前提未破坏，首段无需标注异常。
- `git rev-parse HEAD` = `502a114`（v1.2 设计件）；`origin/main` = `4679ee8`；`git rev-list --count origin/main..HEAD` = 3（设计件 `70c7a3d` + `ecd0322` + `502a114`，均未 push）。
- `hs version` = v1.4.0（目标 1.4.1 未实施，符合「本轮只审设计」）。
- `PYTHONPATH=src python3 -m pytest tests/ -q` → **557 passed in 4.09s**（与基线一致）。
- 回归护栏：`scripts/port-flag-verify.py` 31/31、`scripts/port-residual-verify.py` 13/13（CL004 收尾产物，未随本轮变动）。
- 解释器环境：`/usr/bin/python3` = **3.9.6**（CommandLineTools）、conda py3.12 = `3.12.13`（`hs` shebang 实际部署态）。

---

## 一、F-2a 计时时钟 — 闭合

### 要求 1：双解释器 CLOCK_MONOTONIC 跨进程可比

实证命令（`/tmp` 最小实验，每解释器 3 独立子进程各打印一次）：

```python
# clock_probe.py
import time, subprocess, sys
code = "import time; print(time.clock_gettime(time.CLOCK_MONOTONIC))"
for _ in range(3):
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    print(float(r.stdout.strip()))
```

实测输出：

```
===== conda py3.12 (3.12.13) =====
proc1: 236356.992149   proc2: 236357.000132   proc3: 236357.007897
===== system py3.9.6 =====
proc1: 236357.040916   proc2: 236357.05102    proc3: 236357.060973
```

对照（`time.monotonic()`，证明原方案为何错误）：

```
py3.9.6  time.monotonic(): [0.003277625, 0.003401791, 0.003289583]   ← 近零、跨进程非单调
py3.12   time.monotonic(): [120272.9995, 120273.0064, 120273.0132]   ← CLOCK_UPTIME_RAW
```

判定：✅ **CLOCK_MONOTONIC 在双解释器下均跨进程可比**（py3.12 三进程差 <0.02s、py3.9.6 三进程差 <0.02s、两解释器互差仅 ~0.07s），且**跨解释器可比**。`time.monotonic()` 在 py3.9.6 返回近零（0.003s）的缺陷被坐实——设计改法正确。

### 要求 2：负龄不删锁是否引入新风险（全时序穷举）

锁判据链（D3.3）：`①不可解析 → ②pid 死 → ③pid 活但命令行非本 CLI → ④0≤age 且 age>TTL 才 stale；age<0 不参与判定`。

| 时序 | pid 态 | cmdline | age | 结果 | 是否双持有 |
|:--|:--|:--|:--|:--|:--|
| 跨重启遗留（started_mono 大、now 小） | 死（pid 空间重置） | — | <0 | ② unlink | 否 |
| 跨重启 + pid 被无关进程复用 | 活 | 非本 CLI | <0 | ③ unlink | 否 |
| 伪造未来 started_mono + 活 pid + cmdline 命中 | 活 | 命中 | <0 | ④ 不删 → BUSY → 轮询 3s → rc=1 | 否（fail-closed） |
| 伪造未来 started_mono + 锁 path 恰好命中「就绪」registry 条目 | 活 | 命中 | <0 | BUSY → D3.4① 幂等 rc=0 | 否（幂等返回既有端口） |
| 时钟异常（VM 迁移时钟回拨） | 任意 | — | <0 | 同跨重启/伪造 | 否（fail-closed） |

判定：✅ **「负龄不删锁」不引入双重持有**。负龄时唯一能抵达 ④ 的路径是「pid 活且 cmdline 命中」，此时落 BUSY → D3.4① registry 就绪判定：命中且就绪则幂等 rc=0（复用既有端口，无第二实例）；未就绪则轮询 3s 后 rc=1（fail-closed）。设计 §5「负龄兜底缺口」行的方向判断正确。

「holder 锁内容被外部截断为合法 JSON 但 started_mono 为未来值」子场景：若该伪造锁的 path 与 pid 均不指向真实服务，则只剩「pid/token 兜底 + registry 就绪判定」两道防线，最终 rc=1 fail-closed，不产生第二实例——与设计声明一致。残留边界（🟢，见 R-18）：伪造锁的 pid 若被「长期存活且 cmdline 命中本 CLI」的进程占用，会阻塞启动直到未来时间戳越过（约 offset 秒），属本地文件系统已沦陷前提下的可用性退化，非安全缺陷。

### 要求 3：T26 / T27 可复现性

**T26**（两独立子进程各打印 `clock_gettime(CLOCK_MONOTONIC)`，断言量级一致差 <60s 且 >1e4，双解释器复跑）：
- 实测：py3.12 三进程 236356.99/236357.00/236357.01（差 ~0.02s）；py3.9.6 三进程 236357.04/236357.05/236357.06（差 ~0.02s）。两解释器互差 ~0.07s。**「差 <60s」与「>1e4」均满足**（uptime 236415s）。✅ 可复现。
- 🟡/🟢 可复现性边界（R-16）：`> 1e4` 阈值为「uptime 量级」启发式，在 fresh-boot / 短寿命容器（uptime < 10000s ≈ 2.78h）下 CLOCK_MONOTONIC 合法地 <1e4，将**假失败**。本机（uptime 236415s）不受影响；建议将阈值放宽或改为「跨进程差 < 阈值 + 值远大于 time.monotonic() 的 3.9.6 近零（如 >1e2）」以兼顾容器可移植性（见 R-16）。

**T27**（伪造锁 `started_mono = now + 1e6` 且 pid 活/命令行命中 ⇒ 不删、走 BUSY 等待→rc=1，不产生第二实例）：
- 判定：✅ 可复现。`started_mono` 未来值 ⇒ age<0 ⇒ ④ 不删 ⇒ BUSY。实现要点：需一个「pid 活 + cmdline 命中本 CLI」的 holder pid，可 monkeypatch `is_process_alive→True` + `_cmdline_is_this_cli→True`（锁逻辑落在 utils 模块、常量可 monkeypatch，设计 D3.6 已声明），或 spawn 真实 `hs`/runner 进程。断言「不产生第二实例」以 registry 条目数 + pid 同一性判据（设计 §6 纪律已定）。无不可复现点。

---

## 二、F-4a 测试同步穷举 — 闭合

### 要求 1：全量 grep 与 §4.1 12 条逐条比对

实证命令：`grep -rn "captured\.out\|capsys" tests/`（全量，含 test_port_flag/test_web/test_port_probe/test_doc_* 等）

实测：§4.1 的 **12 条必改** 与 grep 结果逐条对上，**无遗漏**（设计已补出 round-2 漏列的 `test_port_flag.py:178` 与 `:347` 两条）：

| # | 位置 | 文案 | 源码 eprint 点 | grep 实测 |
|:--|:--|:--|:--|:--|
| 1 | test_utils.py:222 | migration failed | utils.py:73 | ✅ 命中 |
| 2 | test_cli.py:365 | Usage | cli.py:172 | ✅ 命中 |
| 3 | test_cli.py:1053 | domain must match | cli.py:212 | ✅ 命中 |
| 4 | test_server.py:87 | all in use, cannot start | server.py:354 | ✅ 命中 |
| 5 | test_server.py:135 | Path does not exist | server.py:204 | ✅ 命中 |
| 6 | test_server.py:228 | not managed by this tool | server.py:607 | ✅ 命中 |
| 7 | test_server.py:250 | still running in background | server.py:478 | ✅ 命中 |
| 8 | test_server.py:314 | not registered（kill 端口） | server.py:692 | ✅ 命中 |
| 9 | test_server.py:320 | not registered（kill 路径） | server.py:704 | ✅ 命中 |
| 10 | test_server.py:326 | Please specify | server.py:680 | ✅ 命中 |
| 11 | test_port_flag.py:178 | not registered（直调 kill） | server.py:692 | ✅ 命中 |
| 12 | test_port_flag.py:347 | not running（restart 分叉） | cli.py:671 | ✅ 命中 |

补充复核：`test_port_flag.py:178` 实测直调 `ServerManager().kill('59999')`（→server.py:692）；`:347` 实测 `_manage_dashboard('restart', json_mode=False)`（→cli.py:671 分叉取 stderr），与设计标注一致。`test_web.py` 错误/警告断言（`add_missing_cmd`/`show_not_found`/`remove_not_found`/`update_not_found`/`cmd_nonzero_exit_warns`/`conflicts`）均已用 `.err`，`test_port_probe.py` stale 文案（`:350`/`:371`/`:395`）均已用 `.err`（CL004 D6 已转 stderr），**无新增将红断言**。`test_doc_*` 文件不存在（`git ls-files tests/test_*.py` 16 个，无 doc 前缀），属指令中「他文件」假设，实测为无。

判定：✅ **12 条穷举完整，无遗漏**。

### 要求 2：§4.1「保持绿」5 条核实

| # | 位置 | 文案 | 源码调用点 | 通道 | 实测 |
|:--|:--|:--|:--|:--|:--|
| G1 | test_server.py:180 | No running HTTP services | server.py:519 | 查询空态→stdout | ✅ |
| G2 | test_server.py:336 | No running services | server.py:785 | 动作无操作→stdout | ✅ |
| G3 | test_server.py:220 | not registered | server.py:616 | status 答案→stdout | ✅ |
| G4 | test_cli.py:296 | No history records | cli.py:519 | 查询空态→stdout | ✅ |
| G5 | test_cli.py:1046 | Default domain set to jaden.local | cli.py:218 | set 成功产物→stdout | ✅ |

判定：✅ 5 条全部真绿。G3 关键核对：`server.py:616`（status「not registered」答案，非 json else 分支）与 kill 的 `:692` 分属不同调用点，`test_server.py:220`（status）→ stdout、`:314`（kill）→ stderr，同文案分叉正确。G5 核对：`test_cli.py:1046` 走 `cli.py:218`（`eprint(f'Default domain set to {value}', '✅')`），换 `print_msg` 后通道不变（stdout）。

### 要求 3：§2.1 表抽查 ≥10 点（源码控制流 × 机器模式可达 × 归类自洽）

| 点 | 源码实测 | 机器模式可达 | 归类 | 判定 |
|:--|:--|:--|:--|:--|
| server.py:519/520 | list 空态，json 在 516-517 提前 return | 否（非 json else） | stdout 查询空态 | ✅ 自洽 |
| server.py:616 | status 未注册，json 分支 600-603 提前 return | 否（非 json else） | stdout 查询答案 | ✅ 自洽 |
| server.py:785 | kill_all 空态，json 782-783 提前 return | 否（非 json else） | stdout 动作无操作 | ✅ 自洽 |
| cli.py:363/364 | _list_servers 空态，json 354-359 提前 return | 否 | stdout 查询空态 | ✅ 自洽 |
| cli.py:671（分叉） | _manage_dashboard not-entry，status/stop/restart 共用 | status 有 json 信封、stop/restart 有 json 信封 | status→stdout / stop·restart→stderr | ✅ 自洽（需按 subcmd 拆分实现） |
| cli.py:929（分叉） | _manage_mcp not-entry，同 dashboard 结构 | 同 | 分叉 | ✅ 自洽 |
| cli.py:196 | set port 成功 `eprint(...'✅')` | 有 json 信封（193-194）提前 return | stdout 产物（换 print_msg 通道不变） | ✅ 自洽 |
| cli.py:218 | set domain 成功 | 有 json 信封（214-216） | stdout 产物 | ✅ 自洽 |
| utils.py:64 | 迁移成功通知 | 否（启动期，无 json） | stderr 过程反馈 | ✅ 自洽 |
| utils.py:68 | 迁移降级（copy 成功） | 否 | stderr 警告 | ✅ 自洽 |
| utils.py:73 | 迁移失败 | 否 | stderr 错误 | ✅ 自洽 |

统计核对：`stdout 23 / stderr 38 / 分叉 2` = 63，算术自洽（23 产物类换名不改通道；38+2 真换通道；分叉 2 点仅 stop/restart 子命令换通道，status 子命令保持 stdout）。

判定：✅ 抽查 ≥10 点全部自洽，**无判错的点**。唯一 🟢 标签误差（R-22）：§2.1 #7 `cli.py:212` 标签「set 写盘失败」失实——实测 line 212 是 domain 分支 `except ValueError` 的 `eprint(str(e),'❌')`（即「domain must match」非法值），非「写盘失败」；通道归 stderr 正确、§4.1 #3 测试映射正确，仅描述性标签错。

---

## 三、N-2 措辞 — 闭合

本版 D3.4①：「命中且**就绪**（复用 CL004 三态：entry_pid 非空 + 进程活 + 端口 LISTEN ⇒ ready；他方占端口 ⇒ others_own_port）」。

判定：✅ **该措辞足以排除「返回未就绪端口」**。「就绪」判据含「端口 LISTEN/占用」，不再以「pid 存活」为唯一条件，因此「holder 已 registry.add 但 runner 尚未 bind 端口」的窗口不再被误判为就绪（round-2 N-2 的核心隐患）。「未就绪 → 不进幂等」已明示，落 ② 轮询。

🟢 措辞级（R-23，非阻断）：`ready` 的字面判据「进程活 + 端口 LISTEN」是 CL004 三态的**简化**——CL004 实际代码（server.py:216）立即判据用 `is_process_alive(entry_pid) and is_port_in_use(port)`（`is_port_in_use` 不区分监听者），宽限路径（server.py:224-238）才用 `get_pid_by_lsof(port, listen_only=True)` 校验「entry_pid in listeners」。精确措辞建议：`ready = entry_pid 非空 + 进程活 + 端口被 entry_pid 监听（lsof -sTCP:LISTEN 确认）`，`others_own_port = 端口被非 entry_pid 占用`。因 D3.4① 已明示「复用 CL004 三态」并据此语义委托，实现者照 CL004 现有代码落地即无 TOCTOU，本点不构成必改。

---

## 四、N-4 裸 `print()` 范围 — 闭合

实证命令：`grep -rn "print(" src/`（不含 eprint/print_msg/def print）

实测输出：裸 `print(` = **303 处**（与设计「约 303 处」一致），分布：`cli.py` 213 / `server.py` 50 / `dashboard.py` 16 / `mcp.py` 10 / `config.py` 8 / `utils.py` 3 / `runner.py` 3。

结构性兜底核验（逐文件）：

| 文件 | 裸 print | json/url 提前 return | 机器模式可达 | 判定 |
|:--|:--|:--|:--|:--|
| cli.py (213) | help/清单/产物/dashboard/MCP/prompt | 各命令 json 分支提前 return | 除 1798 外均否 | ✅ |
| server.py (50) | start 产物/status 诊断/kill 结果 | start json/url 分支提前 return（server.py:250-269/315-341） | 否 | ✅ |
| config.py (8) | `show()` 文本 | `show(json=True)` 81-89 提前 return | 否 | ✅ |
| runner.py (3) | 服务启动 banner | 输出重定向日志文件（D1.4） | 否 | ✅ |
| dashboard.py (16) / mcp.py (10) | 服务端产物 | `json_output_mode` 信封提前 return | 否（且非目标） | ✅ |

仍漏的机器模式可达点：**无**。唯一需改动 `cli.py:1798`（`_web_run` name-not-found 分支的 `print(f'   Available: ...')`）已正确归 stderr。

🟢 措辞级（R-19，非阻断）：D1.3 表对 `cli.py:1798` 的标注「机器模式可达」不精确——实测 1798 处于 `if not svc:` 的 **非 json else 分支**（1792-1793 json_mode 分支 `json_output` 后 1799 `sys.exit(1)` 已提前退出），机器模式（web 仅 `--json`，无 `--url` 机器模式）并不抵达。正确归因是「失败分支（rc=1）语义按 D1.2 应归 stderr」，而非「机器模式可达」；结论（1798→stderr）不变。另 D1.3 表「status 无 json 模式」失实——status **有** `--json`（server.py:601-603/623-624/635-654），但 `server.py:610-614` 占用诊断块位于非 json else 分支，json 模式提前 return 不抵达，故「保持 stdout」结论仍正确。

---

## 五、本版增量审项

### M-1：§2.1 分叉实现与 §3.2 自洽 + 测试影响面

判定：✅ **自洽**。分叉（`cli.py:671` dashboard / `cli.py:929` mcp）仅改**通道**（status→stdout、stop·restart→stderr），**不改退出码**（三子命令 not-running 均 `return` rc=0，与现状一致）。§3.2 退出码表不含 dashboard/mcp stop·restart not-running 行，该 rc=0 由 **O8** 显式登记为「另批」，无自相矛盾。

测试影响面：全量 grep `not running`（dashboard/mcp，非 json 文本断言）仅 **test_port_flag.py:347**（restart）一处；`test_cli.py:964/1007` 走 `result['error']`（json 信封，不受分叉影响）。**无其它受影响测试**。

### M-2：观察项 O7–O10 恰当性

判定：✅ **均恰当，无需升格为本批必改**。

- **O7**（set/search 用法提示 stderr 但 rc=0）：与 D2 三态（用法→2）不自洽，但 CL003 未覆盖 set/search，本批不扩，登记合理。
- **O8**（dashboard/mcp stop·restart not-running rc=0 + json `success=False`）：真实的不一致（`hs web run nonexistent`→1 vs `hs dashboard stop` 未运行→0），但 dashboard/mcp 显式「非目标/不入锁」，且为**既有行为**（非本批引入），登记另批合理。**建议**：后续独立批统一 dashboard/mcp 退出码三态（失败 rc=1），并保持 `success=False` 信封语义。
- **O9**（裸 print 303 处、机器模式靠 json/url 提前 return 结构性兜底）：登记合理，本批仅收 `cli.py:1798`，全量逐点审计仍推迟实现（与 R-15 同）。
- **O10**（`LOCK_WRITE_GRACE=1.0s` 保守值）：登记合理（写内容+fsync >1s 的病理磁盘会误判 stale，属 F-1② 残留 R-10 的延续）。

### M-3：测试数预期「≥582」合理性

判定：✅ **合理**。逐条数 T1–T27（含 T6–T14 为 9 条 web 矩阵、T1/T2 为 2 条、T18 三态计 1 条）：

`T1/T2(2) + T3 + T4 + T5 + T6~T14(9) + T15 + T16 + T17 + T18 + T19 + T20 + T21 + T22a + T22b + T23 + T24 + T25 + T26 + T27 = 28`。

557 + 28 = **585** ≥ 582。设计「新增 ≥25」为**保守下限**（实际枚举 28），不会致假通过；`≥582` 作为 A11 阈值可复跑（基线 557 已实测）。既有的 12 条 `.out→.err` 修改不计新增，符合指令。

### M-4：A11 阈值 / A12 四同步判据可复跑、无恒真

判定：✅ **可复跑、无恒真**。A11「pytest tests/ 0 failed」实测基线 557；A12「`git ls-files tests/test_*.py | wc -l`」实测 **16**（与 CL004 AUD-1「模块数 18→16」同口径，非恒真——增减测试模块即变）。

🟢 标签（R-20）：A12 将「`git ls-files tests/test_*.py` 计数」标为「features 计数」失实——该命令计数的是**测试模块数**（16），非 features.md 的 feature 条数；应改标「模块数」。命令本身可复跑、判据非恒真，仅标签错。

### M-5：§5 风险表遗漏本版新增风险

判定：**漏 2 行**（🟢，建议补入，非阻断）：

1. **CLOCK_MONOTONIC 容器/虚拟化语义 + T26 阈值脆弱**：容器/VM 中 CLOCK_MONOTONIC 可能绑定宿主/命名空间时钟，短寿命容器 uptime < 10000s 时 T26 `>1e4` 断言假失败（R-16）。§5「时钟口径」行仅提「3.9.6 可比性 + T26/T27 回归」，未提容器/虚拟化。
2. **非 macOS 平台 `clock_gettime` 等价性**：设计 D3.3 未保留 round-2 报告建议的「Windows 无 CLOCK_MONOTONIC 时回退 time.monotonic()」；实测本机 `hasattr(time,'CLOCK_MONOTONIC')=True`（macOS/Linux/Windows≥3.3 均有），但 Linux 的 CLOCK_MONOTONIC 为 sleep-inclusive、macOS 为 mach_continuous_time（sleep-inclusive），语义差异未在 §5 声明。

另有 🟢（R-18）：实测 CLOCK_MONOTONIC = **236415s**（= boottime，mach_continuous_time，sleep-inclusive），而 `time.monotonic()` = **120331s**（CLOCK_UPTIME_RAW，sleep-exclusive）。设计「免疫休眠停滞」成立（睡眠期间时钟照走），但**隐含**：TTL(30s) 在 >30s 系统睡眠后会触发 ④ stale。该风险被 start() 幂等（registry.find→ready，server.py:208-290）兜底——活 holder 即便锁被 ④ 清，后续 start 仍幂等返回 rc=0，不产生第二实例——故**无双重持有**，但 §5 应注明「CLOCK_MONOTONIC sleep-inclusive 使 TTL 在睡眠后触发，由 registry 幂等兜底」。

### 负龄兜底链反例

见 §一 要求 2 全时序表。**无反例**导致双重持有。唯一残余（🟢 R-18 后半）：伪造锁 started_mono 未来 + 长存活匹配 cmdline 的 pid 会阻塞启动至未来时点，属本地文件系统已沦陷下的可用性退化，fail-closed。

---

## 六、安全事项

- 🟢 **R-16**：T26 `>1e4` 阈值在 fresh-boot/短寿命容器（uptime <10000s）下假失败；建议改「跨进程差 <阈值 + 值显著 > time.monotonic() 3.9.6 近零（如 >1e2）」。
- 🟢 **R-17**（M-5）：§5 风险表漏「CLOCK_MONOTONIC 容器/虚拟化语义」「非 macOS clock_gettime 等价性」两行。
- 🟢 **R-18**：CLOCK_MONOTONIC 在 macOS = mach_continuous_time（sleep-inclusive，236415s≠time.monotonic() 120331s）；睡眠 >TTL 触发 ④ 由 registry 幂等兜底，无双持有，§5 应注明；负龄伪造锁长阻塞为本地沦陷前提的可用性退化。
- 🟢 **R-19**：D1.3 表 `cli.py:1798` 标「机器模式可达」不精确（实为非 json else 分支）；「status 无 json 模式」失实（status 有 --json，610-614 在非 json else 分支）。两处结论均正确。
- 🟢 **R-20**：A12「features 计数」应为「模块数」（=16，同 CL004 AUD-1 口径）。
- 🟢 **R-21**：D9「五处同步」枚举 6 项（`__init__.__version__` 与 `__release_date__` 同文件两属性 + CHANGELOG + hs version + features.md + spec.yaml），计数措辞歧义。
- 🟢 **R-22**：§2.1 #7 `cli.py:212` 标签「set 写盘失败」应为「set domain 非法值」。
- 🟢 **R-23**：N-2「端口 LISTEN」为 CL004 三态简化（立即判据用 is_port_in_use，宽限用 lsof LISTEN），建议措辞精确化。
- 🟢（承上轮，未闭合观察项）：O7/O8/O9/O10 维持登记，另批。

无 🟡/🔴 必改残留，无注入面/越权/敏感信息新增（本轮为设计件，源码零改动）。

---

## 评分

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 合理性（方向正确性） | 25/25 | F-2a 改法正确（CLOCK_MONOTONIC 双解释器可比 + 负龄 fail-closed）；F-4a 穷举完整；方向无残留错误 |
| 严格性（判据完备） | 22/25 | T26 阈值脆弱（R-16）+ §5 漏容器/跨平台两行（R-17）+ 睡眠 TTL 语义未入 §5（R-18） |
| 可执行性（落点清晰） | 24/25 | 63 点表 + 12 条同步清单完整可执行；A12「features 计数」标签错（R-20） |
| 回归风险控制 | 22/25 | 12+5 条实测无遗漏；T26 脆弱 + §5 睡眠语义缺口影响可移植回归 |
| **合计** | **93/100** | Rating **A-**（78 → 86 → 93） |

评分链：78（round-1 CONDITIONAL_PASS）→ 86（round-2 CONDITIONAL_PASS）→ **93（round-3 PASS）**。

---

## 结论

**PASS**（93/100，A-）。round-2 的 2 项 🟡 必改（F-2a / F-4a）与 2 项增量残留（N-2 / N-4）**全部闭合**，本版增量（§2.1 表 / T26·T27 / O7–O10 / 负龄兜底链）无方向性错误、无双重持有反例。剩余 8 项 🟢 记录（R-16~R-23）均为标签/措辞/可移植性/风险表完备性，非阻断，随实现 commit 或下批 docs@sync 同批勘误即可。

### 🟢 记录清单（同批落点，非阻断）

| # | 标题 | 落点 |
|:--|:--|:--|
| R-16 | T26 `>1e4` 阈值 fresh-boot/容器假失败 | 设计 §6 T26 |
| R-17 | §5 风险表漏容器/虚拟化 + 非 macOS 两行 | 设计 §5 |
| R-18 | CLOCK_MONOTONIC sleep-inclusive 使 TTL 睡眠后触发（幂等兜底）；负龄伪造锁长阻塞 | 设计 §5 / §2 D3.3 |
| R-19 | D1.3「1798 机器模式可达」/「status 无 json 模式」两处措辞失实 | 设计 §2 D1.3 |
| R-20 | A12「features 计数」应为「模块数」 | 设计 §6 A12 |
| R-21 | D9「五处同步」枚举 6 项计数歧义 | 设计 D9 |
| R-22 | §2.1 #7 `cli.py:212` 标签「写盘失败」→「domain 非法值」 | 设计 §2.1 |
| R-23 | N-2「端口 LISTEN」措辞可精确化（lsof listen_only） | 设计 §2 D3.4① |
