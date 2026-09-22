# http-server.cli CL004 实现审计报告 v1.0

- 件号：`documents/review/http-server-cli-cl004-audit-v1.0-20260922.md`
- 设计依据：`documents/http-server-port-residual-design-v1.4-20260922.md`（v1.4，设计复审 PASS 100/100）
- 被测对象（合并单一批，6 笔 commit）：`36b1e91`（fix@cli 探测 D1′+D11+快照）· `2651511`（fix@cli 归位 D2 + web 退出码 D3）· `4ecf537`（fix@cli stale 三态 D4/D5/D6/R-4~R-7）· `6f8392f`（tests@cli test_port_probe.py + 旧行为同步）· `275ae93`（docs@sync 四同步 + 设计 §13）· `127db13`（test@verify ops harness + 报告）
- 审计基线：HEAD `127db13`，本地 ahead 6（未 push），工作树 clean
- 审计人：Security Reviewer（review profile）· 日期：2026-09-22
- 环境：macOS 26.6.2 · `hs` = conda py3.12 editable 安装（指向本仓 `src/`，改动即时生效）· 真实 registry 9 服务在跑

## 0 结论（前置）

**PASS（99/100，Rating: A）** —— 无阻断性缺陷、无实现与设计方向性冲突。

核心结论：
- **D1′ 探测口径偏差（lsof LISTEN 为准 + socket 回退）独立复核成立**（§2.1 专项）：本审计用独立最小实验复现设计 §13.1 的 3×3 探测矩阵，实测与设计逐格一致 —— macOS `SO_REUSEADDR` 确实允许「不同本地地址同端口」共存，纯 socket + SO_REUSEADDR 会漏判 `127.0.0.1`/LAN 绑定的真监听；lsof LISTEN 在所有绑定地址上命中。**偏差正当、必要，非放宽真占用，反而比原设计更强。**
- 全量回归 557 passed（0 failed），CL003 harness 31/31 PASS，ops 核查 A1–A11 独立复跑 13/13 PASS。
- 四同步以实测核对为真；真实数据目录审计前后 registry/services `sha256` **逐字节一致**，无 cl004 残留、无主 runner listener 0。

非阻断发现（详见 §三）：
- **AUD-1 🟢**：`features.md` 测试模块数写「18 个测试模块」，实测为 **16 个**（`git ls-files tests/test_*.py` = 16；基线 15 + 本批新增 test_port_probe.py 1 = 16）。测试**用例数** 557 正确，仅模块数失真。建议下次 docs@sync 改为 16。

---

## 一、数据验证（独立复算，不采信 ops）

| 项 | 实测 | 判定 |
|:--|:-----|:--|
| git HEAD | `127db13`（ahead 6，`git status --porcelain` 空） | ✅ 与基线一致 |
| 全量回归 | `PYTHONPATH=src python -m pytest tests/ -q` → **557 passed in 3.79s**（0 failed） | ✅ |
| CL003 回归 | `python scripts/port-flag-verify.py` → **31/31 PASS**，残留 0 | ✅ |
| ops 核查 | `python scripts/port-residual-verify.py` → **13/13 PASS**（A1–A11，含 3 项修前反证） | ✅ 独立复跑 |
| `hs version` | `http-server v1.4.0` | ✅ |
| 三处版本 | `__init__.py:28` / `CHANGELOG.md:3` / `spec.yaml:2` 均 `1.4.0` | ✅ |
| spec.yaml | `yaml.safe_load` 通过，`version: 1.4.0`；新增 `port-05`/`lifecycle-06`/`cli-05` | ✅ |
| CHANGELOG | `### Fixed` 五条；`grep -c "另批处理"` = **0**（R-1） | ✅ |
| 测试文件数 | 基线 15 → 现 16（新增 test_port_probe.py） | ✅（features.md「18」失真，见 AUD-1） |
| 审计前 registry/services | registry 9 条 `sha256=82dee2cb…` · services 11 条 `sha256=3bbf34ee…` | ✅ 记录 |
| 审计后 registry/services | **sha256 逐字节一致**，cl004/tmp 残留 0，无主 runner listener 0 | ✅ 无污染 |

---

## 二、逐项审计（实证命令 + 实测输出 + 判定）

### 1. 探测口径（D1′）

