# http-server.cli CL004 设计复审报告 v1.0（round 2，v1.2 复审）

- 件号：`documents/review/http-server-cli-cl004-design-rereview-v1.0-20260922-round2.md`
- 被审对象：`documents/http-server-port-residual-design-v1.2-20260922.md`（设计 v1.2，commit `6017695`）
- 评审链：v1.0 `6edb021` → CONDITIONAL 90/100（F-1/F-2 + R-1~R-7）→ v1.1 `3b0d37a` → CONDITIONAL 93/100（F-1 闭合、R-1~R-7 落实；F-2 残留 (a)(b)(c) + R-8/R-9）→ **v1.2（本版）**
- 评审性质：**设计复审**（只审设计文档与现状事实，不审实现代码）。只读：`git log/show/diff`、读源码/文档、只读实验（socket/lsof/realpath）
- 评审人：Security Reviewer（review profile）· 日期：2026-09-22
- 环境：macOS 26.6.2 · 基线 HEAD `6017695`（ahead 3，工作树含前两轮未提交评审产物）
- 复审范围：F-2 残留 (a)(b)(c) 逐点闭合 / R-8·R-9 落实 / v1.2 增量是否引入新问题

---

## 0 结论（前置）

**CONDITIONAL_PASS（95/100，Rating A）** —— 上轮唯一必改 **F-2 残留 (a)(b)(c) 三子点全部闭合**，记录项 **R-8/R-9 均落实**；v1.2 增量未引入方向性冲突或自相矛盾。但新增 **1 处 🟡 必改（F-3，措辞级最小补强）**：A4③/A10/A11 的 `<tmpdir>` 路径匹配未声明「解析后的 abs_path」口径，与 `server.py` 存储 / runner 命令行口径不一致，macOS `/var`→`/private/var`、`/tmp`→`/private/tmp` 符号链接使 `mkdtemp()` 返回的原始字符串与 registry 存储的解析路径**恒不相等** ⇒ A4 假失败、A11 注入条目永不命中。另有 3 处 🟢 待确认（非阻断）。

按治理规范：**不提交、不 push**，回 ops 出设计 v1.3 补强 F-3（单行口径声明）后收口。

---

## 一、数据验证（独立复算，不采信设计自述）

| 项 | 实测 | 判定 |
|:--|:-----|:--|
| git HEAD | `6017695`（design v1.2），`git diff 3b0d37a 6017695` = 仅新增 `http-server-port-residual-design-v1.2-20260922.md` | ✅ 与基线一致 |
| registry 路径 | `utils.py:21-23`：`DATA_DIR = ~/.http-server.cli`、`REGISTRY_PATH = DATA_DIR/registry.json` | ✅ F-2(a) 路径 `~/.http-server.cli/registry.json` 正确 |
| `hs list --json` 过滤 | `cli.py:318-321`：`active_servers()` 后 `[s for s in user_servers if s.get('_alive')]`；`registry.py:104-106` `_alive = is_process_alive(pid) and is_port_in_use(port)` | ✅ F-2(a)「掩盖死 pid 条目」机制坐实 |
| 全量 LISTEN 枚举 | `lsof -nP -iTCP -sTCP:LISTEN -F p` 实测返回 23 个 LISTEN pid（`p<PID>` 行，跨全端口） | ✅ F-2(b) 全量枚举命令有效 |
| R-9 lsof 口径 | `lsof -i :7000 -P -n -F p -sTCP:LISTEN` 实测 rc=0 且输出正确（p634） | ✅ `listen_only=True` 追加 `-sTCP:LISTEN` 写法与 `utils.py:172-191` 现状兼容 |
| `get_pid_by_lsof` 调用点 | grep 全 `src/`：仅 `server.py:60`、`server.py:520` 两处，均 `get_pid_by_lsof(port)` 不传第二参 | ✅ N9「默认行为不变」成立 |
| runner 命令行 | `server.py:291-292`：`Popen([sys.executable, runner_path, str(port), abs_path, '--bind', domain, '--index', index], ...)` | ✅ 归属规则双 token（`runner.py` + `abs_path`）可落地 |
| `abs_path` 口径 | `server.py:128` `abs_path = resolve_path(path)`；`utils.py:285-287` `resolve_path = str(Path(...).resolve())`；`registry.add(path=abs_path)`（`server.py:338`） | ⚠️ 见 §五 F-3（解析路径 vs 原始 tmpdir 不一致） |
| 符号链接实况 | `ls -la /var /tmp` → `lrwxr-xr-x ... /var -> private/var`、`/tmp -> private/tmp`；`python -c` 实测 `mkdtemp()=/var/folders/...` vs `realpath=/private/var/folders/...` **equal: False** | ⚠️ F-3 根因坐实 |
| kill 语义 | `server.py:645-651`：`getpgid(pid)` → `killpg(SIGTERM)` → 0.5s → 仍活 `killpg(SIGKILL)` | ✅ R-4 伪码对齐 |
| `get_process_info` | `utils.py:205-222`：`ps -o user=,args=`，返回 `{'user','command'}` | ✅ R-6 依赖函数存在 |
| registry 加载 | `registry.py:26-40` `_get_cached_data` 仅 `read_json` + `'servers'` 兜底；`find(path)` 用 `entry.get('path') == path`；`remove`/stale 路径不读 `started_at` | ✅ R-8 注入无需 `started_at` 即可被解析 |

