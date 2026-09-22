# HTTP-SERVER-CL004 ops 核查报告（Step 4）

- 件号：`documents/review/http-server-cli-cl004-ops-verify-v1.0-20260922.md`
- 设计依据：`documents/http-server-port-residual-design-v1.4-20260922.md` §8（A 段断言表 A1–A11）+ §13（实施记录与偏差）
- 被测源码：Step 3 五笔 commit —— `36b1e91`（fix@cli 探测）/ `2651511`（fix@cli 归位+退出码）/ `4ecf537`（fix@cli stale 三态）/ `6f8392f`（tests@cli）/ `275ae93`（docs@sync + 设计 §13）
- harness：`scripts/port-residual-verify.py`（可复跑，纯标准库；含三项修前反证）
- 原始结果：`cache/closed-loop/20260922-http-server.cli-HTTP-SERVER-CL004-ops-verify.json`（逐条 detail）
- 基线（修前反证）：`git worktree add /tmp/hs-cl004-prefix ef125b3` + `PYTHONPATH=<wt>/src python3 -m http_server_cli.cli`
- 环境：macOS 26.6.2 / host 192.168.31.178 / `hs` = conda py3.12 editable 安装（`src/` 生效）/ 真实 registry 9 服务在跑（含 8080 被 `~/CodeSpace/script-miner/project/macosx` 占用）/ 核查后 registry 复原 9 条
- 核查日期：2026-09-22

## 1 结论

**13/13 PASS**（A1–A11，含 3 项修前反证子项），**残留 0**（registry 无临时目录条目、无主 runner listener、`/tmp/hs-cl004-verify` 与临时 worktree 均已移除）。

复跑命令：

```bash
cd /Users/jadenli/CodeSpace/http-server.cli && python3 scripts/port-residual-verify.py   # 期望：13/13 PASS + 残留 0
```

## 2 逐条结果（实测摘要）

| # | 命令/构造 | 实测 | 判定 |
|:--|:-----|:-----|:--|
| A1 | 残留态端口 9500（服务端先 close 造 TIME_WAIT）→ `is_port_in_use` | 修后 `False`；**修前（基线 `ef125b3`）`True`** ⇒ 判据随修法翻转 | PASS |
| A2 | 真 LISTEN：wildcard 9500 + 仅 `127.0.0.1` 9501 | 修后 `True True`（两种绑定均判占用） | PASS |
| A3 | 残留态端口 9500 + `hs <dir> -p 9500 -d --url` | rc=**0**，`http://jaden.local:9500`（不再假拒绝、不漂移） | PASS |
| A4-修后 | 同目录 100ms 内两次 `hs <dir> -d --url` | registry 该 path **1 条**；`listener_pids=[77264] == registry_pids=[77264]`（pid 同一性） | PASS |
| A4-修前反证 | 基线双击 ×5 样本 | **4/5** 出现 `listener 集合 != registry 集合`（≥3 有效）⇒ 孤儿真实存在、判据非恒真 | PASS |
| A5-修后 | `hs -i index.html -p 9500 -d --url <target>`（CWD 存在同名文件） | rc=0，registry 落 **target** 且 `index_page='index.html'` | PASS |
| A5-修前反证 | 基线同一命令（干净端口 9600） | rc=0 但落 **CWD**（目标目录条目 0 / CWD 条目 1）；stderr「⚠️ 未识别参数（已忽略）: …/a5target」 | PASS |
| A6 | `hs web add … --port 99` / `… --port 9001 --no-port` | rc=**2** / rc=**2**，且未误建条目 | PASS |
| A7 | `python3 scripts/port-flag-verify.py`（CL003 回归） | rc=0，**31/31 PASS** | PASS |
| A8 | 全量 `pytest tests/ -q`（py3.12） | rc=0，**557 passed**（基线 535 + 新增 22） | PASS |
| A9 | `hs version` / CHANGELOG / spec.yaml | `http-server v1.4.0`；`### Fixed` 存在；旧「另批处理」**0 命中**；spec `version: 1.4.0` | PASS |
| A10 | 残留核查（原始 registry + 全量 LISTEN 枚举 + pid 归属） | 临时目录条目 **0**；无主 runner listener **[]** | PASS |
| A11 | 注入死 pid 条目 → `hs <dir> --json` | stdout 首字符 `{` 且 `json.loads` 通过；stderr 含 `Found stale registry entry`；rc=0 | PASS |

