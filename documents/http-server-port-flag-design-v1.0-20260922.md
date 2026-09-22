# http-server.cli 端口参数（`-p/--port`）+ 未识别参数告警 + 周边端口面 — 设计 v1.0

> 编号: **HTTP-SERVER-CL003** · 日期: 2026-09-22 · 状态: 待设计评审
> 基线: `1ff81e6`（main == origin/main，未推送 0）· 版本 v1.3.1 · 目标版本 **1.4.0**（minor）
> 决策来源: 2026-09-22 探讨（用户口径「全采推荐 / 文案对齐一并定 / 独立模式完整闭环」）· draft: `cache/draft/TODO-20260922.md`
> 设计原则: 零外部依赖（仅标准库）· 展示名与内部标识不变 · 不改变既有命令的成功语义（除明确 fail-closed 的新分支）

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

| # | 现象 | 根因定位（已读源码 + 实测） |
|:--|:-----|:---------------------------|
| P1 | `-p 8089` 完全无效 | `_cmd_start` 用 `parser.parse_known_args`（cli.py:190）；`unknown` 仅在 cli.py:215 用于「多 html 文件取最近修改」，其余**静默丢弃**，零告警。`-p`/`8089` 双双落 unknown ⇒ 端口仍取 `self.config.port`（server.py:124 = 8080） |
| P2 | 端口漂移到 8085（8084 本可绑） | `is_port_in_use` 用裸 socket `bind(('', port))`（utils.py:118-132），**无 SO_REUSEADDR**；8084 服务 15:56:04 刚被 kill（history 实测 11:44:12→15:56:04），残留连接使裸 bind 报占用；而真实服务是 `http.server.HTTPServer`（`allow_reuse_address = 1`，实测 =1）。对照实验（`/tmp/hs-port-probe-demo.py`，端口 8099）：裸 bind `FAIL(48 Address already in use)` vs SO_REUSEADDR bind `OK` |
| P3 | `-d` 体感「没生效」 | `-d` 服务侧**确实生效**（registry `mode=daemon`、PID 脱离终端 session leader 实测），但实现随后在前台 `tail -f` 日志（server.py:320-326），终端仍被占用；`_HELP` 写「后台运行（不占用终端）」（cli.py:30）⇒ **文案与行为不一致** |
| P4 | 参数错误「假成功」 | argparse 报错触发 `SystemExit`，被 `except SystemExit: return`（cli.py:191-192）吞掉 ⇒ 实测 `hs dashboard -p abc` 打印 `error: argument -p/--port: invalid int value: 'abc'` 但 **EXIT=0**（对照：`--url --json` 互斥走 cli.py:195-197 是 EXIT=2） |

附带发现：`hs -p 8089`（flag 在路径前 / 无路径）实测 `command='8089'` → 「Unknown command: 8089」（cli.py:1786-1816）；已有兜底只覆盖「command=None 且 unknown 非空」（cli.py:1781-1785，即 `hs -d -o` 可用）。

### 1.3 现状端口面盘点

| 命令 | 端口能力现状 |
|:-----|:------------|
| `hs start` / 隐式 start（路径快捷方式 / bookmark 名 / 无命令名） | **无** `-p`；唯一来源 config.json（`hs set port`） |
| `hs dashboard` | `-p/--port` 默认 8180（cli.py:574）；`dashboard restart` **硬编码 8180**（cli.py:678） |
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
- **G4** 错误语义一致化：新参数面 fail-closed，退出码 0/1/2 三态明确，消灭「假成功」。
- **G5** 文案对齐（仅文案，不改 `-d` 行为）。
- **G6** 编号/缓存命名口径改 hm 新式（D13=A），使 `hm loop status/artifacts/next-code` 可用。

### 2.2 非目标（明确不做）

- N1 `is_port_in_use` 增 SO_REUSEADDR 的探测语义修复 → 观察项 O1，另批 + 评审（影响所有端口判断，需独立论证）。
- N2 `hs list --port` 改名（破坏兼容）→ 仅 help 消歧。
- N3 新增 `--no-tail` / 改变 `-d` 行为（保留既有肌肉记忆）。
- N4 `hs bookmark` 固化端口（固定端口场景由 `hs web` 承载）。
- N5 gitee 镜像（维护策略：仅 GitHub）。
- N6 `kill/status/search/mcp/prompt/help/version/config` 参数面变更。

