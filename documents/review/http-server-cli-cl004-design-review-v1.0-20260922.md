# http-server.cli CL004 设计评审报告 v1.0

- 件号：`documents/review/http-server-cli-cl004-design-review-v1.0-20260922.md`
- 被审对象：`documents/http-server-port-residual-design-v1.0-20260922.md`（设计 v1.0，commit `6edb021`）
- 评审性质：**设计评审**（只审设计文档与现状事实，不审实现代码）
- 评审人：Security Reviewer（review profile）· 日期：2026-09-22
- 环境：macOS 26.6.2 · `hs` = conda py3.12 editable 安装（指向本仓 `src/`）
- 基线：HEAD `6edb021`（ahead 1，工作树 clean）· `hs version` = v1.4.0（未发布）· `PYTHONPATH=src python3 -m pytest tests/ -q` → **535 passed**

---

## 0 结论（前置）

**CONDITIONAL_PASS（90/100，Rating A-）** —— 无「阻断」、无方向性冲突。四项根因（P1–P4）全部实测成立，八项决策（D1–D8）核心正确：D1 `SO_REUSEADDR` 经 socket 级实测证明**只放宽残留态、不放宽真占用**（真 LISTEN 端口在修法下仍判占用）；D2 分支序交换五形态推演无破坏性回归；D3/D4/D5/D7/D8 均自洽。存在 **2 处必改（F-1/F-2）+ 7 处记录（R-1~R-7）**，均为设计规格层面的澄清/补全（非决策重选），回 ops 出 v1.1 后走 rereview。

---

## 一、数据验证（独立复算，不采信设计自述）

| 项 | 实测 | 判定 |
|:--|:-----|:--|
| git HEAD | `6edb021`，ahead 1（= 本设计件），工作树 clean | ✅ 与基线一致 |
| `hs version` | `http-server v1.4.0` | ✅ |
| 全量回归 | `PYTHONPATH=src python3 -m pytest tests/ -q` → **535 passed in 1.56s**（0 failed） | ✅ |
| `is_port_in_use` 源码 | `utils.py:118-132`：裸 bind `('', port)`，`settimeout(0.5)`，任一族失败 return True；**全文件 0 处 `setsockopt`/`SO_REUSEADDR`/`SO_REUSEPORT`**（grep 确认） | ✅ P1 根因成立 |
| 版本三处 | `__init__.py:28` / `CHANGELOG.md:3` / `spec.yaml:2` 均 `1.4.0` | ✅ |

---

## 二、缺陷认定与根因（§一 必审 1–4，逐条实证）

### 1. P1 端口探测「假占用」（🔴 根因）→ **成立**

- 读源码：`utils.py:118-132 is_port_in_use()` 用裸 socket bind（无 `SO_REUSEADDR`），逐族探测，任一族 `OSError` 即 `return True`。与设计 §1 P1 描述逐字一致。
- 独立复现（`cl004_p1_probe.py`，本机实测）：
  - **TIME_WAIT 残留态端口**（服务端主动关闭构造，`make_time_wait`）：
    - 裸 bind：`FAIL(errno=48 Address already in use)`
    - `SO_REUSEADDR` bind：`OK`
  - **真 LISTEN 端口**（`0.0.0.0:port` listen）：
    - 裸 bind：`FAIL(errno=48)`
    - `SO_REUSEADDR` bind：`FAIL(errno=48)` ← 关键：SO_REUSEADDR **不放宽真占用**
  - 本仓 `is_port_in_use`（裸 bind 现实现）：TIME_WAIT 端口 = `True`（假占用），真 LISTEN = `True`。
- 现场证据链（8084 kill→8085）可解释：残留连接端口裸 bind 判占用 → `find_available_port` 漂移。
- **判定：✅ P1 根因成立，证据链完整，非恒真。**

### 2. P2 顶层 `-i` 值泄漏走路径快捷方式（🟡）→ **成立**