---

## 二、F-2 残留三子点逐点闭合

### ① F-2(a)：registry 原始文件路径 + 禁 `hs list --json` → **闭合**

- **路径正确**：§8 头注（L258）写明 `~/.http-server.cli/registry.json`（`utils.py:23 REGISTRY_PATH`），与实测 `utils.py:21-23` 一致。
- **A10 已改口径**：§8 A10（L272）为 `json.load(~/.http-server.cli/registry.json)`（**原始文件，非 `hs list --json`**）+ 按归属规则的全量 LISTEN pid + `lsof -nP -iTCP -sTCP:LISTEN`。自洽性修复到位。
- **无别处残留**：全文 grep `hs list|list --json|_alive` 命中 12 处，逐条核验——L16/258/272 为修订表描述旧文与规则本身（正确），其余为 §1 P1/P4 影响面、§4.4 伪码 `is_process_alive`、§6 CHANGELOG、§10 O4，均非「用 `hs list --json` 作孤儿/残留判据」。**§7/A9/§12 零残留**。
- **附加闭合**：A5（L267）亦从 v1.1 的「`hs list --json` path 一致」改为「读 registry.json 该 path 条目核对」——`hs list --json` 作为判据视图的用法已全量清除。

**判定：✅ F-2(a) 闭合，无遗漏。**

### ② F-2(b)：全量 LISTEN 枚举 + 归属规则 → **闭合**

- **全量枚举有效**：`lsof -nP -iTCP -sTCP:LISTEN -F p` 实测返回 23 个 LISTEN pid，`-iTCP` 不限端口 + `-sTCP:LISTEN` 过滤 + `-F p` 字段输出，**能取到全部 LISTEN pid（含孤儿所在另一端口）**。
- **归属规则足以唯一定位**：规则「`ps -o args=` 命令行**同时**含 `runner.py` 且含该 tmpdir」。
  - runner 由 `server.py:291-292` 以 `[sys.executable, runner_path, str(port), abs_path, ...]` 启动，命令行含 `runner.py` + `abs_path` 双 token。
  - **无恒真/恒假风险**：`hs list` 自身不 spawn runner（不产生 LISTEN pid，不会误命中）；归属判定用「每个 pid 的 `ps -o args=`」（非 `ps | grep` 管道），`grep` 进程自身命令行不含 runner.py 且不 LISTEN，**不会自匹配**。
  - **唯一边界（见 §五 待确认 1）**：`abs_path in command` 为子串匹配，嵌套/前缀路径（`/tmp/foo` vs `/tmp/foobar`）会过度包含 → 属「假失败」方向（O 偏大），非「假通过」，harness 用唯一 mkdtemp 目录时无实际影响。

**判定：✅ F-2(b) 闭合；归属规则满足唯一定位，无恒真/恒假风险。**

### ③ F-2(c)：pid 同一性 + `len(R)==1` 前置 + 反证推演 → **闭合**

