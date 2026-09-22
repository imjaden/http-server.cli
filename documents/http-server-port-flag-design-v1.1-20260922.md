# http-server.cli 端口参数（`-p/--port`）+ 未识别参数告警 + 周边端口面 — 设计 v1.1

> 编号: **HTTP-SERVER-CL003** · 日期: 2026-09-22 · 状态: 待设计复审（rereview）
> 基线: `7f3376d`（本地 ahead 1，未 push）· 版本 v1.3.1 · 目标版本 **1.4.0**（minor）
> 决策来源: 2026-09-22 探讨（「全采推荐」「文案对齐一并定」「独立模式完整闭环」）· draft: `cache/draft/TODO-20260922.md`
> 设计原则: 零外部依赖（仅标准库）· 展示名与内部标识不变 · 不改变既有**成功**语义（例外仅本版显式声明的失败退出码统一，见 §4.6/§11）
>
> **v1.1 修订说明**（依据 `documents/review/http-server-cli-cl003-design-review-v1.0-20260922.md`，CONDITIONAL_PASS 82/100）：
> 必改 F-1（§4.1 执行顺序链）· F-2（§4.3 dashboard restart 现状勘误）· F-3（§8 A14 四同步 grep 落地）·
> F-4（§5/§9 capability 5 项）· F-5（§4.6 退出码表 + 失败退出码统一，新增 §4.7 返回契约）；
> 记录项 F-6（§11 假占用继承）· F-7（§9 item 8 更正为「已满足」）· F-8（§10 O3 枚举/表述）· F-9（§4.4 字段明确）·
> F-10（§4.1 D8 重组规则精确化）· F-11（§5 行号勘误）· F-12（§9 CHANGELOG 1.3.1 补注）· F-13（§4.1 区间与 MAX_PORT 差异）·
> F-14（§4.1 保留端口双态提示）。新增定案 **D14/D15/D16**（对应评审待确认 1/2/3）。

---

## 1 背景与问题（全部为实测证据）

### 1.1 现场

```
$ hs ~/CodeSpace/hermes-manager/web -i index.html -p 8089 -d -o
🔀 Port 8080 in use, auto-assigned port 8085
✅  http://jaden.local:8085/index.html
...
🔄 Press Ctrl+C to stop log tail, service still running in background
```

用户预期起在 8089，实际落在 8085；且终端被 tail 占用（与 help 宣称「不占用终端」不符）。

### 1.2 四个独立缺陷

| # | 现象 | 根因定位（已读源码 + 实测，评审独立复现成立） |
|:--|:-----|:-------------------------------------------|
| P1 | `-p 8089` 完全无效 | `_cmd_start` 用 `parser.parse_known_args`（cli.py:190）；`unknown` 仅在 cli.py:215 用于「多 html 文件取最近修改」，其余**静默丢弃**，零告警。`-p`/`8089` 双双落 unknown ⇒ 端口仍取 `self.config.port`（server.py:124 = 8080） |
| P2 | 端口漂移到 8085（8084 本可绑） | `is_port_in_use` 用裸 socket `bind(('', port))`（utils.py:118-132），**无 SO_REUSEADDR**；8084 服务 15:56:04 刚被 kill（history 实测 11:44:12→15:56:04），残留连接使裸 bind 报占用；真实服务是 `http.server.HTTPServer`（`allow_reuse_address = 1`，评审实测亦为 `1`）。对照实验（`/tmp/hs-port-probe-demo.py`，端口 8099）：裸 bind `FAIL(48 Address already in use)` vs SO_REUSEADDR bind `OK` |
| P3 | `-d` 体感「没生效」 | `-d` 服务侧**确实生效**（registry `mode=daemon`、PID 脱离终端 session leader 实测），但实现随后在前台 `tail -f` 日志（server.py:320-326），终端仍被占用；`_HELP` 写「后台运行（不占用终端）」（cli.py:30）⇒ **文案与行为不一致** |
| P4 | 参数错误「假成功」 | argparse 报错触发 `SystemExit`，被 `except SystemExit: return`（cli.py:191-192）吞掉 ⇒ 实测 `hs dashboard -p abc` 打印 `error: argument -p/--port: invalid int value: 'abc'` 但 **EXIT=0**（对照：`--url --json` 互斥走 cli.py:195-197 是 EXIT=2） |

评审补充实测：`grep -c parse_known_args cli.py` = **22** 处（与本文一致）；`hs /nonexistent` 现状 **exit 0**（见 §4.6/F-5）；
`pytest --collect-only` = **490** collected（`def test_` 472）。

附带发现：`hs -p 8089`（flag 在路径前 / 无路径）实测 `command='8089'`、`unknown=['-p']` → 「Unknown command: 8089」（cli.py:1786-1816）；
已有兜底只覆盖「command=None 且 unknown 非空」（cli.py:1781-1785，即 `hs -d -o` 可用）。详见 §4.1 D8 重组规则。

