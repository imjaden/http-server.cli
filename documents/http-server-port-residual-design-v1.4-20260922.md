# HTTP-SERVER-CL004 设计 v1.4 — 端口探测「假占用」根因 + CL003 遗留三项

- 件号：`documents/http-server-port-residual-design-v1.4-20260922.md`
- 编号：HTTP-SERVER-CL004（draft `cache/draft/TODO-20260922.md`，状态 READY，2026-09-22 登记）
- 前置：HTTP-SERVER-CL003（`-p/--port` 端口参数面，1.4.0 未发布）；本批为 CL003 收尾登记的**遗留项合并单一批**
- 基线：`c58f222`（CL003 实现审计 PASS 95/100，已 push）
- 评审链：v1.0 `6edb021` → **CONDITIONAL 90/100**（F-1/F-2 + R-1~R-7）→ v1.1 `3b0d37a` → **CONDITIONAL 93/100**（F-1 闭合、R-1~R-7 落实；F-2 残留三子点 + R-8/R-9）→ v1.2 `6017695` → **CONDITIONAL 95/100**（F-2(a)(b)(c) + R-8/R-9 全闭合；必改 F-3 + 3 🟢）→ v1.3 `c7e2afb` → **CONDITIONAL 96/100**（F-3 闭合 + 待确认 2/3 得当；必改 **F-4** 单点 + R-10/R-11/R-12）→ **v1.4（本版）**
- 依据来源：CL003 设计 §10 O1 + CL003 审计 AUD-1/AUD-2/AUD-3

## 0 v1.4 修订落点表

### 0.4 第四轮（v1.3 → v1.4，对 rereview round-3）

| 项 | 级别 | 评审要求 | v1.4 落点 |
|:--|:--|:--|:--|
| **F-4** | 🟡 必改（唯一，单点收口） | §4.4 ⊙2 **生产 kill 门**仍用 `in` 子串匹配（`'runner.py' in command and abs_path in command`），与 §8 头注「禁用 `in` 子串判断」自相矛盾 ⇒ 嵌套路径下 `abs_path in command` 恒 True，理论上可误杀另一目录 runner（`/tmp/foobar` 被当成 `/tmp/foo`） | §4.4 ⊙2 伪码改为**与 §8 同口径的 token 精确匹配**：`parts = command.split()`；`is_ours = bool(info) and any(os.path.basename(t) == 'runner.py' for t in parts) and abs_path in parts`（`abs_path in parts` 为列表成员判定 = 完全相等，非子串）；并注明「归属校验与 §8 归属规则同口径」 |
| R-10 | 🟢 | 反证样本判据「同端口同 pid」略强（修前 bug 签名为「漂移新端口」，比对 `--url` 端口即可） | §8 A4 反证样本口径简化为**以端口判定**：两次调用输出端口相同 ⇒ 幂等命中样本（剔除）；端口不同 ⇒ 有效反证样本 |
| R-11 | 🟢 | 就绪等待「单数 LISTEN」时序：双 runner 下 PID1 先 LISTEN 即采集，展示不干净 | §8 A4 就绪等待改为**等 pid 集合稳定**（连续两次采样 0.2s 间隔 `O` 集合一致）后再采集 |
| R-12 | 🟢 | §0.3 F-3 行落点遗漏 A5 | §0.3 F-3 落点补「A5 亦用 `$TD`」 |

### 0.3 第三轮（v1.2 → v1.3，对 rereview round-2）

| 项 | 级别 | 评审要求 | v1.3 落点 |
|:--|:--|:--|:--|
| **F-3** | 🟡 必改（唯一） | §8 的 `<tmpdir>` 未声明「解析后 abs_path」口径：实测 `mkdtemp()` 返回 `/var/folders/…` 而 `realpath` 为 `/private/var/folders/…`（`/var`、`/tmp` 均为符号链接）；`server.py:128 resolve_path()` + `registry.add` + runner 命令行（`server.py:291-292`）全用解析路径 ⇒ `path == <tmpdir>`（原始）**恒 False**（A4 假失败）、A11 注入**永不命中** stale | §8 头注新增**口径声明（F-3）**：`<tmpdir>` 一律指 **`resolve_path(<tmpdir>)`**（`Path.resolve()`），**不得**用 `mkdtemp()`/`mktemp -d` 的原始字符串；命令模板同步改写为 `TD=$(python3 -c "from pathlib import Path;print(Path('<raw>').resolve())")`——**A4 / A5 / A11 三处均用 `$TD`**（R-12 补） |
| 待确认 1 | 🟢 | 归属规则子串匹配过度包含（`/tmp/foo` vs `/tmp/foobar`） | §8 归属规则改为**按空白切分后的 token 精确匹配**（某 token 的 basename == `runner.py`；某 token 与 `abs_path` **完全相等**），禁用 `in` 子串判断 |
| 待确认 2 | 🟢 | 修前反证概率（5 次 4 次复现） | §8 A4 增「反证样本口径」：每次尝试先确认是否为**幂等命中**（同端口/同 pid）；要求 **≥3 次有效反证样本**，若某次未复现则记为「非反证样本」不计入 |
| 待确认 3 | 🟢 | A4 采集前需等 runner 达 LISTEN | §8 A4 增**就绪等待**：采集前轮询（≤2.0s，0.2s × 10）直到该路径 runner 出现 LISTEN，超时则记录「采集未就绪」并标记该次样本无效 |

