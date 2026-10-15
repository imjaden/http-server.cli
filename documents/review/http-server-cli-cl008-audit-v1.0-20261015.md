# http-server.cli CL008 实现审计报告 v1.0（web --domain 防呆 + 横幅修正 + help 规范化）

- 件号：`documents/review/http-server-cli-cl008-audit-v1.0-20261015.md`（Style B 首轮件）
- 编号：**HTTP-SERVER-CL008**
- 被审对象：单 commit `0e6ee00`（ahead 1，相对 `f4633b6`；14 文件，+738/-145）——未 push
- 设计依据：`documents/http-server-cl008-web-domain-guard-design-v1.0-20261015.md`（v1.0）
- 审计人：Security Reviewer（review profile）· 日期：2026-10-15 11:25 CST
- 环境：macOS 26.6.2 · `.venv` Python 3.11.15（`hs` = editable 指向本仓 `src/`）· 复审基线工作树 clean @ `0e6ee00`
- 探针沙箱：`HS_DATA_DIR=<tmpdir>`（`~/.hermes/profiles/review/cache/scratch/*.py`），真实数据目录零触碰

## 0 结论（前置）

**CONDITIONAL PASS（82/100，Rating: B）—— 无 🔴 阻断项；本批不 push。**

A1（横幅）/ A3（风险标记）/ A6（存量止血，真机态已清）/ help 规范化 四项实证通过，且 JSON 信封与真机数据零污染均已逐项复算。但存在 **3 项 🟡**：

- **SEC-001** 防呆判据函数 `_is_hs_cmd` 的绕过面（`~/bin/hs`、`./hs`、`sh -c 'hs …'`、非同一 PATH 的绝对路径）**既不拦也不标记**——实测可静默注册出 `use_domain=true` + hs 型 cmd 的风险条目（exit 0），A3 同函数失效导致该条目 `list` 无 ⚠️（双重失效，同根因）。
- **SEC-002** A2 判据只看「本次是否传 `--domain`」，不看 update 后的**有效状态**——`hs web update <name> --cmd '<hs …>'` 在既有 `use_domain=true` 条目上 exit 0 且落成 `use_domain=true + hs 型 cmd`，与 AC A2 字面（「use_domain=True + hs 型 cmd 时 fail-closed」）不符，即 CL008 要消灭的 R4 风险态可由一条命令重建。
- **SEC-003** 版本 1.5.1 上移未同步历史 harness 版本/计数白名单（CL006/CL007 每轮均同步，CL007 明确「历史 harness 版本断言放宽至 1.5.0」）→ `scripts/cl005-verify.py::a12_sync` 实测 FAIL（version=False/features=False/spec=False），`port-flag-verify.py:274`、`port-residual-verify.py:406,411` 同族断言均为 False。本批 ops/历史回归证据链断（A9/A10/A12/A14 复跑即红）。

另有 4 项 🟢（记录，非阻断）：`--plain` 路径无风险标记 / `--no-domain --domain` 同给仍 exit 2 与提示自相矛盾 / 请求与 TODO 的「668 基线」口径 / 治理 §8「空参数 → help」范例返回 0 而本仓按 CL007 A2 契约 exit 2。

**push 判定**：SEC-002 属 AC 字面偏差、SEC-003 使本仓自证工具链复跑即红，若现在 push 则发布件的验收声明与仓库自身的可复跑证据不完全相符 → **本轮不 push**，3 项 🟡 修复后走 round-2 限定复审（只审闭合面 + 回归）。

## 一、数据验证（独立复算，非采信 dev 自评）