- 读源码：`cli.py:1875-1911` 分支序 ➊ bookmark → ➋ 路径快捷方式（`cli.py:1897-1901`，`os.path.exists(cmd)`）→ ➌ 取值型 flag 重组（`cli.py:1902-1907`）。**➋ 先于 ➌**，与设计 §1 P2 描述一致（行号 1897-1911 覆盖两分支，属正常）。
- 实测（CWD 下 `index.html` 存在，29387 B）：
  - 形态 A `hs -i index.html -p 8091 <tmp>`：rc=1（8091 恰被 favorite-manager 服务占用），stderr `⚠️ 未识别参数（已忽略）: <tmp>`；`-i` 被当 path（index.html→CWD），`<tmp>` 被当未识别参数忽略。**证实走 ➋、-i 丢弃、dir 忽略**。
  - 形态 B `hs -i no-such-cl004.html -p 8092 <tmp>`：rc=0，`http://jaden.local:8092/no-such-cl004.html`，stderr 空，无「未识别参数」。**证实走 ➌、-i 保留、path=tmp**。
- **判定：✅ P2 根因成立，两形态行为差异实测复现，与设计 §1 一致。**

### 3. P3 web 退出码（🟢）→ **成立**

- 读源码：`cli.py:1429-1442`（`_web_add` 互斥 + `validate_port`）与 `cli.py:1702-1715`（`_web_update` 同）失败仅 `print + return` ⇒ rc=0。与设计 §1 P3 一致。
- 实测：
  - `hs web add cl004chk --cmd true --port 99; echo $?` → `❌ Port must be between 1024-65535`，**exit_code=0**。
  - `hs web update cl004chk --port 9001 --no-port; echo $?` → `❌ --port and --no-port are mutually exclusive`，**exit_code=0**。
  - 清理：`hs web remove cl004chk`，`cl004chk in list: False`。
- **判定：✅ P3 根因成立（软拒绝 rc=0）。**

### 4. P4 stale 孤儿（🟢）→ **成立**

- 读源码：`server.py:174-235`：`entry` 存在且 `is_process_alive(pid) and is_port_in_use(port)` → 幂等；否则 stale → `registry.remove(path=...)`（`:234`）后继续，**只删登记不 kill**。与设计 §1 P4 一致。
- 独立复现（`cl004_p4_probe.py`，同目录并发两次 `hs <tmpdir> -d --url`，5 次尝试）：
  - 尝试 1：registry **1 条**、listeners **2**（8084 + 8086）→ **孤儿**。
  - 尝试 2：registry **0 条**、listeners **1**（8084）→ **孤儿（完全隐形）**。
  - 尝试 3：同尝试 2 → **孤儿（隐形）**。
  - 尝试 4：registry 1 条、listeners 1 → 无孤儿（幂等命中）。
  - 尝试 5：registry 1 条、listeners 2 → **孤儿**。
  - **5 次中 4 次复现孤儿**（含「registry 0 条可见 + 1 listener」的完全隐形形态，见 F-2）。
- **判定：✅ P4 根因成立，且孤儿存在两种形态（可见/隐形），超出设计 §1 的单一描述。**

---

## 三、修法设计（§二 必审 5–14）

### 5. D1 `SO_REUSEADDR` 修法 → ✅ 成立（含反例压力测试）

- 反例口径实测（§8 A2）：真 LISTEN 端口在 `SO_REUSEADDR` bind 下**仍 FAIL(48)** ⇒ 修法只放宽残留态、不放宽真占用。判据非恒真。
- `tests/test_dashboard.py:82-83` 真监听断言（`assert is_port_in_use(port)`）：dashboard `serve()` 真监听下 `is_port_in_use` 仍 True（SO_REUSEADDR 不放行活跃 listener），断言不受影响。✅
- N1 `SO_REUSEPORT` 排除：合理。`SO_REUSEPORT` 允许同 addr:port 双绑定（改变「占用」语义，两个服务可共存），与本工具「占用即独占」语义冲突，排除正确（本机实测 SO_REUSEADDR 已足够，无需 REUSEPORT）。
- **判定：✅ D1 正确，无放宽真占用风险。**