### 0.2 第二轮（v1.1 → v1.2，已闭合，保留留档）

| 项 | 级别 | 评审要求 | v1.2 落点 |
|:--|:--|:--|:--|
| **F-2(a)** | 🟡 必改 | A4 未显式给 registry 原始文件路径、未明示「不得用 `hs list --json`」（其按 `_alive` 过滤死 pid 条目，`cli.py:318-321`）；且 A10 自身仍用 `hs list --json`，不自洽 | §8 A4 写明 `~/.http-server.cli/registry.json`（`utils.py:23`）为**唯一数据源**并显式禁止 `hs list --json`；**A10 同步改用原始 registry.json 读文件**（+ lsof 孤儿比对） |
| **F-2(b)** | 🟡 必改 | 「逐端口」范围歧义：可见孤儿 listener 会落在**另一端口**（v1.0 评审实测 8084 + 8086）⇒ 只 lsof 登记端口会漏 | §8 A4 改为**全量枚举**：`lsof -nP -iTCP -sTCP:LISTEN -F p` 取全部 LISTEN pid，再与 registry **全量条目 pid 集合**交叉比对（不限登记端口） |
| **F-2(c)** | 🟡 必改 | 计数相等 `1 == 1` 无法区分「1 健康 entry + 1 listener」与「1 dead-pid entry + 1 orphan listener」 | §8 A4 判据升级为 **pid 同一性**：`set(我方 runner listener pid) == set(registry 该 path 条目 pid)`（不仅计数），并定义归属规则（命令行含 `runner.py` 且含该 tmpdir） |
| R-8 | 🟢 | A11「构造 dead entry」手法未写明，不可复跑 | §8 A11 写明 recipe（手工向 `~/.http-server.cli/registry.json` 注入 `{port: 空闲端口, path: <tmpdir>, pid: 999999}` 后跑 `hs <tmpdir> --json`） |
| R-9 | 🟢 | R-7 用 `get_pid_by_lsof`（无 `-sTCP:LISTEN`）与 A4 的 LISTEN 口径不一致 | §4.4 R-7 与 §8 A4 统一为 **`get_pid_by_lsof(port, listen_only=True)`**：`utils.get_pid_by_lsof` 增可选参数 `listen_only=False`（默认行为不变，lsof 追加 `-sTCP:LISTEN`） |

### 0.2 第一轮（v1.0 → v1.1，已闭合，保留留档）

| 项 | 级别 | 评审要求 | v1.1 落点 | 状态 |
|:--|:--|:--|:--|:--|
| F-1 | 🟡 | D6「其余沿用现状」自相矛盾；json/默认 stale 文案经 `eprint`→stdout 污染 JSON 信封（`JSONDecodeError`） | D6 重写为三态一律 stderr + §4.5 通道表 + A11/T11 | ✅ 复审判定**闭合** |
| F-2 | 🟡 | A4 孤儿判据口径不足 | A4 改 lsof LISTEN 判据（删 `ps` 同名） | 🟡 部分闭合 → 本版 (a)(b)(c) 补强 |
| R-1 | 🟢 | CHANGELOG `### Notes` 旧「假占用本批不修」矛盾 | §6/§9 + A9（grep「另批处理」0 命中） | ✅ 落实 |
| R-2 | 🟢 | spec.yaml 未覆盖 P2/P3 | §6/§9 `cli-interface` 两场景 | ✅ 落实 |
| R-3 | 🟢 | T2 未指定 TIME_WAIT 关闭方向 | §7 T2 服务端主动 close | ✅ 落实 |
| R-4 | 🟢 | killpg 升级未定 | §4.4 ⊙2 对齐 `server.py:645-651` | ✅ 落实 |
| R-5 | 🟢 | 宽限后 kill 前应再判端口 | §4.4 ⊙3 | ✅ 落实 |
| R-6 | 🟢 | pid 复用误杀 | §4.4 ⊙2 归属校验 | ✅ 落实 |
| R-7 | 🟢 | 宽限内他人抢端口 | §4.4 ⊙1 监听者核验 | ✅ 落实（口径由 R-9 统一） |