---

## 3 决策定案（D1–D13）

| # | 议题 | 定案 |
|:--|:-----|:-----|
| D1 | `-p` 指定端口被占 | **fail-closed**：stderr 报占用者（PID/路径）+ `exit 1`；未给 `-p` 时保持现有 `find_available_port` 逐 +1 |
| D2 | 与 8180/8181 冲突 | **硬拦** `exit 1` + 提示「内置服务保留端口（dashboard/mcp）」 |
| D3 | `-p` 与 config 关系 | 仅本次生效（`CLI > config`），**不回写** config.json |
| D4 | 取值区间 | **1024-65535**（复用 `hs set port` 文案与边界） |
| D5 | 同路径已在别端口运行 + 给了 `-p` | **幂等优先**：提示「已在 `<port>` 运行，`-p` 未生效；如需换端口先 `hs kill <port>`」并按现有语义开浏览器，不另起实例 |
| D6 | 未知参数告警范围 | **全命令统一 helper** + 仅 stderr 警告，**退出码不变** |
| D7 | `--json` 信封 | `start` 的 `data` **补 `port` 字段**（additive，向后兼容） |
| D8 | 顶层 `hs -p 8089 [path]` | **修**：按 start 参数处理，不再误判 Unknown command |
| D9a | `dashboard restart` | **透传 `--port`**（修 8180 硬编码） |
| D9b | `hs web add/update` | **加 `--port`**：执行期向 cmd 追加 `--port N`（与 `--domain` 注入同构），json 体现 `cmd_effective` |
| D9c | 其他命令 | 不动（见 N6） |
| D9d | `hs list --port` 撞名 | 保留布尔语义，**help 并列消歧**，不改名 |
| D9e | 参数错误假成功 | **修**：与互斥 flag 对齐，显式 `exit 2` |
| D10 | 探测假占用 | 另批（N1 / 观察项 O1） |
| D11 | 版本与发布 | **1.4.0（minor）+ 同批 PyPI 发布**；features.md/CHANGELOG/`__version__`/spec.yaml 四同步 |
| D12 | 文案对齐 | 仅改文案：`_HELP`（cli.py:30）+ `skills/hs-cli/SKILL.md:30` + README.md/README.zh.md（如含该表述）；不新增 `--no-tail` |
| D13 | 编号与缓存命名 | **A**：本批起 cache/closed-loop 用 hm 新式命名（`{YYYYMMDD}-http-server.cli-HTTP-SERVER-CL{NNN}-{step}.json`），与 html-gen 对齐；skill 内 review 调度 `--usage-file` 命名范式同步 |

---

## 4 接口设计

### 4.1 `start` 的 `-p/--port`

```
hs [start] [path] [-p <port>] [-i <index>] [-d|-f] [-o] [--json|--url]
```

- **解析**：`parser.add_argument('-p', '--port', type=int, default=None)`（cli.py:182-188 区块），透传 `manager.start(..., port=parsed.port)`（cli.py:220-228）。
- **服务层**：`ServerManager.start(..., port: Optional[int] = None)`（server.py:78-80）；server.py:124 改为
  `default_port = port if port is not None else self.config.port`。
- **优先级**：CLI `-p` > `config.port`；两者都不满足时（`-p` 被占）**不漂移**（fail-closed）。
- **校验顺序**（全部先于任何进程/写盘副作用）：
  1. 非整数 / 缺值 → argparse 报错 → `exit 2`（D9e）。
  2. `port < 1024 or port > 65535` → `❌ Port must be between 1024-65535` + `exit 2`。
  3. 保留端口（8180/8181）→ `⚠️ <port> 为内置服务保留端口（dashboard/mcp），请换端口` + `exit 1`。
  4. 已被占用（`is_port_in_use(port)`）→ stderr：
     `⚠️ 端口 <port> 已被占用（PID <pid> / <path|未知服务>）` + `💡 换端口: hs . -p <other>；或关闭: hs kill <port>` + `exit 1`。
     占用者查询：先 `Registry().find(port=port)`（registry.py:89-96）取 path/pid；未命中再 `utils.get_pid_by_lsof(port)`（utils.py:172-191，macOS）；均无 → 「未知服务」。
