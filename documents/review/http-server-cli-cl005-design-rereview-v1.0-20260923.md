# HTTP-SERVER-CL005 设计复审 — review 报告 v1.0（round-2 design-rereview）

- 件号：`documents/review/http-server-cli-cl005-design-rereview-v1.0-20260923.md`
- 被审对象：`documents/http-server-cl005-hardening-design-v1.1-20260923.md`（commit `ecd0322`，355 行，含 §0 修订落点表 20 行）
- 上轮：v1.0（`70c7a3d`）→ CONDITIONAL_PASS 78/100（B），4 🟡（F-1~F-4）+ 9 🟢（R-1~R-9）
- 范围限定（按指令）：只审上轮未闭合项 F-1~F-4 及 SEC-1/SEC-2；只审本版增量（D3.4 busy 重试 / D3.3 读三态 / D1.2 灰区定案）；🟢 记录项与审项19 只核落点
- 性质：设计复审（审闭合度 + 增量是否引入新问题），非实现审计

## 基线核验（评审前提）

- `git status --porcelain` → 仅 review 侧三件套改动（`.review-level.yaml` / `review-log.md` 已修改 + 未跟踪 round-1 报告）。**源码零改动**（`git diff --stat HEAD` 仅 2 个 review 侧文件，56 行），与指令「本轮源码仍未改动」一致，评审前提未破坏，首段无需标注异常。
- `git rev-list origin/main..HEAD` = 2（设计件 `70c7a3d` + `ecd0322`，均未 push）。
- `git rev-parse HEAD` = `ecd0322`（v1.1 设计件），`origin/main` = `4679ee8`。
- 关键环境事实：`which hs` → `/opt/homebrew/Caskroom/miniconda/base/envs/py3.12/bin/hs`（shebang `python3.12`）；`python3` = `/usr/bin/python3` = **3.9.6**；`.venv/bin/python` = **3.11.15**。

---

## §0 修订落点表逐行闭合判定