### 1.3 现状端口面盘点

| 命令 | 端口能力现状 |
|:-----|:------------|
| `hs start` / 隐式 start（路径快捷方式 / bookmark 名 / 无命令名） | **无** `-p`；唯一来源 config.json（`hs set port`） |
| `hs dashboard` | `-p/--port` 默认 8180（cli.py:574）；`dashboard restart` **硬编码 8180**（cli.py:678，D9a 修）；`restart` 未运行 → `dashboard not running` 不启动（cli.py:610-616） |
| `hs mcp` | `--port` 默认 8181，仅 SSE（cli.py:812 / serve_sse 914）；stdio 不使用 |
| `hs list --port` | **布尔过滤器**（cli.py:237），与新增 `--port <N>` 语义不同名同形 |
| `hs status/kill <port>`、`hs search <kw>` | 位置参数（已端口感知，无需改） |
| `hs set port <N>` | 改全局默认（cli.py:123-139，校验 1024-65535） |
| `hs web add --cmd '…'` | 端口固化在 cmd/url 字符串；已有 `--domain` 执行期注入先例（cli.py:1327-1328、1734-1736） |
| `hs bookmark` | 路径模型（name/path/index_page/created_at），无端口字段 |

---

## 2 目标与非目标

### 2.1 目标

- **G1** `hs start` 系列支持 `-p/--port <N>`（一次性覆盖 config，不写回）：三种入口全覆盖 + 顶层写法兜底。
- **G2** 未识别参数一律告警（不再静默丢弃），并给常见近形 typo 用法引导。
- **G3** 周边端口面收敛：`dashboard restart` 透传端口；`hs web add/update` 支持 `--port` 注入。
- **G4** 错误语义一致化：新参数面 fail-closed；退出码 0/1/2 三态明确；**失败退出码统一**（消灭「假成功」，
  含 P4 的参数错误 exit 2 与既有「路径不存在返回 0」→ 改为 1，见 D14/§4.6）。
- **G5** 文案对齐（仅文案，不改 `-d` 行为）。
- **G6** 编号/缓存命名口径改 hm 新式（D13=A），使 `hm loop status/artifacts/next-code` 可用。

### 2.2 非目标（明确不做）

- N1 `is_port_in_use` 增 SO_REUSEADDR 的探测语义修复 → 观察项 O1，另批 + 评审（影响所有端口判断，需独立论证）。
- N2 `hs list --port` 改名（破坏兼容）→ 仅 help 消歧。
- N3 新增 `--no-tail` / 改变 `-d` 行为（保留既有肌肉记忆）。
- N4 `hs bookmark` 固化端口（固定端口场景由 `hs web` 承载）。
- N5 gitee 镜像（维护策略：仅 GitHub）。
- N6 `kill/status/search/mcp/prompt/help/version/config` 参数面变更。
- N7 端口区间与自动分配上限（`MAX_PORT=10000`）的口径统一（D15 维持现状，仅注明差异）。

---

## 3 决策定案（D1–D16）