- **同一性判据**：A4（L266）判据为 `len(R) == 1` **且** `O == R_pids == {该条目 pid}`（**同一性，非计数**），消除「1 dead-pid entry + 1 orphan listener」计数相等（1==1）假阴性。
- **恒真风险已排除**：`len(R) == 1` 作为**前置条件显式要求**（L266 原文「修后：`len(R) == 1` **且** `O == R_pids == ...`」）。当 `R` 恰 1 条且正常流程 `registry.add`（`registry.py:116-126`）恒写入 `pid` 字段时，`R_pids` 非空 ⇒ **`∅ == ∅` 误判通过的情形被排除**。
- **修前反证 `O != R_pids` 必然成立**（两形态推演，均已核对成立）：
  - **可见形态**（孤儿落另一端口，登记 8086 而孤儿在 8084）：registry 恰 1 条（legit 进程 B，pid=P_B）；`O` = 按归属规则过滤的全部 runner LISTEN pid = {P_A(孤儿,8084), P_B(legit,8086)}（两者命令行均含 runner.py + tmpdir）；`R_pids` = {P_B}。故 `O ⊋ R_pids`（P_A ∈ O 且 P_A ∉ R_pids）⇒ `O != R_pids`。**成立**（P_A ≠ P_B，<1s 内 pid 不复用）。
  - **隐形形态**（registry 0 条 + 1 listener）：`R_pids = ∅`；`O = {P_A} ≠ ∅`。故 `O != R_pids`。**成立**。
  - 补充：上轮 §三③ 的「1 dead-pid entry（P_B 死）+ 1 orphan（P_A）」形态亦满足 `O = {P_A} ≠ {P_B} = R_pids` ⇒ `O != R_pids`。两形态列举为**示例**（非穷举），一般断言 `O != R_pids` 对所有「孤儿已产生」的修前态成立；仅健康态 `O == R_pids`。

**判定：✅ F-2(c) 闭合；同一性 + `len(R)==1` 前置 + 反证推演均成立。**

---

## 三、R-8 / R-9 落实

| # | 要求 | v1.2 落点 | 实证核对 | 判定 |
|:--|:--|:--|:--|:--|
| R-8 | A11 写明构造 dead entry 的 recipe | §8 A11（L273）：① 备份 registry.json ② 注入 `{"port": 空闲端口, "path": "<tmpdir>", "pid": 999999, "started_at": "..."}` ③ `hs <tmpdir> --json` ④ 还原 | recipe 四步可复跑；**注入无需 `started_at`**——`registry.py:26-40` 加载仅 `read_json` + `'servers'` 兜底，`find(path)` 用 `entry.get('path')`，stale 路径（`server.py:229-235`）不读 `started_at`。含 `started_at` 亦无害。注入 `path` 须为解析后 abs_path（见 F-3） | ✅ 落实（附 F-3 口径） |
| R-9 | R-7 与 A4 的 lsof 过滤口径统一 | §4.4 ②（L158）`get_pid_by_lsof(port, listen_only=True)` + D11（L107）+ §5 新增 utils 172-191 行 + §7 T13 | `listen_only=True` 追加 `-sTCP:LISTEN` 写法实测有效（rc=0）；**N9 成立**——两处既有调用点 `server.py:60/520` 均不传第二参，默认 False 行为不变；T13（L249）覆盖默认 vs listen_only 在「仅 ESTABLISHED」端口上的差异 | ✅ 落实 |

---

## 四、v1.2 增量是否引入新问题（§0.1 / §4.4 R-7 / §5 / §7 T13 / §8 A4·A10·A11 / §10 O5 / §11 / §12）

逐条检查结论：**未引入方向性冲突、自相矛盾或恒真断言**；`D11`（R-9）为新增决策，与既有 D1–D10 无冲突，`N9` 非目标声明与 D11 自洽。新增 `O5`（无启动锁 ⇒ 极端并发 >2 次仍可能残留孤儿）与 `N8` 范围声明一致。§12 Step 3 首条 commit 由「D1 探测」扩为「D1 探测 + D11 lsof 参数」，作用域自洽。

**§0.2 已闭合标注与上轮结论一致性**：F-1 ✅ / R-1~R-7 ✅ / F-2 🟡 部分闭合 → 本版 (a)(b)(c) 补强。逐项与 round-1 报告结论一致（R-7 标注「口径由 R-9 统一」为准确增注）。**✅ 一致。**

唯一新必改见 §五 F-3。

---

## 五、安全事项（findings）

### 必改（F-x）