---

## 1 背景与缺陷（四项，含行号实测 + 两轮评审独立复现）

### P1（O1，🔴 根因）端口探测「假占用」
`utils.py:118-133 is_port_in_use()` 用**裸 socket bind**（无 `SO_REUSEADDR`）逐族探测，任一族 bind 失败即判「占用」。残留连接（`TIME_WAIT` / `FIN_WAIT_2`）让裸 bind 返回 `EADDRINUSE(48)`，而真实服务用的 `http.server.HTTPServer`（`allow_reuse_address=1`）本可绑上 ⇒ **刚被 kill 的端口被判占用**。

实测（本仓独立探针 + 评审双证）：
- 残留态端口（服务端主动 close 构造 TIME_WAIT）：裸 bind `FAIL(=48)` / `SO_REUSEADDR` `OK`；仓库当前 `is_port_in_use` → **True（假占用）**
- 真 LISTEN 端口：裸 bind `FAIL(=48)` / `SO_REUSEADDR` **亦 `FAIL(=48)`** ⇒ 修法**不放宽真占用**
- 现场：`hs ~/CodeSpace/hermes-manager/web -i index.html -d -o` 在 8084 于 15:56:04 被 kill 后 **3 秒**重启 → 落到 **8085**

影响面：① `hs start` 自动漂移（无提示）；② CL003 `-p` 占用校验**可能假拒绝**；③ `registry._alive`（`registry.py:98-107`）与 dashboard/mcp 可用性同源受影响（`dashboard.py:460`/`mcp.py:516`）。

### P2（AUD-1，🟡 P2）顶层 `-i` 值泄漏时走「路径快捷方式」分支
`cli.py:1875-1911` 分支序：➊ bookmark → ➋ 路径快捷方式（`cli.py:1897-1901`）→ ➌ 取值型 flag 重组（`cli.py:1905-1907`，CL003 D8）。

`hs -i <在 CWD 存在的文件> -p <port> <dir>`：argparse 把 `-i` 的值当 `command`，`unknown=['-i']`，`args=['-p','<port>','<dir>']`；➋ 因 `os.path.exists(command)=True` 先命中 ⇒ 重组不执行 ⇒ **`-i` 被丢弃、`<dir>` 当未识别参数忽略、服务落 CWD**（端口仍正确，故 CL003 A8-2 未捕获）。评审实测：「`-i` 值在 CWD 存在」走 ➋；「`-i no-such`」保留 `-i`。

CL003 D8 显式收窄为「非存在路径/globs」，故**当年不算实现偏差**；本批按可用性诉求修正分支顺序。

### P3（AUD-2，🟢）`hs web --port` 校验失败返回 0
`cli.py:1428-1441`（add）/ `cli.py:1702-1715`（update）：互斥与区间校验失败仅 `print/stderr + return` ⇒ **rc=0**（软拒绝），与 CL003 D9e「用法错误 exit 2」口径不一致。评审实测两形态均 rc=0。

### P4（AUD-3，🟢）stale 判定窗口内「只删登记不 kill 进程」
`server.py:174-235`：entry 存在且 `is_process_alive(pid) and is_port_in_use(port)` → 幂等返回；否则判 stale → `registry.remove(path=...)`（`server.py:235`）后继续启动。

竞态：同目录 <100ms 连续两次 `hs <path>`，第一次已 `Popen`（`server.py:291-292`）但**尚未 LISTEN**，第二次读到 entry（pid 活、端口未监听）⇒ 判 stale 删登记，第一个进程继续存在 ⇒ **孤儿 + registry 与事实不一致**（审计复现 PID 37510；v1.0 评审 5 次尝试 **4 次复现**，含「registry 0 条可见 + 1 listener」隐形形态；**可见形态孤儿落在另一端口**，如登记 8086 而孤儿在 8084）。

