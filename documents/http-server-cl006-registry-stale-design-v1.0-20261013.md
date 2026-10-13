# http-server.cli — `hs status` 同端口沉积记录口径 设计/收口 v1.0

- 编号：**HTTP-SERVER-CL006**
- 日期：2026-10-13
- 交付版本口径：**1.4.2**（1.4.1 → patch）
- 来源：script-miner ops 会话转交（2026-10-13「3 转交修复」）
- 范围：仅本仓（`~/CodeSpace/http-server.cli`）

## 1. 现象（转交单 §1，本机实测可复跑）

同一端口 8080、同一时刻：

```
$ hs status 8080
🔍 http://jaden.local:8080  ❌ stopped
  Path:  ~/CodeSpace/script-miner/project/macosx      ← 错拼（少一个 s）
  PID:   1289  ·  Process: exited  ·  Port: in use     ← 自相矛盾

$ hs list
✅  http://jaden.local:8080
    📁  ~/CodeSpace/script-miner/projects/macosx
    🔧  PID: 1016  |  Started: 2026-10-13T10:31:35
```

`hs status` 报「已停」（且进程死、path 陈旧），却又 `Port: in use`；`hs list` 指向存活实例 1016 ⇒ 使用者会误判「服务已停」。

根因（本机 `~/.http-server.cli/registry.json`）：同端口存在多条记录（历史沉积，未清理）。实测该端口 **3 条**（陈旧 1289 / llm-radar.lab 92334 / 存活 1016）。

## 2. 根因定位

| 编号 | 缺陷 | 位置（修前） |
|:--|:--|:--|
| D1 | `hs status <port>` 按端口取**首条**命中，未做存活过滤；`hs list` 做存活过滤 ⇒ 结论不一致 | `registry.Registry.find(port=)`（首个命中）；`server.status()` |
| D2 | 访问记账 `last_access_at` 写到同端口**首条**（陈旧条） | `registry._flush_access_cache()` / `Registry.touch()` 均用 `find(port=)` 首条 |
| D3 | 状态输出「❌ stopped」与「Port: in use」并存，无解释 → 误导 | `server.status()` 文案 |

## 3. 决策（Q1–Q4）

- **Q1 选条口径（A1）** → 集中在 `Registry.find(port=)`：**存活优先 + 最近 `started_at`**（同分且多条时取最近 `started_at`，再退回原始顺序）。保留 `prefer_alive=False` 逃生口还原旧「首个命中」语义。选中央修复而非仅改 `status`：`status` / `kill` / dashboard 同源收敛，避免同类缺陷在有别的调用点再现。
- **Q2 记账目标（A2）** → 不改调用面（handler 热路径仍是 `_touch_memory(port)` → 60s `_flush_access_cache()`），只让 `find` 选存活条 ⇒ `touch()` 与刷盘自动落到存活实例，陈旧条不再被污染。
- **Q3 输出口径（A3）** → 显式区分 `Status: live` / `Status: stale-record`；端口被他人占用时 `Port:  occupied by PID <n>（非本记录）`、空闲时 `Port:  free` ⇒ 不再出现「stopped + in use」矛盾组合。`--json` **additive** 增 `record_status`（`live`/`stale-record`）与 `occupants`（占用者 pid 列表）。exit code / 状态图标语义不变（`❌ stopped` 仍表 stopped）。
- **Q4 沉积治理（A4）** → **组合口径**：①展示层「存活优先 + 最近 `started_at`」保留一条（`select_display_entries`，用于 `hs list` / `server.list`）；②`list`/`status` 标注陈旧（`hs list` 末尾 `N stale registry record(s) hidden — run hs prune to clean`；`--json` 增 `stale_count`）；③新增 **`hs prune [-n|--dry-run] [--json]`** 显式清理 pid 已死记录 —— **默认命令（list/status/start）不动手删**。`history.json` 独立，不受影响。

## 4. 实施（改动面）