| # | 级别 | 标题 | 落点 | 修复要求 |
|:--|:--|:--|:--|:--|
| **F-3** | 🟡 | A4③/A10/A11 的 `<tmpdir>` 未声明「解析后 abs_path」口径，与 registry 存储/runner 命令行不一致 | 设计 §8 A4③/A10/A11 + 头注归属规则 | 在 §8 头注明示：`<tmpdir>` 一律指 `resolve_path(<tmpdir>)`（`Path.resolve()`，即 `server.py` 存储的 `abs_path`），**非** `mkdtemp()`/`mktemp -d` 原始字符串。macOS `/var`→`/private/var`、`/tmp`→`/private/tmp` 符号链接使两者恒不等，`path == <tmpdir>`（原始）⇒ `R=[]` A4 假失败；A11 注入 `"path":"<tmpdir>"`（原始）⇒ `find(path=abs_path)` 永不命中，stale 不触发。单行口径声明即可收口 |

### 待确认清单（🟢 非阻断）

| # | 事项 | 说明 |
|:--|:--|:--|
| 待确认 1 | 归属规则子串匹配（`abs_path in command`）对前缀/嵌套路径（`/tmp/foo` vs `/tmp/foobar`）会过度包含 | harness 侧致 O 偏大（假失败，非假通过）；生产侧 `server.py` ⊙2 同式（R-6 kill 路径）理论误杀边界。测试用唯一 mkdtemp 不触发；建议后续改 token 边界匹配（`path in command.split()` 或 `path + ' '` 边界）。非阻断 |
| 待确认 2 | A4 修前反证依赖 <100ms 双启动复现竞态（v1.0 实测 5 次 4 次） | 1/5 未复现孤儿时反证 `O != R_pids` 假失败（healthy `O==R_pids`）。反证为 sanity check 非主断言；harness 应重试至复现或记录复现率。非阻断 |
| 待确认 3 | A4 采集 O/L 前需等 runner 达 LISTEN | `--url` 在 `registry.add` 后立即返回（`server.py:352-358`），runner 可能尚未 bind ⇒ 极端时序下 `O=∅ ≠ R_pids` 假失败。harness 应 poll `lsof -sTCP:LISTEN` 至该 pid 出现后再采。非阻断 |

---

## 六、评分（维度/权重沿用前两轮）

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 缺陷认定与根因（§1 P1–P4） | 通过 | 未变，v1.0 已源码 + 独立实测双证，无需重验 |
| 修法设计正确性（D1–D11） | 通过 | D1–D10 未变且正确；D11（R-9）新增经 lsof 实测 + 调用点 grep 复核正确，N9 成立 |
| 规格完备性（A4/A10/A11/T13） | 部分通过 | F-2(a)(b)(c) 全闭合 + R-8/R-9 落实；新增 1 🟡 F-3（路径口径声明）+ 3 🟢 待确认 |
| 安全事项 | 1 🟡 + 3 🟢 | 非方向性冲突、非阻断；F-3 为措辞级最小补强 |

**总分 95 / 100（Rating: A）**

---

## 七、结论

**CONDITIONAL_PASS**。设计 v1.2 已**逐点闭合上轮 F-2 残留三子点**：F-2(a) registry 原始文件路径 `~/.http-server.cli/registry.json`（`utils.py:23`）+ 显式禁 `hs list --json` + A10 改原始文件读 + A5 连带清除过滤视图，全文无 `hs list` 判据残留；F-2(b) 全量 `lsof -nP -iTCP -sTCP:LISTEN -F p`（实测 23 pid）+ 归属规则双 token 唯一定位、无 `hs list`/`grep` 恒真风险；F-2(c) `len(R)==1` 前置 + `O == R_pids` 同一性 + 可见/隐形两形态反证推演均成立，`∅==∅` 恒真风险已排除。R-8 recipe 可复跑（`started_at` 非必需，`registry.py` 加载逻辑坐实）；R-9 `get_pid_by_lsof(port, listen_only=True)` 经 lsof 实测有效且 N9 默认不变（调用点 `server.py:60/520` 不传参）。

唯一新必改 **F-3（🟡，措辞级）**：A4③/A10/A11 的 `<tmpdir>` 未声明解析后 `abs_path` 口径，macOS 符号链接使原始 `mkdtemp()` 路径与 registry 存储的 `resolve_path()` 路径恒不等 ⇒ A4 假失败、A11 注入永不命中。为单行口径声明，可一轮收口。

按治理规范：**不提交、不 push**，回 ops 出设计 v1.3 补强 F-3 后收口。