同时发现（F-1 关联，已闭合）：stale 文案在 json/默认模式经 `eprint`（`utils.py:33-38`，无 `file=sys.stderr`）**写 stdout**，`hs <dir> --json` 触发 stale 时 JSON 信封被污染（`JSONDecodeError`）。

---

## 2 目标与非目标

### 2.1 目标
1. 消除探测「假占用」：残留连接端口不再判占用；真实 LISTEN 端口仍判占用。
2. 顶层 `-i`/`-p` 泄漏时重组分支优先 ⇒ `hs -i <CWD文件> -p <port> <dir>` 与 `hs <dir> -i <文件> -p <port>` 等价。
3. 退出码口径统一：`hs web add/update` 用法错误 → exit 2。
4. stale 判定不再制造孤儿（三态 + 宽限 + 负责终止）且**不误杀**（pid 归属校验）。
5. stale/宽限/kill 文案**三态一律 stderr**，`--json` 信封与 `--url` 输出零污染。
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
- N9 `get_pid_by_lsof` 仅**新增可选参数**（默认行为不变），不改既有调用点语义。

---

## 3 决策定案（D1–D11）

| # | 决策 | 内容 |
|:--|:-----|:-----|
| **D1** | P1 修法 | `is_port_in_use` 两个探测 socket 先 `setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)` 再 bind（保留 `settimeout(0.5)`、`('', port)` 目标、任一族失败即占用） |
| **D2** | P2 修法 | `main()` 分支序改为 **➊ bookmark → ➋ 取值型 flag 重组 → ➌ 路径快捷方式**；触发条件不变（`unknown` 含 `-p/--port/-i/--index` 之一；`-o/-d/-f` 不触发） |
| **D3** | P3 修法 | `_web_add` / `_web_update` 校验失败（互斥 + `validate_port`）由 `return` 改 **`sys.exit(2)`**（`json_mode` 先输出 error 信封再退出） |
| **D4** | P4 修法 | stale 判定三态 + 宽限 + 负责终止（详见 §4.4） |
| **D5** | 宽限参数 | `START_GRACE_INTERVAL = 0.2`、`START_GRACE_ATTEMPTS = 5`（总 ≤1.0s），模块级常量便于测试 monkeypatch |
| **D6** | 文案通道（F-1 重写） | stale / 宽限 / kill 三类文案在 **url_only / json / 默认三态一律 `print(..., file=sys.stderr)`**；stdout 仅承载 URL / 信息块 / JSON 信封；不沿用 `eprint` |
| **D7** | 版本口径 | 并入未发布的 1.4.0：CHANGELOG `## 1.4.0` 增 `### Fixed` 四条 + 按 R-1 修订 `### Notes` 旧行 |
| **D8** | 四同步范围 | CHANGELOG（Fixed + Notes 修订）/ features.md / spec.yaml（`port-allocation` + `service-lifecycle` + `cli-interface` 两场景）/ README ×2 |
| **D9** | 测试落点 | 新增 `tests/test_port_probe.py`（§7 T1–T13）；既有 `tests/test_port_flag.py` 不动 |
| **D10** | 核查口径 | 新增 harness `scripts/port-residual-verify.py`（A1–A11，A4 用**全量 LISTEN pid 同一性**判据）；CL003 harness 31/31 复跑列为 A7 |
| **D11** | lsof 口径统一（R-9） | `utils.get_pid_by_lsof(port, listen_only=False)` 新增可选参数（`listen_only=True` 时 lsof 追加 `-sTCP:LISTEN`）；R-7 核验与 A4 判据均用 `listen_only=True`；既有调用点不传参 ⇒ 行为不变 |

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
- 语义边界：`SO_REUSEADDR` 只放行「本地 addr:port 处于 `TIME_WAIT` 等残留态」的绑定；对**另一进程正在 LISTEN 的同一 addr:port** 仍 `EADDRINUSE` ⇒ 真占用判定不变（A2 + `tests/test_dashboard.py:82` 为回归证据）。
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
互斥（`--port` + `--no-port`）同法；成功路径与其余 error 分支保持原语义（N7）。