| # | 议题 | 定案 |
|:--|:-----|:-----|
| D1 | `-p` 指定端口被占 | **fail-closed**：stderr 报占用者（PID/路径）+ `exit 1`；未给 `-p` 时保持现有 `find_available_port` 逐 +1 |
| D2 | 与 8180/8181 冲突 | **硬拦** `exit 1` + 保留端口提示（**双态**：占用/未占用措辞不同，见 §4.1） |
| D3 | `-p` 与 config 关系 | 仅本次生效（`CLI > config`），**不回写** config.json |
| D4 | 取值区间 | **1024-65535**（复用 `hs set port` 文案与边界） |
| D5 | 同路径已在别端口运行 + 给了 `-p` | **幂等优先**：提示「已在 `<port>` 运行，`-p` 未生效；如需换端口先 `hs kill <port>`」并按现有语义开浏览器，不另起实例 |
| D6 | 未知参数告警范围 | **全命令统一 helper** + 仅 stderr 警告，**退出码不变** |
| D7 | `--json` 信封 | `start` 的 `data` **补 `port` 字段**（additive，向后兼容） |
| D8 | 顶层 `hs -p 8089 [path]` | **修**：按 start 参数重组处理（泄漏值重组规则见 §4.1），不再误判 Unknown command |
| D9a | `dashboard restart` | **透传 `--port`**（修 8180 硬编码）；未运行仍 `dashboard not running` 不启动 |
| D9b | `hs web add/update` | **加 `--port`**：执行期向 cmd 追加 `--port N`（与 `--domain` 注入同构），json 体现 `cmd_effective` |
| D9c | 其他命令 | 不动（见 N6） |
| D9d | `hs list --port` 撞名 | 保留布尔语义，**help 并列消歧**，不改名 |
| D9e | 参数错误假成功 | **修**：与互斥 flag 对齐，显式 `exit 2` |
| D10 | 探测假占用 | 另批（N1 / 观察项 O1） |
| D11 | 版本与发布 | **1.4.0（minor）+ 同批 PyPI 发布**；features.md/CHANGELOG/`__version__`/spec.yaml 四同步 |
| D12 | 文案对齐 | 仅改文案：`_HELP`（cli.py:30/34）+ `skills/hs-cli/SKILL.md:30` + README.md/README.zh.md（如含该表述）；不新增 `--no-tail` |
| D13 | 编号与缓存命名 | **A**：本批起 cache/closed-loop 用 hm 新式命名（`{YYYYMMDD}-http-server.cli-HTTP-SERVER-CL{NNN}-{step}.json`），与 html-gen 对齐 |
| **D14** | （评审待确认 1 / F-5）路径不存在、服务未找到的退出码 | **改 1**（对齐 G4「消灭假成功」；与 `--url` 模式已有的 `sys.exit(1)` 一致）；纳入 CHANGELOG `### Changed` + §11 风险表 + A15 断言 |
| **D15** | （评审待确认 2 / F-13）区间与 `MAX_PORT` | **维持 1024-65535**（`-p` 为直绑，可超 10000；`MAX_PORT=10000` 仅约束自动漂移扫描上限），在 §4.1 注明差异 |
| **D16** | （评审待确认 3 / F-14）保留端口提示 | **区分双态**：保留且被占用 → 报「由内置服务占用（PID/路径）」；保留且空闲 → 报「内置服务保留端口，请换端口」（§4.1） |

---

## 4 接口设计

### 4.1 `start` 的 `-p/--port`

```
hs [start] [path] [-p <port>] [-i <index>] [-d|-f] [-o] [--json|--url]
```

**执行顺序链（F-1 明确，按此实现；顺序即语义，不可重排）**：

```
0. argparse 解析：非整数 / 缺值 → 报错 → exit 2（D9e）
1. 路径解析与存在性检查（server.py:126-134）→ 不存在：exit 1（D14）
2. 幂等检查（server.py:137-185）：该路径已注册且存活
     ├─ 命中：返回既有端口，**忽略 -p**（D5），stderr 注记「已运行在 <port>（-p <N> 未生效…）」→ exit 0
     └─ 未命中（含 stale entry 清理，server.py:187-192）→ 继续
3. `-p` 校验（仅在第 2 步未命中后执行，替换 server.py:195 的 find_available_port 分支）
     3a. 区间：< 1024 或 > 65535 → 提示 → exit 2（D4）
     3b. 保留端口 8180/8181 → 双态提示 → exit 1（D2/D16）
     3c. 占用：is_port_in_use(port) → 报占用者 → exit 1（D1）
     （未给 -p：走原 find_available_port(config.port) +1 漂移，行为不变）
4. 启动后台进程 + 注册（server.py:208-269）→ 成功 exit 0
```

> 说明：第 1–3 步全部为**只读检查**（无进程/写盘副作用），但**排序**决定语义 —— 幂等命中必须早于 `-p` 校验，
> 否则 `hs . -p 8099`（该路径已运行在 8099）会误报「已被占用」、`hs . -p 8180`（已运行在别端口）会误报「保留端口」（评审 F-1 指出的两个反例）。

- **优先级**：CLI `-p` > `config.port`；`-p` 被占**不漂移**（fail-closed），未给 `-p` 保持 +1 漂移。
- **服务层**：`ServerManager.start(..., port: Optional[int] = None)`（server.py:78-80）；server.py:124 改为
  `default_port = port if port is not None else self.config.port`。
- **校验文案**（统一 eprint + stderr）：
  - 区间：`❌ Port must be between 1024-65535`（与 `hs set port` 同文案）+ `exit 2`
  - 保留端口占用：`⚠️ <port> 为内置服务保留端口（<dashboard|mcp> 正在使用，PID <pid>），请换端口` + `exit 1`
  - 保留端口空闲：`⚠️ <port> 为内置服务保留端口（dashboard=8180 / mcp=8181），如需启动请用 hs dashboard -p <port>` + `exit 1`
  - 普通占用：`⚠️ 端口 <port> 已被占用（PID <pid> / <path|未知服务>）` + `💡 换端口: hs . -p <other>；或关闭: hs kill <port>` + `exit 1`
    占用者查询：先 `Registry().find(port=port)`（registry.py:89-96）取 path/pid；未命中再 `utils.get_pid_by_lsof(port)`（utils.py:172-191，macOS）；均无 → 「未知服务」
