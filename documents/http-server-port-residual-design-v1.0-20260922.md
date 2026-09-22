# HTTP-SERVER-CL004 设计 v1.0 — 端口探测「假占用」根因 + CL003 遗留三项

- 件号：`documents/http-server-port-residual-design-v1.0-20260922.md`
- 编号：HTTP-SERVER-CL004（draft `cache/draft/TODO-20260922.md`，状态 READY，2026-09-22 登记）
- 前置：HTTP-SERVER-CL003（`-p/--port` 端口参数面，1.4.0 未发布）；本批为 CL003 收尾登记的**遗留项合并单一批**
- 基线：`c58f222`（CL003 实现审计 PASS 95/100，已 push；工作树 clean）
- 依据来源：CL003 设计 §10 O1 + CL003 实现审计报告 AUD-1/AUD-2/AUD-3

---

## 1 背景与缺陷（四项，含行号实测）

### P1（O1，🔴 根因）端口探测「假占用」
`utils.py:118-133 is_port_in_use()` 用**裸 socket bind**（无 `SO_REUSEADDR`）逐族探测，任一族 bind 失败即判「占用」。残留连接（`TIME_WAIT` / `FIN_WAIT_2`）会让裸 bind 返回 `EADDRINUSE(48)`，而真实服务用的 `http.server.HTTPServer`（`allow_reuse_address=1`）本可正常绑上 ⇒ **刚被 kill 的端口被判占用**。

实测（CL003 探讨期，对照脚本两态）：
- 裸 bind：`FAIL(48 Address already in use)`
- `SO_REUSEADDR` bind：`OK`
- 现场：`hs ~/CodeSpace/hermes-manager/web -i index.html -d -o` 在 8084 于 15:56:04 被 kill 后 **3 秒**（15:56:07）重启 → 落到 **8085**

影响面：① `hs start` 未给 `-p` 时自动漂移（用户看不到原因）；② CL003 新增的 `-p` 占用校验**可能假拒绝**（设计 CL003 §11 风险行已预警）；③ `registry` 的 `_alive` 判定与 dashboard/mcp 可用性判断同源受影响。

### P2（AUD-1，🟡 P2）顶层 `-i` 值泄漏时走「路径快捷方式」分支
`cli.py:1875-1911` 分支序：➊ bookmark → ➋ 路径快捷方式（`cli.py:1897-1901`）→ ➌ 取值型 flag 重组（`cli.py:1905-1907`，CL003 D8）。

`hs -i <在 CWD 存在的文件> -p <port> <dir>`：argparse 把 `-i` 的值当 `command`，`unknown=['-i']`，`args=['-p','<port>','<dir>']`；➋ 因 `os.path.exists(command)=True` 先命中 ⇒ 重组不执行 ⇒ **`-i` 被丢弃、`<dir>` 被当未识别参数忽略、服务落在 CWD**（端口仍正确，故 CL003 的 A8-2 断言未捕获）。

CL003 设计 D8 显式收窄为「非存在路径/globs」，故**当年不算实现偏差**；本批按用户可用性诉求修正分支顺序。

### P3（AUD-2，🟢）`hs web --port` 校验失败返回 0
`cli.py:1428-1441`（add）与 `cli.py:1702-1715`（update）：互斥与区间校验失败仅 `print/stderr + return` ⇒ **rc=0**（软拒绝），与 CL003 D9e 确立的「用法错误 exit 2」（`hs start -p 99` → 2）口径不一致。

### P4（AUD-3，🟢）stale 判定窗口内「只删登记不 kill 进程」
`server.py:174-235`：`entry` 存在且 `is_process_alive(pid) and is_port_in_use(port)` → 幂等返回；否则视为 stale → `registry.remove(path=...)`（`server.py:235`）后继续启动。

竞态：`hs <path>` 连续两次（间隔 <100ms）时，第一次已 `Popen` 但**尚未 LISTEN**，第二次读到 entry（pid 活、端口未监听）⇒ 判 stale 删登记，而第一个进程继续存在 ⇒ **孤儿进程 + registry 与事实不一致**（审计自测复现 PID 37510）。

---

## 2 目标与非目标

