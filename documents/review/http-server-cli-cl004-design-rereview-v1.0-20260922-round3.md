# http-server.cli CL004 设计复审报告 v1.0（round 3，v1.3 复审）

- 件号：`documents/review/http-server-cli-cl004-design-rereview-v1.0-20260922-round3.md`
- 被审对象：`documents/http-server-port-residual-design-v1.3-20260922.md`（设计 v1.3，commit `c7e2afb`）
- 评审链：v1.0 `6edb021` → CONDITIONAL 90/100（F-1/F-2 + R-1~R-7）→ v1.1 `3b0d37a` → CONDITIONAL 93/100（F-1 闭合、R-1~R-7 落实；F-2 残留 (a)(b)(c) + R-8/R-9）→ v1.2 `6017695` → CONDITIONAL 95/100（F-2(a)(b)(c) + R-8/R-9 全闭合；唯一必改 F-3 + 3 🟢 待确认）→ **v1.3（本版）**
- 评审性质：**设计复审**（只审设计文档与现状事实，不审实现代码）。只读：`git log/show/diff`、读源码/文档、只读实验（Path.resolve/mkdtemp）
- 评审人：Security Reviewer（review profile）· 日期：2026-09-22
- 环境：macOS 26.6.2 · 基线 HEAD `c7e2afb`（ahead 4，工作树含前三轮未提交评审产物）
- 复审范围：F-3 是否闭合 / 3 项 🟢 待确认处置是否得当 / v1.3 增量是否引入新问题

---

## 0 结论（前置）

**CONDITIONAL_PASS（96/100，Rating A）** —— 上轮唯一必改 **F-3 已闭合**（§8 头注口径声明 + A4/A5/A11 三处命令模板逐处一致，`恒 False` 论断经实证成立）；3 项 🟢 待确认中 **待确认 2/3 处置得当**，**待确认 1 仅闭合一半**：§8 归属规则已改 token 精确匹配（harness 侧闭合），但 **§4.4 ⊙2 生产 kill 门仍用 `in` 子串匹配**，与 §8「禁用 `in` 子串判断」自相矛盾，「生产理论误杀边界」未闭环。

由此新增 **1 处 🟡 必改（F-4，单点收口）** + 3 处 🟢 记录。

按治理规范：**不提交、不 push**，回 ops 出设计 v1.4 对齐 §4.4 ⊙2 后收口。

---

## 一、数据验证（独立复算，不采信设计自述）

| 项 | 实测 | 判定 |
|:--|:-----|:--|
| git HEAD | `c7e2afb`（design v1.3），`git diff 6017695 c7e2afb` = 仅 v1.3 文档（v1.2 → v1.3 改名 + 增量） | ✅ 与基线一致 |
| `resolve_path` | `utils.py:285-287`：`str(Path(path_str).expanduser().resolve())`，即 `Path.resolve()` | ✅ F-3 引用的 `Path.resolve()` 坐实 |
| `abs_path` 口径 | `server.py:128` `abs_path = resolve_path(path)` | ✅ 与设计一致 |
| registry 写入 | `server.py:337-341` `registry.add(port=..., path=abs_path, pid=proc.pid, ...)` | ✅ registry 存解析路径坐实 |
| registry 查找 | `server.py:174` `entry = self.registry.find(path=abs_path)`；`registry.py:94` `entry.get('path') == path` | ✅ stale 路径匹配用解析路径坐实 |
| runner 命令行 | `server.py:291-292` `Popen([sys.executable, runner_path, str(port), abs_path, '--bind', domain, '--index', index], ...)` | ✅ 命令行含 `abs_path`（解析后）坐实 |
| 符号链接实况 | `python3.12 -c` 实测：`mkdtemp()=/var/folders/yx/…/tmpbq1ze09d`，`resolve()=/private/var/folders/…/tmpbq1ze09d`，**equal: False**；`/var -> private/var`、`/tmp -> private/tmp`（均 symlink） | ✅ F-3「恒 False」根因坐实 |
| resolve 幂等性 | `resolve(resolved) == resolved` 实测 **True** | ✅ A11 注入 `$TD`（已解析）与 `find(path=abs_path)` 可命中 |
| `get_process_info` | `utils.py:205-222`：`ps -o user=,args=`，返回 `{'user','command'}`（`command` 为完整 `args=` 行） | ✅ §4.4 ⊙2 / §8 归属规则同数据源坐实 |
| `get_pid_by_lsof` 现状 | `utils.py:172-191` 签名 `get_pid_by_lsof(port)`（无 `listen_only` 参数，为 Step 3 待增） | ✅ R-9/D11 属待实现，非本版新增 |

