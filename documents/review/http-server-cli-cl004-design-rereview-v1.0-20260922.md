# http-server.cli CL004 设计复审报告 v1.0

- 件号：`documents/review/http-server-cli-cl004-design-rereview-v1.0-20260922.md`
- 被审对象：`documents/http-server-port-residual-design-v1.1-20260922.md`（设计 v1.1，commit `3b0d37a`）
- 上一轮：设计 v1.0（`6edb021`）评审 **CONDITIONAL_PASS 90/100**（2 🟡 必改 F-1/F-2 + 7 🟢 记录 R-1~R-7）
- 评审性质：**设计复审**（只审设计文档与现状事实，不审实现代码）
- 评审人：Security Reviewer（review profile）· 日期：2026-09-22
- 环境：macOS 26.6.2 · 基线 HEAD `3b0d37a`（ahead 2，工作树含上一轮评审未提交产物）
- 复审范围：F-1（D6 文案通道）/ F-2（A4 孤儿判据）/ R-1~R-7 逐条处置

---

## 0 结论（前置）

**CONDITIONAL_PASS（93/100，Rating A）** —— F-1 完全闭合，R-1~R-7 逐条落实到位；F-2 方向已修正（lsof LISTEN 端口级判据 + 删除 `ps` 同名判据 + 修前反证），但 **A4 判据仍有 1 处必改（3 个子点）** 需在 v1.2 补强，否则 harness 存在假阴性盲区。另 2 处 🟢 记录（A11 手法、R-7 与 A4 的 lsof 口径差异）。

按治理规范：**不提交、不 push**，回 ops 出设计 v1.2 补强 A4 后再次 rereview。

---

## 一、数据验证（独立复算，不采信设计自述）

| 项 | 实测 | 判定 |
|:--|:-----|:--|
| git HEAD | `3b0d37a`（design v1.1），`git diff --name-status 6edb021 3b0d37a` = 仅 `A documents/http-server-port-residual-design-v1.1-20260922.md` | ✅ 与基线一致 |
| D6 删除「其余沿用现状」 | 设计全文 grep「沿用现状」仅命中 §0 修订表（描述 v1.0 旧文）+ D6 行（「删除 v1.0「其余沿用现状」表述」），**无主动沿用表述** | ✅ F-1 根因表述已删净 |
| `eprint` 通道 | `utils.py:33-38`：`eprint` 内部 `print(f'{emoji} {msg}')`，**无 `file=sys.stderr`**，写 stdout | ✅ F-1 污染点坐实 |
| stale 现状代码 | `server.py:229-234`：`url_only` → `print(..., file=sys.stderr)`；`else`（json/默认）→ `eprint(..., '🔄')` → stdout | ✅ 设计 §1 P4/F-1 描述逐字一致 |
| `hs list --json` 过滤 | `cli.py:318-321`：`active_servers()` 后 `[s for s in user_servers if s.get('_alive')]`；`registry.py:98-107` `_alive = is_process_alive(pid) and is_port_in_use(port)` | ✅ F-2「隐形」形态机制坐实 |
| registry.json 路径 | `utils.py:23` `REGISTRY_PATH = ~/.http-server.cli/registry.json` | ✅ A4 需显式引用此路径 |
| runner 命令行 | `server.py:291-292`：`Popen([sys.executable, runner_path, str(port), abs_path, '--bind', domain, '--index', index], ...)` | ✅ R-6 `runner.py`+`abs_path` 校验可执行 |
| kill 语义 | `server.py:645-651`：`getpgid(pid)` → `killpg(pgid, SIGTERM)` → `sleep(0.5)` → `is_process_alive` 仍活则 `killpg(pgid, SIGKILL)` | ✅ R-4 伪码对齐 |
| `get_process_info` | `utils.py:205-222`：返回 `{'user', 'command'}`，`command` 为 `ps -o args=` 完整命令行 | ✅ R-6 依赖函数存在 |
| `get_pid_by_lsof` | `utils.py:172-191`：`lsof -i :<port> -P -n -F p`，**无 `-sTCP:LISTEN`** | ⚠️ R-9 口径差异（见 §五） |