### 6. D1 覆盖面 → ✅ 完整

- `is_port_in_use` 全部调用点（grep 实测）：`server.py:177`（幂等）/`:249`（保留端口）/`:261`（占用校验）/`:558`（status）· `registry.py:105`（`_alive`）· `registry_managed.py:56`（托管 `_alive`）· `dashboard.py:224`（API alive）/`:460`（restart 幂等）· `cli.py:678`/`:738`/`:937`（status/dashboard）· `mcp.py:516`（mcp 可用性）· `utils.py:167`（`find_available_port` 内部）。
- 与设计 §4.1「调用方（不变）：server.start / registry._alive / dashboard·mcp 可用性 / find_available_port」完全吻合，**无遗漏调用者**。
- 三条语义不变：探测目标 `('', port)`（`utils.py:129`）、`settimeout(0.5)`（`:128`）、任一族失败即占用（`:130-131`）——D1 仅在其间插入 `setsockopt`，三语义保持。✅
- **判定：✅ D1 影响面完整，语义不变。**

### 7. D2 分支序 → ✅ 成立（五形态推演 + 无破坏性形态）

按新序（➊ bookmark → ➋ 取值型 flag 重组 → ➌ 路径快捷方式）逐形态推演：

| 形态 | command | unknown | 新序归属 | 结果 |
|:--|:--|:--|:--|:--|
| `hs -p 8099`（无路径） | `8099` | `[-p]` | ➋ | `-p` 生效，path 默认 CWD（与旧序同） |
| `hs -i index.html -p 8095 <dir>` | `index.html` | `[-i]` | ➋（修复点） | `-i` 保留，path=`<dir>` |
| `hs -i index.html`（CWD 存在，无路径） | `index.html` | `[-i]` | ➋ | `-i` 生效 + path=CWD（旧序走 ➌ 结果等价：index.html 文件→dirname=CWD + index_page） |
| `hs index.html`（无 flag） | `index.html` | `[]` | ➌ | 快捷方式保留（unknown 无触发位，➋ 不命中） |
| `hs -o index.html` | `index.html` | `[-o]` | ➌ | `-o` 非触发位，走快捷方式（行为与旧序一致） |

- 触发条件不变（`unknown` 含 `-p/--port/-i/--index` 之一，`-o/-d/-f` 不触发）。
- CL003 D8 两形态（`hs -p 8099`、`hs -i a.html -p 8099`）在新序下仍命中重组、args 顺序原样 ⇒ 不回退。
- 唯一受交换影响的是「`unknown` 含触发位 **且** `command` 为 CWD 存在路径」——恰为 P2 修复目标。无破坏性形态。
- 边缘注记（非阻断）：`hs -p <非数字但存在的文件名>`（如 CWD 存在名为 `8080` 的文件）将从「静默丢 `-p` 按路径服务」变为「exit 2 非法端口」——属正确化（消 silent flag drop），非破坏合法用法。
- **判定：✅ D2 成立，五形态归属正确，无破坏性回归。**

### 8. D3 退出码 → ✅ 成立

- 与 CL003 D9e 口径自洽：`hs start -p 99` → 2（已确立），D3 把 `web add/update` 的 `--port` 互斥 + `validate_port` 两处失败对齐为 `sys.exit(2)`。
- 落点核实：`_cmd_web`（`cli.py:1330-1347`）直接调用 `_web_add`/`_web_update`，无 `try/except` 包裹；`sys.exit(2)` 自校验点（解析之后）抛出 `SystemExit(2)` 向上穿透 `main()` → 进程 rc=2。`_parse_known_args`（`:66-68`）仅在 `parse_known_args` 阶段捕 SystemExit，不拦截校验点的 `sys.exit(2)`。✅
- N7「成功路径与其余 error 分支不改」界定清晰：仅互斥 + `validate_port` 两处改；`--cmd` 缺失、名称非法、`--no-domain` 冲突、名称冲突、store 异常等分支保持 rc=0（`services.py` 的 `validate_name/cmd/open_mode/url` 均不受影响）。
- 兼容影响：「脚本按退出码判 web 失败」从 0→2 是**有意变更**（对齐三态退出码语义），应在 CHANGELOG `### Fixed` 记录（D7 已列）。✅
- **判定：✅ D3 成立，技术落点可落地。**