- 读源码：`utils.py:118-146 _listening_ports()` darwin 用 lsof `-sTCP:LISTEN` 取 LISTEN 集合；区分「无监听 ⇒ 空集（rc≠0 且 stdout/stderr 皆空）」与「lsof 不可用 ⇒ None（TimeoutExpired/OSError/rc≠0 且 stderr 非空）」。`utils.py:149-174 is_port_in_use()` darwin 主路径 `port in listening`；非 darwin 或 lsof 不可用回退 socket（开 `SO_REUSEADDR`）。
- 实证：`_listening_ports()` 实测返回 `set`（32 端口，含 8080/8081/8082/8083/8085）；真监听 wildcard + 仅 127.0.0.1 → `is_port_in_use` 均 `True`（ops A2 实测 `True True`）；残留态 TIME_WAIT → `False`（A1）；lsof 不可用回退不抛异常（test_t14 monkeypatch `_listening_ports→None` + 真实 socket 断言）。
- **判定：✅**。空集/None 区分实现正确（`return set() if not stdout.strip() and not stderr.strip() else None`）；回退路径语义等价、异常兜底。

### 2. D1′ 偏差是否正当（重点）→ 见 §2.1 专项复核

**判定：✅ 偏差正当**（详细矩阵见下节）。

### 3. D11 `get_pid_by_lsof(port, listen_only=False)`

- 读源码：`utils.py:201-228` 新参数默认 `False`（不追加 `-sTCP:LISTEN`，行为与旧版一致）；`True` 追加 `-sTCP:LISTEN`。`grep -rn "get_pid_by_lsof" src/`：既有调用点（`server.py:60`、`server.py:594`）不传参 ⇒ 行为不变；仅 `server.py:224/234`（R-7/R-5）传 `listen_only=True`。
- 实证：真实监听端口上 `get_pid_by_lsof(sp)` 与 `get_pid_by_lsof(sp, listen_only=True)` 均返回 `[当前 pid]`；ESTABLISHED-only 端口差异由 test_t13（默认非空 / listen_only 空）覆盖，557 通过。
- **判定：✅**。参数新增默认值不变（N9 落实）。

### 4. D2 顶层归位

- 读源码：`cli.py:1897-1912` 分支序 ➊ bookmark → ➋ 取值型 flag 重组（`-p/--port/-i/--index`）→ ➌ 路径快捷方式；`-o/-d/-f` 不触发 ➋。
- 实证（ops A5-修后）：`hs -i index.html -p 9500 -d --url <target>`（CWD 存在同名 index.html）→ rc=0，registry 落 `<target>` 且 `index_page='index.html'`。A5-修前反证：基线同一命令落 CWD + `⚠️ 未识别参数（已忽略）: …/a5target`。
- 测试五形态（test_t4×4 + test_t5）全部通过：`hs -p 8099`→`['-p','8099']`；`hs -i index.html -p 8095 <dir>`→四 token 原样；`hs index.html`/`hs -o index.html` 仍走快捷方式。
- **判定：✅**。

### 5. D3 web 用法错误退出码

- 读源码：`cli.py:1429-1442`（add）/ `cli.py:1702-1715`（update）互斥 + `validate_port` 失败由 `return` 改 `sys.exit(2)`（json 先输出 error 信封再退出）。
- 实证（ops A6）：`hs web add cl004v-a6a --cmd true --port 99` → rc=**2**；`… --port 9001 --no-port` → rc=**2**；services.json 未误建条目。
- **判定：✅**。

### 6. D4/D5 stale 三态

- 读源码：`server.py:208-308` ① 幂等（pid 活 + 端口监听，零等待）→ ② 宽限（`START_GRACE_INTERVAL=0.2 × START_GRACE_ATTEMPTS=5`，≤1.0s）→ ③ stale（先终止进程组再清登记）；R-5 宽限结束、kill 前再判端口（`server.py:231-238`）。
- 实证（ops A4-修后）：同目录 100ms 双击 → registry 该 path **1 条**，`listener_pids=[80486] == registry_pids=[80486]`（pid **同一性**，非计数）。A4-修前反证：基线双击 ×5 样本 **5/5** 出现 `listener 集合 != registry 集合`（孤儿真实存在，判据非恒真）。
- **判定：✅**。

### 7. R-6/R-7 归属与防误杀

