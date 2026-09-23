# http-server.cli CL005 实现审计报告 v1.0

- 件号：`documents/review/http-server-cli-cl005-audit-v1.0-20260923.md`
- 设计依据：`documents/http-server-cl005-hardening-design-v1.2-20260923.md`（v1.2，设计复审 PASS 93/100，含 §9 实施记录与偏差）
- 被测对象（5 笔 commit）：`f3a4ac6`（fix@cli src）· `7e92521`（tests@cli）· `709424d`（feat@tool 派发件）· `0706bd4`（docs@sync 四同步 + §9）· `31bf823`（test@verify ops harness）
- 审计基线：HEAD `31bf823`，本地 ahead 5（未 push），工作树 clean
- 修前反证基线：`4679ee8`（CL004 收尾）
- 审计人：Security Reviewer（review profile）· 日期：2026-09-23
- 环境：macOS 26.6.2 · `hs` = conda py3.12 editable 安装（指向本仓 `src/`，实测 `pip show` editable + `utils.__file__` 命中本仓）· 真实 registry 9 服务在跑

## 0 结论（前置）

**CONDITIONAL_PASS（90/100，Rating: A-）** —— 1 项 🟡 必改（D3.5 registry.add 回滚未实现）+ 3 项 🟢 记录；核心交付（D1 输出通道 / D2 web 退出码 / D3 启动锁互斥 / D4 派发件）全部实测成立，无方向性冲突、无回归。

核心结论：
- **D1 输出通道**：独立 AST/grep 静态扫描 63 点表（stdout 23 / stderr 38 / 分叉 2）逐点对账**零漏点零错归类**；新增 4 处锁相关 `eprint` 均走 stderr。`eprint`→stderr / `print_msg`→stdout 子进程实测分离；5 条错误路径在 `--json`/`--url` 下 stdout 仅信封/单行 URL 且 `json.loads` 可解析。
- **D2 web 退出码三态**：14 行矩阵独立实测逐行命中（用法→2 / 运行期→1 / 成功幂等→0）；P1 修正（`remove --json` rc=0）复核已修正；cmd 失败信封 `success=false`+`data.status=cmd_failed`+`data.exit_code` 命中。
- **D3 目录级启动锁（本批核心）**：并发互斥 3 样本（registry 1 条 + **pid 同一性** + 无孤儿 + 锁 0 残留）；**修前反证**基线 worktree 3/3 样本 `registry pid ≠ listen pid`（竞态真实）；锁键归一（`hs index.html` 与 `hs <dir>` 同 sha1 `e4ee1cc7e9e546ed`）；stale 四判据逐例自愈 + 负龄不删（fail-closed rc=1）；mid-write 新鲜空锁等待不删 / 陈旧清锁重试；等待三态（fail-closed rc=1 / daemon 幂等 rc=0 / 用法错误优先 rc=2）；**D3-1 偏差独立复现**（临时副本回退两处修法 → 5 并发 3 样本各 **4 个真实 runner + registry 仅 1 条**；恢复后 3 样本恒 1 runner 1 条）。
- **D4 派发件**：`--dry-run` 三路径 / 缺必填 rc=2 / 空提示词 rc=2 / `bash -n` / 大小写归一全部实测；**本轮审计自身即由该模板派发**（派发壳 LOG/PROMPT/USAGE 三行与落盘件逐字核对一致，A9 实战成立）。
- 全量回归 `pytest tests/ -q -n 4` = **590 passed**；§4.1 12 必改断言全量 grep 逐条 `.err` 命中；四同步（`__init__`/CHANGELOG/spec = 1.4.1、features 计数 17 模块、spec 新场景、README 双语言退出码）实测为真。

**🟡 必改（SEC-1）**：设计 §2 D3.5 明确要求「`registry.add` 抛异常 ⇒ 释放锁前先 `_terminate_runner` 终止本次 runner ⇒ 不产生孤儿」，§9.3 以「落地 + 2 处偏差」隐式声称已实现；**实测代码未实现**（`server.py` 唯一 `_terminate_runner` 调用在 stale 清理 line 386，`registry.add` line 496 无 try/except 回滚），monkeypatch `registry.add` 抛异常后 runner **仍存活（孤儿）**。修复 trivial（约 3–5 行）。非回归（CL005 前同现象）、触发罕见（磁盘满/权限），但属设计必改项未落地，判 🟡。

---

## 一、数据验证（独立复算，不采信 ops 21/21 与 dev 自评）

