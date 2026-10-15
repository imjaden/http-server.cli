# http-server.cli CL008 实现审计报告 v1.1（round-2 限定复审 — SEC-001/002/003 闭合）

- 件号：`documents/review/http-server-cli-cl008-audit-v1.1-20261015.md`（Style B 续件，v1.0 之 round-2 复审）
- 编号：**HTTP-SERVER-CL008**
- 被审对象：`0e6ee00`（round-1 修复）+ **`5a33f4d`（round-2 修订，本回复审新增面）**；基线 `f4633b6`，ahead 3（未 push）
- 前置件：`documents/review/http-server-cli-cl008-audit-v1.0-20261015.md`（round-1，CONDITIONAL PASS 82/B）
- 复审范围（严格按 v1.0 §六「复审建议」）：**仅** SEC-001 / SEC-002 闭合面 + SEC-003 harness 复跑转绿 + 本批回归面（pytest 全量 / 历史 harness）；**不重开** A1/A3/A4/A5 与 help 改造（仅做零改动 smoke 确认）
- 审计人：Security Reviewer（review profile）· 日期：2026-10-15 11:58 CST
- 环境：macOS 26.6.2 · `.venv` Python 3.11.15（`hs` = editable 指向本仓 `src/`）· 复审基线工作树 clean @ `1bcd5bc`
- 探针沙箱：`HS_DATA_DIR=<tmpdir>`（`cache/scratch/cl008_round2_probe.py`，56 断言）；真实数据目录只读核对

## 0 结论（前置）

**PASS（96/100，Rating: A）—— 3 项 🟡 全部闭合，无新增 🟡/🔴；本批 push。**

三项闭合均为**独立复现**（非采信 dev 自评），且 round-1 的 4 项 🟢 之一（OBS-002）随本次修复自动收敛：

| round-1 finding | 闭合证据（本轮独立实测） | 状态 |
|:--|:--|:--|
| HM-CL008-SEC-001 `_is_hs_cmd` fail-open | 纯函数矩阵 25/25 命中预期；`add --domain` 8/8 拦截（含 `HS`/`./hs`/`~/bin/hs`/`/opt/other/bin/hs`/`hs.exe` + **PATH 中无 hs** 两例）；4 例非 hs 零误伤 | ✅ Closed |
| HM-CL008-SEC-002 update 用「本次 flag」代替「有效状态」 | round-1 实测漏洞场景现 **exit 2 且零落盘**（cmd 未改写 / use_domain 保持 true）；JSON 通道同判；负例（既有 true + 非 hs 新 cmd）不误伤 | ✅ Closed |
| HM-CL008-SEC-003 历史 harness 白名单未随 1.5.1 同步 | `cl005-verify --only A12` = **PASS**；`port-flag-verify` **31/31**（含 A14-1/A14-2 = `v1.5.1`/`1.5.1`）；`port-residual-verify` **13/13**（含 A9） | ✅ Closed |
| HM-CL008-OBS-002 `--no-domain --domain` 同给提示矛盾 | `update --cmd '<hs …>' --no-domain --domain` → rc=0、`use_domain=false`（清除语义赢） | ✅ Closed（随 SEC-002） |

回归面：**691 passed**（= round-1 678 + 13 新 SEC 回归，`test_cl008_web_domain_guard.py` 31 用例实测 31 passed）；A1/A3/help 零改动 smoke 全绿；真机态 11 条、风险条目 0。

## 一、数据验证（独立复算）