### 2.1 目标
1. 消除探测「假占用」：残留连接端口不再判占用；真实 LISTEN 端口仍判占用（**不得放宽真占用**）。
2. 顶层 `-i`/`-p` 泄漏时重组分支优先 ⇒ `hs -i <CWD文件> -p <port> <dir>` 语义与 `hs <dir> -i <文件> -p <port>` 等价。
3. 退出码口径统一：`hs web add/update` 的用法错误 → exit 2。
4. stale 判定不再制造孤儿：引入「启动中」宽限 + 判 stale 时对存活进程负责。
5. 四同步 + 发布清单（并入未发布的 1.4.0）。
6. 回归：CL003 全部行为与断言不回退（`scripts/port-flag-verify.py` 31/31 复跑为准）。

### 2.2 非目标（明确不做）
- N1 不引入 `SO_REUSEPORT`（会真正允许双绑定，改变「占用」语义）。
- N2 不改 `MAX_PORT=10000`（自动漂移上限）与 `find_available_port` 的逐 1 递增策略。
- N3 不把探测主路径改为 lsof（保持零依赖纯 socket；lsof 仍只用于「占用者 PID/路径」展示）。
- N4 不新增 `--no-tail`、不动 `-d` 前台 tail 语义（CL003 D12 已定案）。
- N5 不改 `eprint()`（实际写 stdout 的既有行为）；本批新文案仍用 `print(..., file=sys.stderr)`。
- N6 不动 `documents/` 历史留档表述（CL003 F-8 豁免口径沿用）。
- N7 不为 web 子命令引入「后台重试/幂等」等新语义，仅对齐退出码。

---

## 3 决策定案（D1–D10）

| # | 决策 | 内容 |
|:--|:-----|:-----|
| **D1** | P1 修法 | `is_port_in_use` 的两个探测 socket 显式 `setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)` 后再 bind（保留 `settimeout(0.5)` 与「任一族失败即占用」判定）；不改探测目标（`('', port)` 全接口） |
| **D2** | P2 修法 | `main()` 分支序调整为 **➊ bookmark → ➋ 取值型 flag 重组 → ➌ 路径快捷方式**；重组的触发条件不变（`unknown` 含 `-p/--port/-i/--index` 之一，`-o/-d/-f` 仍不触发）。语义：flag 在场 ⇒ 用户明确使用参数形态，路径快捷方式让位 |
| **D3** | P3 修法 | `_web_add` / `_web_update` 的两处校验失败（互斥 + `validate_port`）由 `return` 改为 **`sys.exit(2)`**（`json_mode` 时先输出 error 信封再退出，与 `_cmd_start` 的 UsageError 模式一致） |
| **D4** | P4 修法 | stale 判定升级为三态：**① pid 活 + 端口监听 → 幂等**（不变）；**② pid 活 + 端口未监听 → 「启动中」宽限**：轮询 `0.2s × 5`（≤1.0s）内出现监听即转①；仍无监听则按③；**③ pid 死 → stale**：只删登记（无孤儿）；若走到③时 pid 已活（宽限后仍失败/端口被他人占）→ **kill 该进程组**后再删登记，并 stderr 说明 |
| **D5** | 宽限参数 | 轮询 `interval=0.2s`、`attempts=5`（总 ≤1.0s）；常量落 `server.py` 模块级 `START_GRACE_INTERVAL/_ATTEMPTS`，便于测试 monkeypatch |
| **D6** | P4 文案 | stale 分支文案区分：杀进程时 `🔄 Found stale registry entry (pid N, 已终止)…`；仅删登记时沿用原文案；两者均不污染 stdout（`--url` 走 stderr，其余沿用现状） |
| **D7** | 版本口径 | **并入未发布的 1.4.0**（PyPI 尚未发布 1.4.0 ⇒ 不另起 1.4.1）：CHANGELOG `## 1.4.0` 增 `### Fixed` 四条；`__version__`/spec.yaml 版本号保持 1.4.0（`__release_date__` 保持 2026-09-22） |
| **D8** | 四同步范围 | CHANGELOG（Fixed 段）/ features.md（端口检测条目 + 测试数）/ spec.yaml（`port-allocation` 增「残留连接不判占用」场景 + `service-lifecycle` 增 stale 宽限场景）/ README ×2（`-p` 行补「刚释放端口可直接使用」一句） |
| **D9** | 测试落点 | 新增 `tests/test_port_probe.py`：O1 两态（真监听判占用 / 残留连接不判占用）+ D4 三态（幂等 / 宽限转正 / stale 杀进程）+ D2 分支序回归 + D3 退出码；既有 `tests/test_port_flag.py` 不动（CL003 断言基线） |
| **D10** | 核查口径 | 新增 harness `scripts/port-residual-verify.py`（A 段断言表见 §8），并把 **CL003 harness 31/31 复跑**列为 CL004 的回归断言（A7） |