---

## 二、F-3（唯一必改）闭合核验

### ① 三处命令模板逐处一致 → **闭合**

- **§8 头注（L267）**：新增「路径口径（F-3，强制）」条，声明 `<tmpdir>` 一律指 `resolve_path(<tmpdir>)`（`Path.resolve()`），并给命令模板 `TD=$(python3 -c "from pathlib import Path;print(Path('<raw>').resolve())")`。
- **A4（L276）**：`① TD=$(resolve_path(<raw>))（F-3 口径）`。✅
- **A5（L277）**：`hs -i index.html -p <port> -d --url "$TD"`（`TD` 同上 F-3 口径）。✅
- **A11（L283）**：注入 `"path": "$TD"`（`$TD` 按 F-3 口径 = `resolve_path(<raw>)`）。✅

**全文 `<tmpdir>`/`$TD` 残留核查**（grep 全量）：命中 8 处——L16（§0.3 F-3 修订表）、L27/L28（§0.2 历史留档，非现行规格）、L267（头注口径声明）、L275（A3）、L276（A4）、L277（A5）、L283（A11）。

- **L275 A3 为唯一「裸 `<tmpdir>`」**：命令 `hs <tmpdir> -p P -d --url`，断言仅核对端口 `= P`，**不做 `path == <tmpdir>` 匹配**——`<tmpdir>` 仅作 `hs` 的输入路径（`hs` 内部自会 `resolve_path`），且 `resolve_path` 幂等，传原始串/解析串结果一致。**无路径匹配问题，非残留缺陷**。
- **§10（O1–O5）/ §12（Step 3–6）**：零 `<tmpdir>`。
- **L27/L28**：属 §0.2 第二轮「已闭合留档」的历史叙述（描述 v1.2 的修复），非现行规格路径匹配。

**判定：✅ F-3 闭合，A4/A5/A11 三处逐处一致，无残留裸 `<tmpdir>` 用于路径匹配。**

### ② 口径与源码实际写入值一致 → **一致**

`server.py:128`（`abs_path = resolve_path(path)`）+ `server.py:337-341`（`registry.add(path=abs_path)`）+ `server.py:291-292`（runner 命令行 `abs_path`）三者全用解析路径，与 §8 头注声明的 `resolve_path(<tmpdir>)` 口径一致。`server.py:174`（`find(path=abs_path)`）与 `registry.py:94`（`entry.get('path') == path`）同样以解析路径匹配。

**判定：✅ 口径一致。**

### ③ 「恒 False」论断仍成立 → **成立**

实测 `mkdtemp()` 返回 `/var/folders/…`，`resolve()` 返回 `/private/var/folders/…`，`equal: False`（`/var`、`/tmp` 均为符号链接）。registry 存解析路径，故修复前：

- **A4 假失败**：`path == <tmpdir>`（原始）恒 False ⇒ `R = []` ⇒ `len(R)==1` 前置不满足 ⇒ 假失败。✅ 成立。
- **A11 永不命中**：注入 `"path": "<tmpdir>"`（原始）⇒ `find(path=abs_path)` 中 `entry['path']`（原始）≠ `abs_path`（解析）⇒ stale 不触发。✅ 成立。

**判定：✅「恒 False」论断经实证成立；v1.3 用 `$TD`（解析后）注入/匹配后，A11 可命中（resolve 幂等性实测坐实）。**

---

## 三、3 项 🟢 待确认处置核验

### 待确认 1（归属规则子串匹配过度包含）→ **部分闭合（见 §五 F-4）**

- **§8 头注（L269）** 已改为 **token 精确匹配**：取 `ps -o args=` 命令行，按空白切分；「存在 token，其 `basename` == `runner.py`」且「存在 token 与 `abs_path` 完全相等」；**显式禁用 `in` 子串判断**。
- **过度包含是否消除（harness 侧）**：✅ 消除。`/tmp/foo` vs `/tmp/foobar` 下，`token == abs_path` 精确相等判定不会把 `/tmp/foobar` 误判为 `/tmp/foo` 的 runner。
- **反例核验**：
  - `runner.py` 写成绝对路径 token：✅ 已覆盖。`runner_path = os.path.join(SCRIPT_DIR, 'runner.py')`（`server.py:287`）为绝对路径，但规则用 `basename(token) == 'runner.py'` 而非 `token == 'runner.py'`，故绝对/相对形式均命中。
  - 路径含空格 tmpdir：⚠️ 理论边界。`ps -o args=` 按空白切分后，含空格的 `abs_path`（如 `/tmp/my dir`）会被拆成 `/tmp/my` + `dir` 两个 token，无单 token 与 `abs_path` 完全相等 ⇒ 归属**欠匹配**（安全方向：不误杀、但会留孤儿）。因 harness 用 `mkdtemp()`（路径无空格），A4 不受影响；生产侧见 F-4。