- **幂等分支（D5）**：即使给了 `-p`，若路径已注册且存活（server.py:137-185 命中），仍走幂等：返回既有端口，
  并在 stderr 追加 `ℹ️ 路径已运行在 <port>（-p <N> 未生效；换端口请先 hs kill <port>）`；`--url/--json` 亦保持返回**既有**端口（不误导调用方）。
- **三入口覆盖**：路径 / 路径快捷方式 / bookmark 名均经 `main()` 的 REMAINDER 透传（cli.py:1781-1812），无需分别改。
- **顶层兜底（D8）**：`main()` 判定「`cmd` 既非命令、非 bookmark、非路径」时，若 argv 含 start 级 flag（`-p/--port/-i/--index/-o/--open/-d/--daemon/-f/--foreground`），则整体按 start 参数处理（等价于 cli.py:1781-1785 现有分支的推广），使
  `hs -p 8089 <path>`、`hs -p 8089` 均可用；不满足则该分支维持「Unknown command」现状（不放大兜底面）。

### 4.2 未识别参数告警 helper（D6）

新增 cli.py 内部函数（零依赖，纯 stderr）：

```python
def _warn_unknown_args(cmd: str, unknown: list, *, allow: tuple = (), hint_map: dict | None = None) -> list:
    """过滤白名单后，将未识别参数打印到 stderr；返回未识别清单（供测试断言）。"""
```

- **文案**：`⚠️ 未识别参数（已忽略）: -p 8089` + 引导行 `💡 指定端口请用: hs . -p <port>`。
  引导按「近形映射」给出：`-p/--port` → `hs . -p <port>`；`--prot/--portt/--prot` → 同上；
  `-i/--index` → `hs . -i <file>`；`-d/--daemon`、`-o/--open` → 对应 start 用法；未命中映射则不附引导，仅列参数。
- **白名单（按命令传入 `allow`）**：`start` 的 html 通配文件（cli.py:215 既有语义）+ 以 `.html/.htm` 结尾的 token；
  `kill/status` 的端口或路径位置参数；`search` 的关键词；`web add/update` 的 `--cmd` 值等。
- **覆盖站点**：cli.py 全部 `parse_known_args` 调用点（当前 22 处，含 `main()` 1771；`main()` 层因 REMAINDER 已兜住，
  只在其判定 branch 内做一次告警，避免与子命令层重复报同一参数）。
- **退出码不变**（D6）；**stdout / `--json` 信封零污染**（告警只走 stderr，与 `--url` 模式的既有约定一致）。
- **不引入 argparse 严格模式的理由**：`parse_known_args` 承载「多 html 文件取最近修改」等既有宽松语义（cli.py:212-219），
  改严格会破坏向后兼容；告警是兼容路径下的最小可见性修复。

### 4.3 `dashboard restart --port`（D9a）

- `_cmd_dashboard` 子命令分支（cli.py:568-571）当前只把 `sub` 传 `_manage_dashboard`；改为解析 `-p/--port`（默认 `None`）并透传。
- `_manage_dashboard('restart', port=...)`：`port is None` → 沿用 `entry['port']`（若未运行则回 8180，保持现行为）；
  显式给端口 → 用该端口（同样受 D2 保留端口规则约束：允许 8180 自身、拒绝 8181；非保留端口按 D1 校验占用）。
- `dashboard stop/status` 保持按 `name='dashboard'` 查 managed registry（无需端口参数）。

### 4.4 `hs web add/update --port`（D9b）

- 存储层 `services.py`：`ServiceStore.add/update` 增布尔字段 `use_port`（默认 False，破坏性最小；与 `use_domain` 同构）。
- 执行期（cli.py:1732-1737）：`use_port` 为真且 store 中记录了 `port` → `cmd_line = f"{cmd_line} --port {port}"`；
  与 `--domain` 的拼接顺序固定为 **domain 先、port 后**（`cmd --domain "<d>" --port <N>`），保证可预测。
- 新增 `--port <N>`（add/update 均支持）+ `--no-port`（update 清除）；`list/show` 显示 port 维度；
  `--json` 的 `cmd_effective` 体现注入后的完整命令。
- url 语义不变（固定端口建议填 `--url`，动态端口留空）；本项的端口不参与 start 的保留端口校验
  （被注册命令自管），仅做 1024-65535 区间校验。

### 4.5 `--json` 信封补 `port`（D7）

