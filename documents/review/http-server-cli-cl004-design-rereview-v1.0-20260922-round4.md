# http-server.cli CL004 设计复审报告 v1.0（round 4，v1.4 收口轮）

- 件号：`documents/review/http-server-cli-cl004-design-rereview-v1.0-20260922-round4.md`
- 被审对象：`documents/http-server-port-residual-design-v1.4-20260922.md`（设计 v1.4，commit `f3db2d0`）
- 评审链：v1.0 `6edb021` → CONDITIONAL 90/100（F-1/F-2 + R-1~R-7）→ v1.1 `3b0d37a` → CONDITIONAL 93/100（F-1 闭合、R-1~R-7 落实；F-2 残留 (a)(b)(c) + R-8/R-9）→ v1.2 `6017695` → CONDITIONAL 95/100（F-2(a)(b)(c) + R-8/R-9 全闭合；必改 F-3 + 3 🟢）→ v1.3 `c7e2afb` → CONDITIONAL 96/100（F-3 闭合 + 待确认 2/3 得当；必改 F-4 单点 + R-10/R-11/R-12）→ **v1.4（本版，收口）**
- 评审性质：**设计复审**（只审设计文档与现状事实，不审实现代码）。只读：读文档/源码、grep 全文残留核验
- 评审人：Security Reviewer（review profile）· 日期：2026-09-22
- 环境：macOS 26.6.2 · 基线 HEAD `f3db2d0`（ahead 5，工作树含前四轮未提交评审产物）
- 复审范围：F-4 是否闭合 / R-10·R-11·R-12 是否落实 / v1.4 增量是否引入新问题

---

## 0 结论（前置）

**PASS（100/100，Rating A）** —— 上轮唯一必改 **F-4 已闭合**（§4.4 ⊙2 生产 kill 门改为与 §8 同口径的 token 精确匹配，四子点逐项核验通过）；**R-10 / R-11 / R-12 三项 🟢 全部落实**；v1.4 增量**未引入新必改**，仅 1 处 🟢 措辞级记录（非阻断）。

按治理规范：**提交 + push（仅 github）**，收口闭环。

---

## 一、数据验证（独立复算，不采信设计自述）

| 项 | 实测 | 判定 |
|:--|:-----|:--|
| git HEAD | `f3db2d0`（design v1.4），`git rev-list origin/main..HEAD` = 5 commits（v1.0~v1.4 全未 push） | ✅ 与评审链一致 |
| `get_process_info` | `utils.py:205-222`：`ps -p <pid> -o user=,args=`，返回 `{'user', 'command'}`（`command` = 完整 `args=` 行），无结果/异常返回 `None` | ✅ §4.4 ⊙2 `parts = (info or {}).get('command','').split()` 数据源坐实；`(info or {})` None 守卫与 `bool(info)` 一致 |
| `resolve_path` | `utils.py:285-287`：`str(Path(path_str).expanduser().resolve())` = `Path.resolve()` | ✅ F-3 口径坐实 |
| `abs_path` 口径 | `server.py:128` `abs_path = resolve_path(path)`（解析后） | ✅ 与 F-3 一致 |
| runner 命令行 | `server.py:287` `runner_path = os.path.join(SCRIPT_DIR, 'runner.py')`（绝对路径，basename=`runner.py`）；`server.py:291-292` `Popen([sys.executable, runner_path, str(port), abs_path, '--bind', domain, '--index', index], ...)` | ✅ 命令行含 `runner_path` token 与 `abs_path`（解析后）token，与归属规则双 token 同口径坐实 |
| `os.path.basename` 唯一性 | `sys.executable` = python 解释器路径（basename 非 `runner.py`）；`str(port)`/`--bind`/`domain`/`--index`/`index` 均 ≠ `abs_path` | ✅ `basename(t)=='runner.py'` 唯一命中 `runner_path`、`abs_path in parts` 唯一命中 `abs_path`，无恒真/恒假 |

---

## 二、F-4（唯一必改）闭合核验

v1.4 落点（§4.4 ⊙2，L186-190）：

```python
info = get_process_info(pid)                  # utils.py:205 → {'user','command'}
parts = (info or {}).get('command', '').split()   # F-4：与 §8 同口径 token 精确匹配（禁 in 子串）
is_ours = bool(info) and any(os.path.basename(t) == 'runner.py' for t in parts) \
          and abs_path in parts
```