## 3 修前反证（三项，均在基线 `ef125b3` 上取相反结果）

| 断言 | 修后 | 基线（`ef125b3`） | 说明 |
|:--|:--|:--|:--|
| A1 探测口径 | 残留态 `False` | 残留态 `True` | O1「假占用」本体 |
| A4 并发启动 | 1 条 + pid 同一性 | 5 次样本 4 次出现集合不等 | AUD-3 孤儿真实存在 |
| A5 顶层 `-i` | 落 target | 落 CWD（+ 未识别参数告警） | AUD-1 值泄漏 |

## 4 harness 自身缺陷留档（两处，均为本轮实测暴露）

1. **A8 解释器不稳**：首轮 `sys.executable -m pytest` rc=1 无输出 —— 该次运行由前台超时提升为后台进程，上下文解释器变为 conda base 3.13（无 pytest）。修法：`pytest_python()` 解释器候选链（`sys.executable` → conda py3.12 → PATH `python3`，逐个 `import pytest` 探活），并把选中解释器写进断言 detail。同 skill pitfall #14。
2. **A5 修前反证首轮作废**：基线 run 复用刚释放的端口 9500，而**基线实现的裸 bind 判定把自己刚释放的 TIME_WAIT 端口判成「占用」**（正是 O1 本体）⇒ 基线 fail-closed、未落任何条目，采样无效。修法：`free_port_fresh()`（独立 9600+ 段、不复用）+ 3 次重试 + 要求基线 `rc==0` 才算有效样本。**结论**：修前反证必须在「对基线也干净」的输入上做，否则会被待证缺陷本身污染成假阴性。

## 5 与设计的偏差核查（D1′）

设计 §13.1 记录的实施偏差「darwin 以 lsof LISTEN 为准 + socket 回退」在本核查中被实测确认：

- A2 覆盖了 **wildcard 与仅 `127.0.0.1`** 两种绑定，均判占用 ✓（纯 socket + `SO_REUSEADDR` 口径在 `127.0.0.1` 绑定时会漏判 —— 实施中由 `tests/test_dashboard.py::TestServe::test_foreground_starts_server` 暴露）。
- A1/A3 确认残留态不再触发假占用/漂移 ✓。
- 限度：本次 A2 未直接构造 **LAN-only 绑定**（如 `192.168.31.178:P`）的样本；该情形只在设计 §13.1 的探测矩阵实验中取证（lsof 命中）。审计如需，可按 §13.1 矩阵命令复核。

## 6 残留与数据完整性

- registry：核查前 9 条 → 核查后 **9 条**（harness 结束时按快照复原；A11 注入的临时条目与 A3/A5 启动的条目均已清除）。
- services.json：未新增条目（A6 两条用法错误均未落盘）。
- 进程：`lsof -nP -iTCP -sTCP:LISTEN` 中所有 `runner.py` listener 均能对应 registry 条目 pid；本次核查启动的端口（9500/9501/9600…）无遗留监听。
- 文件系统：`/tmp/hs-cl004-verify` 已删、`/tmp/hs-cl004-prefix`（worktree）已移除。

## 7 复跑须知

- A4-修前反证依赖 `git worktree`（需仓库干净可建 worktree），且**必须用干净端口段**（脚本内置 9600+ 游标）。
- A8 依赖本机装有 pytest 的解释器（脚本自动探活）。
- 核查期间勿手动 `hs kill` 脚本正在使用的端口（9500–9699 段）。