- 读源码：`server.py:72-84 _is_our_runner()` 命令行 token 精确匹配（`any(os.path.basename(t)=='runner.py' for t in parts) and abs_path in parts`，`in parts` 为列表成员判定 = 完全相等，**禁 `in` 子串**，F-4 同口径）；不匹配 ⇒ 只清登记 + stderr「登记 pid 非本工具服务」。R-7（`server.py:222-229`）宽限内 `get_pid_by_lsof(port, listen_only=True)` 核监听者，非登记 pid ⇒ 判「端口已被其他进程占用」且**不 kill 他人**。
- 实证：test_t12a（命令行不含 runner.py → `killed==[]` 且只清登记，stderr「非本工具服务」）；test_t12b（宽限内他人监听 → `killed==[]` 且 stderr「端口已被其他进程占用」）。均 557 通过。
- **判定：✅**。F-4 收口点（harness `scripts/port-residual-verify.py:172-191 listen_pids()` 与生产 `_is_our_runner`）同口径（token 精确匹配，无 `in` 子串）。

### 8. D6 文案通道

- 读源码：`server.py:296-307` stale/终止/他人占用三类文案统一 `print(f'🔄 {stale_msg}', file=sys.stderr)`，**不再经 `eprint`**（旧 `if url_only: … else: eprint(…)` 双路径已合并为单 stderr 路径）；url/json/默认三态同一出口。
- 实证（ops A11）：`hs <dir> --json`（注入死 pid 条目）→ stdout 首个非空字符 `{` 且 `json.loads` 成功；stderr 含 `Found stale registry entry`；rc=0。默认模式由 `test_server.py::test_start_cleans_stale_entry` 断言 `captured.err`；url 模式由 test_t8/t9/t10 断言 `capsys.readouterr().err`。
- **判定：✅**。

### 9. `find_available_port` 快照

- 读源码：`utils.py:184-199` 一次 `_listening_ports()` 快照 + 集合比对（避免 N 次 lsof）；lsof 不可用（`occupied is None`）回退逐端口 `is_port_in_use`（语义等价）。
- 实证：test_t3（残留态端口 `find_available_port` 返回该端口本身，不再漂移）；ops A3（残留态端口 + `-p` rc=0 不漂移）。
- **判定：✅**。

### 10. 未越界改动

- `git diff ef125b3..HEAD -- src/` 逐 hunk 核对：仅动 `utils.py`（探测/lsof 参数/快照）、`server.py`（stale 三态+归属+终止）、`cli.py`（main 分支序交换 + web exit 2）。**未改**：`eprint()`（`utils.py:33-38` 仍写 stdout，O1/N5 落实）、`hs set port` 语义、`hs list --port` 语义、reserved 端口 8180/8181 硬拦（`server.py:46 RESERVED_PORTS` 不变）、CL003 `-p` 校验顺序链（`server.py:311-343` 区间/保留/占用三态不变）。
- **判定：✅**。

### 11. 新增 `tests/test_port_probe.py` 覆盖设计 §7 T1–T13

- 实测 22 例，与 §7 清单逐条对照：T1（wildcard 真监听）/ T1b（仅 127.0.0.1，D1′）/ T1c（LAN 绑定）/ T14（lsof 不可用回退）/ T2（残留态）/ T3（快照不漂移）/ T4×4（顶层归位五形态）/ T5（-i CWD 存在文件）/ T6/T6b（web 越界/互斥 exit 2）/ T7/T7b（update 同）/ T8（宽限转正）/ T9（归属通过先终止）/ T10（pid 死只清登记）/ T11（--json 通道）/ T12a/T12b（非 runner / 他人占用不杀）/ T13（listen_only 差异）。
- **判定：✅**。设计 §7 所有用例落位，且 T1b/T1c/T14 三项为 D1′ 偏差的测试固化。

### 12. 旧行为测试两处改动正当性（重点）

- `tests/test_port_flag.py`：两处 web 校验由「rc=0 软拒绝」改为 `pytest.raises(SystemExit)` + `assert code == 2`。对应 D3 的**有意行为变更**，断言**增强**（原仅「未建条目」，现追加退出码 2），非削弱。
- `tests/test_server.py::test_start_cleans_stale_entry`：`captured.out` → `captured.err`。对应 D6 通道迁移，断言强度等价（仅换通道）。
- 两处改动均与设计决策一一对应，**无**「为变绿而削弱断言」情形。
- **判定：✅**。

### 13. 断言强度