- `start` 成功（新建与幂等两条路径）与 `--json` 错误路径的 `data/error` 结构：
  `data` 增 `port: <int>`；既有键（`url/path/pid/started_at/index_page/stats/duration`）不动。
- 兼容性：纯 additive；消费方若严格校验键集合需同步（本仓 `mcp.py` 的 `_TOOL_MAP` 不消费 start 信封，无影响）。

### 4.6 退出码规范（G4）

| 码 | 语义 | 触发 |
|:--|:-----|:-----|
| 0 | 成功（含幂等命中、未知参数告警但命令成功） | 正常启动 |
| 1 | 运行期拒绝（保留端口 / 端口被占 / 路径不存在 / 服务未找到） | D1/D2 |
| 2 | 用法错误（非法值 / 缺值 / 越界 / 互斥 flag） | D4/D9e |

---

## 5 影响矩阵（基线 `1ff81e6`）

| 文件 | 改动点 | 行号基线 |
|:-----|:-------|:---------|
| `src/http_server_cli/cli.py` | start parser 加 `-p/--port` 与校验；未知参数 helper 与 22 处调用点接入；`_HELP` 文案（30 行区）；`main()` 顶层兜底（1781-1816）；`_manage_dashboard` 透传 port；`_web_add/_web_update` 加 `--port/--no-port`；执行期注入（1734-1736） | 30、181-192、195-197、215、220-228、565-585、676-685、1284-1330、1450-1520、1732-1740、1767-1816 |
| `src/http_server_cli/server.py` | `start(port=None)` 签名 + `default_port` 取值 + fail-closed 提示 + 幂等分支注记 + `--json/--url` 路径带 port | 78-80、124、136-185、195-206、275-301 |
| `src/http_server_cli/services.py` | `use_port` 字段 + CRUD/校验 | add/update/get/list |
| `http-server.cli.spec.yaml` | `port-allocation` / `cli-interface` / `service-lifecycle` 三个 capability 补 `-p` 场景（given/when/then） | 143、268、34 |
| `tests/test_server.py` / `test_cli.py` / `test_dashboard.py` / `test_web.py` | 新增用例（见 §7） | — |
| `README.md` / `README.zh.md` | 首屏用法补 `-p`；`-d` 描述对齐 | 双页同步 |
| `skills/hs-cli/SKILL.md` | 用法表补 `-p` + `-d` 文案对齐 | 30 行区 |
| `features.md` / `CHANGELOG.md` / `src/http_server_cli/__init__.py` | 功能条目 + 测试数 + 1.4.0 | 126（测试数） |
| `cache/`（本仓流程面） | 步 JSON 改新式命名（D13=A） | — |

---

## 6 文案对齐清单（D12，仅文案）

| 位置 | 现状 | 改为 |
|:-----|:-----|:-----|
| `cli.py:30`（`_HELP`） | `hs . -d                  后台运行（不占用终端）` | `hs . -d                  后台运行 + 前台 tail 日志（Ctrl+C 仅退出 tail）` |
| `cli.py:34`（快捷方式行） | `-d 后台` | `-d 后台（前台 tail 日志）` |
| `skills/hs-cli/SKILL.md:30` | `hs . -d                  后台运行（不占用终端）` | 同 `_HELP` |
| `README.md` / `README.zh.md` | 若有同表述则同改；并补一句「要零占用请用 `--url` / `--json`」 | 同 |
| `documents/url-flag-design-v2.0-20250715.md:216` | 同句 | **不改**（历史设计留档，按惯例不回改） |
| `http-server.cli.spec.yaml:54` | 「Ctrl+C 时日志查看停止，服务仍在后台运行」 | 不改（表述本就准确） |

---

## 7 测试清单

- `tests/test_server.py`
  1. `-p` 生效：`start(port=8099)` → registry 记录 8099、URL 含 8099（隔离 fixture，不触真实数据目录）。
  2. `-p` 被占 → fail-closed（假占用：预置 register 一条 8099 或直接 monkeypatch `is_port_in_use`）→ 返回失败 + 无新 registry 条目。
  3. 保留端口 8180/8181 → 拒绝。
  4. 区间：`-p 99` / `-p 70000` → 拒绝；`-p 0` → 拒绝。
  5. 未给 `-p` → 沿用 config.port 且保持 +1 漂移（回归保护）。
  6. 幂等 + `-p` → 返回既有端口 + stderr 注记（D5）。
  7. `--json` 信封含 `port`（新建/幂等两路径）。