| 项 | 实测命令（本轮亲自执行） | 实测结果 | 判定 |
|:--|:--|:--|:--|
| 全量测试 | `.venv/bin/python -m pytest tests/ -q` | **691 passed** in 6.22s | ✅ 与 commit / features.md「21 模块 / 691」一致 |
| CL008 测试面 | `pytest tests/test_cl008_web_domain_guard.py -q` | **31 passed**（`grep -c "def test"` = 31） | ✅ 声明「31 用例 / +13 回归」为真 |
| help 测试面 | `pytest tests/test_help_format.py -q` | 10 passed | ✅ round-1 面零回归 |
| 模块数 | `git ls-files 'tests/test_*.py' \| wc -l` | 21 | ✅ 与 features.md 21 一致 |
| SEC-003-A | `cl005-verify.py --only A9,A10,A11,A12` | A9 PASS／A10 PASS（`port-flag 31/0`、`port-residual 13/0`）／**A12 PASS**（`version=True CHANGELOG=True features=True spec=True README=True 测试模块数=21`）／A11 异常（见 §二 OBS-008） | ✅ 与 round-1 的 FAIL 形成前后对照 |
| SEC-003-B | `port-flag-verify.py` | **31/31 PASS**；`A14-1 hs version='http-server v1.5.1'`、`A14-2 __init__=1.5.1 / spec=1.5.1` | ✅ |
| SEC-003-C | `port-residual-verify.py` | **13/13 PASS**（含 A9、A8 pytest 691） | ✅ |
| round-1 漏洞场景复现 | `cache/scratch/cl008_round2_probe.py` P3.1 | `update u1 --cmd 'hs …'`（既有 `use_domain=true`）→ **rc=2**，落盘 `cmd` 仍为 `dk …`、`use_domain` 仍 true | ✅ round-1 实测口径被翻转 |
| SEC-001 矩阵 | 同上 P1（25 例）/P2（8 例，两种 PATH） | 25/25 + 8/8 命中预期，**零误伤**（`hsync`/`hs-helper`/`dk`/`python3 -m http.server`） | ✅ |
| 真机态 | 直读 `~/.http-server.cli/services.json` + `hs web list` | 11 条；`use_domain=true` 5 条（`dk`/`daily.checker`/`daily-checker`/`daily-keeper`/`tool-nav`）**均非 hs 型 → 风险条目 0**、零 ⚠️ | ✅ 与 round-1 A6 结论一致 |
| 探针沙箱合规 | 全部 CLI 探针 `HS_DATA_DIR=<tmp>` | 汇总 **56/56 OK**；真实 registry/services 仅只读（详见 OBS-007 关于 harness 自身副作用） | ✅ |

## 二、发现项

### 🟡 建议修复

**无。** round-1 的三项 🟡 全部闭合（§0 表），未发现新的 🟡/🔴。

### 🟢 记录项（非阻断）