### 9. D4/D5 stale 三态 → ✅ 成立（边界压力测试，2 处记录）

三态：① pid 活 + 端口监听 → 幂等（不变）；② pid 活 + 端口未监听 → 宽限 0.2s×5（≤1.0s）；③ pid 死 → stale 只删登记；② 宽限后 pid 仍活 → kill 进程组 + 删登记。逐边界：

- ① 宽限内端口被他人占用：② 轮询 `is_port_in_use` 变 True → 幂等返回，**但未验证监听者 pid**（见 R-7）。
- ② pid 复用：`is_process_alive` 为 signal-0 判定，无法区分「我们的进程」vs「复用 pid」；killpg 理论上可误杀无关进程组（见 R-6）。
- ③ `killpg` 失败：设计「best-effort，失败仅记 stderr」，异常吞掉不阻塞启动。✅ 但需补 SIGTERM→SIGKILL 升级与 `os.getpgid` 取值（见 R-4）。
- ④ 幂等命中路径：① 判定在最前，命中即返回，**不引入新等待**（与 CL003 F-1 顺序链一致）。✅
- ⑤ 宽限体感：≤1.0s 仅「同路径重复启动 + pid 活但未监听」场景触发，罕见。✅
- **判定：✅ D4/D5 成立，边界大体覆盖，R-4/R-6/R-7 记录。**

### 10. D6 文案 → 🟡 必改（F-1）

- 现状（`server.py:229-234`）：stale 文案 url_only → stderr（正确）；**json / 默认 → `eprint` → stdout**。
- 实测复现（`cl004_d6_probe.py`）：`hs <dir> --json`（dead entry 触发 stale）→ stdout 首行为 `🔄 Found stale registry entry, cleaning up before restart`，随后才是 JSON 信封 ⇒ `json.loads` 抛 `JSONDecodeError`，**JSON 信封被污染**。
- D6 文本「两者均不污染 stdout（--url 走 stderr，**其余沿用现状**）」自相矛盾：`其余沿用现状` 恰把 json/默认留在 stdout，违反「均不污染 stdout」与 CL003 §13.1「新文案用 stderr」口径。
- **判定：🟡 F-1（见 §四），须在 v1.1 明确三态均走 stderr。**

### 11. D7/D8 版本与同步 → ✅ 成立（2 处记录）

- D7 并入未发布 1.4.0：合理。1.4.0 尚未发布 PyPI，CL004 并入同一未发布版本，不触碰已发布版本号（1.3.0/1.3.1 先例：1.3.1 为发布后展示名 patch，与「未发布版本内合并」不同，不构成反例）。✅
- CHANGELOG `### Fixed` 四条覆盖 P1–P4：① 假占用（P1）② `-i` 泄漏（P2）③ web rc 0→2（P3）④ stale 孤儿（P4），**四对四齐全**。✅
- spec.yaml：`port-allocation`（L171）/`service-lifecycle`（L34）两 capability 均存在，D8 补「残留连接不判占用」+「stale 宽限」场景方向正确。但 P3（web 退出码）未同步 spec（见 R-2）。
- **判定：✅ D7/D8 成立，R-1/R-2 记录。**

### 12. §7 测试清单 → ✅ 可落地（1 处记录）