| 级别 | 评审要求（要点） | 判定 | 实证 |
|:--|:--|:--|:--|
| 🟡 F-1① 锁键归一 | html→父目录改写后的最终 abs_path | ✅ 闭合 | 源码 `server.py:162-177`：`resolve_path`→html 改写(165-168)→通配(171-177) 全在 isdir(197)/registry.find(208) 之前，锁落点处 abs_path 已归一。六类入口（html/.htm/通配/相对/尾 `/`/符号链接）逻辑必同（详见 §F-1①） |
| 🟡 F-1② mid-write | 读三态：新鲜空锁→等待不删 | ✅ 闭合 | `/tmp` 实验复现两时序（空锁 O_EXCL 仍 FileExistsError；新鲜 age=0.0000s→WAIT、陈旧 age=1.1053s→unlink）。残留 🟢：`LOCK_WRITE_GRACE=1.0s` 极端情形（见 §F-1②） |
| 🟡 F-1③ 锁放置 | 收窄到「用法校验后、registry.find 前」 | ✅ 闭合 | 三时序推演 rc 符合 §3.2（① 无竞争 `-p 70000`→2；② 持锁 `-p 70000`→2；③ 持锁 `-p 8080`→1）。D3.4③ 补偿不 hoist `-p` 入正链 ⇒ 与 CL003 D5 不冲突（见 §F-1③） |
| 🟡 F-1④ release 归属 | pid==getpid() 才删 | ✅ 闭合（残留 🟢） | 读-删非原子 TOCTOU 窗口极窄（需 age>30s + release 交错），见 §F-1④ |
| 🟡 F-2 计时 | `time.monotonic()` 跨进程可比 | ⚠️ 部分闭合 | **部署态（3.12/3.11）可比，但 3.9.6 不可比**（`python3 -c` 三次进程 monotonic = 0.0059/0.0034/0.0047，近零非单调）。见 §F-2，🟡 残留 |
| 🟡 F-3 web 退出码 | ValueError→2、run 失败→1+信封 success=False | ✅ 闭合 | `services.py:129-231` 全量 `ValueError` 均为用法/校验类（无运行期 ValueError）；信封改法无消费方契约冲突（见 §F-3） |
| 🟡 F-4 测试同步 | 补 test_utils.py:222 + 隔离 | ⚠️ 部分闭合 | `lock_dir()` 函数派生自 `DATA_DIR` ⇒ conftest 已覆盖 ✓；但全量 grep 漏 **8 处**将红断言（见 §F-4），🟡 残留 |
| 🟢 R-1 计数 63 | 63 非 64 | ✅ 落点 | `grep -c "eprint("` = 64（含 def 行），调用点 cli 28/server 32/utils 3 = 63 ✓ |
| 🟢 R-2 stdout 一行 | 改「一个可 json.loads 文档」 | ✅ 落点 | §3.1 措辞已改 |
| 🟢 R-3/R-4 字段/去 host | 4 字段去 host | ✅ 落点 | §2 D3.3 与 §3.3 伪码已统一 4 字段 |
| 🟢 R-5 started_at 墙钟 | 并入 F-2 | ✅ 落点 | `started_mono` 为主判据 |
| 🟢 R-6 token 收紧 | pid 活性为主 + token 精确 | ✅ 落点 | §2 D3.3 判据重排 |
| 🟢 R-7 D4 路径 | 双模板 + 单 step | ✅ 落点 | §2 D4 重写 |
| 🟢 R-8 派发壳 10 | 10 非 9 | ✅ 落点 | §1.4 已改 10（实测 cl003 3+cl004 6+cl005 1=10） |
| 🟢 R-9 print() 诊断 | 范围扩裸 print() | ✅ 落点 | §2 D1.3 已扩（但全量审计仍推迟，见 §N-4） |
| 🟢 SEC-1/SEC-2 | 与 F-1①② 同源 | ✅ 闭合 | 随 F-1①/② 闭合 |
| 🟢 审项19 覆盖缺口 | 7 项补测 | ✅ 补入 | §6 T19–T25 + A15–A17 已列（daemon/foreground 释放 T24/A17、html 同锁 T20/A15、mid-write T21/A15、dashboard/mcp 不入锁 §0 非目标、release 归属 T19/A16、cmd 失败信封 T13/A4、JSON 矩阵 A4） |

---

## 一、F-1 逐项实证

### F-1① 锁键归一 — 闭合

实证命令：`read_file src/http_server_cli/server.py:161-177`

实测输出（关键行）：
```
162: abs_path = resolve_path(path)
165: if os.path.isfile(abs_path) and abs_path.lower().endswith(('.html', '.htm')):
166:     index_page = os.path.basename(abs_path)
167:     abs_path = os.path.dirname(abs_path)      # html → 父目录
171: if index_page and '*' in index_page:          # 通配仅改 index_page，不改 abs_path
177:     index_page = os.path.relpath(latest, abs_path)
```

判定：✅ 闭合。锁落点（D3.2 = isdir/index 校验后、registry.find 前，即 line 197 与 208 之间）处的 `abs_path` 已完成「html→父目录」改写与通配解析。六类入口收敛性推演：
- `hs index.html` 与 `hs <dir>`：line 167 将文件路径改写为父目录 ⇒ 同 abs_path ⇒ 同锁键（`sha1(abs_path)[:16]`）✓
- `--index '*.html'`：line 171-177 只改 `index_page`（`relpath(latest)`），`abs_path` 不变 ⇒ 锁键不受通配影响 ✓
- 相对路径：`resolve_path` 已 `expanduser().resolve()` ⇒ 绝对化 ✓
- 尾部 `/`：`Path(...).resolve()` 归一化 ✓
- 符号链接：`Path.resolve()` 默认跟随符号链接 ⇒ 同实路径 ✓
- `.htm`：line 165 `.lower().endswith(('.html','.htm'))` 覆盖 ✓