| # | Severity | 内容 | 位置 | 处置 |
|:--|:--|:--|:--|:--|
| HM-CL008-OBS-005 | 🟢 | **包装形态仍不识别**（`env hs …` / `command hs …` / `sh -c 'hs …'`）：实测 `add --cmd "sh -c 'hs /tmp/s -o'" --domain` → rc=0 且 `list` 无 ⚠️。属 round-1 明确要求的「文档收窄」边界（`_web_help` + `SKILL.md` 已逐字声明不识别），且运行期由 CL007 fail-closed（`hs … --domain` → exit 2）兜底 → **非静默失效**，接受现状 | `cli.py:1515-1534`；`skills/hs-web/SKILL.md:42` | 记录（边界已文档化） |
| HM-CL008-OBS-006 | 🟢 | **SEC-003 正则化的副作用**：断言由「枚举已知版本」变「任意 `\d+\.\d+\.\d+`」，A12 的「四同步」不再交叉校验**单一源**（`src/http_server_cli/__init__.py::__version__`）——若 1.5.2 只 bump `__init__` 而 spec/CHANGELOG 漂移，A12 仍 PASS。注：round-1 的枚举式同样无等值校验，故**非能力倒退**，且修复方向（消除每轮断链）当时由本审计人提出；建议后续以单源交叉断言加固（`hs version` == spec == CHANGELOG 首条 == `__version__`；features 计数 == `git ls-files tests/test_*.py` 计数 + pytest 实测数——A12 已算出 `n_mod` 但**未参与断言**） | `scripts/cl005-verify.py:505-520`；`port-flag-verify.py:272-284`；`port-residual-verify.py:405-416` | 记录 + 建议（P2，非本批阻断） |
| HM-CL008-OBS-007 | 🟢 | **历史 harness 非沙箱副作用**：`port-flag-verify.py::a11` 对**真实** `~/.http-server.cli/services.json` 执行 `web remove/add/remove cl003-demo`，`a10` 会真实 `dashboard -p 8280 -d` / `restart --port 8290`。本轮复跑使真实 services.json mtime 更新（**内容 11 条不变、零 cl003-demo 残留、零 ⚠️**）。属 CL003/CL004 批次既有形态（本批仅改 a14 断言行，未引入） | `port-flag-verify.py:219-234`、`a10` | 记录；建议后续让 harness 走 `HS_DATA_DIR` 沙箱 |
| HM-CL008-OBS-008 | 🟢 | **A11 断言健壮性**：`cl005-verify.py::a11_full_pytest` 用 `sys.executable -m pytest -n 4`（依赖 pytest-xdist）。`.venv`(3.11.15) 未装 xdist → pytest 报错走 stderr、stdout 为空 → `p.stdout.strip().splitlines()[-1]` 抛 `IndexError` 被记为「断言执行异常」而非 FAIL；同脚本以 `python3.12`（有 xdist 3.8.0）运行 → **A11 PASS 691 passed**。已用 `1bcd5bc:scripts/cl005-verify.py` 副本复跑证明**基线同样 IndexError → 非本批引入** | `cl005-verify.py:485-497` | 记录；建议改为按 `p.returncode` + stderr 判定并选装 xdist 的解释器 |
| HM-CL008-OBS-001 / 003 / 004 | 🟢 | round-1 记录项原样保留（`list --plain` 无风险标记 / 「668 基线」口径 / §8 空参返回码有意偏差），本批未触碰、无变化 | 同 round-1 | 记录 |

### 附：非 finding 的核查结论

- **update 判据的附加效应（有意 fail-closed）**：存量风险条目（`use_domain=true` + hs 型 cmd，仅能由 `--force-domain` 或 SEC-001 边界写法产生）上任何 update——含只改 `--url`/`--open`——均 exit 2（实测 P3.8），须同时给 `--no-domain` 才能继续（实测 P3.8b rc=0 且风险态清除）。这是「有效态判定」的必然推论，错误文案已指引 `--no-domain`，判定为**可接受的防呆收益**。
- `add --force` 覆盖同名风险条目时 `use_domain` 由 `parsed.domain` 重算（`services.py:164-173`），不继承旧值 → 实测 rc=0 且 `use_domain=false`，**无同类 fail-open 残留**。
- 本批未 bump 版本（仍 1.5.1）：`0e6ee00`/`5a33f4d` 均未 push、无已发布版本对应，属同批修订，`__version__`/spec/CHANGELOG/README 保持一致 → 无需 bump。
- 文档同步面逐字核对：`_web_help`（`cli.py:1566-1570` 收窄为「首 token 为 hs，或 basename=hs/hs.exe 的可执行路径，大小写不敏感」）、`skills/hs-web/SKILL.md:42`（判据 + 不识别清单）、`CHANGELOG.md`（round-2 Fixed 三条）、`features.md`（691）四处均与实现一致，无「文档承诺强于实现」。

## 三、Positives

- **SEC-001 改到根因**：`shutil.which('hs')` 的 PATH 依赖被整体移除（不再存在「环境决定判定」），判定退化为 `expanduser + basename.casefold()` 的**纯函数**，`which` 返回 None 的 fail-open 分支在结构上消失；同时把「不识别清单」写进 help/SKILL 两处，实现与承诺同宽。
- **SEC-002 修复顺序正确**：先算有效态（`--no-domain` 清除优先 → `--domain` → 既有态）**再判定**，判据位置仍在 `store.update` 之前 → 拦截零副作用（探针逐项验证「cmd 未改写 / use_domain 未变 / store 无新条目」），且同一处修好顺手收敛了 OBS-002。
- **改面收敛**：round-2 diff 仅 8 文件，`cli.py` 净 +24/-22 且集中在两处判据 + 两行 help，未顺手重构（A1/A3/A4/help 全零改动，smoke 复跑全绿）。
- **回归测试落在契约上**：新增 13 例覆盖「旧实现 fail-open 的具体写法」（`~/bin/hs`、`./hs`）、「既有 use_domain=true + 不带 --domain 的 update」、「--no-domain 清除语义赢」、「风险条目上任意改动被拦」，而非仅断言退出码。
- **harness 白名单正则化方向正确**：一次性消除「每轮版本上移即断链/误归因」的根因（CL006/CL007 均以枚举补丁应急），且三处同族改法一致（`re` 导入补齐，无 NameError 隐患）。