- `src/http_server_cli/registry.py`
  - 新增模块级 `select_entry(candidates)`（存活优先 + 最近 started_at）、`select_display_entries(entries, key)`（按 port 分组保留一条，用于展示层）
  - `Registry.find(..., prefer_alive=True)` 重写为候选集 + 选择
  - `Registry.touch(port)` 改用 `find`（写存活条）
  - 新增 `Registry.stale_entries()` / `Registry.prune_stale()`
  - `_flush_access_cache()` 无需改动（随 `find` 口径受益）
- `src/http_server_cli/server.py`
  - `status()`：`record_status` / 占用者具名 / `Status:` 行；JSON additive 字段
  - `list()`：展示层去重 + 陈旧条数提示（JSON 信封不变，含空态等值断言契约）
  - 新增 `ServerManager.prune_stale(json, dry_run)`
- `src/http_server_cli/cli.py`
  - `_list_servers`：去重 + `stale_count`（JSON additive）+ 非 JSON 提示
  - 新增 `_cmd_prune`（`--json` / `-n|--dry-run`）；`_HELP` 增 prune 行
- `tests/test_cl006_status_registry.py`（25 用例）
- `scripts/cl006-verify.py`（AC A1–A4，16 断言，`HS_DATA_DIR` 沙箱）
- `http-server.cli.spec.yaml`：`version: 1.4.2` + `reg-04` / `reg-05`
- `CHANGELOG.md` / `features.md` / `__init__.py`（1.4.2, 2026-10-13）

## 5. AC 映射与验收

| AC | 实现 | 证据 |
|:--|:--|:--|
| A1 口径一致 | `find` 存活优先；`status`/`list` 同源 | 真机 `hs status 8080` → PID 1016 / `projects/macosx`；`hs list` 同 pid；harness `A1`/`CONSIST` |
| A2 记账正确 | `touch` + 刷盘写存活条 | harness `A2`（存活条 `last_access_at` 刷新、陈旧条保持 `2026-10-13T12:09:10`）；`test_flush_access_cache_writes_to_live_entry` |
| A3 输出不误导 | `Status: stale-record` + 占用者具名 | 真机 `hs status 8081`（无存活）→ `Port:  free` / `Status:  stale-record`；harness `A3` |
| A4 沉积治理 | 展示去重 + 标注 + `hs prune` | harness `A4`（dry-run 不改动 / prune 清沉积留存活）；`test_cl006_*::TestPrune*` |

## 6. 边界遵守

- 只改本仓；未改 script-miner 及其它仓。
- **未 push**（本地 commit，等用户放行）。
- CLI 契约不回归：`list [--short|--port|--path|--json]` / `status` / `kill` / `web` 既有断言与 `--json` 字段保留（新增字段 additive）；`registry.json` 结构 `{"servers":[...]}` 不变；端口/域名解析策略不动。
- `history.json` 语义独立，prune 不触碰。

## 7. 复跑与已知项

- 全量：`pytest tests/ -q` → **629 passed / 1 failed**；红 1 = `test_cl005_hardening.py::test_t26`（断言 `CLOCK_MONOTONIC > 1e4`，本机 uptime 不足 1e4 秒 ⇒ **修前既有、与本次无关**）。
- AC harness：`python3 scripts/cl006-verify.py` → **16/16 PASS**。
- 历史 harness 版本断言已放宽（`cl005-verify` / `port-residual-verify` / `port-flag-verify` 接受 1.4.2），保持可复跑。

## 8. 风险与遗留

- `find(prefer_alive=True)` 仅在**同键多条**时多付一次 `is_process_alive`（`os.kill(pid,0)`）探测；单条路径零开销。
- pid 复用（陈旧 pid 被无关进程占用）不由本批处理 —— 归 `start` 的 `_is_our_runner` 归属校验面（CL004）；`status` 侧仅以 `is_process_alive` 判存活，属既有口径。
- 建议后续（非本批）：`hs list` 考虑提供 `--stale` 视图显式列出沉积条，减少「隐藏计数」的信息损失。