| 项 | 实测 | 判定 |
|:--|:-----|:--|
| git HEAD | `31bf823`（ahead 5，`git status --porcelain` 空） | ✅ 与基线一致 |
| `hs version` | `http-server v1.4.1` | ✅ |
| 全量回归 | `pytest tests/ -q -n 4` → **590 passed in 2.52s**（0 failed） | ✅ |
| 静态扫描 63 点 | `eprint` 44 处（cli 14 / server 25 / utils 5）+ `print_msg` 25 处（cli 16 / server 9）= 设计 63 + 4 新增锁 eprint | ✅ 逐点对账 |
| registry.py 改动 | `git diff 4679ee8 f3a4ac6 -- src/http_server_cli/registry.py` = **空** | ✅ 零改动 |
| 新增 8180/8181/MAX_PORT | `git diff 4679ee8 f3a4ac6 -- src/ | grep 8180|8181|MAX_PORT` = 仅 MAX_PORT=10000 上下文行 | ✅ 无新增保留端口 |
| 审计前后 registry/services | 真实 `~/.http-server.cli/registry.json` 9 条 / `services.json` 11 条不变（本审计全部子进程走隔离 HOME） | ✅ 无污染 |
| `locks/` | 真实 `~/.http-server.cli/locks/` 空 | ✅ |

---

## 二、逐项审计（实证命令 + 实测输出 + 判定）

### A. D1 输出通道

- **静态扫描（独立，非采信 ops）**：`grep -n 'eprint(' cli.py/server.py/utils.py` 得 14/25/5 处，`grep -n 'print_msg('` 得 16/9/0 处。与 §2.1 表逐点对账：stdout（print_msg）23 点 + 分叉 2 点（`cli.py:672/933` status 分支）→ 25 处全部命中；stderr（eprint）38 点 + 分叉 2 点（`cli.py:674/935` stop/restart 分支）→ 40 处全部命中；**新增 4 处锁相关 eprint**（`server.py:195/199`、`utils.py:374/377`）均走 stderr（警告/失败，归类正确）。**零漏点、零「错误类仍写 stdout」漏网。**
- **通道实测**：`hs set port abc` → stdout 空 + stderr `❌ Invalid port number: abc`；`hs list` → stdout 产物 + stderr 空。
- **反例搜索（5 条）**：`hs <nodir> --json`/`--url`、`hs <dir> -p 8180 --json`、`hs kill 99999 --json`、`hs web show nope --json` → 5/5 stdout 仅 JSON 信封（`json.loads` 成功）或空（--url），stderr 空；成功路径 `hs <dir> -p 8091 --url` → stdout 1 行 URL；幂等 `--json` → `json.loads` OK。
- **行为迁移未破坏**：`hs kill 8091` → rc=0，产物「Terminated PID」在 stdout、清理「Log deleted」在 stderr；`hs status 8091` → 答案 stdout；`hs kill 99999`（非注册）→ rc=1 + stderr。
- **N-4 修正**：`hs web nope`（存在其它服务）→ stdout 空 + stderr 含 `Available: x, zz`；`--json` 模式不打印 Available。
- **判定：✅**。

### B. D2 `hs web` 退出码三态

14 行矩阵独立实测（隔离 HOME）：

| 用例 | rc | 期望 | 判定 |
|:--|:--|:--|:--|
| `add` 缺 `--cmd` | 2 | 2 | ✅ |
| `add list`（名冲突） | 2 | 2 | ✅ |
| `add a --cmd 'echo a'`（成功） | 0 | 0 | ✅ |
| `add a`（名已存在） | 2 | 2 | ✅ |
| `add b --open bogus`（open 非法） | 2 | 2 | ✅ |
| `update a`（无参数） | 2 | 2 | ✅ |
| `update a --cmd ''`（空 cmd） | 2 | 2 | ✅ |
| `show nope`（不存在） | 1 | 1 | ✅ |
| `remove nope`（不存在） | 1 | 1 | ✅ |
| `remove a --json`（存在，P1 边界） | **0** | 0 | ✅ 已修正 |
| `remove a`（已删再删） | 1 | 1 | ✅ |
| `list` | 0 | 0 | ✅ |
| `web`（无子命令） | 0 | 0 | ✅ help 在 stdout |
| `web x --no-probe --json`（cmd 失败） | 1 | 1 | ✅ 信封 `success=false` + `data.status=cmd_failed` + `data.exit_code=1` |