## 四、维度评估

| 维度 | 评分 | 备注 |
|:--|:--|:--|
| 合理性 | 96 | 三处修复均对准 round-1 认定的根因（PATH 依赖 / 判据取错对象 / 枚举漂移），无「绕开症状」式改动；改面与请求范围一致 |
| 严格性 | 95 | 闭合证据链完整（纯函数矩阵 + 端到端沙箱 + 三条历史 harness 复跑 + 真机只读核对）；扣分在 OBS-006（回归闸门从「枚举」变「格式」，未升级为单源交叉断言） |
| 安全性 | 96 | 无 🔴/🟡；fail-open 面由「PATH 决定」收敛为「basename 白名单 + 文档化边界」，运行期另有 CL007 fail-closed 兜底；零数据迁移、真机态未被本批改写 |
| **总分** | **96 / 100（A）** | round-1 三项 🟡 全闭合；新增仅 4 项 🟢 记录（均为可延后的加固建议） |

## 五、Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| HM-CL008-SEC-001 | `_is_hs_cmd` 绕过面使防呆 + A3 标记双重失效 | 🟡 | P1 | ✅ Closed（round-2 独立复现） |
| HM-CL008-SEC-002 | update 有效态判据缺失（AC A2 偏差） | 🟡 | P1 | ✅ Closed（round-2 独立复现） |
| HM-CL008-SEC-003 | 历史 harness 版本白名单未随 1.5.1 同步 | 🟡 | P1 | ✅ Closed（A12/A14/A9 三处转绿） |
| HM-CL008-OBS-002 | `--no-domain --domain` 同给提示矛盾 | 🟢 | P2 | ✅ Closed（随 SEC-002 收敛） |
| HM-CL008-OBS-001 | `list --plain` 无风险标记 | 🟢 | P2 | 记录（不变） |
| HM-CL008-OBS-003 | 「668 基线」口径勘误 | 🟢 | P2 | 记录（不变） |
| HM-CL008-OBS-004 | §8 空参返回码有意偏差 | 🟢 | P2 | 记录（不变） |
| HM-CL008-OBS-005 | 包装形态（`env`/`command`/`sh -c`）不识别（文档化边界） | 🟢 | P3 | 记录（运行期 CL007 兜底） |
| HM-CL008-OBS-006 | harness 版本断言正则化后无单一源等值校验 | 🟢 | P2 | 记录 + 建议（后续 `test@verify` 加固） |
| HM-CL008-OBS-007 | 历史 harness 触碰真实 services.json（非沙箱） | 🟢 | P2 | 记录 + 建议（harness 走 `HS_DATA_DIR`） |
| HM-CL008-OBS-008 | A11 在缺 xdist 解释器抛 IndexError（非 FAIL） | 🟢 | P3 | 记录（非本批引入，基线同样） |

## 六、push 判定

三项 🟡 闭合、证据链自洽（源码 + 测试 + harness + 真机只读四方互证）、工作树 clean、无新增 🟡/🔴 → **按 PASS 流程执行 push**（`0e6ee00` / `5a33f4d` / `1bcd5bc` + 本审计件提交一并推至 `origin/main`）。

round-3 无必须项；OBS-006 / OBS-007 / OBS-008 建议折入下一批 `test@verify`（历史 harness 加固：单源版本交叉断言 + `HS_DATA_DIR` 沙箱 + A11 判定健壮性）。