- 无恒真断言：残留态/真监听用真实 socket（服务端主动 close 造 TIME_WAIT）；并发样本用 pid **同一性**（`ours == reg_pids`，非计数）；A4 修前反证要求 ≥3 有效样本（实测 5/5）。
- 路径断言用 `os.path.realpath`（`_abs()`）与 `resolve_path` 同口径（macOS `/tmp`→`/private/tmp`）；竞态样本有就绪等待（ops `wait_ready()` 连续两次 pid 集合稳定）。
- **判定：✅**。

### 14. 四同步以实测为准

| 项 | 实测 | 判定 |
|:--|:--|:--|
| `hs version` | `http-server v1.4.0` | ✅ |
| CHANGELOG `### Fixed` | 五条（假占用/顶层 -i/web 退出码/孤儿/stale 文案） | ✅ |
| Notes R-1 | `grep -c "另批处理"` = 0；旧行改为「已在 1.4.0 内修复」 | ✅ |
| features.md 测试数 | 535 → **557** | ✅ |
| features.md 模块数 | 「18」→ 实测 **16** | 🟢 AUD-1 |
| features.md 新增条目 | 端口检测 lsof 口径 / stale 宽限 / 顶层归位 / 启动竞态防护 均与实现一致 | ✅ |
| README ×2 `-p` 行 | 增「刚释放端口（TIME_WAIT 残留）可复用」 | ✅ |
| spec.yaml | `port-05`/`lifecycle-06`/`cli-05` 已增，`yaml.safe_load` 通过 | ✅ |

- **判定：✅（1×🟢 模块数失真，见 AUD-1）**。

### 15. 设计 §13 偏差承认如实

- §13.1 矩阵：独立复核成立（§2.1）；行号/触发证据（`test_dashboard.py::TestServe::test_foreground_starts_server`）属实。
- §13.2 快照：`find_available_port` 一次 LISTEN 快照属实。
- §13.3 D2–D11 对照表行号：R-5 `server.py:231-238`、R-7 `server.py:222-229` **精确命中**；D3 `cli.py:1705-1718` 实测为 `1702-1715`（漂移 3 行，非实质）。
- §13.4 测试数：22 例（T1/T1b/T1c/T14/T2/T3/T4×4/T5/T6/T6b/T7/T7b/T8/T9/T10/T11/T12a/T12b/T13 = 22）与 pytest 收集 `test_port_probe.py` 22 例一致；557 passed 属实。
- §13.5 真机冒烟：ops A1–A11 覆盖，逐条成立。
- §13.6 commit 清单：5 笔 fix@cli/tests@cli/docs@sync 与 `git log` 一致（+ 1 笔 test@verify 属 Step 4）。
- **判定：✅（1×🟢 行号漂移 3 行，非实质）**。

### 16. 全量回归

- `PYTHONPATH=src python -m pytest tests/ -q` → **557 passed in 3.79s，0 failed**（≥ 557）。
- **判定：✅**。

### 17. CL003 回归

- `python scripts/port-flag-verify.py` → **31/31 PASS**，残留 0（CL004 未破坏 CL003 交付面）。
- **判定：✅**。

### 18. 真实数据目录无污染

- 审计前后 `shasum registry.json services.json`：`82dee2cb…`/`3bbf34ee…` **两次逐字节一致**。
- registry 9 条不变、services 11 条不变；`cl004`/`/tmp/` 残留条目 0；`lsof -sTCP:LISTEN` 中全部 runner listener（5 个 pid）均能对上 registry 条目 pid（**无主 runner listener 0**，判据同 #6 pid 同一性）。
- **判定：✅**。

---

## 2.1 D1′ 偏差专项复核（独立最小实验）

设计 D1 原定「纯 socket + SO_REUSEADDR」；实施改为「darwin 以 lsof LISTEN 为准 + socket 回退」。本审计**独立复跑探测矩阵**（真实 socket，非采信 §13.1）：

| # | 监听地址 | 裸 bind('') | REUSE bind('') | REUSE bind(127.0.0.1) | lsof LISTEN |
|:--|:--|:--|:--|:--|:--|
| 1 | wildcard `0.0.0.0` | FAIL(48) ✓ | FAIL(48) ✓ | **OK（漏判✗）** | 命中 ✓ |
| 2 | `127.0.0.1` | FAIL(48) ✓ | **OK（漏判✗）** | FAIL(48) ✓ | 命中 ✓ |
| 3 | LAN `192.168.31.178` | FAIL(48) ✓ | **OK（漏判✗）** | **OK（漏判✗）** | 命中 ✓ |
| 4 | TIME_WAIT 残留（无监听者） | FAIL(48) 误判✗ | OK ✓ | OK ✓ | 未命中 ✓ |