### 4.4 stale 三态（D4/D5 + R-4~R-7 + R-9）
```
entry = registry.find(path=abs_path)
if entry:
    port = entry['port']; pid = entry.get('pid')
    # ① 幂等（不变，零等待，CL003 F-1 顺序链不回退）
    if is_process_alive(pid) and is_port_in_use(port): → 幂等返回（既有三态输出）
    # ② 「启动中」宽限（仅当 pid 活）
    if is_process_alive(pid):
        for _ in range(START_GRACE_ATTEMPTS):        # 5 × 0.2s
            if is_port_in_use(port):
                listeners = get_pid_by_lsof(port, listen_only=True)      # R-9 口径统一
                if (not listeners) or pid in listeners:
                    → 幂等返回（视为已就绪；文案同 ①）
                else:
                    → 判「端口被他人占」→ break 至 ③（**不 kill 他人进程**）
            if not is_process_alive(pid): break       # 宽限内进程已退 → ③
            sleep(START_GRACE_INTERVAL)
        # ⊙3 R-5：kill 前再判一次（防 TOCTOU 误杀刚就绪的慢绑定 runner）
        if is_port_in_use(port) and (not listeners or pid in listeners):
            → 幂等返回
        # ⊙2 R-6：归属校验（pid 复用防御）
        info = get_process_info(pid)                  # utils.py:205 → {'user','command'}
        parts = (info or {}).get('command', '').split()   # F-4：与 §8 同口径 token 精确匹配（禁 in 子串）
        is_ours = bool(info) and any(os.path.basename(t) == 'runner.py' for t in parts) \
                  and abs_path in parts
        if is_ours:
            try:                                       # R-4：对齐 server.py:645-651
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
    # ③ 清理（所有路径都不留活跃孤儿）
    print(f'🔄 {stale_msg}', file=sys.stderr)          # D6：三态一律 stderr
    registry.remove(path=abs_path)
    → 继续启动流程
```
- 反孤儿保证：任何删登记路径上若进程仍存活且归属校验通过，**必须先终止**。
- 不误杀保证：归属校验不通过 ⇒ 只删登记 + stderr 说明（R-6）。
- 幂等命中（①）零等待，CL003 F-1 顺序链语义不回退。
- `utils.get_pid_by_lsof(port, listen_only=False)`（D11）：`listen_only=True` 时 lsof 命令追加 `-sTCP:LISTEN`；默认 False ⇒ 既有调用点行为不变（N9）。

### 4.5 stale 文案通道表（D6 / F-1）
| 模式 | stdout | stderr |
|:--|:--|:--|
| `--url` | 仅 URL | stale/宽限/kill 文案 |
| `--json` | 仅 JSON 信封（首个非空字符 `{`） | 同上 |
| 默认 | 信息块（✅ URL/PID/日志） | 同上 |

> 验收：`hs <dir> --json` 触发 stale 时 `json.loads(stdout)` 必须成功（A11）。

---

## 5 影响矩阵（基线 `c58f222`）

| 文件 | 行 | 改动 | 风险 |
|:--|:--|:--|:--|
| `src/http_server_cli/utils.py` | 118-133 | `is_port_in_use` 增 `SO_REUSEADDR`（D1） | 极低（A2 守护） |
| `src/http_server_cli/utils.py` | 172-191 | `get_pid_by_lsof(port, listen_only=False)` 新增可选参数（D11） | 低（默认不变，N9） |
| `src/http_server_cli/cli.py` | 1897-1911 | main() ➋/➌ 交换（D2） | 中（T4 五形态 + A7 回归守护） |
| `src/http_server_cli/cli.py` | 1428-1441 / 1702-1715 | web 校验 exit 2（D3） | 低（仅失败路径） |
| `src/http_server_cli/server.py` | 174-235 | stale 三态 + 宽限 + 归属校验 + 通道（D4/D6） | 中（启动路径新增 ≤1.0s 等待，仅同路径已登记场景） |
| `tests/test_port_probe.py` | 新增 | T1–T13 | — |
| `scripts/port-residual-verify.py` | 新增 | A1–A11 harness | — |
| `CHANGELOG.md` / `features.md` / `http-server.cli.spec.yaml` / `README{,.zh}.md` | — | 四同步（D7/D8 + R-1/R-2） | 低 |

---

## 6 文案与同步清单