---

## 二、F-1 复审（D6 文案通道）→ **闭合**

### ① 逐态可执行性 → ✅ 成立

- 现状污染点坐实：`server.py:229-234` 中 `url_only` 走 stderr（正确），**json / 默认两态走 `eprint` → stdout**（`eprint` 实写 stdout，`utils.py:33-38`）。与 v1.0 评审 F-1 描述一致。
- 修法覆盖：设计 D6（§3 L89）「stale/宽限/kill 三类文案在 url_only/json/默认三态一律 `print(..., file=sys.stderr)`」；§4.4 L171 伪码 `print(f'🔄 {stale_msg}', file=sys.stderr)` 为唯一文案出口。三态全部改走 stderr，stdout 仅承载 URL / JSON 信封 / 信息块。逐态可执行。
- **判定：✅ 修法覆盖 json/默认两态污染点，无遗漏。**

### ② A11 断言可复跑性 → 🟢 记录（R-8，见 §五）

- A11 断言本身可复跑，但「构造 dead entry」**具体手法未写明**：§8 A11 仅「`hs <tmpdir> --json`（构造 dead entry 触发 stale）」，未给出构造 dead entry 的 recipe。详见 R-8。

### ③ 新通道矛盾 → ✅ 无

- 幂等命中路径（①）设计标注「不变（既有三态输出）」（§4.4 L139），未改既有输出。
- 实测 ① 路径现状（`server.py:174-227`）：`--url` 仅 `print(url)`、`--json` 仅 `json_output`、默认仅信息块 `print`，均落 stdout 正确；`-p` 未生效的「已运行在 port」提示（`server.py:179-181`）已走 stderr。与 §4.5 通道表一致，**无新矛盾**。
- §4.5 通道表（L180-184）三态 stdout/stderr 分列清晰，与 §4.4 伪码逐条对应。
- **判定：✅ 未引入新通道矛盾，幂等路径未误改。**

---

## 三、F-2 复审（A4 孤儿判据）→ **部分闭合（1 处必改，3 子点）**

### ① 能否捕获两种孤儿形态 → 方向正确，但「逐端口」范围有歧义

- 判据：`lsof -nP -iTCP:<port> -sTCP:LISTEN -F p` 的 pid 数 == `registry.json` 该 path 条目数。
- **隐形形态**（registry 0 条可见 + 1 listener）：读原始 registry.json 时，条目数=0，listener=1 → `1 > 0` → 捕获 ✅。
- **可见形态**（registry 1 条 + 2 listeners）：listener=2 > 条目=1 → 捕获 ✅。
- **但**：可见形态的孤儿 listener 落在**另一端口**（v1.0 评审实测 8084 + 8086，登记端口仅 8086）。A4 的 `-iTCP:<port>` 若只 lsof **登记端口**，则得 1 listener == 1 entry，**漏掉 8084 孤儿**。「逐端口」字样需明确为「枚举全部 LISTEN 端口并与 registry 全量 pid 交叉比对」，而非单端口。→ 必改子点 (b)。

### ② registry.json 直接读文件为必需前提 → **是必需，但 A4 未显式写明路径**

- 必需性坐实：`hs list --json` 经 `cli.py:321` 按 `_alive` 过滤死 pid 条目，正是 v1.0 评审「隐形形态」的成因。A4 必须读**原始 registry.json 文件**，不能用 `hs list --json`。
- 设计 A4 写「registry.json 该 path 条目数」已暗示读文件（区别于「hs list」），但**未给绝对路径**（`~/.http-server.cli/registry.json`，`utils.py:23`），**未明示「不得用 `hs list --json`（其按 `_alive` 过滤）」**。
- 且设计自身不自洽：§8 **A10**（L253）仍用 `hs list --json` 查「registry 无 cl004 残留」——该过滤视图对死 pid 条目同样不可见，与 A4 口径冲突。→ 必改子点 (a)。