- `tests/test_cli.py`
  8. `_warn_unknown_args`：白名单（`.html`）不报、`-p 8089` 报、近形 `--prot` 报并带引导。
  9. 顶层兜底：`main()` 分派把 `['-p','8099','.']` 交给 start（用 monkeypatch 拦截 `_cmd_start` 断言 args）。
  10. 退出码：非法 `-p` → 2（D9e 回归，覆盖 P4）。
- `tests/test_dashboard.py`
  11. `dashboard restart --port 8280` → `serve(port=8280)` 被调用；不带 `-p` → 沿用 entry 端口。
- `tests/test_web.py`
  12. `web add x --cmd 'true' --port 9001` → 存储 `use_port`；执行 `web x` → `cmd_effective` 含 `--port 9001`；`--no-port` 清除。
  13. `--port` 与 `--domain` 同时开启 → 顺序 `--domain "<d>" --port <N>`。
- 既有回归全量：`PYTHONPATH=src python3 -m pytest tests/ -q`（当前 tests/ 472 个 test 函数 / features.md 口径 490 用例）。

---

## 8 A 段断言表（可复跑，ops 核查用）

> 规范：命令 + 实测 + 断言；禁止恒真断言；web/UI 类不含（本批无 UI 变更）。

| # | 命令 | 断言 |
|:--|:-----|:-----|
| A1 | `hs /tmp/hs-cl003-demo -p 8099 -d --url` | 输出 `http://<domain>:8099/…`；`hs list --json` 该条 `port=8099` |
| A2 | 修前反证：`hs /tmp/hs-cl003-demo -p 8099 -d --url`（stash 修复后） | 修前输出非 8099（8080 或漂移端口）⇒ 判据非恒真 |
| A3 | `hs . -p 8080`（8080 在跑） | stderr 含「已被占用」+ 占用者 PID/路径；`echo $?` = 1 |
| A4 | `hs . -p 8180` / `hs . -p 8181` | stderr 含「保留端口」；exit 1 |
| A5 | `hs . -p 99`；`hs . -p abc` | 区间/非法提示；exit 2（且 **不得** 再出现 exit 0，P4 反证） |
| A6 | `hs . --prot 8080` | stderr 含「未识别参数」+ 引导行；stdout 无该文字；exit 0（D6） |
| A7 | `hs . -p 8099 -d --json \| python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["data"]["port"]==8099'` | 信封含 port（D7） |
| A8 | `hs -p 8099 /tmp/hs-cl003-demo -d --url` | 不再报 Unknown command；URL 端口 8099（D8） |
| A9 | 幂等 + `-p`：重复启动同目录另一端口 | stderr 注记「已运行在 8099」；URL 仍 8099（D5） |
| A10 | `hs dashboard restart --port 8280`（dashboard 未跑时先 `-p 8280 -d`） | managed registry 端口 = 8280 |
| A11 | `hs web add cl003-demo --cmd 'true' --port 9001 && hs web cl003-demo --no-probe --json` | `cmd_effective` 含 `--port 9001`（用完 `hs web remove cl003-demo` 清理） |
| A12 | `grep -rn "不占用终端" src/ skills/ README.md README.zh.md` | 0 命中（D12；历史文档 `documents/` 豁免） |
| A13 | `PYTHONPATH=src python3 -m pytest tests/ -q` | `0 failed`，通过数 ≥ 基线 490 |
| A14 | `hs version` / `grep version src/http_server_cli/__init__.py pyproject.toml CHANGELOG.md` | 四同步 = 1.4.0 |

---

## 9 文档/版本/发布同步清单（D11）