| 处 | 改动 |
|:--|:--|
| `CHANGELOG.md` `## 1.4.0 › ### Fixed`（新增） | ① 端口探测残留连接「假占用」（start 漂移 / `-p` 假拒绝 / registry `_alive`）② 顶层 `-i <CWD文件>` 值泄漏走路径快捷方式（`-i` 丢失、服务落 CWD）③ `hs web add/update` 校验失败 rc=0 → 2 ④ stale 判定窗口制造孤儿（并修 stale 文案污染 `--json` 信封） |
| `CHANGELOG.md` `### Notes`（**R-1 修订**） | 旧行「端口探测「假占用」…**本批不修**，另批处理（O1）」（现 `CHANGELOG.md:26`）→「（O1）已在 1.4.0 内修复（见 `### Fixed`）」 |
| `features.md` | 「端口检测」行补「残留连接不判占用（SO_REUSEADDR）」；服务管理补「stale 三态 + 宽限」；测试数 535 → 新值 |
| `spec.yaml` | `port-allocation` 增「残留连接不判占用 + 真监听仍判占用」；`service-lifecycle` 增「同路径 100ms 内重复启动 → 无孤儿、registry 单条」；**`cli-interface` 增两场景**（顶层 `-i/-p` 值泄漏归位；`hs web add/update` 用法错误 exit 2，R-2）；版本保持 1.4.0 |
| `README{,.zh}.md` | `hs . -p <port>` 行补「刚释放/残留连接的端口可直接指定，不被误判占用」 |
| 本文件 | 收尾回填 §13 实施记录 |

---

## 7 测试清单（新增 `tests/test_port_probe.py`）

| # | 用例 | 断言 |
|:--|:--|:--|
| T1 | 真实监听端口（`listen()` + `SO_REUSEADDR`）→ `is_port_in_use` | True（真占用不放宽） |
| T2 | 残留态端口 → `is_port_in_use`。构造：`listen()` → 客户端 `connect()` → **服务端主动 `close()`（先发 FIN）**（R-3） | False（修复点；修前 True） |
| T3 | `find_available_port` 对 T2 端口 | 返回该端口本身（不漂移） |
| T4 | `main()` 五形态（monkeypatch `_COMMANDS['start']` + `sys.argv`） | ➋/➌ 归属正确；`hs index.html` / `hs -o index.html` 仍走快捷方式 |
| T5 | `hs -i <CWD文件> -p <port> <dir>` 重组 | args = `['-i', 文件, '-p', port, dir]`（顺序原样） |
| T6 | `web add x --cmd true --port 99` | `SystemExit.code == 2`；未创建 |
| T7 | `web update --port 9001 --no-port` | `SystemExit.code == 2` |
| T8 | stale②：pid 活 + 端口未监听 → 宽限内转正（`is_port_in_use` 第 2 次 True，`get_pid_by_lsof(listen_only=True)` 含该 pid） | 幂等返回既有端口；未删登记；未 kill |
| T9 | stale③：pid 活 + 宽限后仍未监听 + 归属校验通过 | `registry.remove` 与 `os.killpg` 均被调用（monkeypatch 记录 pid/signal） |
| T10 | stale③：pid 死 | 只 `registry.remove`，不调用 `killpg` |
| T11 | `--json` 模式触发 stale（recipe：向 registry.json 注入 `pid=999999` 死条目） | stdout 首个非空字符为 `{` 且 `json.loads` 成功；stderr 含 stale 文案 |
| T12 | ① `get_process_info` 命令行不含 `runner.py` ⇒ 不 kill；② 宽限内 `get_pid_by_lsof(listen_only=True)` 全为他 pid ⇒ 判「端口被他人占」，不 kill、删登记 | 两分支各自断言 |
| **T13**（R-9/D11） | `get_pid_by_lsof(port)` 默认与 `listen_only=True` 在「仅 ESTABLISHED（无 LISTEN）」端口上的返回差异 | 默认可能非空、`listen_only=True` 为空；既有调用点行为不变 |

（既有 `tests/test_port_flag.py` 45 用例不动；全量回归目标 = 535 + 新增）

---

## 8 A 段断言表（可复跑，ops 核查用）