---

## 4 实现设计

### 4.1 `is_port_in_use`（D1）
```python
for family in (socket.AF_INET, socket.AF_INET6):
    try:
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # ← 新增
            s.settimeout(0.5)
            s.bind(('', port))
    except OSError:
        return True
return False
```
- 语义边界：`SO_REUSEADDR` 只放行「本地地址/端口处于 `TIME_WAIT` 等残留态」的绑定；对**另一个进程正在 LISTEN 的同一 addr:port** 仍返回 `EADDRINUSE` ⇒ 真占用判定不变（`tests/test_dashboard.py:82` 的真监听断言即回归证据）。
- 调用方（不变）：`server.start`（占用校验 + 幂等）、`registry._alive`、`dashboard`/`mcp` 可用性、`find_available_port`。

### 4.2 `main()` 分支序（D2）
```
➊ bookmark 命中 → start <path> [-i idx]
➋ unknown 含 -p/--port/-i/--index → args = unknown + [command] + args → start
➌ 路径快捷方式（. / ~ / 存在 / glob）→ args = [command] + args → start
➍ 否则 Unknown command + exit 1
```
- 形态对照（§7 测试覆盖）：`hs -p 8099`（无路径）→ ➋；`hs -i index.html -p 8095 <dir>` → ➋（修复点）；`hs -i index.html`（CWD 存在，无路径）→ ➋（`-i` 生效 + 路径取 CWD）；`hs index.html`（无 flag）→ ➌（快捷方式保留）；`hs -o index.html` → ➌（`-o` 非触发位）。
- 兼容：CL003 D8 的两形态（`hs -p 8099`、`hs -i a.html -p 8099`）行为不变（均命中➋，且顺序保持原样）。

### 4.3 web 校验退出码（D3）
```python
err = ServiceStore.validate_port(parsed.port)
if err:
    if json_mode: json_output(False, cmd, error=err)
    else: print(f'❌ {err}', file=sys.stderr)
    sys.exit(2)          # ← 原为 return（rc=0）
```
- 互斥（`--port` + `--no-port`）同法处理；**成功路径与既有 error 分支**（如 `--no-domain` 冲突、名称非法、store 异常）保持原语义不动（非本批）。
- 影响面：`hs web add/update --json` 的失败信封仍先输出（内容不变），仅退出码 0 → 2。

### 4.4 stale 三态（D4/D5）
```
entry 存在:
  if is_process_alive(pid) and is_port_in_use(port):  → 幂等返回（不变）
  if is_process_alive(pid):                            # ② 「启动中」宽限
      for _ in range(START_GRACE_ATTEMPTS):            # 5 × 0.2s
          if is_port_in_use(port): → 幂等返回（视为已就绪）
          sleep(START_GRACE_INTERVAL)
      # 宽限后仍未监听：pid 仍活 ⇒ 判 stale 且**负责 kill**
      if is_process_alive(pid): killpg(pid)（best-effort，失败仅记 stderr）
  # ③ stale 清理
  registry.remove(path=abs_path)  → 继续启动流程
```
- 反孤儿保证：任何「删登记」路径上若进程仍存活，必须**先终止**该进程（`os.getpgid` + `os.killpg`，异常吞掉并 stderr 提示）。
- 幂等命中路径不引入新等待（①判定在最前，与 CL003 顺序链一致，F-1 语义不回退）。

---

## 5 影响矩阵（基线 `c58f222`）

| 文件 | 行 | 改动 | 风险 |
|:--|:--|:--|:--|
| `src/http_server_cli/utils.py` | 118-133 | `is_port_in_use` 增 `SO_REUSEADDR` | 极低：只放宽残留态；真监听不受影响 |
| `src/http_server_cli/cli.py` | 1897-1911 | main() ➋/➌ 交换（D2） | 中：影响顶层解析；由 §7 形态表 + CL003 A8 回归守护 |
| `src/http_server_cli/cli.py` | 1428-1441 / 1702-1715 | web 校验 exit 2（D3） | 低：仅失败路径退出码 |
| `src/http_server_cli/server.py` | 174-235 | stale 三态 + 宽限 + kill（D4） | 中：启动路径新增 ≤1.0s 等待（仅同路径已登记的重复启动场景） |
| `tests/test_port_probe.py` | 新增 | D1/D2/D3/D4 用例 | — |
| `scripts/port-residual-verify.py` | 新增 | A 段断言 harness | — |
| `CHANGELOG.md` / `features.md` / `http-server.cli.spec.yaml` / `README{,.zh}.md` | — | 四同步（D7/D8） | 低 |