1. `__version__` 1.3.1 → **1.4.0**（`src/http_server_cli/__init__.py:28`）。
2. `CHANGELOG.md` 加 `## 1.4.0 (2026-09-22)`（Added/Breaking/Notes 三段）。
3. `features.md`：CLI 命令节补 `-p`；HTTP 服务节补 fail-closed/幂等语义；测试数同步；待定项清理。
4. `http-server.cli.spec.yaml`：`port-allocation` / `cli-interface` / `service-lifecycle` 补场景；`version` 字段 → 1.4.0。
5. `README.md` + `README.zh.md`：用法补 `-p` + `-d` 文案对齐。
6. `skills/hs-cli/SKILL.md`：同步；`hs prompt hs-cli` 输出即生效（新增篇目无需改 `EXPECTED_SKILLS`——篇目不增删）。
7. 发布：`bash scripts/release-pypi.sh -p -n`（dry-run，验证 Description 非空 + 链接）→ `python3 -m twine check dist/*` → `-p` 正式上传；PyPI 描述与 README 同源。
8. 流程面（D13=A）：本批步 JSON / 审计记录统一用 `{YYYYMMDD}-http-server.cli-HTTP-SERVER-CL003-{step}.json`；
   skill `http-server-ops` 内 review `--usage-file` 命名范式同步为新式。

---

## 10 观察项与出口判据

| # | 事项 | 事实 / 落点 | 处置 |
|:--|:-----|:-----------|:-----|
| O1 | 端口探测「假占用」 | `utils.is_port_in_use`（utils.py:118-132）裸 bind 无 SO_REUSEADDR；实测裸 bind FAIL(48) vs SO_REUSEADDR OK ⇒ 刚释放/有残留连接的端口被判占用，导致端口漂移 | **显式升级**：另批 + 评审（改探测语义影响全部端口判断：start 漂移、registry `_alive`、dashboard/mcp 可用性判断） |
| O2 | `hm loop next-code` 序列偏差 | 本仓返回旧式 `CL-SEC24`；`hm loop status HTTP-SERVER-CL002` 报「无匹配 JSON」（cache 旧式小写单文件命名） | **本批处置**（D13=A 改命名）→ 收尾复测；仍偏则出 hermes-manager 侧 handoff |
| O3 | 历史设计文档同句 | `documents/url-flag-design-v2.0-20250715.md:216` 含「不占用终端」 | 留档不回改（历史设计文档按惯例不追改） |

**遗留率**：升级项 1 / 本批步数（design·design-review·dev·ops-check·impl-audit·retro = 6）= 0.17。

---

## 11 风险与回滚

| 风险 | 影响 | 缓解 |
|:-----|:-----|:-----|
| `-p` 被占 fail-closed 改变既有脚本行为 | 用户脚本 `hs . -p X` 原本不存在（当时静默忽略）⇒ 无历史依赖；不构成回归 | 未给 `-p` 的路径零行为变更（A13 回归） |
| 未知参数告警在脚本中被误当错误 | 告警走 stderr 且退出码不变 | A6 断言 exit 0 + stdout 干净 |
| 退出码 2 引入（新语义） | 原「假成功 0」可能被脚本依赖 | 视为缺陷修复（P4）；CHANGELOG 明确标注 |
| `hs web --port` 改变已注册 cmd 行为 | 仅当显式 `--port` 时注入 ⇒ 存量条目 `use_port=False` 不受影响 | services.json 兼容（缺字段视为 False） |
| D13 改命名导致历史 glob 失配 | 历史文件仍按旧名保留（不重命名） | 新批起新名；hm 侧 `resolve_jsons` 按编号 glob，历史条目靠仍存的文件名解析（不改动历史） |

**回滚**：单批 commit 分组（feat/feat/fix/tests/docs），任一失败 `git revert` 该组；`-p` 面与告警面互不依赖，可分别回滚。

---

## 12 实施与门禁（Step 3–6 摘要）

| 步 | 产物 | 门禁 |
|:--|:-----|:-----|
| Step 3 dev | `feat@cli:`（-p 面 + 校验 + fail-closed）／`feat@cli:`（未知参数 helper + exit 2）／`feat@cli:`（dashboard restart + web --port）／`tests@cli:`／`docs@sync:`（help + README 双页 + 四同步） | 本地全量 pytest 零回归 |
| Step 4 ops 核查 | harness（A1–A14）+ 核查报告 `documents/review/http-server-cli-cl003-ops-verify-v1.0-20260922.md` | 全部断言 PASS |
| Step 5 实现审计 | review 侧报告 + review-log + `.review-level.yaml`；PASS → push（github only） | PASS / CONDITIONAL 回修 |
| Step 6 收尾 | 复盘 md + 清单 + 四件套 + O1/O2 登记 | `hm loop artifacts` 齐全 |