> 规范：命令 + 实测 + 断言；禁止恒真断言。
> **路径口径（F-3，强制）**：下文所有 `<tmpdir>` 一律指 **`resolve_path(<tmpdir>)`**（`Path.resolve()`，即 macOS 上 `/var/folders/…` → `/private/var/folders/…`），**不得**使用 `mkdtemp()` / `mktemp -d` 的原始字符串——`server.py:128 resolve_path()` 与 `registry.add`、runner 命令行（`server.py:291-292`）全用解析路径，原始字符串匹配恒 False。命令模板：`TD=$(python3 -c "from pathlib import Path;print(Path('<raw>').resolve())")`。
> **registry 原始文件**：`~/.http-server.cli/registry.json`（`utils.py:23 REGISTRY_PATH`）——A4/A10 **必须读该文件**，**不得用 `hs list --json`**（`cli.py:318-321` 按 `_alive` 过滤掉死 pid 条目，会掩盖隐形孤儿，F-2(a)）。
> **我方 runner 归属规则（显式定义，token 精确匹配）**：取某 pid 的 `ps -o args=` 命令行，**按空白切分**；当且仅当「存在 token，其 `basename` == `runner.py`」**且**「存在 token 与 `abs_path` **完全相等**」时，计为该目录的服务进程。**禁用 `in` 子串判断**（避免 `/tmp/foo` 误含 `/tmp/foobar`，待确认 1）。

| # | 命令 | 断言 |
|:--|:-----|:-----|
| A1 | 残留态端口构造（服务端主动 close）后 `python3 -c "from http_server_cli.utils import is_port_in_use; print(is_port_in_use(P))"` | 修后 **False**；修前（worktree `c58f222`）**True** ⇒ 非恒真 |
| A2 | 真监听端口（`listen()`）同命令 | **True**（真占用不放宽） |
| A3 | 残留态端口 P 构造后 `hs <tmpdir> -p P -d --url` | rc=0 且 URL 端口 = P（不再假拒绝/漂移） |
| **A4**（F-2 三轮口径 + 待确认 2/3 + R-10/R-11） | ① `TD=$(resolve_path(<raw>))`（F-3 口径）；② 同目录 100ms 内连续两次 `hs "$TD" -d --url`；③ **就绪等待（R-11）**：轮询 ≤2.0s（0.2s × 10），以「连续两次采样（间隔 0.2s）的 `O` 集合一致」为稳定判据，超时记「采集未就绪」⇒ 该次样本无效；④ 采集：`L = lsof -nP -iTCP -sTCP:LISTEN -F p` 的**全部 LISTEN pid**，按 **token 精确匹配**归属规则过滤出 `O`；`R = json.load(~/.http-server.cli/registry.json)` 中 `path == "$TD"` 的条目、`R_pids = {e['pid'] for e in R}` | 修后：`len(R) == 1` **且** `O == R_pids == {该条目 pid}`（**同一性**，非计数）；修前（worktree）反证：`O != R_pids`（可见形态：孤儿在**另一端口**，`O ⊋ R_pids`；隐形形态：`R_pids == ∅` 而 `O ≠ ∅`）。**反证样本口径（R-10）**：同法重复 5 次，**以端口判定幂等命中**——两次调用输出端口相同 ⇒ 幂等命中样本（剔除），端口不同 ⇒ 有效反证样本；要求 **≥3 次有效反证样本**，不足则如实记录未复现 |
| A5 | `hs -i index.html -p <port> -d --url "$TD"`（CWD 下同名文件存在；`TD` 同上 F-3 口径） | 服务落 **`$TD`**（读 registry.json 该 path 条目核对）且 index_page 生效；修前反证：落 CWD |
| A6 | `hs web add cl004 --cmd true --port 99; echo $?` / `... --port 9001 --no-port; echo $?` | 均 **2**（修前 0）；且未创建条目 |
| A7 | **CL003 回归**：`python3 scripts/port-flag-verify.py` | **31/31 PASS**，残留 0 |
| A8 | `PYTHONPATH=src python3 -m pytest tests/ -q` | 0 failed，通过数 ≥ 535 + 新增 |
| A9 | `hs version`；`grep -n "### Fixed" CHANGELOG.md`；`grep -n "另批处理" CHANGELOG.md`；`grep -n "^version:" http-server.cli.spec.yaml` | v1.4.0 一致；Fixed 段存在；Notes 旧「不修」表述 **0 命中**；spec 1.4.0 |
| **A10**（F-2(a) 改口径） | 核查前后各采一次：`json.load(~/.http-server.cli/registry.json)`（**原始文件，非 `hs list --json`**）+ 按归属规则的全量 LISTEN pid 集合 + `lsof -nP -iTCP -sTCP:LISTEN` | 无 cl004 残留条目、`O == R_pids`（无孤儿 listener 无主）、真实服务目录条目数与核查前一致 |
| **A11**（F-1 + R-8 recipe） | ① 备份 registry.json；② 手工注入死条目 `{"port": <空闲端口如 8093>, "path": "$TD", "pid": 999999, "started_at": "..."}`（`$TD` 按 F-3 口径 = `resolve_path(<raw>)`，`started_at` 非必需，`registry.py:26-40` 加载逻辑已核）；③ `hs "$TD" --json`；④ 还原备份 | stdout 首个非空字符 `{` 且 `json.loads` 成功；stderr 含 `Found stale registry entry`；退出码 0 |