| 项 | 实测命令 | 实测结果 | 判定 |
|:--|:--|:--|:--|
| 全量测试 | `.venv/bin/python -m pytest -q` | **678 passed** in 6.40s | ✅ 与 commit/features 一致 |
| 基线复算 | worktree@`f4633b6` 同解释器 pytest | 646 passed + **4 failed** = **650** | ✅ 650 与 features.md「19 模块/650」一致；4 处失败即本 commit 更新的 4 断言（`test_cl005 t13a`/`test_cl007 ×2`/`test_web`），因 `.venv` editable 指向主仓 `src/` → worktree 跑的是新源码，属版本偏斜**非基线红** |
| 增量口径 | — | 678 = 650 + 18（CL008）+ 10（help） | ✅ 请求/TODO 的「668 基线」为中间态（650+18），见 OBS-003 |
| 版本机器可读 | `hs version` / `hs -v` | `http-server v1.5.1`（E1 保持） | ✅ |
| 主 help | `hs help` | 60×`=` 规则线 + `📖 http-server · 1.5.1(20261015) · 别名 hs`；含【功能概述】/`── 分组 ──`/`── 选项 ──`/`📋 示例:`/数据目录尾行；rc=0 | ✅ |
| 空参契约 | `hs` | rc=**2**（打印 help，CL007 A2 不变） | ✅ |
| help 别名 | `hs help` / `hs --help` / `hs kill 8090 -h` | rc=0；`kill -h` 未执行 kill（无副作用） | ✅ |
| 子命令 help | `hs web help` / `hs bookmark help`（dashboard/mcp 由测试覆盖） | 同结构，rc=0 | ✅ |
| hm-style 逐字对齐 | `hm help`（hermes-manager 实机） | `📖 hermes-manager · 1.10(20261013) · 别名 hm,hermes-manager` vs 本仓 `📖 http-server · 1.5.1(20261015) · 别名 hs` | ✅ 版本(YYYYMMDD)·别名口径一致 |
| 模板花括号 | `_HELP` 全文扫描（`cli.py:134-235`） | 仅 `{version}`/`{date}` 两个占位符 | ✅ 无 `KeyError` 隐患 |
| A1 横幅 | monkeypatch `subprocess.run` returncode=2 | rc=1；stdout 无 ✅；stderr `❌ Service 'f1' failed (exit 2)` | ✅ |
| A1 JSON 兼容 | 同上 `--json` | `success=false` / `data.status='cmd_failed'` / `data.exit_code=3` | ✅ 零变更（`_web_run` JSON 分支 diff 未触碰） |
| A2 add 防呆 | `add x --cmd 'hs …' --domain` | rc=2，store 无条目（零副作用） | ✅ |
| A2 逃生 | `… --domain --force-domain` | 注册成功，`use_domain=true` | ✅ |
| A3 JSON 标记 | `list --json` / `show --json` | 风险条目 `domain_risk=true`；非 hs（dk）`false` | ✅ |
| A3 零落盘 | `list --json` 前后 `services.json` | 逐字节一致、落盘无 `domain_risk` 键（`ServiceStore._read_all` 每次重新读盘 → 富化仅内存） | ✅ |
| A6 真机态 | `~/.http-server.cli/services.json`（11 条） | `daily-tracker` / `local.jaden.tech` 均 `use_domain=false`；`hs web list` 零 ⚠️；`hs web show daily-tracker` rc=0 无 ⚠️；`list --json` 11/11 `domain_risk=false` | ✅ 与「真机复跑无 ❌/⚠️」声明一致 |
| 防呆合法性 | 沙箱 | 全部探针在 `HS_DATA_DIR` 沙箱内；真实 registry/services 未被写入 | ✅ |

## 二、发现项

### 🟡 建议修复

**HM-CL008-SEC-001 — `_is_hs_cmd` 绕过面使防呆与风险标记双重失效（既不拦也不标）**

`src/http_server_cli/cli.py:1515-1538`（`_is_hs_cmd`）仅识别「首 token 字面量 `hs`」或「绝对路径且 `resolve()` 后与 `shutil.which('hs')` 同一」两种形态。实测（`cache/scratch/cl008_probe.py`）：

```
'hs .'                    -> True
'/usr/local/bin/hs .'     -> False   ← 仅与 PATH 解析出的 hs 同一 inode 才命中；PATH 缺 hs（cron/daemon/其他 shell）即静默失效
'~/bin/hs .'              -> False   ← shlex 不展开 ~，Path.is_absolute()=False
'./hs .'                  -> False   ← 相对路径
'$HOME/bin/hs .'          -> False
'sh -c "hs ."' / 'env hs' / 'command hs' / 'HS' -> False
```

