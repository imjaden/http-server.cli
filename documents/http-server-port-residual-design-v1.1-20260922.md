# HTTP-SERVER-CL004 设计 v1.1 — 端口探测「假占用」根因 + CL003 遗留三项

- 件号：`documents/http-server-port-residual-design-v1.1-20260922.md`
- 编号：HTTP-SERVER-CL004（draft `cache/draft/TODO-20260922.md`，状态 READY，2026-09-22 登记）
- 前置：HTTP-SERVER-CL003（`-p/--port` 端口参数面，1.4.0 未发布）；本批为 CL003 收尾登记的**遗留项合并单一批**
- 基线：`c58f222`（CL003 实现审计 PASS 95/100，已 push）；设计 v1.0 = `6edb021`
- v1.0 评审：`documents/review/http-server-cli-cl004-design-review-v1.0-20260922.md`（**CONDITIONAL_PASS 90/100**，2 🟡 必改 F-1/F-2 + 7 🟢 记录 R-1~R-7）
- 依据来源：CL003 设计 §10 O1 + CL003 实现审计报告 AUD-1/AUD-2/AUD-3

## 0 v1.1 修订落点表（对 v1.0 评审）

| 项 | 级别 | 评审要求 | v1.1 落点 |
|:--|:--|:--|:--|
| **F-1** | 🟡 必改 | D6「均不污染 stdout（其余沿用现状）」自相矛盾；实测 json/默认走 `eprint`→stdout 污染 JSON 信封（`JSONDecodeError`） | **D6 重写为「stale/宽限/kill 文案三态（url/json/默认）一律 `print(..., file=sys.stderr)`」**，删除「其余沿用现状」；新增 §4.5 通道表；新增 **A11** 断言（`--json` 触发 stale → stdout 首字符 `{` 且 `json.loads` 成功、stderr 含文案）；新增 T11 |
| **F-2** | 🟡 必改 | §8 A4 孤儿检测口径不足（有「registry 0 条可见 + 1 listener」隐形孤儿形态） | **A4 改为 lsof 端口级判据**：`lsof -nP -iTCP:<port> -sTCP:LISTEN` 的 pid 数 == `registry.json` 该 path 条目数（修后 == 1）；修前反证 = listener 数 **>** registry 条目数；删去「`ps` 同名孤儿」模糊判据 |
| R-1 | 🟢 | CHANGELOG 1.4.0 `### Notes` 仍写「假占用…本批不修（O1）」⇒ 与新 `### Fixed` 矛盾 | §6/§9 明确：**同批修订该行**为「（O1）已在 1.4.0 内修复（见 `### Fixed`）」 |
| R-2 | 🟢 | spec.yaml 未覆盖 P2/P3 | §6/§9：`cli-interface` 补两场景（顶层 `-i/-p` 归位；`hs web add/update` 用法错误 exit 2） |
| R-3 | 🟢 | T2 未指定 TIME_WAIT 关闭方向 | §7 T2 注明「**服务端主动 close**（先发 FIN）」；客户端主动 close 只在客户端临时端口留残留 |
| R-4 | 🟢 | §4.4 `killpg(pid)` 伪码与 prose 不一致、未定升级策略 | §4.4 伪码对齐既有 `server.py:641-651` kill 语义（`os.getpgid` → `SIGTERM` → 0.5s → `SIGKILL`），best-effort |
| R-5 | 🟢 | 宽限循环结束后、kill 前应再判一次端口 | §4.4 步骤 ⊙3：kill 前 **re-check `is_port_in_use`**，已就绪则幂等返回（防 TOCTOU 误杀刚就绪的 runner） |
| R-6 | 🟢 | pid 复用可能误杀无关进程组 | §4.4 步骤 ⊙2：kill 前用 `get_process_info(pid)`（`utils.py:205`）校验 `command` 含 `runner.py` 且含该 path；不匹配 ⇒ **不 kill**，只删登记 + stderr 提示 |
| R-7 | 🟢 | 宽限内他人抢端口会被误判「已就绪」 | §4.4 步骤 ⊙1：宽限每次命中 `is_port_in_use` 时用 `get_pid_by_lsof(port)` 核监听者：含登记 pid ⇒ 就绪（幂等）；全为他 pid ⇒ 判「端口被他人占」走 ③（不 kill 他人） |