- **遗留**：§4.4 ⊙2（生产 kill 门）**仍用 `in`**，未随 §8 同步 → 见 §五 F-4。

**判定：⚠️ 待确认 1 部分闭合（harness 闭合；生产 ⊙2 未闭环，转为 F-4）。**

### 待确认 2（修前反证复现概率）→ **处置得当**

- §8 A4 增「反证样本口径」：重复 5 次，先剔除「幂等命中」样本（**两次调用落在同端口同 pid ⇒ 非反证样本**），要求 ≥3 次有效反证样本；不足则如实记录未复现。
- **「幂等命中」判定是否写明且可判**：✅ 判定标准已写明——「两次调用落在同端口同 pid」。可判性：端口可由两次 `--url` 输出直接比对；pid 可由 registry.json / lsof 观测。**补充说明（🟢 记录 R-10）**：修前 bug 的签名是「第二次调用漂移到新端口」，故「同端口」即可区分幂等命中 vs 反证样本（`--url` 输出即可判别，无需显式读 pid），设计「同端口同 pid」判据略强但方向正确、可落地。
- **不足则如实记录**：✅ 避免了「1/5 未复现反证假失败」被掩盖——未复现记为「非反证样本」并如实记录，反证不作主断言（sanity check）。

**判定：✅ 待确认 2 处置得当。**

### 待确认 3（采集前等 runner 达 LISTEN）→ **处置得当**

- §8 A4 增就绪等待：轮询 ≤2.0s（0.2s × 10）直到出现按归属规则判定属于该 `TD` 的 LISTEN pid，超时记「采集未就绪」⇒ 该次样本无效。
- **等待上限是否足够**：✅ 足够。runner 启动（`python3 -m http.server` 子进程 + bind）实测量级 ~50–100ms（设计自身 P4「<100ms 连续两次启动」即基于此），2.0s 为 20–40 倍余量。
- **超时分支是否掩盖真实失败**：✅ 不掩盖。超时 →「采集未就绪 ⇒ 样本无效」为**诚实弃样**（不计数为 PASS，不产生假通过）；启动挂起类真实失败由 A8（全量 pytest）覆盖，非 A4 职责。
- **时序补充（🟢 记录 R-11）**：就绪等待为「直到**出现** LISTEN pid」（单数）。修前态存在两个 runner（孤儿 PID1 + 登记 PID2），若 PID1 先 LISTEN 即采集，PID2 未 LISTEN 时 `O={PID1}`、`R_pids={PID2}` ⇒ 反证 `O != R_pids` 仍成立（方向正确），仅「可见形态 `O ⊋ R_pids`」不干净展示。不阻断，属 harness 展示细节。

**判定：✅ 待确认 3 处置得当。**

---

## 四、v1.3 增量是否引入新问题（§0.3 / §8 头注 F-3 + token 匹配 / A4·A5·A11）

逐条检查结论：

- **§0.3 表（L12–19）**：F-3 + 待确认 1/2/3 四行，落点与正文一致。**🟢 记录 R-12**：F-3 行落点写「A4/A11 命令模板同步改写」，**未列 A5**（A5 正文用「TD 同上 F-3 口径」已正确），属落点表列举遗漏，非正文缺陷。
- **§8 头注 F-3（L267）**：口径声明 + 命令模板，无自相矛盾。
- **§8 头注 token 匹配（L269）**：规则定义完整（basename + 完全相等 + 禁 `in`），无恒真/恒假（`hs list` 不 spawn runner、`ps -o args=` 无 grep 自匹配，沿用 round-2 已核结论）。
- **命令模板 `python3 -c`（🟢 环境提示）**：本机 `/usr/bin/python3`（3.9.6）`-c` 形态会挂起等 stdin；harness 需用 `python3.12`/`python`（3.12.13）执行模板。非设计缺陷，属环境注意事项。
- **无方向性冲突 / 恒真断言 / 规格缺失**：v1.3 增量整体自洽，唯一新必改见 §五 F-4（§4.4 ⊙2 `in` 残留与 §8「禁用 `in`」的自相矛盾）。

**§0.3 已闭合标注与上轮结论一致性**：F-2(a)(b)(c) ✅ / R-8·R-9 ✅ / F-3 🟡 → 本版收口。逐项与 round-2 报告一致。**✅ 一致。**