- **判定：✅**。P1（`remove --json` 曾误改 rc=1）复核已修正（成功 `json_output(True)` + return，仅「名不存在」`sys.exit(1)`）。

### C. D3 目录级启动锁（重点）

**C1 并发互斥（3 样本 × 5 进程同目录同 `-p`）**：sample1/2/3 均 `registry_entries=1`、`regpid == listen_pids`（pid **同一性**，lsof `-sTCP:LISTEN -F p` 直取，非计数/非子串/非 `hs list --json`）、`lock_residual=[]`、5 进程全 rc=0 同 URL。无孤儿 runner。

**C1′ 修前反证（基线 worktree `4679ee8`）**：同法 3 样本 → sample1 `regpid=9780 ≠ listen=9776`、sample2 `9858 ≠ 9853`、sample3 `9894 ≠ 9889`，**3/3 registry pid ≠ listen pid**（「先 Popen 后登记」竞态真实，判据非恒真）。

**C2 锁键归一**：`hs index.html` 经 `_prepare_start_target` 归一父目录后，`lock_path(dir)` == `lock_path(html归一)` == `…/locks/e4ee1cc7e9e546ed.json`（同 sha1）。

**C3 stale 四判据 + 负龄（CLI 子进程级）**：
- ① 不可解析 + mtime 陈旧 5s → rc=0 + 清锁自愈；
- ② pid 非活 999999 → rc=0 + 清锁；
- ③ pid 活但命令行非本 CLI（`sleep 30`）→ rc=0 + 清锁；
- ④ pid 活 + 命令行命中 + 龄 >30s → rc=0 + 清锁；
- 负龄（`started_mono = now + 1e6`，pid 活 + 命令行命中）→ **不删锁**、fail-closed rc=1 + stderr `另一实例正在启动（pid …）`。

**C4 mid-write**：空锁文件 + 新鲜 mtime → 等待 3s 不删（rc=1，锁保留）；并发级（`os.open O_CREAT|O_EXCL` 占位不写内容）→ 同样等待不删；陈旧空锁（判据①）→ 清锁重试 rc=0。

**C5 等待三态**：有效锁（live CLI holder）→ rc=1 + stderr `另一实例正在启动（pid …）`、他人锁未删；`--daemon` tail 长持锁期间第二实例 → 幂等 rc=0、登记 1 条 + LISTEN 1 个；锁释放→重试整链命中幂等（C1 3 样本 5/5 rc=0 同 URL 即为实证）。

**C6 用法错误优先**：持有效锁时 `hs <dir> -p 70000` → 3.1s 后 rc=**2** + stderr `Port must be between 1024-65535`（不被锁等待掩盖为 rc=1）、他人锁未删。

**C7 实施偏差 D3-1 独立复现**：临时副本 `/tmp/cl005-bug-repro-src`（回退 `_await_start_lock` 的 `Registry()` → `self.registry` + 删除 `start()` 内 `self.registry = Registry()` 刷新）→ 5 并发 auto-port × 3 样本，各样本 **4 个真实 runner（4 个不同 URL）+ registry 仅 1 条（3 孤儿）**；恢复当前工作树 → 3 样本恒 **1 runner + 1 条 + 锁 0 残留**。**修法恰当**：`Registry.__init__` 走模块级 `_get_cached_data()`（P2 mtime 缓存），比他人写入更早构造的实例看不到新条目；等待路径是唯一跨秒级轮询持有快照的路径，生产形态（一次调用一进程）不受影响 ⇒ 在新增等待路径内收敛（每轮 `Registry()` + 重试前刷新 `self.registry`）是**最小且正确**的修法，不必改 `Registry` 本体（改本体会扩散到 CL004 的 list/status/kill 全调用面）。

**C8 锁无残留 + 归属**：正常路径锁释放（C1/C7 修复后锁 0 残留）；异常/被杀路径由 stale 判据②（pid 非活）自愈（C3② 实测）；`release_start_lock` 归属校验（内容 pid == 本进程才删）实测不删他人锁（C5 有效锁保留）。

**🟡 唯一缺陷（见 §三 SEC-1）**：`registry.add` 失败回滚未实现（D3.5 bullet 2）。

### D. D4 派发件模板