---

## 1 背景与缺陷（四项，含行号实测 + 评审独立复现）

### P1（O1，🔴 根因）端口探测「假占用」
`utils.py:118-133 is_port_in_use()` 用**裸 socket bind**（无 `SO_REUSEADDR`）逐族探测，任一族 bind 失败即判「占用」。残留连接（`TIME_WAIT` / `FIN_WAIT_2`）让裸 bind 返回 `EADDRINUSE(48)`，而真实服务用的 `http.server.HTTPServer`（`allow_reuse_address=1`）本可绑上 ⇒ **刚被 kill 的端口被判占用**。

实测（本仓独立探针 + 设计评审双证）：
- 残留态端口（服务端主动 close 构造 TIME_WAIT）：裸 bind `FAIL(=48)` / `SO_REUSEADDR` `OK`；仓库当前 `is_port_in_use` → **True（假占用）**
- 真 LISTEN 端口：裸 bind `FAIL(=48)` / `SO_REUSEADDR` **亦 `FAIL(=48)`** ⇒ 修法**不放宽真占用**
- 现场：`hs ~/CodeSpace/hermes-manager/web -i index.html -d -o` 在 8084 于 15:56:04 被 kill 后 **3 秒**重启 → 落到 **8085**

影响面：① `hs start` 自动漂移（无提示）；② CL003 `-p` 占用校验**可能假拒绝**；③ `registry._alive` 与 dashboard/mcp 可用性判断同源受影响（`dashboard.py:460`/`mcp.py:516`）。

### P2（AUD-1，🟡 P2）顶层 `-i` 值泄漏时走「路径快捷方式」分支
`cli.py:1875-1911` 分支序：➊ bookmark → ➋ 路径快捷方式（`cli.py:1897-1901`）→ ➌ 取值型 flag 重组（`cli.py:1905-1907`，CL003 D8）。

`hs -i <在 CWD 存在的文件> -p <port> <dir>`：argparse 把 `-i` 的值当 `command`，`unknown=['-i']`，`args=['-p','<port>','<dir>']`；➋ 因 `os.path.exists(command)=True` 先命中 ⇒ 重组不执行 ⇒ **`-i` 被丢弃、`<dir>` 被当未识别参数忽略、服务落 CWD**（端口仍正确，故 CL003 A8-2 未捕获）。评审实测：「`-i` 值在 CWD 存在」走 ➋；「`-i no-such`」保留 `-i`。

CL003 D8 显式收窄为「非存在路径/globs」，故**当年不算实现偏差**；本批按可用性诉求修正分支顺序。

### P3（AUD-2，🟢）`hs web --port` 校验失败返回 0
`cli.py:1428-1441`（add）与 `cli.py:1702-1715`（update）：互斥与区间校验失败仅 `print/stderr + return` ⇒ **rc=0**（软拒绝），与 CL003 D9e「用法错误 exit 2」（`hs start -p 99` → 2）口径不一致。评审实测两形态均 rc=0。

### P4（AUD-3，🟢）stale 判定窗口内「只删登记不 kill 进程」
`server.py:174-235`：`entry` 存在且 `is_process_alive(pid) and is_port_in_use(port)` → 幂等返回；否则判 stale → `registry.remove(path=...)`（`server.py:235`）后继续启动。

竞态：同目录 <100ms 连续两次 `hs <path>`，第一次已 `Popen` 但**尚未 LISTEN**，第二次读到 entry（pid 活、端口未监听）⇒ 判 stale 删登记，第一个进程继续存在 ⇒ **孤儿 + registry 与事实不一致**（审计复现 PID 37510；评审 5 次尝试 **4 次复现**，含「registry 0 条可见 + 1 listener」**隐形形态**）。

同时发现（F-1 关联）：stale 文案在 json/默认模式经 `eprint` **写 stdout**，`hs <dir> --json` 触发 stale 时 JSON 信封被污染（`json.loads` → `JSONDecodeError`）。