### ① 语义正确（列表成员判定 = 完全相等，非子串）→ **闭合**

`abs_path in parts` 中 `parts` 为 `.split()` 返回的 **list**，Python 列表 `in` 按元素 **`==` 完全相等**判定，非字符串子串。故 `/tmp/foo` **不会**命中 token `/tmp/foobar`（`'/tmp/foo' == '/tmp/foobar'` → False）。上轮 F-4 指出的「`abs_path in command`（command 为字符串 ⇒ 子串）恒 True 误杀嵌套路径」边界**已消除**。

### ② 与 §8 头注归属规则逐字一致 → **闭合**

§8 头注（L281）：「当且仅当『存在 token，其 `basename` == `runner.py`』**且**『存在 token 与 `abs_path` **完全相等**』」。

- 伪码 `any(os.path.basename(t) == 'runner.py' for t in parts)` ⇔ 「存在 token，其 basename == runner.py」。✅
- 伪码 `abs_path in parts`（列表成员 = 完全相等）⇔ 「存在 token 与 abs_path 完全相等」。✅

两处逻辑算子（`any(...)` + `and`）与 §8「且」结构逐字对应，无偏移。

### ③ 全文无残留 `in` 子串式归属判断 → **闭合**

grep `<路径> in` 类模式（`in command` / `' in ` / `" in ` / `runner\.py' in` / `abs_path in` / ` in parts` / ` in <tmpdir>` / ` in \$TD` / ` in \$`）全量核验，**3 命中全部解释**：

| 命中 | 位置 | 性质 | 判定 |
|:--|:--|:--|:--|
| `'runner.py' in command and abs_path in command` | L16（§0.4 评审要求列） | 描述**旧 bug** 的历史引用（修复前态），非现行规格 | ✅ 非残留 |
| `for t in parts`（命中 ` in parts`） | L189 | `any(... for t in parts)` 迭代器语法，非归属判断 | ✅ 非残留 |
| `abs_path in parts` | L190 | 列表成员判定（完全相等，见 ①） | ✅ 非子串 |

**§8 A4 ④（L288）**：「按 **token 精确匹配**归属规则过滤出 `O`」——显式交叉引用 §8 头注，无 `in` 子串。全文**零残留**子串式归属判断。

### ④ `abs_path in parts` 的 `abs_path` 口径 → **与 F-3 一致**

`abs_path = resolve_path(path)`（`server.py:128`，`Path.resolve()`，解析符号链接）；runner 命令行 `Popen([..., abs_path, ...])`（`server.py:291-292`）同样用解析后 `abs_path`。故 `abs_path in parts` 中比较的 `abs_path` 与命令 token 中的路径**同为解析后路径**，与 §8 头注 F-3 口径（`<tmpdir>` 一律指 `resolve_path(<tmpdir>)`）一致，不会因 `/var`→`/private/var` 符号链接失配。✅

**判定：✅ F-4 四子点全闭合。**

---

## 三、R-10 / R-11 / R-12 落实核验

| # | 要求 | v1.4 落点 | 核验 |
|:--|:--|:--|:--|
| **R-10** | A4 反证样本判据简化（以端口判定幂等命中） | §8 A4（L288）：「同法重复 5 次，**以端口判定幂等命中**——两次调用输出端口相同 ⇒ 幂等命中样本（剔除），端口不同 ⇒ 有效反证样本；要求 ≥3 次有效反证样本，不足则如实记录未复现」 | ✅ 「同端口同 pid」→「同端口」判定，`--url` 输出即可判别；修前签名「第二次漂移新端口」据此可分，无需显式读 pid |
| **R-11** | A4 就绪等待改「pid 集合稳定」 | §8 A4 ③（L288）：「以**连续两次采样（间隔 0.2s）的 `O` 集合一致**为稳定判据，超时记「采集未就绪」⇒ 该次样本无效」 | ✅ 「出现单数 LISTEN」→「O 集合稳定」，双 runner（孤儿 PID1 + 登记 PID2）均达 LISTEN 后再采，`O ⊋ R_pids` 可见形态干净展示 |
| **R-12** | §0.3 F-3 落点补 A5 | §0.3 F-3 行（L25）：「——**A4 / A5 / A11 三处均用 `$TD`**（R-12 补）」 | ✅ A5 已入落点列举 |