- **区间与自动分配上限的差异（F-13/D15）**：`-p` 直绑上限 65535；`find_available_port` 的漂移扫描封顶 `MAX_PORT=10000`（utils.py:29）——
  两者口径不同，**本批不改**，仅在 help/features 注明。
- **幂等命中 + 保留端口**：`hs . -p 8180` 而该路径已运行在其它端口 → 走第 2 步（幂等）返回既有端口 + 注记，不触发 3b（与 F-1/F-14 一致）。

**顶层重组规则（D8 / F-10 精确化）**：`main()` 中当 `cmd` 既非内置命令、非 bookmark、也非存在的路径/globs 时，
若 `unknown` 与 `{'-p','--port','-i','--index'}` 相交（即**取值型 flag 的值被 argparse 误判为 positional**），则重整为：

```
args = unknown + [cmd] + args      # 保持原顺序：flag 在前、其值（泄漏的 cmd）紧随其后
cmd  = 'start'
```

实测依据（本轮复测）：

| 输入 | 解析现状 | 重组后 |
|:-----|:---------|:-------|
| `hs -p 8089` | command=`'8089'`, unknown=`['-p']`, args=`[]` | `['-p','8089']` → start ✓ |
| `hs -p 8089 /tmp/x` | command=`'8089'`, unknown=`['-p']`, args=`['/tmp/x']` | `['-p','8089','/tmp/x']` ✓ |
| `hs -i a.html -p 8089` | command=`'a.html'`, unknown=`['-i']`, args=`['-p','8089']` | `['-i','a.html','-p','8089']` ✓ |
| `hs 8089`（无 flag） | command=`'8089'`, unknown=`[]` | 规则不触发 → 维持 `Unknown command: 8089` ✓ |

规则**有意不含** `-o/-d/-f`（布尔 flag，其泄漏场景不存在；`hs -o <不存在路径>` 维持现状报错），避免放大兜底面。

### 4.2 未识别参数告警 helper（D6）

新增 cli.py 内部函数（零依赖，纯 stderr）：

```python
def _warn_unknown_args(cmd: str, unknown: list, *, allow: tuple = (), hint_map: dict | None = None) -> list:
    """过滤白名单后，将未识别参数打印到 stderr；返回未识别清单（供测试断言）。"""
```

- **文案**：`⚠️ 未识别参数（已忽略）: -p 8089` + 引导行 `💡 指定端口请用: hs . -p <port>`。
  引导按「近形映射」给出：`-p/--port` 与近形（`--prot/--portt/--prt`）→ `hs . -p <port>`；
  `-i/--index` → `hs . -i <file>`；`-d/--daemon`、`-o/--open` → 对应 start 用法；未命中映射则不附引导，仅列参数。
- **白名单（按命令传入 `allow`）**：`start` 的 html 通配文件（cli.py:215 既有语义）+ 以 `.html/.htm` 结尾的 token；
  `kill/status` 的端口或路径位置参数；`search` 的关键词；`web add/update` 的 `--cmd` 值等。
- **覆盖站点**：cli.py 全部 22 处 `parse_known_args`（评审实测计数一致）；`main()` 层因 REMAINDER 已兜住，
  只在其判定 branch 内报一次，避免与子命令层重复报同一参数。
- **退出码不变**（D6）；**stdout / `--json` 信封零污染**（stderr-only，与 `--url` 模式既有约定一致）。
- **不引入 argparse 严格模式的理由**：`parse_known_args` 承载「多 html 文件取最近修改」等既有宽松语义（cli.py:212-219），
  改严格会破坏向后兼容；告警是兼容路径下的最小可见性修复。

### 4.3 `dashboard restart --port`（D9a / F-2 勘误）

**现状（勘误，与源码一致）**：
- `restart` 在 dashboard **未运行**时 → 打印/返回 `dashboard not running`（cli.py:610-616），**不启动**；
- `restart` 在 dashboard 已运行时 → **硬编码** `serve(port=8180, open_browser=False, daemon=True)`（cli.py:678），
  **不沿用** `entry['port']` —— 这正是 D9a 要修的缺陷（改用 `-p` 8180 启动会把面板从自定义端口拉回 8180）。

**新行为**：
```
hs dashboard restart                 # 未运行 → dashboard not running（保持）；已运行 → 沿用 entry['port']
hs dashboard restart --port N        # 用 N 启动（受 D2 保留端口规则：允许 8180 自身、拒绝 8181）；
                                     # 非保留端口按 D1 校验占用
```
- 实现：`_cmd_dashboard` 子命令分支（cli.py:568-571）解析 `-p/--port`（默认 `None`）并透传 `_manage_dashboard('restart', port=...)`。
- `dashboard stop/status` 保持按 `name='dashboard'` 查 managed registry（无需端口参数）。