---

## 2 目标与非目标

### 2.1 目标
1. 消除探测「假占用」：残留连接端口不再判占用；真实 LISTEN 端口仍判占用。
2. 顶层 `-i`/`-p` 泄漏时重组分支优先 ⇒ `hs -i <CWD文件> -p <port> <dir>` 与 `hs <dir> -i <文件> -p <port>` 等价。
3. 退出码口径统一：`hs web add/update` 用法错误 → exit 2。
4. stale 判定不再制造孤儿（三态 + 宽限 + 负责终止）且**不误杀**（pid 归属校验）。
5. stale/宽限/kill 文案**三态一律 stderr**，`--json` 信封与 `--url` 输出零污染（F-1）。
6. 四同步 + 发布清单（并入未发布的 1.4.0）。
7. 回归：CL003 行为与断言不回退（`scripts/port-flag-verify.py` 31/31）。

### 2.2 非目标（明确不做）
- N1 不引入 `SO_REUSEPORT`（会真正允许双绑定，改变「占用」语义）。
- N2 不改 `MAX_PORT=10000` 与 `find_available_port` 逐 1 递增策略。
- N3 不把探测主路径改为 lsof（保持零依赖纯 socket；lsof 仅用于占用者/监听者查询）。
- N4 不新增 `--no-tail`、不动 `-d` 前台 tail 语义。
- N5 不改 `eprint()` 的既有行为（仍写 stdout）；本批新文案一律 `print(..., file=sys.stderr)`。
- N6 不动 `documents/` 历史留档表述。
- N7 不为 web 子命令引入新语义，仅对齐退出码（其余 error 分支退出码留档 §10 O3）。
- N8 不引入「启动锁/单实例锁」等结构性改造（本批以宽限 + 归属校验覆盖窗口）。

---

## 3 决策定案（D1–D10）

| # | 决策 | 内容 |
|:--|:-----|:-----|
| **D1** | P1 修法 | `is_port_in_use` 两个探测 socket 先 `setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)` 再 bind（保留 `settimeout(0.5)`、`('', port)` 目标、任一族失败即占用） |
| **D2** | P2 修法 | `main()` 分支序改为 **➊ bookmark → ➋ 取值型 flag 重组 → ➌ 路径快捷方式**；触发条件不变（`unknown` 含 `-p/--port/-i/--index` 之一；`-o/-d/-f` 不触发） |
| **D3** | P3 修法 | `_web_add` / `_web_update` 校验失败（互斥 + `validate_port`）由 `return` 改 **`sys.exit(2)`**（`json_mode` 先输出 error 信封再退出） |
| **D4** | P4 修法 | stale 判定三态 + 宽限 + 负责终止（详见 §4.4；含 R-5 再判、R-6 归属校验、R-7 监听者核验） |
| **D5** | 宽限参数 | `START_GRACE_INTERVAL = 0.2`、`START_GRACE_ATTEMPTS = 5`（总 ≤1.0s），模块级常量便于测试 monkeypatch |
| **D6** | 文案通道（**F-1 重写**） | stale / 宽限 / kill 三类文案在 **url_only / json / 默认三态一律 `print(..., file=sys.stderr)`**；stdout 仅承载 URL / 信息块 / JSON 信封；删除 v1.0「其余沿用现状」表述（该表述是 F-1 根因） |
| **D7** | 版本口径 | 并入未发布的 1.4.0（PyPI 未发布 1.4.0 ⇒ 不另起 1.4.1）：CHANGELOG `## 1.4.0` 增 `### Fixed` 四条，并按 R-1 同步修订 `### Notes` 旧行 |
| **D8** | 四同步范围 | CHANGELOG（Fixed + Notes 修订）/ features.md（端口检测 + 测试数 + stale 宽限）/ spec.yaml（`port-allocation` + `service-lifecycle` + **`cli-interface` 两场景**，R-2）/ README ×2 |
| **D9** | 测试落点 | 新增 `tests/test_port_probe.py`（§7 T1–T12）；既有 `tests/test_port_flag.py` 不动 |
| **D10** | 核查口径 | 新增 harness `scripts/port-residual-verify.py`（A1–A11）；把 CL003 harness 31/31 复跑列为 A7 回归 |

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
- 语义边界：`SO_REUSEADDR` 只放行「本地 addr:port 处于 `TIME_WAIT` 等残留态」的绑定；对**另一进程正在 LISTEN 的同一 addr:port** 仍 `EADDRINUSE` ⇒ 真占用判定不变（A2 + `tests/test_dashboard.py:82` 真监听断言为回归证据）。
- 调用方（不变）：`server.start`（占用校验 + 幂等）、`registry._alive`、`dashboard`/`mcp` 可用性、`find_available_port`。