---

## 9 文档/版本/发布同步清单（D7/D8 + R-1/R-2）

1. `CHANGELOG.md`：`## 1.4.0` 增 `### Fixed`（四条）+ 修订 `### Notes`（R-1）。
2. `features.md`：端口检测条目 + stale 宽限条目 + 测试数。
3. `http-server.cli.spec.yaml`：`port-allocation` / `service-lifecycle` / `cli-interface`（R-2）补场景；版本保持 1.4.0。
4. `README.md` / `README.zh.md`：`-p` 行补残留端口说明。
5. 版本号保持 `1.4.0` / `__release_date__ = 2026-09-22`（D7）。
6. 发布（Step 7，**待用户放行**）：`bash scripts/release-pypi.sh -p -n` → `python3 -m twine check dist/*` → `-p`（CL003 + CL004 同批 1.4.0）。
7. 流程面：步 JSON 用 `cache/closed-loop/{YYYYMMDD}-http-server.cli-HTTP-SERVER-CL004-{step}.json`。

---

## 10 观察项与出口判据

| # | 事项 | 处置 |
|:--|:-----|:-----|
| O1 | `eprint()` 名不副实（实写 stdout） | 记录不修（N5；本批新文案已用 stderr） |
| O2 | `MAX_PORT=10000` 与 `-p` 上限 65535 口径差异 | CL003 D15 已定案，本批不动（N2） |
| O3 | web 其余 error 分支（名称非法/store 异常）退出码仍 0 | 记录留档（N7） |
| O4 | `is_process_alive`（signal-0）无法区分 pid 复用 | 本批以 `get_process_info` 归属校验缓解（R-6）；根治需启动锁（N8，另批候选） |
| O5 | 无启动锁 ⇒ 极端并发（>2 次同时启动）仍可能残留孤儿 | 本批宽限覆盖 <1.0s 窗口（实测复现面）；根治见 N8，另批候选 |

**出口判据**：A1–A11 全 PASS + CL003 harness 31/31 回归 + 审计 PASS ⇒ 允许 push 与（待放行）发布。

---

## 11 风险与回滚

| 风险 | 缓解 |
|:--|:--|
| `SO_REUSEADDR` 被误认为放宽真占用 | A2 + T1 + `test_dashboard.py` 真监听断言 |
| main() 分支序调整影响快捷方式 | T4 五形态 + A7（CL003 A8 回归） |
| stale 宽限引入启动延迟 | 仅同路径已登记且 pid 活但端口未监听时触发，上限 1.0s；幂等路径零等待 |
| kill 误伤（pid 复用 / 他人进程） | R-6 归属校验 + R-7 监听者核验；不匹配只删登记 |
| `--json` 通道回归 | A11 + T11 |
| `get_pid_by_lsof` 参数新增影响既有调用 | 默认值不变（N9）+ T13 | 
| 回滚 | 五项改动独立，可逐 commit `git revert`；无数据格式变更、无迁移 |

---

## 12 实施与门禁（Step 3–6 摘要）

| 步 | 产物 | 门禁 |
|:--|:-----|:-----|
| Step 3 dev | `fix@cli:`（D1 探测 + D11 lsof 参数）/ `fix@cli:`（D2 分支序 + D3 退出码）/ `fix@cli:`（D4+D6 stale 三态与通道）/ `tests@cli:` / `docs@sync:`（四同步 + R-1/R-2） | 全量 pytest 零回归（§7 全绿） |
| Step 4 ops 核查 | `scripts/port-residual-verify.py`（A1–A11）+ 报告 `documents/review/http-server-cli-cl004-ops-verify-v1.0-20260922.md` | 全断言 PASS（含 CL003 回归 31/31） |
| Step 5 实现审计 | review 侧报告 + review-log + `.review-level.yaml`；PASS → push | PASS / CONDITIONAL 回修 |
| Step 6 收尾 | 复盘 md + 清单 + 四件套 + 观察项登记（O1–O5） | `hm loop artifacts HTTP-SERVER-CL004` 齐全 |
| Step 7 发布 | `release-pypi.sh` 1.4.0（CL003+CL004 同批） | **待用户放行** |