### 4.4 `hs web add/update --port`（D9b / F-9 字段明确）

**存储字段（明确）**：`services.json` 每条服务新增
- `use_port`: bool，默认 `False`（与 `use_domain` 同构；**存量条目缺字段视为 False** ⇒ 兼容）
- `port`: int 或 `None`，默认 `None`（仅当 `use_port=True` 且非 None 时参与注入）

**命令行**：`hs web add <name> --cmd '<cmd>' --port <N>` / `hs web update <name> --port <N> | --no-port`；
`--no-port` 同时清除 `use_port=False` 与 `port=None`（两者同清）。区间校验 1024-65535；本项端口**不参与** start 的保留端口校验（被注册命令自管）。

**执行期注入**（cli.py:1732-1737）：`use_port` 且 `port` 非空 → `cmd_line = f"{cmd_line} --port {port}"`；
与 `--domain` 的固定顺序为 **domain 先、port 后**：`cmd --domain "<d>" --port <N>`。
`list/show` 展示 port 维度；`--json` 的 `cmd_effective` 体现注入后的完整命令。url 语义不变。

### 4.5 `--json` 信封补 `port`（D7）

- `start` 成功（新建与幂等两条路径）的 `data` 增 `port: <int>`；既有键（`url/path/pid/started_at/index_page/stats/duration`）不动。
- 兼容性：纯 additive；`dashboard.py:401` 与 `mcp.py` 不消费 start 信封（已核实仅 `cli.py:220` 与 `dashboard.py:401` 调用 `start()`，
  且后者不使用返回值）。

### 4.6 退出码规范（G4 / F-5 / D14）

| 码 | 语义 | 触发 |
|:--|:-----|:-----|
| 0 | 成功（含幂等命中、含「未知参数告警但命令成功」） | 正常启动 |
| 1 | 运行期失败 | 端口被占（D1）· 保留端口（D2）· **路径不存在（既有 0 → 改 1）** · **服务未找到（既有 0 → 改 1）** |
| 2 | 用法错误 | 非法值/缺值（D9e）· 越界（D4）· 互斥 flag（cli.py:195-197 既有） |

**行为变更声明（F-5/D14，必须落地到 CHANGELOG `### Changed` + §11 风险表 + A15）**：
- `hs <不存在路径>` / `hs kill <未注册端口>` 等「运行期失败」此前返回 **0**（假成功），本批起返回 **1**；
- `kill` 的口径依据：实测现状 `hs kill 59999` → `ℹ️ Port 59999 not registered` + **exit 0**（未执行任何操作却报成功），
  改 1 对齐 Unix `kill <不存在进程>` 语义；**`hs status <未注册端口>` 为查询命令，保持 exit 0**（查询本身成功，无目标不等于失败）；
- 与 `--url` 模式已有语义对齐（cli.py:230-231 `sys.exit(0 if result else 1)`），消除同族不一致。

### 4.7 `ServerManager.start()` 返回契约（D14 的实现前提）

现状返回 `Optional[bool]` 但语义混杂：成功与部分失败路径均 `return`（None）；仅 url 模式显式返回 True/False。

**统一为**：`True` = 成功（含幂等命中/JSON/URL/daemon 各模式）；`False` = 运行期失败（路径不存在、端口不可用、进程启动失败、write log 失败等）。

- server.py 改动：失败路径（现 121/134/204/229/238/247/256 等 `return`）→ 显式 `return False`；
  成功出口（json 分支 314-315、daemon/foreground 之后）→ 显式 `return True`；url 分支保持（281）。
- cli.py 改动：`result = manager.start(...)`；`if parsed.url: sys.exit(0 if result else 1)`（既有）；
  新增 `if result is False: sys.exit(1)`（非 url/json 模式）。
- 影响面：`start()` 仅两处调用——`cli.py:220`（本批处理）与 `dashboard.py:401`（不使用返回值，零影响）。

---

## 5 影响矩阵（基线 `7f3376d`，行号已勘误 F-11）