### 4.2 `main()` 分支序（D2）
```
➊ bookmark 命中 → start <path> [-i idx]
➋ unknown 含 -p/--port/-i/--index → args = unknown + [command] + args → start
➌ 路径快捷方式（. / ~ / 存在 / glob）→ args = [command] + args → start
➍ 否则 Unknown command + exit 1
```
形态对照：`hs -p 8099`（无路径）→ ➋；`hs -i index.html -p 8095 <dir>` → ➋（修复点）；`hs -i index.html`（CWD 存在，无路径）→ ➋（`-i` 生效 + 路径取 CWD）；`hs index.html`（无 flag）→ ➌；`hs -o index.html` → ➌（`-o` 非触发位）；`hs -d -o`（command=None）→ 既有分支不变。

### 4.3 web 校验退出码（D3）
```python
err = ServiceStore.validate_port(parsed.port)
if err:
    if json_mode: json_output(False, cmd, error=err)
    else: print(f'❌ {err}', file=sys.stderr)
    sys.exit(2)          # ← 原为 return（rc=0）
```
互斥（`--port` + `--no-port`）同法；成功路径与其余 error 分支（名称非法、store 异常等）保持原语义（N7）。

### 4.4 stale 三态（D4/D5，含 R-4/R-5/R-6/R-7）
```
entry = registry.find(path=abs_path)
if entry:
    port = entry['port']; pid = entry.get('pid')
    # ① 幂等（不变，零等待，F-1 顺序链不回退）
    if is_process_alive(pid) and is_port_in_use(port): → 幂等返回（既有三态输出）
    # ② 「启动中」宽限（仅当 pid 活）
    if is_process_alive(pid):
        for _ in range(START_GRACE_ATTEMPTS):        # 5 × 0.2s
            if is_port_in_use(port):
                listeners = get_pid_by_lsof(port)     # R-7：核监听者归属
                if (not listeners) or pid in listeners:
                    → 幂等返回（视为已就绪；文案同 ①）
                else:
                    → 判「端口被他人占」→ break 至 ③（**不 kill 他人进程**）
            if not is_process_alive(pid): break       # 宽限内进程已退 → ③
            sleep(START_GRACE_INTERVAL)
        # ⊙3 R-5：kill 前再判一次，防 TOCTOU
        if is_port_in_use(port) and (not listeners or pid in listeners):
            → 幂等返回
        # ⊙2 R-6：归属校验（pid 复用防御）
        info = get_process_info(pid)
        if info and 'runner.py' in info.get('command', '') and abs_path in info.get('command', ''):
            try:                                       # R-4：对齐既有 kill() 语义
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(0.5)
                if is_process_alive(pid):
                    os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass                                   # best-effort，异常不阻塞启动
            stale_msg = f'Found stale registry entry (pid {pid}, 已终止), cleaning up before restart'
        else:
            stale_msg = 'Found stale registry entry, cleaning up before restart（登记 pid 非本工具服务，仅清理登记）'
    else:
        stale_msg = 'Found stale registry entry, cleaning up before restart'
    # ③ 清理（所有路径先/后都不留活跃孤儿）
    print(f'🔄 {stale_msg}', file=sys.stderr)          # D6：三态一律 stderr
    registry.remove(path=abs_path)
    → 继续启动流程
```
- 反孤儿保证：任何「删登记」路径上若进程仍存活且经归属校验确认是本工具服务，**必须先终止**。
- 不误杀保证：归属校验（`runner.py` + path）不通过 ⇒ 只删登记并 stderr 说明（R-6）。
- 幂等命中路径（①）不引入任何新等待，CL003 F-1 顺序链语义不回退。