结论：无第三种入口发散，T20 回归断言可落地。

### F-1② mid-write 读三态 — 闭合（残留 🟢）

实证命令（`/tmp` 最小实验，复现「A 创建锁未写内容 / B 读空锁」两时序）：

实测输出：
```
Case A (empty file, O_EXCL held): second open -> FileExistsError (empty file blocks) ✓
  empty lock age=0.0000s  -> design says fresh(<1s)=WAIT, stale=unlink
Case B (empty file, after 1.1s): age=1.1053s -> design says stale -> unlink+retry ✓
```

判定：✅ 协议排除 double-hold。D3.3 将「无 pid/不可解析」拆为「mtime 新鲜(<1.0s)→WAIT 不删」/「陈旧→unlink retry-once」，mid-write 窗口（O_EXCL 成功但写内容前）的锁不再被误删。D3.3 的 acquire 原子序列（`O_EXCL→write→fsync→close` 同进程单线程）本身已将「写内容窗口」压缩到微秒级，空锁仅在 crash-during-write 时残留。

残留 🟢（非阻断）：
- `LOCK_WRITE_GRACE=1.0s` 取值风险：若 fsync 阻塞 >1s（磁盘满/挂起的网络盘），B 会将「正在写但超 1s」的空锁误判陈旧 → unlink → A 持已 unlink 旧 inode 继续 ⇒ double-hold。属病理磁盘场景，但设计应注明「grace 需大于最长 fsync 时延」或在 unlink 前复核文件仍为空。
- WAIT 态的续接未显式：D3.3 返回 WAIT 后，§3.3 状态机未写明「WAIT → sleep(LOCK_POLL) → 重读锁」，只靠 LOCK_WAIT(3.0s) > LOCK_WRITE_GRACE(1.0s) 隐含保证 1s 后陈旧可清。T21 只断言「不删」，未断言「最终推进到 BUSY/HIT」。建议补一句 WAIT 的 poll 续接。

### F-1③ 锁放置 — 闭合

三时序推演（源码顺序：isdir 197 → [锁落点 D3.2] → registry.find 208 → `-p` 校验 310-343）：

① 无竞争 `hs <dir> -p 70000`：锁 HIT → registry.find 无 → `-p` 越界(313) `raise UsageError` → rc=2，finally 释放锁 ✓
② 持锁者期间 `-p 70000`：FileExists → BUSY → D3.4③ 超时前先做 `-p` 纯语法校验（区间 1024-65535）→ 70000 越界 → rc=2 ✓（不被「正在启动」掩盖）
③ 持锁者期间 `-p 8080`：`-p` 语法合法 → stderr「另一实例正在启动」+ rc=1（fail-closed）✓

判定：✅ 闭合。D3.4③ 把 `-p` 纯语法校验放进 busy 超时 abort 路径（而非 hoist 入正链），既保 rc=2 又不重排 CL003 D5「幂等优先于 `-p` 校验」（spec `cli-05`）。与 CL003 顺序链不冲突。注意：③ 的 rc=1 仅在「holder 已持锁但尚未 registry.add」的 ≤3s 窗口发生；若 holder 是 `--daemon`/`foreground`（registry.add 先于长阻塞），D3.4① 会先幂等命中 rc=0，不落 rc=1——自洽。

### F-1④ release 归属校验 — 闭合（残留 🟢）

判定：✅ 主目标闭合（release 读回锁内容，`pid == os.getpid()` 才 unlink，不匹配只 stderr 不删 ⇒ 防误删他人锁）。

残留 🟢（TOCTOU 边界）：读-删非原子。窗口 =「A 读回确认 pid==A」与「A unlink」之间，若 B 因 age>30s 判 A 的锁 stale → unlink A 锁 → O_EXCL 建 B 锁 → A 的 unlink 删掉 B 锁。触发条件苛刻：需 A 持锁 >30s（即 daemon/foreground 会话锁）且恰在 release 瞬间与 B 的 stale-cleanup 交错。非 daemon 场景 A 持锁 <1s，age 永不 >30s，窗口不成立。POSIX 无「unlink-if-content-match」原子原语，此残余属已知局限，建议设计 §5 风险表补一行声明（release 与 stale-cleanup 竞态在会话锁下仍有极小窗口，依赖 TTL>会话时长的实际使用约束兜底）。