| 文件 | 改动点 | 行号基线 |
|:-----|:-------|:---------|
| `src/http_server_cli/cli.py` | start parser 加 `-p/--port` + 顺序链 + 校验；未知参数 helper + 22 处接入；`_HELP`（30/34）；`main()` 顶层重组（1781-1816）；`_cmd_start` 退出码（220-231）；`_manage_dashboard` 透传 port（565-571、676-685）；`_web_add`（**1321-1408**）；`_web_list/_web_show` 展示（**1420-1527**）；`_web_update`（**1574-1670**）；`_web_run` 注入（1732-1740） | 30、34、181-192、195-197、215、220-231、565-571、676-685、1321-1408、1420-1527、1574-1670、1732-1740、1767-1816 |
| `src/http_server_cli/server.py` | `start(port=None)` 签名 + `default_port` 取值 + 顺序链（幂等先于 `-p` 校验）+ fail-closed/双态提示 + 返回契约 + `--json/--url` 带 port | 78-80、124、126-134、136-192、195-206、275-301、314-318 |
| `src/http_server_cli/services.py` | `use_port`(bool, 默认 False) + `port`(int/None, 默认 None) + CRUD/校验 | add(118-156)、update(167-199)、get/list_all/show 展示 |
| `http-server.cli.spec.yaml` | **5 个 capability**：`service-lifecycle`(34) / `port-allocation`(143) / `cli-interface`(268) / `dashboard`(600) / `json-output`(712)；`version` → 1.4.0 | 34、143、268、600、712、2 |
| `tests/test_server.py` / `test_cli.py` / `test_dashboard.py` / `test_web.py` | 新增用例（见 §7） | — |
| `README.md` / `README.zh.md` | 首屏用法补 `-p`；`-d` 描述对齐 | 双页同步 |
| `skills/hs-cli/SKILL.md` | 用法表补 `-p` + `-d` 文案对齐 | 30 行区 |
| `features.md` / `CHANGELOG.md` / `src/http_server_cli/__init__.py` | 功能条目 + 测试数 + 1.4.0（含 1.3.1 补注） | features.md:126（测试数） |
| `cache/`（流程面） | 步 JSON 改新式命名（D13=A） | — |

---

## 6 文案对齐清单（D12，仅文案）

| 位置 | 现状 | 改为 |
|:-----|:-----|:-----|
| `cli.py:30`（`_HELP`） | `hs . -d                  后台运行（不占用终端）` | `hs . -d                  后台运行 + 前台 tail 日志（Ctrl+C 仅退出 tail）` |
| `cli.py:34`（快捷方式行） | `-d 后台` | `-d 后台（前台 tail 日志）` |
| `skills/hs-cli/SKILL.md:30` | `hs . -d                  后台运行（不占用终端）` | 同 `_HELP` |
| `README.md` / `README.zh.md` | 若有同表述则同改；并补一句「要零占用请用 `--url` / `--json`」 | 同 |
| `documents/url-flag-design-v2.0-20250715.md:216`、`documents/hs-cli-design-v1.0-20260624.md:506` | 同句 / 同表述 | **不改**（**`documents/` 下全部历史留档豁免**，F-8 统一表述） |
| `http-server.cli.spec.yaml:54` | 「Ctrl+C 时日志查看停止，服务仍在后台运行」 | 不改（表述本就准确） |

---

## 7 测试清单

- `tests/test_server.py`
  1. `-p` 生效：`start(port=8099)` → registry 记录 8099、URL 含 8099（隔离 fixture，不触真实数据目录）。
  2. `-p` 被占 → fail-closed（预置 registry 一条 8099 或 monkeypatch `is_port_in_use`）→ `False` + 无新条目。
  3. 保留端口 8180/8181 → 拒绝，且**双态文案**分别命中（占用/空闲，D16）。
  4. 区间：`-p 99` / `-p 70000` / `-p 0` → 拒绝；`-p 20000`（> MAX_PORT=10000）→ **允许**（D15 差异守护）。
  5. 未给 `-p` → 沿用 config.port 且保持 +1 漂移（回归保护）。
  6. **顺序链**：路径已运行 + `-p <该端口>` → 幂等返回（不报占用）；已运行 + `-p 8180` → 幂等返回（不报保留）。（F-1 反例回归）
  7. **返回契约**：路径不存在 → `False`；成功/幂等/JSON/URL 各模式 → `True`。（§4.7）
  8. `--json` 信封含 `port`（新建/幂等两路径）。
- `tests/test_cli.py`
  9. `_warn_unknown_args`：白名单（`.html`）不报、`-p 8089` 报、近形 `--prot` 报并带引导。
  10. **顶层重组**：`['-p','8099']` / `['-p','8099','.']` / `['-i','a.html','-p','8099']` 三形态 → 交给 start；
      `['8089']`（无 flag）→ 仍 `Unknown command`。（D8 表驱动）
  11. **退出码**：非法 `-p abc` → 2；`hs <不存在路径>` → 1（D14/A15，覆盖 P4 与假成功族）。
- `tests/test_dashboard.py`
  12. `dashboard restart --port 8280` → `serve(port=8280)` 被调用；不带 `-p` 且已运行 → 沿用 `entry['port']`；
      未运行 → `not running` 不启动（F-2 三种现状回归）。
- `tests/test_web.py`
  13. `web add x --cmd 'true' --port 9001` → 字段 `use_port=True`/`port=9001`；执行 → `cmd_effective` 含 `--port 9001`；
      `--no-port` 同清两字段；`--port` 与 `--domain` 同时开启 → 顺序 `--domain "<d>" --port <N>`。
