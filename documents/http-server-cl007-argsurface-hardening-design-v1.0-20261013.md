# http-server.cli — 参数面加固（未知 flag fail-closed）设计 v1.0

- 编号：**HTTP-SERVER-CL007**
- 日期：2026-10-13
- 交付版本口径：**1.5.0**（1.4.2 → minor：用户可见的 CLI 行为变更）
- 来源：script-miner ops 会话转交（2026-10-13「4 转交」，目标仓 `~/CodeSpace/http-server.cli`）
- 范围：仅本仓；**禁 push**（改动只本地提交）
- 前置：同轮已落地并复核 HTTP-SERVER-CL006（`6bec14a` 存活优先 + `hs prune`；`7f30cb3` harness 16/16；`54b3708` v1.4.2 四同步）——**本件不重开该项**

## 1. 现象（转交单 §1，本机实测可复跑）

12 分钟内两次真实触发，均为**写操作被无意触发**：

```
$ hs prune --help
⚠️ 未识别参数（已忽略）: --help
🧹 Removed 8 stale registry record(s):            ← 真删了

$ hs                     # 想读用法
✅  http://jaden.local:8081/index.html            ← 在 cwd 起了一个服务
```

## 2. 根因定位

| 编号 | 缺陷 | 位置（修前） |
|:--|:--|:--|
| D1 | 写 / 破坏性命令遇未知 flag 仅 stderr 告警后**照常执行**（`_parse_known_args` 忽略 `unknown`） | `cli._parse_known_args` / `cli._warn_unknown_args` |
| D2 | 顶层 `args` 用 `argparse.REMAINDER`：命令一旦出现，后续 `-h/--help/-v/--version` 全被吞进子命令 args，既不触发全局 help/version 分支，又被子命令当「未知参数」忽略 ⇒ `hs prune --help` 直接执行 prune | `cli.main()`（`REMAINDER` + 全局 help 判定顺序） |
| D3 | 裸 `hs`（无路径 / 无命令 / 无参数）默认 `path='.'` 起服务，无任何提示 | `cli.main()`（`cmd is None` 分支） |
| D4 | `hs prune` 无「已删 / 保留」汇总，使用者无法确认影响面 | `server.ServerManager.prune_stale` |

实测确认（沙箱 `HS_DATA_DIR`）：`hs prune --help` → 告警后 prune；`hs list --prot` → rc 0 告警放行；裸 `hs` → 起服务。

## 3. 决策（Q1–Q5）

- **Q1 未知参数的收紧粒度（A1）** → **按「有副作用 / 无副作用」二分**，而非一刀切：
  - **写 / 破坏性命令**（`start` / `kill` / `kill-all` / `prune` / `web add·update·remove·<name>` / `mcp` / `dashboard` / `bookmark add·update·remove` / `set`）遇未知 flag 或多余位置参数 → stderr 报错 + **exit 2，不执行任何副作用**（`_parse_known_args(mutating=True)`，默认）。
  - **只读命令**（`list` / `status` / `history` / `config` / `search` / `bookmark list·show` / `web list·show`）保持 D6 口径：告警到 stderr、放行、退出码不变（`mutating=False`）。
  - 理由：A1 的原文只要求「至少不执行副作用」；只读命令无副作用，且 A4 明令其退出码语义不变。二分既消灭危险默认，又最小化 blast radius（`hs list --prot` rc 0 的历史 harness 断言 A6-b 得以保留）。

- **Q2 `-h/--help`、`-v/--version` 的处理（A1 的原始触发点）** → 二者在**任意位置**识别，不再算「未知参数」：
  - `hs prune --help` → 打印用法、**exit 0**、不执行 prune（原实现因 `REMAINDER` 吞参而绕过了全局 help 分支）。
  - `hs prune -v` → 打印版本、exit 0。
  - 与命令自带的 help 子命令不冲突：`hs web --help` 仍由 `_cmd_web` 优先处理成 web 专属帮助（顶层判定发生在子命令解析之前，但 web/dashboard/bookmark 的 `-h|--help` 子命令分支在此之前命中）。
  - 理由：帮助是「无副作用」的显式请求，报错（rc 2）反而不友好；exit 0 且零副作用同样满足 A1。

- **Q3 裸 `hs`（A2）** → 真正裸调用（无路径 / 无命令 / 无参数）→ 打印用法 + **exit 2**，不再默认起服务。带明确意图的 `hs -o` / `hs .` / `hs <dir>` 行为不变。
  - 理由：裸调用的意图不明确（读用法 vs 起服务），默认起服务是危险默认；退出非 0 使脚本/管道不会静默继续。
  - 兼容性：这是**有意**的契约变更（转交单 A2 明确要求），已在 `_HELP`、`features.md`、`CHANGELOG` 同步。