---

## 6 文案与同步清单

| 处 | 改动 |
|:--|:--|
| `CHANGELOG.md` `## 1.4.0` | 新增 `### Fixed`：① 端口探测残留连接「假占用」（start 漂移 / `-p` 假拒绝 / registry `_alive`）② 顶层 `-i <CWD文件>` 值泄漏走路径快捷方式（`-i` 丢失、服务落 CWD）③ `hs web add/update` 校验失败 rc=0 → 2 ④ stale 判定窗口制造孤儿 |
| `features.md` | 「端口检测」行补「残留连接不判占用（SO_REUSEADDR）」；测试数 535 → 新值；服务管理补「stale 宽限」一行 |
| `spec.yaml` | `port-allocation` 增 requirement/scenario（残留连接端口 → 不判占用且可直接启动；真监听 → 仍判占用）；`service-lifecycle` 增 scenario（同路径 100ms 内重复启动 → 不产生孤儿、registry 单条）；`version` 保持 1.4.0 |
| `README{,.zh}.md` | `hs . -p <port>` 行补「刚释放/残留连接的端口可直接指定，不被误判占用」 |
| `documents/http-server-port-residual-design-v1.0-20260922.md` | 本文件 + 收尾回填 §12/§13 |

---

## 7 测试清单（新增 `tests/test_port_probe.py`）

| # | 用例 | 断言 |
|:--|:--|:--|
| T1 | 真实监听端口（`socket.listen()` 且 `SO_REUSEADDR`）→ `is_port_in_use` | True（真占用不放宽） |
| T2 | 残留态端口（绑定→连接→关闭，留 TIME_WAIT）→ `is_port_in_use` | False（修复点；修前 True） |
| T3 | `find_available_port` 对 T2 端口 | 返回该端口本身（不再漂移） |
| T4 | `main()` 形态表（§4.2 五个形态，monkeypatch `_COMMANDS['start']` + `sys.argv`） | ➋/➌ 归属正确；`hs index.html` 仍走快捷方式 |
| T5 | `hs -i <CWD文件> -p <port> <dir>` 重组结果 | args = `['-i', 文件, '-p', port, dir]`（顺序原样） |
| T6 | `_COMMANDS['web'](None, ['add','x','--cmd','true','--port','99'])` | `SystemExit.code == 2`；未创建 |
| T7 | `web update --port 9001 --no-port` | `SystemExit.code == 2` |
| T8 | stale ②：pid 活 + 端口未监听 → 宽限内转正（`is_port_in_use` 第 2 次返回 True） | 幂等返回既有端口，未删登记，未 kill |
| T9 | stale ③：pid 活 + 宽限后仍未监听 → 判 stale | `registry.remove` 被调用 + `killpg` 被调用（monkeypatch 断言 pid） |
| T10 | stale ③（pid 死） | 只删登记，不调用 `killpg` |

（既有 `tests/test_port_flag.py`（CL003，45 用例）不动；全量回归目标 = 535 + 新增）

---

## 8 A 段断言表（可复跑，ops 核查用）

> 规范：命令 + 实测 + 断言；禁止恒真断言。修前反证统一用 `git worktree add <wt> c58f222` + `PYTHONPATH=<wt>/src`。

| # | 命令 | 断言 |
|:--|:-----|:-----|
| A1 | 残留态端口构造（绑定→连接→关闭）后 `python3 -c "from http_server_cli.utils import is_port_in_use; print(is_port_in_use(P))"` | 修后 **False**；修前（worktree）**True** ⇒ 判据非恒真 |
| A2 | 真监听端口（`python3 -m http.server P` 或 socket.listen）同命令 | **True**（真占用不放宽） |
| A3 | 构造残留态端口 P 后 `hs <tmpdir> -p P -d --url` | rc=0 且 URL 端口 = P（不再假拒绝/漂移） |
| A4 | 同目录 100ms 内连续两次 `hs <tmpdir> -d --url` | 第二次幂等（URL 同端口）；`hs list --json` 该路径 **1 条**；`ps` 无同名孤儿进程；修前（worktree）复现 stale 文案 + 孤儿 |
| A5 | `hs -i index.html -p <port> -d --url <dir>`（CWD 下存在同名 index.html） | 服务落在 **`<dir>`**（`hs list --json` path 一致）且 index_page 生效；修前（worktree）落 CWD |
| A6 | `hs web add cl004 --cmd true --port 99; echo $?` / `... --port 9001 --no-port; echo $?` | 均 **2**（修前 0）；且未创建条目 |
| A7 | **CL003 回归**：`python3 scripts/port-flag-verify.py` | **31/31 PASS**（探测改动不破坏 `-p` 面） |
| A8 | `PYTHONPATH=src python3 -m pytest tests/ -q` | 0 failed，通过数 ≥ 535 + 新增 |
| A9 | `hs version` + `grep -n "### Fixed" CHANGELOG.md` + `grep -n "^version:" http-server.cli.spec.yaml` | v1.4.0 一致；Fixed 段存在；spec 1.4.0 |
| A10 | `hs list --json` + `ps`（核查前后） | 真实 registry 无 cl004 残留、无孤儿进程；services.json 无新增残留 |