- 既有回归全量：`PYTHONPATH=src python3 -m pytest tests/ -q`（基线 490 collected）。

---

## 8 A 段断言表（可复跑，ops 核查用）

> 规范：命令 + 实测 + 断言；禁止恒真断言。

| # | 命令 | 断言 |
|:--|:-----|:-----|
| A1 | `hs /tmp/hs-cl003-demo -p 8099 -d --url` | 输出 `http://<domain>:8099/…`；`hs list --json` 该条 `port=8099` |
| A2 | 修前反证：stash 修复后同命令 | 修前端口非 8099（8080 或漂移端口）⇒ 判据非恒真 |
| A3 | `hs . -p 8080`（8080 在跑） | stderr 含「已被占用」+ 占用者 PID/路径；`echo $?` = 1 |
| A4 | `hs . -p 8180` / `hs . -p 8181` | stderr 含「保留端口」（并按 D16 区分占用/空闲态）；exit 1 |
| A5 | `hs . -p 99`；`hs . -p abc` | 区间/非法提示；exit 2（不得再出现 exit 0） |
| A6 | `hs . --prot 8080` | stderr 含「未识别参数」+ 引导行；stdout 无该文字；exit 0（D6） |
| A7 | `hs . -p 8099 -d --json \| python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["data"]["port"]==8099'` | 信封含 port（D7） |
| A8 | `hs -p 8099 /tmp/hs-cl003-demo -d --url`、`hs -i index.html -p 8099 /tmp/hs-cl003-demo` | 不再报 Unknown command；端口 8099（D8 两形态） |
| A9 | 幂等 + `-p`：同目录重复启动并给不同 `-p` | stderr 注记「已运行在 8099」；URL 仍 8099；不另起实例（D5/F-1） |
| A10 | `hs dashboard -p 8280 -d` → `hs dashboard restart --port 8290` → `hs dashboard status` | managed registry 端口 8290；无 `--port` 重启则沿用 entry 端口 |
| A11 | `hs web add cl003-demo --cmd 'true' --port 9001 && hs web cl003-demo --json` | `cmd_effective` 含 `--port 9001`（用完 `hs web remove cl003-demo` 清理） |
| A12 | `grep -rn "不占用终端" src/ skills/ README.md README.zh.md` | 0 命中（D12；`documents/` 全部豁免） |
| A13 | `PYTHONPATH=src python3 -m pytest tests/ -q` | `0 failed`，通过数 ≥ 基线 490 |
| **A14**（F-3 修正） | `hs version` + `grep -n "1.4.0" src/http_server_cli/__init__.py CHANGELOG.md` + `grep -n "^version:" http-server.cli.spec.yaml` | 三处均 = 1.4.0（**不 grep pyproject.toml**：版本为 dynamic 无字面量） |
| **A15**（F-5/D14） | `hs /nonexistent; echo $?`、`hs kill 59999; echo $?` | 均为 1（修前为 0 ⇒ 非恒真；与 CHANGELOG Changed 一致） |
| **A16**（F-14/D16） | `hs . -p 8180`（dashboard 在跑）/（dashboard 未跑） | 前者含「正在使用，PID」；后者含「如需启动请用 hs dashboard -p 8180」 |
| **A17**（F-12） | `grep -n "1.3.1" CHANGELOG.md` | 命中 1.4.0 条目内的 1.3.1 补注行（版本链承认既有漂移） |

---

## 9 文档/版本/发布同步清单（D11）

1. `__version__` 1.3.1 → **1.4.0**（`src/http_server_cli/__init__.py:28`）。
2. `CHANGELOG.md`：加 `## 1.4.0 (2026-09-22)`（Added / **Changed** / Notes）；`### Changed` 必列
   ①失败退出码统一（路径不存在/服务未找到 0→1，含 D14）②参数错误 exit 2；`### Notes` 补注
   「1.3.1 为 2026-09-04 的 patch 发布，未单列 CHANGELOG 条目（F-12）」。
3. `features.md`：CLI 命令节补 `-p`（含区间与 MAX_PORT 差异注）；HTTP 服务节补 fail-closed/幂等/退出码语义；
   Web 节补 `--port/--no-port`；测试数同步；待定项清理。