---

## 五、安全事项（findings）

### 必改（F-x）

| # | 级别 | 标题 | 落点 | 修复要求 |
|:--|:--|:--|:--|:--|
| **F-4** | 🟡 | §4.4 ⊙2 生产 kill 门仍用 `in` 子串匹配，与 §8 头注「禁用 `in` 子串判断」自相矛盾；「生产理论误杀边界」未闭环 | 设计 §4.4 L179（`'runner.py' in command and abs_path in command`） | 将 §4.4 ⊙2 伪码改为与 §8 同口径的 **token 精确匹配**：`any(os.path.basename(t) == 'runner.py' for t in cmd.split()) and abs_path in cmd.split()`，或显式交叉引用「归属校验与 §8 归属规则同口径（token 精确匹配，非 `in` 子串）」。当前 §8 已声明「禁用 `in`」，但 §4.4 ⊙2 仍保留 `in`，Step 3 实现者将照伪码写 `in`，`/tmp/foo` vs `/tmp/foobar` 嵌套路径下 `abs_path in command` 恒 True ⇒ 误杀另一目录的 runner（`/tmp/foobar` 被误判为 `/tmp/foo`）。单点收口即可 |

### 记录清单（🟢 非阻断）

| # | 事项 | 说明 |
|:--|:--|:--|
| R-10 | 待确认 2「同端口同 pid」判定略强 | 修前 bug 签名为「第二次调用漂移新端口」，`--url` 输出比对「同端口」即可判别幂等命中 vs 反证样本，无需显式读 pid；当前判据方向正确、可落地，仅口径可更简 |
| R-11 | 待确认 3 就绪等待「单数 LISTEN」时序 | 修前双 runner 下 PID1 先 LISTEN 即采集，反证 `O != R_pids` 仍成立，仅「可见形态 O ⊋ R_pids」展示不干净；harness 可等 pid 集合稳定后再采（非阻断） |
| R-12 | §0.3 F-3 行落点未列 A5 | F-3 落点写「A4/A11 命令模板」，A5 亦用 `$TD`（正文「TD 同上 F-3 口径」正确），落点表列举遗漏，属文档完备性微瑕 |

---

## 六、评分（维度/权重沿用前三轮）

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 缺陷认定与根因（§1 P1–P4） | 通过 | 未变，v1.0 已源码 + 独立实测双证，无需重验 |
| 修法设计正确性（D1–D11） | 通过 | 未变且正确；本版无新增决策 |
| 规格完备性（F-3 + 3 待确认） | 部分通过 | F-3 全闭合（三模板一致 + 口径与源码一致 + 恒 False 实证）；待确认 2/3 得当；待确认 1 部分闭合（harness 闭合、生产 ⊙2 未闭环 → F-4） |
| 安全事项 | 1 🟡 + 3 🟢 | F-4 为措辞级单点（§4.4 ⊙2 与 §8 对齐），非方向性冲突、非阻断 |

**总分 96 / 100（Rating: A）**

---

## 七、结论

**CONDITIONAL_PASS**。设计 v1.3 已**闭合上轮唯一必改 F-3**：§8 头注新增口径声明（`<tmpdir>` 一律指 `resolve_path(<tmpdir>)`）+ 命令模板，A4/A5/A11 三处命令模板逐处一致；「恒 False」论断经实证坐实（`mkdtemp()=/var/folders/…` vs `resolve=/private/var/folders/…`，`equal=False`；`/var→private/var`、`/tmp→private/tmp` 符号链接），且 `resolve_path` 幂等性保证 A11 注入 `$TD`（解析后）可命中 `find(path=abs_path)`。全文无残留裸 `<tmpdir>` 用于路径匹配（仅 A3 为输入路径、L27/L28 为历史留档）。

3 项 🟢 待确认：**待确认 2/3 处置得当**（反证样本口径可判、就绪等待 2.0s 充足且超时诚实弃样）；**待确认 1 部分闭合**——§8 归属规则 token 精确匹配（harness 侧闭合，`basename` 覆盖绝对路径 token），但 **§4.4 ⊙2 生产 kill 门仍用 `in` 子串匹配**，与 §8「禁用 `in`」自相矛盾，生产理论误杀边界未闭环。

由此新增 **1 处 🟡 必改（F-4，单点收口）**：将 §4.4 ⊙2 伪码对齐 §8 token 精确匹配（或显式交叉引用），即可一轮收口。另有 3 处 🟢 记录（R-10/R-11/R-12）。

按治理规范：**不提交、不 push**，回 ops 出设计 v1.4 对齐 §4.4 ⊙2 后收口。