---

## 9 文档/版本/发布同步清单（D7/D8）

1. `CHANGELOG.md`：`## 1.4.0` 增 `### Fixed`（四条）。
2. `features.md`：端口检测条目 + 测试数 + stale 宽限条目。
3. `http-server.cli.spec.yaml`：`port-allocation` / `service-lifecycle` 补场景；版本保持 1.4.0。
4. `README.md` / `README.zh.md`：`-p` 行补残留端口说明。
5. 版本号（`__version__` / `__release_date__` / spec / CHANGELOG）**保持 1.4.0 / 2026-09-22**（D7）。
6. 发布（Step 7，**待用户放行**）：`bash scripts/release-pypi.sh -p -n` → `python3 -m twine check dist/*` → `-p`；CL003 + CL004 同批发布 1.4.0。
7. 流程面（CL003 D13 口径延续）：本批步 JSON 用 `cache/closed-loop/{YYYYMMDD}-http-server.cli-HTTP-SERVER-CL004-{step}.json`。

---

## 10 观察项与出口判据

| # | 事项 | 处置 |
|:--|:-----|:-----|
| O1 | `eprint()` 名不副实（实写 stdout） | 记录不修（N5；本批新文案已用 stderr） |
| O2 | `find_available_port` 上限 `MAX_PORT=10000` 与 `-p` 上限 65535 口径差异 | CL003 D15 已定案，本批不动（N2） |
| O3 | web 子命令其余 error 分支（名称非法/store 异常）退出码仍为 0 | 记录留档（非本批 N7；如用户要求再单列） |

**出口判据**：A1–A10 全 PASS + CL003 harness 31/31 回归 + 审计 PASS ⇒ 允许 push 与（待放行）发布。

---

## 11 风险与回滚

| 风险 | 缓解 |
|:--|:--|
| `SO_REUSEADDR` 被误认为放宽真占用 | A2 断言 + `test_dashboard.py` 真监听断言；测试 T1 常驻 |
| main() 分支序调整影响既有快捷方式 | T4 形态表 5 例 + CL003 A8 回归（A7）；`-o/-d/-f` 不在触发位 |
| stale 宽限引入启动延迟 | 仅在「同路径已登记且 pid 活但端口未监听」时触发，上限 1.0s；幂等命中路径零等待 |
| kill 误伤 | 仅对 registry 中该路径登记的 pid 且已判定 stale 时执行；`killpg` 异常捕获不阻塞启动 |
| 回滚 | 四项改动各自独立，可逐项 `git revert`（无数据格式变更、无迁移） |

---

## 12 实施与门禁（Step 3–6 摘要）

| 步 | 产物 | 门禁 |
|:--|:-----|:-----|
| Step 3 dev | `fix@cli:`（utils 探测）/ `fix@cli:`（main 分支序 + web 退出码）/ `fix@cli:`（stale 三态）/ `tests@cli:` / `docs@sync:`（四同步） | 本地全量 pytest 零回归（§7 全绿） |
| Step 4 ops 核查 | `scripts/port-residual-verify.py`（A1–A10）+ 报告 `documents/review/http-server-cli-cl004-ops-verify-v1.0-20260922.md` | 全断言 PASS（含 CL003 回归 31/31） |
| Step 5 实现审计 | review 侧报告 + review-log + `.review-level.yaml`；PASS → push | PASS / CONDITIONAL 回修 |
| Step 6 收尾 | 复盘 md + 清单 + 四件套 + 观察项登记 | `hm loop artifacts HTTP-SERVER-CL004` 齐全 |
| Step 7 发布 | `release-pypi.sh` 1.4.0（CL003+CL004 同批） | **待用户放行** |