---

## 二、F-2 计时 — 部分闭合（🟡 残留）

实证命令（按指令「两个独立 `python3 -c` 进程各打印一次」）：

```
$ python3 -c "import time; print(time.monotonic())"      # → 0.005889
$ python3 -c "import time; print(time.monotonic())"      # → 0.003449
$ sleep 1; python3 -c "import time; print(time.monotonic())"  # → 0.004671（晚 1s 反而更小）
```

关键实测（同进程内两时钟源对比）：
```
$ python3 --version        # → Python 3.9.6
$ python3 -c "import time; print(time.monotonic(), time.clock_gettime(time.CLOCK_MONOTONIC))"
  → monotonic()=0.003606   CLOCK_MONOTONIC=235526.204528
$ .venv/bin/python -c "import time; print(time.monotonic(), time.clock_gettime(time.CLOCK_MONOTONIC))"
  → (3.11.15) monotonic()=119475.087   CLOCK_MONOTONIC=235559.213
$ conda py3.12 (hs shebang) → monotonic()=119500.638   CLOCK_MONOTONIC=235584.764
```

判定：⚠️ **部分闭合**。设计关键假设「`time.monotonic()` 同机跨进程可比」：

1. **部署态成立**：`hs` 实际运行在 conda Python 3.12（shebang 已证实），其 `time.monotonic()` = 119500s ≈ `CLOCK_UPTIME_RAW`，跨进程可比、单调不回退 ⇒ `age < 0` 在本次 boot 内永不触发、`age > 30s` 正常触发，协议在部署态正确。
2. **但 `python3`（系统 3.9.6）不可比**：`time.monotonic()` 返回 ~0.003s 近零（`get_clock_info('monotonic')` 报 `implementation='mach_absolute_time()'`，但值近零），三个独立进程互不单调（晚启动的反而更小）。在此 Python 下 `age = now - started_mono` 为 ~随机近零值：`age > 30s` 永不触发（TTL 失效），且 **`age < 0` 约 50% 概率伪触发 → 活 holder 锁被误删 → retry-once 双重持有**——正是锁要防的缺陷。
3. **文档层面**：Python 文档明示 `time.monotonic()`「reference point is undefined，only the difference between two calls [同进程] is valid」⇒ 跨进程可比是**未文档化的、版本/平台相关的行为**，非契约。`requires-python >= 3.7` 声称支持 3.9，但 3.9.6（本机系统 Python）实测破坏。
4. **睡眠停滞**：macOS `time.monotonic()`(=mach_absolute_time) 在系统睡眠期间停止（119500 vs `CLOCK_MONOTONIC` 235526 差 116084s≈1.34 天睡眠），TTL 在睡眠期间不推进（依赖 pid 活性兜底，影响小但应知）。

替代方案（必改方向，二选一）：
- **首选**：`time.clock_gettime(time.CLOCK_MONOTONIC)` —— 实测跨进程可比（235526/235559/235584 三个进程一致）、文档保证、免疫睡眠停滞、重启后重置（跨重启 stale 仍由 pid 活性兜底）。Windows 无 CLOCK_MONOTONIC 时回退 `time.monotonic()`。
- **次选**：锁文件 mtime（单一文件系统时钟，所有进程读同一值，无需跨进程时钟比对；以 `time.time()` 差值算 age）。
- **建议同时**：审视 `age < 0 ⇒ stale` 规则——它与 `is_process_alive(pid)` 判跨重启**冗余**（重启后 holder pid 必死），且是 3.9.6 下伪触发的唯一危险源。可改为「仅 `age > LOCK_TTL` 判 stale，跨重启交由 pid 活性」，彻底消除近零时钟伪触发面。