### ③ 判据恒真/恒假风险 → **计数相等存在假阴性盲区**

- 纯计数 `==` 无法区分「1 健康 entry + 1 健康 listener」与「**1 dead-pid entry + 1 orphan listener**」（两者计数均 1==1）。
- 该「1+1 dead-pid」形态**可达**：call#1 选端口 P→Popen pid A；call#2 读到 entry（pid A 活、端口未监听）→ stale 移除→`find_available_port` 重选 P（因 A 尚未 LISTEN，`is_port_in_use` 为 False）→Popen pid B。A 先 bind 胜、B bind 失败退出 ⇒ registry 1 条（pid B 死）+ 1 listener（pid A 孤儿）= **1==1 假阴性**。
- v1.0 评审「尝试 4：registry 1 + listeners 1 → 无孤儿（幂等命中）」即默认了「1+1=无孤儿」，但该计数无法排除上述 dead-pid 形态。
- 补强：断言 **lsof LISTEN pid == registry 该 path 条目 pid（同一性）**，而非仅计数相等。→ 必改子点 (c)。

**F-2 小结**：方向正确（lsof LISTEN 计数 + 删除 `ps` 判据 + 修前反证非恒真），但 A4 需补强三处（见 §五 F-2 残留）。

---

## 四、R-1~R-7 逐条处置落实（记录项，非阻断）

| # | 要求 | v1.1 落点 | 实证核对 | 判定 |
|:--|:--|:--|:--|:--|
| R-1 | CHANGELOG `### Notes` 旧「假占用本批不修（O1）」同步修订 | §6 L209 / §9 L260 / A9（grep「另批处理」0 命中） | CHANGELOG.md:26 现写「本批不修，另批处理（O1）」；设计明确「→（O1）已在 1.4.0 内修复（见 ### Fixed）」 | ✅ 落实 |
| R-2 | spec.yaml 补 P2/P3 场景 | §6 L211 / §9 L262（`cli-interface` 两场景） | spec.yaml `cli-interface` capability 存在（L341），已有 cli-04「顶层 flag 归位」场景（L381-400）；设计新增「-i 值泄漏归位」「web 用法错误 exit 2」两场景 | ✅ 落实 |
| R-3 | T2 TIME_WAIT 关闭方向 | §7 T2（L222）「服务端主动 `close()`（先发 FIN）」 | 与 v1.0 R-3 要求逐字一致 | ✅ 落实 |
| R-4 | killpg 升级策略 + `getpgid` 取值 | §4.4 ⊙2（L156-164） | 对齐 `server.py:645-651`：`getpgid`→`SIGTERM`→0.5s→`SIGKILL`，best-effort `except (ProcessLookupError, PermissionError, OSError)` | ✅ 落实 |
| R-5 | 宽限后 kill 前再判端口 | §4.4 ⊙3（L151-153）「kill 前 re-check `is_port_in_use`，已就绪幂等返回」 | 防 TOCTOU 误杀慢绑定 runner，落点明确 | ✅ 落实 |
| R-6 | pid 复用误杀防御 | §4.4 ⊙2（L155-156）`get_process_info` + `runner.py` + `abs_path` 校验；不匹配只删登记 | `utils.py:205` 函数存在；`server.py:292` runner 命令行含 `runner.py` + `abs_path` 双 token，校验可落地 | ✅ 落实 |
| R-7 | 宽限内他人抢端口 | §4.4 ⊙1（L143-148）`get_pid_by_lsof` 监听者核验，全他 pid 判「端口被他人占」不 kill 他人 | 落点明确；仅存 lsof 过滤口径差异（见 R-9） | ✅ 落实（附 R-9） |

---

## 五、安全事项（findings）

### 必改（F-x）