`hs web add tilde --cmd '~/bin/hs /tmp/site -o' --domain` → **rc=0 注册成功（use_domain=true）**，防呆未拦；同一 `_is_hs_cmd` 驱动 A3 标记，故 `hs web list` 该条目**无 ⚠️**（实测输出：`2/2 🌐 tilde … 👁 Open: url 🏷 Domain: on`，无风险标记）。风险在于：**该函数是本批唯一判据，检测面既非 fail-closed 也非 fail-safe，而是 fail-open（静默放行）**；条目随后在运行期因 CL007 fail-closed 必挂 exit 2——即 CL008 要消灭的缺陷类可由未识别的写法重新引入，且用户看不到任何风险提示。

**修复建议**（3 行级）：
1. `first = os.path.expanduser(tokens[0])`（覆盖 `~/bin/hs`）。
2. 命中条件改为「`first == 'hs'`（大小写归一 `casefold()`）**或** `os.path.basename(first) in ('hs', 'hs.exe')`」——覆盖 `./hs`、相对/绝对路径、symlink 名。
3. 若保留 `shutil.which('hs')` 分支，须把「PATH 中无 hs」视为**无法判定**而非「不是 hs」（当前 `which()` 返回 None → 直接返回 False = fail-open）。
4. 明确边界：`env hs` / `command hs` / `sh -c 'hs …'` / `HS` 若判定为非目标，应在 `_web_help` + `skills/hs-web/SKILL.md` 把「hs 型 cmd」表述限定为「首 token 为 `hs` 或 hs 可执行文件路径」，避免文档承诺强于实现。

**HM-CL008-SEC-002 — A2 update 判据用「本次是否传 --domain」代替「更新后的有效状态」，风险态可被一条命令重建（AC A2 字面偏差）**

`src/http_server_cli/cli.py:1964-1973`：判据为 `if parsed.domain and not parsed.force_domain`，未纳入 `existing['use_domain']` 与 `parsed.no_domain` 的合成结果。设计/AC A2 的字面判据是「`use_domain=True` + hs 型 cmd → fail-closed」，实现在 update 路径只覆盖「本次显式注入」的一支。

实测（`cache/scratch/cl008_probe.py` P3）：

```
add u1 --cmd 'dk server start --daemon --open' --domain      # use_domain=true
update u1 --cmd 'hs /Users/jadenli/CodeSpace/daily-tracker -i index.html -o'   # 不带 --domain
→ rc=OK(0)，结果 use_domain=true 且 cmd 为 hs 型 → 风险态=True（正是 R4/存量缺陷态）
```

影响：CL008 的 A2+A6 组合（源头防呆 + 存量清理）可被「先注册 dk 带 domain，再 update 换成 hs 命令」一次绕过，且退出码 0、无任何提示；之后 `list`/`show` 才以 ⚠️ 事后提示（且遇 SEC-001 写法时连提示也无）。

**修复建议**：先算有效态再判定（顺序：算 effective → 判 → 写）：

```
eff_cmd = parsed.cmd if parsed.cmd is not None else existing['cmd']
eff_use_domain = False if parsed.no_domain else (True if parsed.domain else bool(existing.get('use_domain')))
if eff_use_domain and not parsed.force_domain and _is_hs_cmd(eff_cmd): → exit 2
```

（`_web_add` 因默认 `use_domain=False`，无此缺口，实测通过。）

**HM-CL008-SEC-003 — 版本 1.5.1 上移未同步历史 harness 白名单 → 本仓自证工具链复跑即红（断链）**

`CL006`/`CL007` 每轮版本上移均在 `scripts/*-verify.py` 同步放宽白名单（CL007 注释原文：「历史 harness 版本断言放宽至 1.5.0（历史 harness 保持可复跑）」；CL007 闭环内另有 `fad4a56` 专做该项）。本 commit 未触碰 `scripts/`，而版本已由 1.5.0 → 1.5.1 → 白名单全不匹配：