---

## 三、F-3 web 退出码 — 闭合

实证命令：`read_file src/http_server_cli/services.py:129-231`（store.add/update 抛错面全量）+ `read_file cli.py:1330-1852`（web 段）

实测（`store.add/update` 抛 `ValueError` 的全部场景）：
- `add`：`validate_name`（空/超长/非法字符）→ `validate_cmd`（cmd 空）→ `validate_open_mode` → `validate_url` → `validate_port` → 「already exists」无 force（services.py:162）。**全部为用法/校验类**。
- `update`：`validate_cmd`（`--cmd ''`）→ `validate_url` → `validate_open_mode` → `validate_port`（services.py:203-227）。**全部用法/校验类**。
- 运行期失败唯一形态是 `_read_all()` 抛 `DataCorruptionError`（services.py:58/65），**非 ValueError**。

判定：✅ 闭合。设计 §1.2 把 `add/update` 的 `ValueError` 归「用法→2」、`DataCorruptionError` 归「运行期→1」的分类**无误伤**（不存在「其实是运行期失败的 ValueError 分支」）。行号核对全部一致（1466/1471/1496/1571-1577/1621-1633/1667-1673/1750/1783-1788/1790-1799/1850-1851/1776-1778）。

信封改法（`_web_run` cmd 失败）：设计改 `json_output(False, 'web-run', error=…)`（`success=False`、`data=None`、无 `status` 字段）。消费方核对：`test_web.py:474-475` 断言 `data.status=='started'`、`:485` 断言 `'running'` 均为**成功态**信封（已运行/启动成功），非失败态；`mcp.py:174` 引用的是 `hs_status`（status 命令）非 web-run。⇒ 失败信封从 `success=True+data.status` 改为 `success=False+error` **无既有消费方契约冲突**，且更符合 `json_output` schema（失败时 data=None）。T13/A4 已覆盖。

---

## 四、F-4 测试同步与隔离 — 部分闭合（🟡 残留）

### 4.1 隔离 — 闭合

实证：conftest `_isolate_data_dir`（autouse）`monkeypatch.setattr('http_server_cli.utils.DATA_DIR', tmp)`（conftest.py:36）。设计 D3.6 把 `lock_dir()` 定为**函数** `return DATA_DIR / 'locks'`，运行时读模块全局 `DATA_DIR`（非 import 期快照）⇒ conftest 的 autouse 补丁自动覆盖 `lock_dir()`，无需新增 fixture。**前提**：所有调用方必须走 `utils.lock_dir()`，不得在模块顶层快照 `LOCK_DIR = lock_dir()`（会绑死真实路径）。设计 §4 已写 `lock_dir()/lock_path()` 均为函数，满足。✅

### 4.2 测试同步清单 — 不完整（🟡 必改）

实证命令：`grep -rn "captured.out\|capsys" tests/`（全量核对，非只查已知两条）

实测——设计 §4.1 仅列 2 处（`test_utils.py:222`、`test_cli.py:1052`），但 `eprint → stderr` 将使以下 **8 处额外断言变红**（均 `assert <错误/警告文案> in captured.out`，而源码该文案走 `eprint`）：

| 断言 | 文案 | 源码 eprint 点 | D1.2 归口 | 设计是否列 |
|:--|:--|:--|:--|:--|
| `test_server.py:87` | `all in use, cannot start` | `server.py:354` | 失败→stderr | ❌ 漏 |
| `test_server.py:135` | `Path does not exist` | `server.py:204` | 失败→stderr | ❌ 漏 |
| `test_server.py:228` | `not managed by this tool` | `server.py:607` | 诊断→stderr | ❌ 漏 |
| `test_server.py:250` | `still running in background` | `server.py:478` | 过程反馈→stderr | ❌ 漏 |
| `test_server.py:314` | `not registered`（kill 端口） | `server.py:692` | 失败→stderr | ❌ 漏 |
| `test_server.py:320` | `not registered`（kill 路径） | `server.py:704` | 失败→stderr | ❌ 漏 |
| `test_server.py:326` | `Please specify`（kill 无参） | `server.py:680` | 用法→stderr | ❌ 漏 |
| `test_cli.py:365` | `Usage`（search 缺关键字） | `_cmd_search` | D1.2 明定 set/search→stderr | ❌ 漏 |