- T2（残留态端口构造）：**可落地且已实测**（本评审 P1 复现即用「服务端主动 close」构造 TIME_WAIT，裸 bind FAIL / SO_REUSEADDR OK）。但 §7 T2 未指定关闭方向，见 R-3。
- T4（monkeypatch `_COMMANDS['start']` + `sys.argv`）：`_COMMANDS` 为模块级 dict（`cli.py` 顶部分派），monkeypatch 点真实存在，可落地。
- T8/T9（monkeypatch `is_port_in_use`/`is_process_alive`/`registry.remove`/`killpg` + D5 常量）：`server.py` 顶部 `from http_server_cli.utils import is_port_in_use, is_process_alive`（模块级绑定，可 monkeypatch）；`START_GRACE_INTERVAL/_ATTEMPTS` 模块级常量（D5）便于免等待。可落地。
- **判定：✅ T2/T4/T8/T9 可落地，R-3 记录。**

### 13. §8 A 段断言表 → 🟡 必改（F-2，A4 孤儿检测口径）

- A1（残留态端口 + 修前 worktree 反证）：**可复跑且非恒真**——本评审实测残留态端口可稳定构造、修前裸 bind=True/修后 False。✅
- A2（真监听判占用）：**可复跑且非恒真**——本评审 socket 级实测真 LISTEN 在 SO_REUSEADDR 下仍 FAIL。✅
- A4（孤儿检测）：**口径不足**——本评审实测孤儿存在两种形态：可见（registry 1 条 + 2 listeners）与**隐形（registry 0 条可见 + 1 listener，因 `hs list --json` 按 `_alive` 过滤掉死 pid 条目）**。A4 的「该路径 1 条 + `ps` 无同名孤儿」：(a) `ps` 判「同名孤儿」未定义（如何从 `ps` 区分两个 `runner.py <dir>` 的归属？）；(b) 可见孤儿形态下「该路径 1 条」仍为 True，仅靠模糊的 `ps` 判据兜底。见 F-2。
- A5（落点 path）/A6（web rc）/A7（CL003 31/31 回归，harness 存在）/A8（pytest）/A9（version）/A10（无残留）均可复跑。✅
- **判定：🟡 F-2（A4），其余 A1/A2/A5-A10 可落地。**

### 14. 风险与回滚（§10/§11）→ ✅ 成立

- 探测改动对 lsof 展示路径：`is_port_in_use` 与 `get_all_occupied_ports`/`get_pid_by_lsof` 相互独立（N3 不改主路径为 lsof），SO_REUSEADDR 不影响 lsof 展示。✅
- 对 dashboard/mcp 启动判定：`dashboard.py:460`/`mcp.py:516` 的 `is_port_in_use` 同源受影响——刚 kill 的服务（进程已死、端口 TIME_WAIT）从「判占用」变「判空闲」，是**修复预期**（假占用消除），非回归（dashboard/mcp 自身 `HTTPServer` 均 `allow_reuse_address=1`，可重绑 TIME_WAIT）。✅
- 回滚：四项改动各自独立（utils.py / cli.py 分支序 / cli.py 退出码 / server.py 三态），无数据格式变更、无迁移，可逐 commit `git revert`。✅
- **判定：✅ 风险与回滚可行。**

---

## 四、安全事项（findings）

### 必改（F-x）

| # | 级别 | 标题 | 落点 | 修复要求 + 验证方法 |
|:--|:--|:--|:--|:--|
| **F-1** | 🟡 | D6「两者均不污染 stdout（其余沿用现状）」自相矛盾：json/默认 模式 stale 文案经 `eprint` 仍写 stdout，污染 JSON 信封 | 设计 D6 / §4.4 | 改为三态（url/json/默认）均 `print(..., file=sys.stderr)`；删除「其余沿用现状」。验证：`hs <dir> --json`（dead entry 触发 stale）→ stdout 首字符 `{` 且 `json.loads` 成功、stderr 含 stale 文案 |
| **F-2** | 🟡 | §8 A4 孤儿检测口径不足：孤儿有「registry 0 条可见 + 1 listener」隐形形态（`hs list --json` 按 `_alive` 过滤死 pid），A4 的「该路径 1 条 + `ps` 无同名孤儿」无法可靠捕获 | 设计 §8 A4 | 孤儿判据改为 lsof 端口级：`lsof -i :<port>` 的 LISTEN pid 数 == registry 该 path 条目数（修后应 == 1）；修前 worktree 反证断言「listener 数 > registry 条目数」。验证：复现后 `lsof -i :<port> -F p` 计数与 `registry.json` 比对 |