| Harness | 断言位置 | 实测 |
|:--|:--|:--|
| `cl005-verify.py` | `a12_sync`（版本 + features 计数 + spec） | **`[FAIL] A12 四同步：version=False CHANGELOG=True features=False spec=False README=True 测试模块数=21`**（import 后直调 `a12_sync()`，无副作用） |
| `port-flag-verify.py:274` | `any(v in out for v in ('v1.4.0','v1.4.1','v1.4.2','v1.5.0'))` | `False`（`hs version` = `http-server v1.5.1`） |
| `port-residual-verify.py:406,411` | 同族 `ver_ok` / `spec_ok` | `False` / `False`（spec `version: 1.5.1`） |

三处是 CL005/CL004 批次的 ops 复跑闸门（A9/A10/A12/A14 及其「既有 harness 回归」），现在复跑必 FAIL 且失败原因与 CL005/CL004 无关 → 会造成 **误归因**（历史批次被判红）与 **证据链断**（本批「零回归」缺一份独立 harness 证据）。

**修复建议**：白名单改正则化（一次性消除此类漂移）——`re.search(r'v1\.\d+\.\d+', out)`、`re.search(r'^version: 1\.\d+\.\d+', spec, re.M)`；features 计数改 `re.search(r'2\d 个测试模块，\d{3} 个测试用例', feat)`（或把 `21 个测试模块，678` 加入枚举）。与 CL007 同法提交（`test@verify`），可在本批内补一笔或紧随 follow-up commit。

### 🟢 记录项（非阻断）

| # | Severity | 内容 | 位置 | 处置 |
|:--|:--|:--|:--|:--|
| HM-CL008-OBS-001 | 🟢 | `hs web list --plain` 路径打印 `name: cmd`，**不带** ⚠️ 风险标记（人类默认路径与 `--json` 均有） | `cli.py:1762-1765` | 记录；建议 plain 行尾追加 ` [RISK]`，或在 `_web_help` 注明 plain 为纯清单不带标记 |
| HM-CL008-OBS-002 | 🟢 | `update --no-domain --domain` 同给时判据仍 exit 2，提示「请用 --no-domain」而用户已给（清除语义本应赢） | `cli.py:1964` / `1975-1980` | 随 SEC-002 修复一并收敛（用 effective 判定即消失） |
| HM-CL008-OBS-003 | 🟢 | 请求与 `cache/draft/TODO-20261015.md` 的验收口径「668 passed 基线」与实测不符：650（`f4633b6`）→ 678（+18+10）；「-18 重复计数修正」无对应实测事实 | 请求件 / TODO 完成行 | 记录；仓库文档（features.md 21/678、spec 1.5.1）自洽正确，无需改码 |
| HM-CL008-OBS-004 | 🟢 | 治理规范 §8 参考形态「空参数 → 打印 help」通常 `return 0`；本仓按 CL007 A2 契约打印 help 后 exit 2（有意偏差，help 内容已完整打印） | `cli.py:2144-2147` | 记录（有意偏差，已有前批裁定，非本批引入） |

### 附：非 finding 的核查结论

- `spec.date: 2026-06-23` 未随版本更新 — 与历史一致（`f4633b6`/`54b3708` 同法），属惯例，不计。
- `--force-domain` 新增后 argparse 前缀缩写（`allow_abbrev=True` 为既有形态）：`--f` 因 `--force`/`--force-domain` 歧义报错 exit 2，`--force` 精确匹配仍走原语义 → 未引入新绕过。
- 新测试模块对真实路径/真实服务零副作用：`HS_CMD` 仅作解析输入，执行路径均由 monkeypatch/`--no-probe` 拦截；conftest autouse 沙箱生效。

## 三、Positives