### 4.5 stale 文案通道表（D6 / F-1）
| 模式 | stdout | stderr |
|:--|:--|:--|
| `--url` | 仅 URL | stale/宽限/kill 文案 |
| `--json` | 仅 JSON 信封（首个字符 `{`） | 同上 |
| 默认 | 信息块（✅ URL/PID/日志） | 同上 |

> 验收：`hs <dir> --json` 触发 stale 时 `json.loads(stdout)` 必须成功（A11）。

---

## 5 影响矩阵（基线 `c58f222`）

| 文件 | 行 | 改动 | 风险 |
|:--|:--|:--|:--|
| `src/http_server_cli/utils.py` | 118-133 | `is_port_in_use` 增 `SO_REUSEADDR`（D1） | 极低（A2 守护） |
| `src/http_server_cli/cli.py` | 1897-1911 | main() ➋/➌ 交换（D2） | 中（§7 T4 五形态 + A7 回归守护） |
| `src/http_server_cli/cli.py` | 1428-1441 / 1702-1715 | web 校验 exit 2（D3） | 低（仅失败路径） |
| `src/http_server_cli/server.py` | 174-235 | stale 三态 + 宽限 + 归属校验 + 通道（D4/D6） | 中（启动路径新增 ≤1.0s 等待，仅同路径已登记场景） |
| `tests/test_port_probe.py` | 新增 | T1–T12 | — |
| `scripts/port-residual-verify.py` | 新增 | A1–A11 harness | — |
| `CHANGELOG.md` / `features.md` / `http-server.cli.spec.yaml` / `README{,.zh}.md` | — | 四同步（D7/D8 + R-1/R-2） | 低 |

---

## 6 文案与同步清单

| 处 | 改动 |
|:--|:--|
| `CHANGELOG.md` `## 1.4.0 › ### Fixed`（新增） | ① 端口探测残留连接「假占用」（start 漂移 / `-p` 假拒绝 / registry `_alive`）② 顶层 `-i <CWD文件>` 值泄漏走路径快捷方式（`-i` 丢失、服务落 CWD）③ `hs web add/update` 校验失败 rc=0 → 2 ④ stale 判定窗口制造孤儿（并修 stale 文案污染 `--json` 信封） |
| `CHANGELOG.md` `### Notes`（**R-1 修订**） | 旧行「端口探测「假占用」…**本批不修**，另批处理（O1）」→「（O1）已在 1.4.0 内修复（见 `### Fixed`）」 |
| `features.md` | 「端口检测」行补「残留连接不判占用（SO_REUSEADDR）」；服务管理补「stale 三态 + 宽限」；测试数 535 → 新值 |
| `spec.yaml` | `port-allocation` 增「残留连接不判占用 + 真监听仍判占用」场景；`service-lifecycle` 增「同路径 100ms 内重复启动 → 无孤儿、registry 单条」场景；**（R-2）`cli-interface` 增两场景**：顶层 `-i/-p` 值泄漏归位、`hs web add/update` 用法错误 exit 2；版本保持 1.4.0 |
| `README{,.zh}.md` | `hs . -p <port>` 行补「刚释放/残留连接的端口可直接指定，不被误判占用」 |
| 本文件 | 收尾回填 §13 实施记录 |

---

## 7 测试清单（新增 `tests/test_port_probe.py`）