4. `http-server.cli.spec.yaml`：**5 个 capability** 补场景（`service-lifecycle`/`port-allocation`/`cli-interface`/
   **`dashboard`（restart --port）**/**`json-output`（start 信封含 port）**）+ `version` → 1.4.0。
5. `README.md` + `README.zh.md`：用法补 `-p` + `-d` 文案对齐 + 零占用建议（--url/--json）。
6. `skills/hs-cli/SKILL.md`：同步（篇目不增删 ⇒ `EXPECTED_SKILLS` 无需改）。
7. 发布：`bash scripts/release-pypi.sh -p -n`（dry-run，验证 Description 非空 + GitHub/PyPI 链接）→
   `python3 -m twine check dist/*` → `-p` 正式上传。
8. 流程面（D13=A）：本批步 JSON / 审计记录统一 `{YYYYMMDD}-http-server.cli-HTTP-SERVER-CL003-{step}.json`。
   `http-server-ops` skill 的 `--usage-file` 范式**已含新式命名**（评审实测 SKILL.md:46-49），**无需动作**（F-7 更正；其属跨仓/跨 profile，不在本仓范围）。

---

## 10 观察项与出口判据

| # | 事项 | 事实 / 落点 | 处置 |
|:--|:-----|:-----------|:-----|
| O1 | 端口探测「假占用」 | `utils.is_port_in_use`（utils.py:118-132）裸 bind 无 SO_REUSEADDR；实测裸 bind FAIL(48) vs SO_REUSEADDR OK ⇒ 刚释放/有残留连接的端口被判占用（影响 start 漂移、registry `_alive`、dashboard/mcp 可用性判断，**并使 `-p` 占用检查可能假拒绝**，见 §11） | **显式升级**：另批 + 评审 |
| O2 | `hm loop next-code` 序列偏差 | 本仓返回旧式 `CL-SEC24`；`hm loop status HTTP-SERVER-CL002` 报「无匹配 JSON」（cache 旧式小写单文件命名） | **本批处置**（D13=A 改命名）→ 收尾复测；仍偏则出 hermes-manager 侧 handoff |
| O3 | 历史文档同表述 | `documents/url-flag-design-v2.0-20250715.md:216`、`documents/hs-cli-design-v1.0-20260624.md:506` 含「不占用终端」 | 留档不回改（**统一表述：`documents/` 全部豁免**，F-8） |

**遗留率**：升级项 1 / 本批步数 6 = 0.17。

---

## 11 风险与回滚

| 风险 | 影响 | 缓解 |
|:-----|:-----|:-----|
| `-p` 被占 fail-closed 改变既有脚本行为 | 用户脚本原本不存在 `-p`（当时静默忽略）⇒ 无历史依赖 | 未给 `-p` 的路径零行为变更（A13 回归） |
| **失败退出码 0→1（D14/F-5）** | 依赖「失败也返回 0」的脚本会感知变化（属缺陷修复） | CHANGELOG `### Changed` 显式声明 + A15 断言 + 与 `--url` 既有语义对齐 |
| 退出码 2 引入（新语义） | 原「假成功 0」可能被脚本依赖 | 视为缺陷修复（P4）；CHANGELOG 标注 |
| **`-p` 占用检查继承 O1 假占用（F-6）** | 刚释放/有残留连接的端口可能被**假拒绝**（实际 HTTPServer 可绑）⇒ 用户看到「已被占用」但换端口才成功 | §4.1 文案含「或关闭: hs kill <port>」兜底；O1 闭环后自动消失；本批不修探测 |
| `hs web --port` 改变已注册 cmd 行为 | 仅显式 `--port` 时注入 ⇒ 存量条目 `use_port=False` 不受影响 | services.json 兼容（缺字段 = False，F-9 明确） |
| D13 改命名导致历史 glob 失配 | 历史文件按旧名保留（不重命名） | 新批起新名；hm 侧按编号 glob，历史条目不受影响 |
| `start()` 返回契约变更 | 其他调用方误用 | 已核实仅 `cli.py:220`（本批处理）与 `dashboard.py:401`（不看返回值） |

**回滚**：分组 commit（feat/feat/fix/tests/docs），任一失败 `git revert` 该组；`-p` 面、告警面、退出码面互不依赖，可分别回滚。

---

## 12 实施与门禁（Step 3–6 摘要）

| 步 | 产物 | 门禁 |
|:--|:-----|:-----|
| Step 3 dev | `feat@cli:`（-p 面 + 顺序链 + 校验 + 双态提示）／`feat@cli:`（未知参数 helper + 顶层重组）／`fix@cli:`（退出码 2/1 + 返回契约）／`feat@cli:`（dashboard restart + web --port）／`tests@cli:`／`docs@sync:`（help + README 双页 + 5 capability 四同步） | 本地全量 pytest 零回归 |
| Step 4 ops 核查 | harness（A1–A17）+ 核查报告 `documents/review/http-server-cli-cl003-ops-verify-v1.0-20260922.md` | 全部断言 PASS |
| Step 5 实现审计 | review 侧报告 + review-log + `.review-level.yaml`；PASS → push（github only） | PASS / CONDITIONAL 回修 |
| Step 6 收尾 | 复盘 md + 清单 + 四件套 + O1/O2 登记 | `hm loop artifacts` 齐全 |