- `--dry-run` 三路径：`编号/步骤/派发壳/日志/提示词/用量` 六行全部推导正确（LOG=`…/HTTP-SERVER-CL005-audit-dispatch.log`、USAGE=`…/20260923-http-server.cli-HTTP-SERVER-CL005-audit.json`）。
- 缺必填 → rc=2；空提示词 → rc=2（`提示词文件缺失或为空`）；大小写归一（`http-server-cl005` → `HTTP-SERVER-CL005`）。
- 生成物 `bash -n` 通过；派发后 `[ ! -s "$USAGE" ]` 自校验存在。
- **本轮审计自身实战（A9）**：实际派发壳 `cache/review-prep/dispatch-http-server.cli-http-server-cl005-audit-20260923.sh` 内 `LOG/PROMPT/USAGE` 三行与落盘件逐字一致；派发日志 `…/HTTP-SERVER-CL005-audit-dispatch.log` 记录「启动 → 等待 420s → 派发」；提示词文件首行 = 本审计提示词标题。凭「编号+项目+步骤+日期」可唯一复现三路径（`CODE.upper()` / 脚本名 `.lower()`）。
- **判定：✅**。（🟢 注：§2 D4「usage 缺失/空 ⇒ exit 2」措辞与 §9.4/实现「日志告警」软告警不符，见 §三 R-3。）

### E. 测试与同步

- **33 用例**（`test_cl005_hardening.py`）：TestOutputChannels 5 + TestWebExitCodes 11 + TestStartLockConcurrency 2 + TestStartLockProtocol 10 + TestReviewDispatchTemplate 5 = 33，逐类抽查为真断言（capsys 两通道分离 / exit code 具体值 / `len(entries)==1` / `len(popen_calls)==1` / 锁保留/删除），无恒真空转。
- **T16 可失败**：临时副本禁用锁（`acquire_start_lock` 恒返回 hit）→ T16 转红（`assert 2 == 1`，entries 2 条 pid 90001/90002）。恢复后 590 全绿 ⇒ 非恒真。
- **§4.1 12 必改**：全量 grep `captured.out|readouterr().err|.err` 逐条核对 12 处全部 `.err`（`test_utils:222` / `test_cli:365,1053` / `test_server:87,135,228,250,314,320,326` / `test_port_flag:178,347`）；「保持绿」G3（`test_server:220` status 答案 `.out`）正确保留；无遗漏 `.out` 错误断言。
- **web 单测 SystemExit 同步**：`test_web.py` 新增 12 处 + `test_port_flag.py` 1 处 `pytest.raises(SystemExit) as exc: assert exc.value.code == N`（🟢 注：§9.2 称「test_web.py 13 处」、§9.5 称「+15」，实测 12 + 1 = 13，见 R-2）。
- **四同步**：`__init__.__version__=1.4.1` / `CHANGELOG 1.4.1 (2026-09-23)` / `spec version: 1.4.1` 三处一致；features.md「17 个测试模块，590 个测试用例」== `git ls-files tests/test_*.py | wc -l` = 17；spec 新场景 `lifecycle-07`（L182）/`lifecycle-08`（L201）/`cli-06`（L552）在场；README.md L188 英文 + README.zh.md L188 中文退出码小节 + 启动锁 + stderr 口径均在场。
- **判定：✅（1 🟢 `__release_date__` 未更新，见 R-1）**。

### F. 未越界与残留

- `registry.py` 零改动（`git diff` 空）；无新增 `8180`/`8181`/`MAX_PORT` 保留常量。
- `hs set port` 越界/非法：`70000`/`abc` → rc=0 + stderr、config **不改写**（O7 已登记，非本批缺陷）；`8080` → rc=0 + stdout + config 改写。
- 审计前后真实 `registry.json`（9 条，用户 8080–8086 服务）`services.json`（11 条）不变、`locks/` 空；无残留 runner/listener/锁；`git worktree remove` 基线 + 临时副本 `/tmp/cl005-{bug-repro,nolock}-src` 已清理，工作树 clean。
- O7（set/search 缺参 rc=0）· O8（dashboard/mcp stop 未运行 rc=0 + json `success=false`，实测）· O9（裸 print 结构性兜底，N-4 已收 1798）· O10（`LOCK_WRITE_GRACE=1.0s` 保守）仍成立。
- **判定：✅**。

---

## 三、安全事项（findings）