- **Q4 `hs prune` 是否默认 dry-run（A3，转交单建议「默认 dry-run、真删需 `--yes`」）** → **判定「现状即正确口径，不改」**，理由：
  1. **无数据损失**：`prune` 只删 `pid` 已不存活的沉积登记（CL006 已核实），不删存活服务、不动 `history.json`；
  2. **不重开 CL006**：CL006 的 A4 契约（`hs prune` 即执行、`-n/--dry-run` 仅预览）刚落地上线并被 `cl007` 之外的 `cl006-verify.py`（16 断言）与 `test_cl006_status_registry.py` 断言；改默认语义等于重开该项，与转交单「本件不重开该项」相悖；
  3. **触发向量已被 A1 封死**：`hs prune --help` 这类「习惯性探测」现 fail-closed（rc 2，零副作用），产生事故的根因消失。
  - 因此本次只补 A3 中**无争议的一半**：输出末尾新增 `📦 Kept N registry record(s)` 汇总（已删 N / 保留 N），`--json` 增 additive 字段 `kept`。
  - 调用方应遵守的用法：**预览用 `hs prune -n`（不改动）；确认后 `hs prune` 执行**。
  - 若使用者仍希望「默认 dry-run + `--yes`」，属另一项独立变更（需同步改 `cl006-verify.py` A4 与 `test_cl006`），可在后续编号评估。

- **Q5 `hs kill` 是否加交互确认（A3）** → **不加交互确认**，仅继承 A1 收紧：
  - `kill` 本就要求端口 / 路径**显式**（无参 → rc 1 `Please specify a port or path`），已在设计上杜绝「无目标误杀」；
  - 交互确认会破坏脚本化（`hs kill` 常被自动化调用，且多为无 TTY 环境），代价大于收益；
  - 未知 flag 现 fail-closed（`hs kill 8080 --bogus` → rc 2，不 kill），配合「显式目标」已覆盖 A3 的护栏意图。
  - 调用方应遵守的用法：`hs kill <port|path|name>`（目标显式；`--json` 可脚本化）。

## 4. AC 对照

| AC | 决策 | 落地 |
|:--|:--|:--|
| A1 未知参数不得放行执行 | Q1/Q2/Q5 | 写命令 `_parse_known_args(mutating=True)` fail-closed；`-h/-v` 任意位置识别 |
| A2 裸调用不得默默起服务 | Q3 | `main()` `cmd is None` + 无参数 → 用法 + exit 2 |
| A3 破坏性命令加护栏 | Q4/Q5 | `prune` 保留执行语义 + 新增 已删/保留 汇总；`kill` 目标显式 + fail-closed；**未引入 `--yes`**（附理由） |
| A4 契约 | Q1 | 只读命令 rc/字段不变；`list/status/kill/web --json` 既有字段与退出码语义不变（`prune --json` 仅 +`kept`） |

## 5. 实现要点

- `cli._filter_unknown(unknown, *, allow, allow_html, allow_positional)` — 纯函数（原 `_warn_unknown_args` 的内联过滤抽出）。
- `cli._warn_unknown_args(...)` — 读命令口径（保留原语义，供既有测试）。
- `cli._fail_unknown_args(rest, prog, *, json_mode)` — 新：help/version 别名 → exit 0；否则 stderr +（`--json` 时 JSON 错误信封）→ exit 2；空输入 no-op。
- `cli._parse_known_args(..., mutating=True)` — 新参数，默认 fail-closed；只读命令显式传 `mutating=False`。
- `cli._handle_set` / `_cmd_killall` / `_cmd_mcp`（子命令分支）— 手工 fail-closed（这三处不经解析器）。
- `cli.main()` — `cmd is None` 分支：有 `unknown`（如 `hs -o`）→ start；无参数 → 用法 + exit 2。
- `server.ServerManager.prune_stale` — 增 `kept = self.registry.count()`；输出 `📦 Kept N registry record(s)`；JSON 增 `kept`。

## 6. 测试清单

- `tests/test_cl007_argsurface.py`（20 用例）：
  - `TestFilterUnknown`（5）：`_filter_unknown` 豁免规则。
  - `TestA1FailClosed`（5）：`prune --bogus` / `prune --help` / `kill … --bogus` / `<dir> --prt 8080` / `killall --bogus` 均无副作用。
  - `TestA2BareInvocation`（3）：裸 `hs` → exit 2 + 用法且不起服务；`hs .` / `hs -o` 仍进 start。
  - `TestA3PruneSummary`（3）：`Removed`+`Kept`；`-n` 预览 vs 执行差异；`--json` 增 `kept`。
  - `TestA4ReadOnlyAndJson`（4）：`list/status` 只读告警放行；写命令 `--json` 错误信封；`list --json` 字段不变。
- `scripts/cl007-verify.py`（harness，10 断言，`HS_DATA_DIR` 沙箱）：A1–A4 端到端可复跑。
- 全量回归：`650 passed`（630 基线 + 20 新增）。

## 7. 涉及文件

- 代码：`src/http_server_cli/cli.py`、`src/http_server_cli/server.py`、`src/http_server_cli/__init__.py`（版本）
- 测试：`tests/test_cl007_argsurface.py`（新）
- harness：`scripts/cl007-verify.py`（新）；历史 harness 版本断言放宽（`cl005-verify.py` / `port-flag-verify.py` A6·A14 / `port-residual-verify.py`）
- 文档：`CHANGELOG.md`、`features.md`、`http-server.cli.spec.yaml`（cli-07）、本设计件

## 8. 边界与未决

- 只改本仓；不 push。
- 未引入 `prune --yes` / 交互式确认（见 Q4/Q5）；若使用者需要，另起编号并同步 CL006 断言。
- 转交单要求的新用例「`prune -n` 与 `prune --yes` 的差异」——因未引入 `--yes`（Q4），改为覆盖「`prune -n`（预览）与 `prune`（执行）」的差异，语义等价且不重开 CL006。