**判定：✅ R-10/R-11/R-12 三项全部落实。**

---

## 四、v1.4 增量是否引入新问题（§0.4 表 / §0.3 F-3 行 / §4.4 ⊙2 / §8 A4）

逐条检查结论：

- **§0.4 表（L14-19）**：F-4 / R-10 / R-11 / R-12 四行，评审要求与落点两列一致，落点与正文逐项吻合。🟢 记录见 §五。
- **§0.3 F-3 行（L25）**：补「A4/A5/A11 三处均用 `$TD`」，与正文三模板（L288/L289/L295）一致，无自相矛盾。
- **§4.4 ⊙2（L186-190）**：伪码语义正确（见 §二），`os` 模块与同段 `os.getpgid`（L193）复用一致；`(info or {})` None 守卫 + `bool(info)` 双保险，空 info 时 `is_ours=False` 只删登记不 kill，安全方向不变。
- **§8 A4（L288）**：③ 就绪等待（R-11）在 ④ 定义 `O` 之前引用了 `O`（文本前向引用，`O` = 归属规则过滤后的 LISTEN pid 集合，定义紧随其后），可读性微瑕但逻辑无歧义；R-10/R-11 判据均为运行时可观测值（端口输出 / O 集合），非恒真。超时诚实弃样 + ≥3 次有效反证样本的双重护栏未变。

**判定：✅ v1.4 增量整体自洽，无方向性冲突、无恒真断言、无规格缺失，无新必改。**

---

## 五、安全事项（findings）

### 必改（F-x）

无。

### 记录清单（🟢 非阻断）

| # | 事项 | 说明 |
|:--|:--|:--|
| R-13 | §0.4 F-4 落点表用简写 `parts = command.split()`，§4.4 正文为 `parts = (info or {}).get('command','').split()` | 落点表为摘要式简写（省 None 守卫），§4.4 为权威规格且更精确（null-safe，优于 round-3 建议的 `cmd.split()`）。摘要无误导，Step 3 实现以 §4.4 为准，非阻断 |

---

## 六、评分（维度/权重沿用前四轮）

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 缺陷认定与根因（§1 P1–P4） | 通过 | 未变，v1.0 已源码 + 独立实测双证，无需重验 |
| 修法设计正确性（D1–D11） | 通过 | 未变且正确；本版无新增决策 |
| 规格完备性（F-4 + R-10/R-11/R-12） | 通过 | F-4 四子点全闭合（语义正确/§8 逐字一致/零残留 in 子串/abs_path 口径与 F-3 一致）；R-10/R-11/R-12 全落实 |
| 安全事项 | 0 必改 + 1 🟢 | 无 🟡/🔴；仅 1 措辞级 🟢 记录（R-13），非阻断 |

**总分 100 / 100（Rating: A）**

---

## 七、结论

**PASS**。设计 v1.4 **闭合上轮唯一必改 F-4**：§4.4 ⊙2 生产 kill 门由 `in` 子串匹配改为与 §8 同口径的 **token 精确匹配**（`abs_path in parts` = 列表成员判定 = 完全相等，非子串；`any(os.path.basename(t)=='runner.py' ...)` 与 §8「存在 token basename==runner.py 且存在 token == abs_path」逐字一致）。四子点经源码 + 语义独立复核全部通过：`get_process_info` 返回 `command`（`utils.py:205`）、`abs_path = resolve_path(path)`（`server.py:128`）、runner 命令行含 `runner_path` + `abs_path` 双 token（`server.py:291-292`）三处坐实；全文 grep 零残留 `in` 子串式归属判断（3 命中全为历史引用/迭代器语法/列表成员判定）。嵌套路径 `/tmp/foo` vs `/tmp/foobar` 误杀边界已消除。

**R-10/R-11/R-12 三项 🟢 全部落实**：反证样本判据简化为「以端口判定幂等命中」、就绪等待改「pid 集合稳定（连续两次 `O` 一致）」、§0.3 F-3 落点补 A5。v1.4 增量无新必改，仅 1 处 🟢 措辞级记录（R-13，落点表简写 vs 正文精确形式，非阻断）。

按治理规范：**提交 + push（仅 github）**，收口闭环。