不红（设计已正确归口 stdout，需实现把 `eprint` 迁 `print_msg`）：`test_server.py:180`（list 空）、`:336`（kill_all 空）、`:343`（service(s) closed）、`:76`（`or '8081'` 兜底）、`test_cli.py:296`（history 空）、`:1046`（set 成功）、`test_cli.py:394`（search 空）。

判定：⚠️ F-4 部分闭合。根因是设计把「63 调用点逐点通道归类」推迟到「实现 commit 调用点清单表」（D1.3），导致 §4.1 测试同步清单只枚举了 2 处、漏 8 处。测试同步是**确定性**的（不依赖分类歧义——上表 8 处 D1.2 均已明定 stderr），应在设计阶段穷举。要求：§4.1 表列出全部 **10 处** `.out→.err` 同步（现有 2 + 漏 8）。

---

## 五、本版增量审项 N-1~N-7

### N-1 busy 重试整链活锁/饥饿 — 无活锁（残留 🟢）

推演：锁协议保证**至多一个持锁**（O_EXCL 唯一赢家），不存在「两进程互相等待」——A 持锁即推进，B 只在 FileExists 后进 poll。B 的 poll 以 `LOCK_WAIT=3.0s` 有界；「unlink+retry-once」为单次重试，若重试再 FileExists 应回落 BUSY（非无限循环）。双 rc=1 仅当「双方都超时」——但唯一持锁者不 poll，故不可能双方同时超时。结论：无活锁、无饥饿。残留 🟢：`retry-once` 失败后的续接（回 BUSY 还是再 WAIT）在 §3.3 状态机未显式，建议补一句「retry-once 再 FileExists → 按新鲜/陈旧走 WAIT/BUSY」。

### N-2 D3.4① 只读 registry.find 的 TOCTOU — 🟡 措辞级

D3.4① 写「命中**且存活** → 幂等返回」。「存活」≠「就绪」。若 holder 已 `registry.add`（server.py:411）但 runner 尚未 bind 端口（Popen 365 后 ~亚秒），B 只读 `registry.find` 见「pid 活但端口未 LISTEN」，若按字面「存活」即返回幂等 rc=0，会返回一个**尚未就绪**的端口。设计虽补「复用既有端口/URL 分支」（即 CL004 line 216-238 的 entry_pid/ready/others_own_port 三态 + ≤1.0s 宽限），但「存活」字面可误导实现者跳过就绪判定。**建议**：D3.4① 措辞改「命中且**就绪**（复用 CL004 三态：entry_pid + is_port_in_use + others_own_port）」，未就绪才落 ② poll。非阻断（正确复用即无此 TOCTOU），但属「不放过模糊点」应改。

### N-3 D1.2 灰区定案自洽性 — 自洽（O7 已登记）

- 「查询空态/not-found → stdout」与「动作命令无事可做（kill all 空）→ stdout」自洽：`hs kill <port>` 未注册=失败（stderr，你指定目标不存在）、`hs kill all` 空=无副作用成功（stdout），语义可区分，无反例。
- 「set/search 用法 → stderr 但 rc 仍 0」与 D2 退出码三态（用法→2）**不自洽**，但设计已登记观察项 **O7**（CL003 未覆盖 set/search，本批不扩），属显式声明的范围边界，非遗漏。
- 「同文案不同通道」已在 §2 D1.2 末显式举例（`Port X not registered` status=stdout / kill=stderr）✓。