- **A1 修到根上**：横幅与退出码语义解耦（`cmd_failed` → stderr `❌ … failed (exit N)`，✅ 仅 `exit_code=0`），且 JSON 分支零变更——两条通道同时自洽，未用「补一句 warning」的方式与旧 ✅ 共存。
- **A3 只做运行时富化**：`domain_risk` 未落盘（`list --json` 前后 `services.json` 逐字节一致），以「只增字段 + 零数据迁移」实现向后兼容；真机 11 条零假阳性。
- **A6 已落地且可核**：真机服务注册表中两条存量已 `use_domain=false`，与「真机复跑无 ❌/⚠️」声明互证。
- **help 与参照实机逐字对齐**（`hm help` 版本行/别名/分组/示例同形），且模板化 `_help_text()` 单一入口消除了 `_HELP.format` 的散落调用（`_fail_unknown_args`/`_cmd_help`/bare-args 三处统一）；`hs version` 机器可读格式保持不变（E1 兑现）。
- **测试断言落在契约上**：新增用例覆盖「零副作用」（阻断后 store 无条目 / `use_domain` 保持原值）、「JSON 兼容」（信封三字段）、「escape hatch 生效」，而非只断言退出码；`_is_hs_cmd` 纯函数单测含负例（`echo hs` 非首 token）。
- **审计可复跑性**：本次全部结论由沙箱探针 + harness 直调产出，未采信 dev 自评的「668/678」单一数字。

## 四、维度评估

| 维度 | 评分 | 备注 |
|:--|:--|:--|
| 合理性 | 88 | 三处修复方向均对准真实根因（R3 注入面 / R5 横幅 / 存量态），help 改造与治理 §8 + hm 实机一致；扣分在 A2 判据取「触发条件」而非「有效状态」 |
| 严格性 | 78 | SEC-001/002 显示防呆判据存在「不拦也不标」的自证缺口；SEC-003 使本批自证工具链复跑即红，验收链不完整 |
| 安全性 | 86 | 无注入/越权/敏感信息面变更；无权限模型改动；新增 `--force-domain` 为显式逃生开关（可接受）；扣分在 fail-open 判据与「文档承诺强于实现」的边界 |
| **总分** | **82 / 100（B）** | 无 🔴；3 🟡 均为小改（合计约 10 行 + harness 白名单正则化） |

## 五、Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| HM-CL008-SEC-001 | `_is_hs_cmd` 绕过面（`~/bin/hs`/`./hs`/`sh -c`/PATH 依赖）使防呆与 A3 标记双重失效 | 🟡 | P1 | 待修（回 ops） |
| HM-CL008-SEC-002 | update 判据用「是否传 --domain」代替「有效状态」→ `update --cmd '<hs …>'` 重建风险态（AC A2 偏差） | 🟡 | P1 | 待修（回 ops） |
| HM-CL008-SEC-003 | 1.5.1 未同步历史 harness 白名单 → cl005/port-flag/port-residual 复跑即红（证据链断） | 🟡 | P1 | 待修（回 ops） |
| HM-CL008-OBS-001 | `list --plain` 无风险标记 | 🟢 | P2 | 记录 |
| HM-CL008-OBS-002 | `--no-domain --domain` 同给提示自相矛盾 | 🟢 | P2 | 记录（随 SEC-002 收敛） |
| HM-CL008-OBS-003 | 请求/TODO「668 基线」口径与实测 650→678 不符 | 🟢 | P2 | 记录 |
| HM-CL008-OBS-004 | §8 空参 help 返回码范例差异（有意偏差，前批已裁定） | 🟢 | P2 | 记录 |

## 六、复审建议（round-2 限定复审）

范围仅限：SEC-001/002 闭合面 + SEC-003 harness 复跑转绿 + 本批回归（`pytest` 全量 + `cl005-verify --only A9,A10,A12` 或整跑 + `port-flag`/`port-residual` 版本断言）；**不重开**已 PASS 的 A1/A3/A4/A5 与 help 改造。闭合后同样走「PASS → push」流程（当前 `0e6ee00` 保持未 push，配合修复提交 rebase/叠加即可）。