| # | 用例 | 断言 |
|:--|:--|:--|
| T1 | 真实监听端口（`listen()` + `SO_REUSEADDR`）→ `is_port_in_use` | True（真占用不放宽） |
| T2 | 残留态端口 → `is_port_in_use`。构造：`listen()` → 客户端 `connect()` → **服务端主动 `close()`（先发 FIN）**（R-3；客户端主动 close 只在客户端临时端口留残留） | False（修复点；修前 True） |
| T3 | `find_available_port` 对 T2 端口 | 返回该端口本身（不漂移） |
| T4 | `main()` 五形态（monkeypatch `_COMMANDS['start']` + `sys.argv`） | ➋/➌ 归属正确；`hs index.html`/`hs -o index.html` 仍走快捷方式 |
| T5 | `hs -i <CWD文件> -p <port> <dir>` 重组 | args = `['-i', 文件, '-p', port, dir]`（顺序原样） |
| T6 | `web add x --cmd true --port 99` | `SystemExit.code == 2`；未创建 |
| T7 | `web update --port 9001 --no-port` | `SystemExit.code == 2` |
| T8 | stale②：pid 活 + 端口未监听 → 宽限内转正（`is_port_in_use` 第 2 次 True，`get_pid_by_lsof` 含该 pid） | 幂等返回既有端口；未删登记；未 kill |
| T9 | stale③：pid 活 + 宽限后仍未监听 + 归属校验通过 | `registry.remove` 与 `os.killpg` 均被调用（monkeypatch 记录 pid/signal） |
| T10 | stale③：pid 死 | 只 `registry.remove`，不调用 `killpg` |
| **T11**（F-1） | `--json` 模式触发 stale（dead entry） | stdout 首个非空字符为 `{` 且 `json.loads` 成功；stderr 含 stale 文案 |
| **T12**（R-6/R-7） | ① pid 活但 `get_process_info` 命令行不含 `runner.py` ⇒ 不 kill；② 宽限内 `get_pid_by_lsof` 全为他 pid ⇒ 判「端口被他人占」，不 kill、删登记 | 两分支各自断言 |

（既有 `tests/test_port_flag.py` 45 用例不动；全量回归目标 = 535 + 新增）

---

## 8 A 段断言表（可复跑，ops 核查用）

> 规范：命令 + 实测 + 断言；禁止恒真断言。修前反证统一 `git worktree add <wt> c58f222` + `PYTHONPATH=<wt>/src`。

| # | 命令 | 断言 |
|:--|:-----|:-----|
| A1 | 残留态端口构造（服务端主动 close）后 `python3 -c "from http_server_cli.utils import is_port_in_use; print(is_port_in_use(P))"` | 修后 **False**；修前（worktree）**True** ⇒ 非恒真 |
| A2 | 真监听端口（`listen()`）同命令 | **True**（真占用不放宽） |
| A3 | 构造残留态端口 P 后 `hs <tmpdir> -p P -d --url` | rc=0 且 URL 端口 = P（不再假拒绝/漂移） |
| **A4**（F-2 改口径） | 同目录 100ms 内连续两次 `hs <tmpdir> -d --url`；随后**逐端口判据**：`lsof -nP -iTCP:<port> -sTCP:LISTEN -F p` 的 pid 数 vs `registry.json` 中该 path 条目数 | 修后：listener 数 **== 1 == registry 条目数**；修前（worktree）反证：listener 数 **> registry 条目数**（评审实测 5 次尝试 4 次复现，含 registry 0 条 + 1 listener 隐形形态） |
| A5 | `hs -i index.html -p <port> -d --url <dir>`（CWD 下同名文件存在） | 服务落 **`<dir>`**（`hs list --json` path 一致）且 index_page 生效；修前反证：落 CWD |
| A6 | `hs web add cl004 --cmd true --port 99; echo $?` / `... --port 9001 --no-port; echo $?` | 均 **2**（修前 0）；且未创建条目 |
| A7 | **CL003 回归**：`python3 scripts/port-flag-verify.py` | **31/31 PASS**，残留 0 |
| A8 | `PYTHONPATH=src python3 -m pytest tests/ -q` | 0 failed，通过数 ≥ 535 + 新增 |
| A9 | `hs version` + `grep -n "### Fixed" CHANGELOG.md` + `grep -n "另批处理" CHANGELOG.md` + `grep -n "^version:" http-server.cli.spec.yaml` | v1.4.0 一致；Fixed 段存在；**Notes 旧「不修」表述 0 命中**（R-1）；spec 1.4.0 |
| A10 | `hs list --json` + `ps`（核查前后） | registry 无 cl004 残留、无孤儿进程；services.json 无新增残留 |
| **A11**（F-1） | `hs <tmpdir> --json`（构造 dead entry 触发 stale） | stdout 首个非空字符 `{`、`json.loads` 成功；stderr 含 stale 文案 |