### N-4 D1.3 裸 print() 审计范围 — 部分兑现（🟡 残留）

`grep -rn "print(" src/`（不含 eprint/print_msg）≈ **303 处**。设计 D1.3 只点名 `server.py:1798`、`607-614` 两处，其余「逐点定案写入实现 commit 清单表」。结论：「机器模式 stdout 零污染」承诺**当前靠 json/url 提前 return（server.py:466/469）而非全量 print() 审计兑现**——json/url 分支在到达诊断 print() 前已 return，故机器模式暂不污染，但默认模式存在通道错位。实测反例（设计已点名 1798 但未给归口）：`_web_run` name-not-found 分支 `cli.py:1795 print('❌ …', file=sys.stderr)` 与 `1798 print('   Available: …')`（**stdout**）同分支混通道——name-not-found 是失败，其「Available 提示」也应在 stderr。建议 §4.1 表把 `cli.py:1798` 明确归 stderr，并在实现 commit 全量审计裸 print() 的「失败/诊断」子集（非 303 全部）。

### N-5 D3.5 registry.add 失败回滚 — 复用点存在

`server.py:87 def _terminate_runner(pid) -> bool` 已存在，stale 清理路径（line 301）已复用。D3.5「registry.add 抛异常 → finally 释放锁前先终止本次 Popen 的 runner」可**直接复用 `_terminate_runner(proc.pid)`**（killpg 终止本次进程组）。缺口：设计未点名该函数；且 `_terminate_runner` 需确认能对「刚 Popen、尚未 registry.add」的 `proc.pid`（非 registry 里的 entry_pid）正确终止（其内部走 `os.killpg` + 归属校验，应无 registry 依赖，但实现时应核对签名是否仅需 pid）。非阻断。

### N-6 D4 双模板路径推导 — 逐字符一致 ✅

实证命令：`ls -1 cache/closed-loop/ | grep CL00[345]`

实测（比对两类命名）：
```
LOG:   HTTP-SERVER-CL003-design-rereview-dispatch.log
       HTTP-SERVER-CL004-design-rereview3-dispatch.log
       HTTP-SERVER-CL004-design-rereview4-dispatch.log
USAGE: 20260922-http-server.cli-HTTP-SERVER-CL004-design-rereview3.json
       20260922-http-server.cli-HTTP-SERVER-CL004-design-rereview4.json
```

判定：✅ D4 双模板与既有文件**逐字符一致**：`LOG = {CODE-upper}-{STEP}-dispatch.log`（无 date/project 前缀）、`USAGE = {YYYYMMDD}-{PROJECT}-{CODE-upper}-{STEP}.json`；轮次已含于 step（`design-rereview3` 裸数字后缀无横线）。`--step design-rereview2`（本批 round-2）与既有命名规则吻合。

### N-7 §6 T/A 覆盖 §0 落点表 — 覆盖 ✅

逐条抽查：F-1①→T20/A15、F-1②→T21/A15、F-1③→T22a/T22b/T23、F-1④→T19/A16、F-2→（stale 三态 T18 + A7）、F-3→T8/T9/T13/T14/A4、F-4→§4.1 同步清单 + A11。恒真/不可复现抽查：T20（lock_path 相等）可翻转（若未归一则不等）；T21（空锁新鲜不删）可翻转（若实现仍删则删）；T22b（持锁越界 rc=2）可翻转（若不补偿则 rc=1）。无恒真断言。A16「registry.add 失败无孤儿」依赖 `_terminate_runner` 复用，实现可复现。

---

## 安全事项