实测与设计 §13.1 矩阵**逐格一致**（本审计实测端口 55148/55149/55150）。结论：

- **纯 socket + SO_REUSEADDR 在 macOS 上确实漏判**：BSD/macOS `SO_REUSEADDR` 允许「不同本地地址同端口」共存 —— wildcard 监听时 `bind(127.0.0.1)` 成功、`127.0.0.1` 监听时 `bind('')` 成功、LAN 监听时两者皆成功。故 D1 原口径会**放宽真占用**（违反 §2.1 目标 1）。
- **lsof LISTEN 在所有绑定地址命中**（含 wildcard/127.0.0.1/LAN），且天然不受 TIME_WAIT 残留影响。
- **偏差正当且必要**：若坚持 D1 纯 socket，`tests/test_dashboard.py::TestServe::test_foreground_starts_server`（dashboard 仅监听 127.0.0.1）会由 PASS 变 FAIL。改为 lsof 后 A2 断言比原设计更强。
- **回退路径的残留漏判（🟢 记录，非缺陷）**：lsof 不可用（非 darwin 或 lsof 缺失/超时）时回退 socket + SO_REUSEADDR，该路径在 darwin 上仍有跨地址漏判（回退语义等价旧实现）。此为该偏差的**文档化降级**（§13.1「回退与降级」），且 darwin 上 lsof 恒可用、非 darwin 上 socket 语义正确（Linux `SO_REUSEADDR` 不允许跨地址共存），故组合口径在两平台均正确。不构成阻断。

---

## 三、安全事项（findings）

| # | 级别 | 标题 | 落点 | 处置 |
|:--|:--|:--|:--|:--|
| AUD-1 | 🟢 | `features.md` 测试模块数「18 个测试模块」与实测不符（实际 16：基线 15 + 本批新增 1） | `features.md:133` | 记录 + 建议下次 docs@sync 改 16 |
| OBS-1 | 🟢 | 设计 §13.3 D3 对照行号 `cli.py:1705-1718` 实测为 `1702-1715`（漂移 3 行，非实质） | 设计 §13.3 | 记录 |
| OBS-2 | 🟢 | lsof 不可用回退 socket + SO_REUSEADDR 在 darwin 仍有跨地址漏判（文档化降级，见 §2.1） | `utils.py:165-174` | 记录（§13.1 已声明） |

无 🟡 必改、无 🔴 阻断。误杀他人进程 / 探测放宽真占用 / 孤儿复现均**未发生**（R-6/R-7 实测不 kill 他人、A2 真监听全判占用、A4 双击 registry 单条 + pid 同一性）。

---

## 四、评分

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 实现与设计一致性（§二 1–10） | 通过 | D1′ 偏差复核成立、D2/D3/D4/D5/D6/D11/R-4~R-7/快照全部实测成立；未越界 |
| 测试审查（§二 11–13） | 通过 | 22 例覆盖 T1–T13；旧行为两处改动与 D3/D6 一一对应、断言增强非削弱；无恒真断言 |
| 文档/规格同步（§二 14–15） | 通过 | 四同步实测为真；§13 偏差承认如实；仅 1×🟢 模块数失真 |
| 回归与残留（§二 16–18） | 通过 | 557 passed、CL003 31/31、数据目录 sha256 逐字节一致无污染 |
| 安全事项 | 1 🟢 + 2 🟢 | 均非阻断、无方向性冲突 |

**总分 99 / 100（Rating: A）**

---

## 五、结论

**PASS**。实现忠实落地设计 v1.4 全部 D 项与 R-4~R-7；关键偏差 D1′（探测主路径改 lsof LISTEN）经独立最小实验复核为**正当且必要**（纯 socket + SO_REUSEADDR 在 macOS 会放宽真占用，lsof 口径更严）；stale 三态 + 宽限 + 归属校验 + 文案通道以 pid 同一性实测成立、不误杀；四同步以实测核对为真、无「假同步」；全量 557 测试零回归、CL003 31/31、真实数据目录审计前后逐字节一致。

遗留（非阻断）：AUD-1（features.md 模块数 18→16，建议下次 docs@sync 修正）+ OBS-1/OBS-2（行号漂移 / 回退降级，均已记录）。