### 记录（R-x，非阻断）

| # | 级别 | 标题 | 落点 |
|:--|:--|:--|:--|
| R-1 | 🟢 | CHANGELOG 1.4.0 `### Notes`（L26）「假占用 已知观察项 本批不修（O1）」须随新增 `### Fixed` 同步删除/更新，避免与「假占用已修」自相矛盾 | 设计 §6/§9 CHANGELOG 项 |
| R-2 | 🟢 | spec.yaml 仅补 P1（port-allocation）/P4（service-lifecycle）场景；P3（web 退出码 0→2）未同步 web/cli capability 的退出码场景，P2（分支序）未入 spec | 设计 §6/§9 spec 项 |
| R-3 | 🟢 | §7 T2「绑定→连接→关闭，留 TIME_WAIT」未指定关闭方向；TIME_WAIT 需**服务端主动 close**（先发 FIN），客户端主动 close 只在客户端 ephemeral 端口留 TIME_WAIT | 设计 §7 T2 |
| R-4 | 🟢 | §4.4 伪码 `killpg(pid)` 未定 SIGTERM→SIGKILL 升级与 `os.getpgid(pid)` 取值（prose「getpgid+killpg」与伪码「直接 killpg(pid)」不一致）；建议对齐 `server.py:645-651` 现有 kill 方法 | 设计 §4.4 / 折入 Step 3 |
| R-5 | 🟢 | D4 宽限循环结束后、kill 前应再判一次 `is_port_in_use(port)`（若已就绪则幂等返回），避免 kill 掉 >1s 慢绑定刚就绪的 runner（TOCTOU） | 设计 §4.4 / 折入 Step 3 |
| R-6 | 🟢 | pid 复用边界：`is_process_alive`（signal-0）无法区分「我们的进程」vs「复用 pid」，stale kill 理论上可误杀无关进程组；窗口极窄（≤1.0s）且与现有 stale 判定同源，建议 kill 前用 `get_process_info` 校验命令行含 `runner.py`（可选 defense-in-depth） | 设计 §4.4 |
| R-7 | 🟢 | ② 宽限轮询仅判 `is_port_in_use(port)`（端口级），未验证监听者 pid；宽限内他人抢端口会误判「已就绪」幂等返回。窗口极窄，③ 分支已用「端口被他人占」措辞部分覆盖 | 设计 §4.4 |

---

## 五、评分

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 缺陷认定与根因（§一 1–4） | 通过 | P1–P4 四项全部源码 + 独立实测双证成立，证据链非恒真 |
| 修法设计正确性（§二 5/6/7/8/9/11/14） | 通过 | D1 反例实测不放宽真占用；D2 五形态无破坏；D3 落点可落地；D4/D5 三态边界大体覆盖；D7/D8 版本同步合理；风险回滚可行 |
| 规格完备性（§二 10/12/13） | 部分通过 | D6 文案（F-1）+ A4 孤儿口径（F-2）两处规格缺口 |
| 安全事项 | 2 🟡 必改 + 7 🟢 记录 | 均非方向性冲突、非阻断 |

**总分 90 / 100（Rating: A-）**

---

## 六、结论

**CONDITIONAL_PASS**。设计 v1.0 的根因定位（P1–P4）与决策定案（D1–D8）核心正确，经源码 + 独立实测（含 P1 socket 级反例、P4 孤儿 5 次复现、D6 JSON 污染复现）逐条核对成立。无「阻断」、无 D1 放宽真占用 / D2 破坏快捷方式 的方向性冲突。

遗留 2 处必改（F-1 D6 文案通道自相矛盾、F-2 A4 孤儿检测口径不足）+ 7 处记录，均为设计规格澄清/补全（非决策重选）。按治理规范：**不提交、不 push**，回 ops 出设计 v1.1 修订 F-1/F-2（R-1~R-7 同批勘误），随后派 rereview。