- 🟡 **SEC-3（F-2 实质，新）**：`time.monotonic()` 跨进程可比性非文档契约，实测在 Python 3.9.6（`requires-python>=3.7` 支持范围）返回近零、跨进程非单调 ⇒ `age<0 ⇒ stale` 会伪触发 → 活 holder 锁被误删 → 双重持有。部署态（3.12）不触发，但属「锁协议正确性依赖未文档化的时钟行为」。建议改用 `clock_gettime(CLOCK_MONOTONIC)` 并重审/删除 `age<0` 规则。
- 🟢 release 与 stale-cleanup 的读-删 TOCTOU（F-1④ 残留，窗口极窄，会话锁 + age>30s 才成立）。
- 🟢 `LOCK_WRITE_GRACE=1.0s` 在 fsync>1s 病理磁盘下误判陈旧。
- 🟢 上轮 🟢（holder token `basename hs` 过松、`shell=True` web run 透传）已由 R-6 收紧 token 主判据 / 非目标声明维持，无新增注入面。

---

## 评分

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 合理性（方向正确性） | 24/25 | F-1 四子项全闭合（锁键归一/mid-write/锁放置/归属），方向无残留错误 |
| 严格性（判据完备） | 21/25 | F-2 monotonic 跨进程可比性有实缺口；N-2 就绪口径措辞偏松 |
| 可执行性（落点清晰） | 21/25 | F-4 测试同步清单漏 8 处；D1.3 全量 print() 审计推迟实现 |
| 回归风险控制 | 20/25 | F-4 漏列断言将在实现测试阶段变红，属可避免的回归面 |
| **合计** | **86/100** | Rating **B+**（上轮 78 → 86） |

评分链：78（round-1 CONDITIONAL_PASS）→ **86（round-2 CONDITIONAL_PASS）**。

---

## 结论

**CONDITIONAL_PASS**（86/100，B+）。方向正确、F-1（上轮最重的两处锁正确性缺口）已全部闭合、F-3 闭合。剩 **2 项 🟡 必改**（F-2a 计时时钟、F-4a 测试同步穷举），须 ops 出 v1.2 后复审。本评审不提交、不 push。

### 🟡 必改清单（编号 + 落点 + 验证要求）

| # | 标题 | 落点 | 验证要求 |
|:--|:--|:--|:--|
| F-2a | `time.monotonic()` 跨进程可比性无契约保证（3.9.6 实测破坏 + `age<0` 伪触发风险） | 设计 §2 D3.3 / §3.3 | 计时改 `time.clock_gettime(time.CLOCK_MONOTONIC)`（Windows 回退 `time.monotonic()`）或锁文件 mtime；重审/删除 `age<0 ⇒ stale`（与 pid 活性冗余）。验证：两独立进程 `clock_gettime(CLOCK_MONOTONIC)` 差值 ~常数；伪造活 holder 锁断言 age<0 不误删 |
| F-4a | 测试同步清单漏 8 处将红断言 | 设计 §4.1 | 补列全部 **10 处** `.out→.err`：现有 `test_utils.py:222`/`test_cli.py:1052` + 漏 `test_server.py:87/135/228/250/314/320/326` + `test_cli.py:365`。验证：全量 `grep captured.out` 与 §4.1 表逐条对上 |

### 🟢 记录清单（同批落点，非阻断）

| # | 标题 |
|:--|:--|
| R-10 | `LOCK_WRITE_GRACE=1.0s` 在 fsync>1s 病理磁盘下误判陈旧（建议 unlink 前复核文件仍为空） |
| R-11 | WAIT 态续接（sleep LOCK_POLL → 重读锁）与 retry-once 再 FileExists 的续接未显式 |
| R-12 | release 归属读-删 TOCTOU 窗口（会话锁 + age>30s 才成立，POSIX 无原子原语） |
| R-13 | D3.4①「命中且存活」措辞偏松，应改「命中且就绪（复用 CL004 三态）」 |
| R-14 | `cli.py:1798`「Available 提示」在 name-not-found 失败分支走 stdout，应归 stderr |
| R-15 | 裸 `print()` 约 303 处，全量逐点定案推迟实现 commit（机器模式靠 json/url 提前 return 兜底） |
| O7 | `set`/`search` 用法提示 stderr 但 rc=0（CL003 未覆盖，已登记观察项，本批不扩） |