| # | 级别 | 标题 | 落点 | 处置 |
|:--|:--|:--|:--|:--|
| SEC-1 | 🟡 | D3.5「`registry.add` 抛异常 ⇒ `_terminate_runner` 回滚 ⇒ 不产生孤儿」未实现 | `server.py:496`（`registry.add` 无 try/except；唯一 `_terminate_runner` 在 stale 清理 line 386） | 必改：`registry.add`（及 `history.add` line 504）包 try/except 调 `_terminate_runner(proc.pid)` 再 re-raise |
| R-1 | 🟢 | `__init__.__release_date__='2026-09-22'` + 模块 docstring「Version: 1.4.0(2026-09-22)」未随 1.4.1/09-23 更新（`__release_date__` 无下游消费者，`hs version` 只显示 1.4.1） | `__init__.py:29` + docstring | 记录（下次 docs@sync 勘误） |
| R-2 | 🟢 | §9.2 称「test_web.py 13 处」实测 12 处新增 SystemExit；§9.5 称「+15」实测 +13（test_web 12 + port_flag 1） | 设计 §9.2/§9.5 | 记录 |
| R-3 | 🟢 | §2 D4「usage 缺失/空 ⇒ exit 2」措辞与 §9.4/实现「日志告警」（软告警，不 exit 2）不符；`review-dispatch.sh` 仅提示词空→exit 2，usage 空→stderr 告警 | 设计 §2 D4 / `scripts/review-dispatch.sh:149-151` | 记录（设计措辞歧义，实现符合 §9.4 意图） |

**SEC-1 详析**：设计 §2 D3.5 bullet 2 明确「`registry.add` 抛异常 ⇒ 释放锁前先 `_terminate_runner`（server.py:87 复用点，N-5 确认存在）终止本次 runner ⇒ 不产生孤儿」；§9.3 标题「落地 + 2 处偏差」仅列 D3-1/D3-2，隐式声称 D3.5 已落地。实测：`server.py` 中 `_terminate_runner` 仅在 stale 清理路径（line 386）被调用，`registry.add`（line 496）与 `history.add`（line 504）无 try/except；monkeypatch `registry.add` 抛异常后 runner（`sleep 30` 进程）**仍存活**（`is_process_alive=True`）。后果：磁盘满/权限异常时，刚启动的 runner 成孤儿（运行中 + 未登记 + 占端口，`hs kill` 无法定位，须手动 kill），锁本身由 `start()` 的 finally 正确释放（不泄漏）。非回归（CL005 前同现象）、触发罕见，但属设计必改项未落地 + §9.3 实施记录失实。修复约 3–5 行。

---

## 四、评分

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| D1 输出通道 | 通过 | 63 点表逐点对账零漏点 + 4 新增锁 eprint 均 stderr；5 条反例机器模式 stdout 纯信封 |
| D2 web 退出码 | 通过 | 14 行矩阵逐行命中；P1 修正复核；cmd 失败信封三字段命中 |
| D3 启动锁 | 通过（-1 🟡） | 并发互斥/锁键归一/stale 四判据/mid-write/等待三态/用法优先/D3-1 复现全实测成立；仅 D3.5 registry.add 回滚未落地 |
| D4 派发件 | 通过 | 三路径/错误路径/bash -n/大小写归一 + 本轮自身实战 A9 |
| 测试与同步 | 通过 | 33 用例 + T16 可失败 + §4.1 12 必改 + 四同步实测为真 |
| 未越界与残留 | 通过 | registry 零改动、无新增保留端口、数据目录无污染、残留 0 |
| 安全事项 | 1 🟡 + 3 🟢 | SEC-1 必改（非回归、罕见触发、修复 trivial） |

**总分 90 / 100（Rating: A-）**

---

## 五、结论

**CONDITIONAL_PASS**。D1/D2/D3 互斥核心/D4/测试同步全部忠实落地设计 v1.2，且经独立实证（不采信 ops 21/21 与 dev 自评）：63 点通道表零漏点、web 退出码三态逐行命中、启动锁并发互斥以 pid 同一性 + 修前反证 3/3 不一致坐实、D3-1 偏差在临时副本独立复现（回退 4 runner / 恢复 1 runner）、派发件以本轮审计自身实战验证 A9。

唯一 🟡 必改（SEC-1）：设计 §2 D3.5 要求的「`registry.add` 抛异常 ⇒ `_terminate_runner` 回滚不产生孤儿」未在代码实现，§9.3 实施记录失实。非回归、触发罕见、修复 trivial（`registry.add`/`history.add` 包 try/except 调 `_terminate_runner(proc.pid)` 再 re-raise）。

按纪律：CONDITIONAL_PASS 不 push，回 ops 重审 SEC-1 修复后复审；本报告 + review-log 以 `audit@review:` 提交。