---

## 9 文档/版本/发布同步清单（D7/D8 + R-1/R-2）

1. `CHANGELOG.md`：`## 1.4.0` 增 `### Fixed`（四条）+ **修订 `### Notes`**（删除「本批不修（O1）」表述，R-1）。
2. `features.md`：端口检测条目 + stale 宽限条目 + 测试数。
3. `http-server.cli.spec.yaml`：`port-allocation` / `service-lifecycle` / `cli-interface`（R-2）补场景；版本保持 1.4.0。
4. `README.md` / `README.zh.md`：`-p` 行补残留端口说明。
5. 版本号保持 `1.4.0` / `__release_date__ = 2026-09-22`（D7）。
6. 发布（Step 7，**待用户放行**）：`bash scripts/release-pypi.sh -p -n` → `python3 -m twine check dist/*` → `-p`（CL003 + CL004 同批 1.4.0）。
7. 流程面：步 JSON 用 `cache/closed-loop/{YYYYMMDD}-http-server.cli-HTTP-SERVER-CL004-{step}.json`（CL003 D13 口径延续）。

---

## 10 观察项与出口判据

| # | 事项 | 处置 |
|:--|:-----|:-----|
| O1 | `eprint()` 名不副实（实写 stdout） | 记录不修（N5；本批新文案已用 stderr） |
| O2 | `MAX_PORT=10000` 与 `-p` 上限 65535 口径差异 | CL003 D15 已定案，本批不动（N2） |
| O3 | web 其余 error 分支（名称非法/store 异常）退出码仍 0 | 记录留档（N7） |
| O4 | `is_process_alive`（signal-0）无法区分 pid 复用 | 本批以 `get_process_info` 归属校验缓解（R-6）；根治需启动锁（N8，另批候选） |

**出口判据**：A1–A11 全 PASS + CL003 harness 31/31 回归 + 审计 PASS ⇒ 允许 push 与（待放行）发布。

---

## 11 风险与回滚

| 风险 | 缓解 |
|:--|:--|
| `SO_REUSEADDR` 被误认为放宽真占用 | A2 + T1 + `test_dashboard.py` 真监听断言 |
| main() 分支序调整影响快捷方式 | T4 五形态 + A7（CL003 A8 回归）；`-o/-d/-f` 不在触发位 |
| stale 宽限引入启动延迟 | 仅「同路径已登记且 pid 活但端口未监听」触发，上限 1.0s；幂等路径零等待 |
| kill 误伤（pid 复用 / 他人进程） | R-6 归属校验（`runner.py` + path）+ R-7 监听者核验；不匹配只删登记 |
| `--json` 通道回归 | A11 + T11 |
| 回滚 | 四项改动独立，可逐 commit `git revert`；无数据格式变更、无迁移 |

---

## 12 实施与门禁（Step 3–6 摘要）

| 步 | 产物 | 门禁 |
|:--|:-----|:-----|
| Step 3 dev | `fix@cli:`（D1 探测）/ `fix@cli:`（D2 分支序 + D3 退出码）/ `fix@cli:`（D4+D6 stale 三态与通道）/ `tests@cli:` / `docs@sync:`（四同步 + R-1/R-2） | 全量 pytest 零回归（§7 全绿） |
| Step 4 ops 核查 | `scripts/port-residual-verify.py`（A1–A11）+ 报告 `documents/review/http-server-cli-cl004-ops-verify-v1.0-20260922.md` | 全断言 PASS（含 CL003 回归 31/31） |
| Step 5 实现审计 | review 侧报告 + review-log + `.review-level.yaml`；PASS → push | PASS / CONDITIONAL 回修 |
| Step 6 收尾 | 复盘 md + 清单 + 四件套 + 观察项登记（含 O4） | `hm loop artifacts HTTP-SERVER-CL004` 齐全 |
| Step 7 发布 | `release-pypi.sh` 1.4.0（CL003+CL004 同批） | **待用户放行** |