| # | 级别 | 标题 | 落点 | 修复要求 |
|:--|:--|:--|:--|:--|
| **F-2 残留** | 🟡 | A4 孤儿判据仍需补强三处，否则 harness 存在假阴性盲区 | 设计 §8 A4 | ①（a）显式写 registry.json 绝对路径 `~/.http-server.cli/registry.json`，并明示「不得用 `hs list --json`（其按 `_alive` 过滤死 pid 条目，`cli.py:321`）」；同时 §8 A10 改用原始 registry.json 读文件（当前仍用 `hs list --json`，不自洽）；②（b）明确「逐端口」枚举范围：可见孤儿 listener 落在另一端口，须枚举全部 LISTEN 端口与 registry 全量 pid 交叉比对，而非只 lsof 登记端口；③（c）补 pid 同一性断言（lsof LISTEN pid == registry 该 path 条目 pid），消除「1 dead-pid entry + 1 orphan listener」计数相等(1==1)的假阴性 |

### 记录（R-x，非阻断）

| # | 级别 | 标题 | 落点 |
|:--|:--|:--|:--|
| R-8 | 🟢 | A11「构造 dead entry」手法未写明，不可复跑。应给 recipe：手动向 `~/.http-server.cli/registry.json` 写一条 `{port: <空闲端口>, path: <tmpdir>, pid: <死 pid 如 999999>}` 后执行 `hs <tmpdir> --json`，断言 stdout 首非空字符 `{` 且 `json.loads` 成功、stderr 含 stale 文案 | 设计 §8 A11 / §7 T11 |
| R-9 | 🟢 | §4.4 ② R-7 用 `get_pid_by_lsof(port)`（`utils.py:172-191`，内部 `lsof -i :<port> -F p` **无** `-sTCP:LISTEN`，返回含 ESTABLISHED/TIME_WAIT 的 pid）与 §8 A4 的 `-sTCP:LISTEN` 口径不一致。post-D1 下 TIME_WAIT 不判占用，影响有限；建议 R-7 监听者核验也对齐 LISTEN 过滤（或注明语义差） | 设计 §4.4 ② |

### 待确认清单

- 无「阻断」级待确认；F-2 残留三子点 (a)(b)(c) 为必改，其余为记录。

---

## 六、评分（维度/权重沿用 v1.0）

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 缺陷认定与根因（§一 1–4） | 通过 | P1–P4 未变，v1.0 已源码 + 独立实测双证成立，无需重验 |
| 修法设计正确性（D1–D8） | 通过 | D1–D5、D7、D8 未变且正确；D6 重写后三态 stderr 逐态可执行，幂等路径未误改 |
| 规格完备性（D6/A4） | 部分通过 | D6（F-1）闭合；A4（F-2）方向修正但残留 3 子点补强 |
| 安全事项 | 1 🟡 必改 + 2 🟢 记录 | 非方向性冲突、非阻断 |

**总分 93 / 100（Rating: A）**

---

## 七、结论

**CONDITIONAL_PASS**。设计 v1.1 已闭合 F-1（D6 三态 stderr，污染点坐实 + 修法覆盖 + 无新矛盾），并逐条落实 R-1~R-7（七项全部源码核对到位：R-4 对齐 `server.py:645-651`、R-6 依赖的 `get_process_info`/runner 命令行双 token 均实存、R-7 监听者核验落点明确）。F-2 方向已修正（lsof LISTEN 端口级判据 + 删除 `ps` 判据 + 修前反证非恒真），但 A4 判据仍有 1 处必改（3 子点：显式写 registry.json 绝对路径并禁 `hs list --json`、明确「逐端口」枚举范围、补 pid 同一性断言），否则 harness 对「1 dead-pid entry + 1 orphan listener」与「跨端口孤儿」存在假阴性盲区。

按治理规范：**不提交、不 push**，回 ops 出设计 v1.2 补强 A4 后再次 rereview。
