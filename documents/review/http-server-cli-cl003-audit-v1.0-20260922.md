# http-server.cli CL003 实现审计报告 v1.0

- 件号：`documents/review/http-server-cli-cl003-audit-v1.0-20260922.md`
- 设计依据：`documents/http-server-port-flag-design-v1.1-20260922.md`（v1.1，rereview 已 PASS 96/100）
- 被测对象：`src/http_server_cli/{cli.py,server.py,services.py}`（commit `3919da7`）· `tests/test_port_flag.py`（45 新增）+ `tests/test_web.py`（1 更新，commit `484e0ec`）· 四同步（commit `8f041cd`）· ops 核查产物（commit `231452e`）
- 审计基线：HEAD `231452e`，本地 ahead 4（未 push），工作树 clean
- 审计人：Security Reviewer（review profile）· 日期：2026-09-22
- 环境：macOS 26.6.2 · `hs` = conda py3.12 editable 安装（指向本仓 `src/`）

## 0 结论（前置）

**PASS（95/100，Rating: A）** —— 无阻断性缺陷、无实现与设计方向性冲突。核心 `-p/--port` 面在全部已文档化形态下实测成立，四同步以实测为准（非 commit subject）逐一核对为真。

非阻断发现（详见 §三）：
- **AUD-1 🟡 P2**：顶层 `hs -i <在 CWD 存在的文件> -p <port> <dir>` 会走「路径快捷方式」分支而非 D8 重组，导致 `-i` 被丢弃、`<dir>` 被当「未识别参数」忽略、服务落在 CWD 而非 `<dir>`（端口仍正确）。属设计 D8「非存在路径/globs」显式收窄的边界，实现与设计一致，**非实现偏差**，建议随 O1 另批处置。
- **AUD-2 🟢**：`hs web add/update --port 99` 与 `--port 9001 --no-port` 拒绝时 rc=0（软拒绝），与 `hs start -p 99` 的 rc=2 口径不一致（设计 §4.4/§4.6 未对 web 子命令强制退出码，属既有 web 校验风格延续）。
- **AUD-3 🟢**：「stale registry entry」清理分支在服务启动后 bind 前（~50ms）误判并**只删登记、不 kill 进程**，可留孤儿（既有行为，O1 同源；审计自测复现，已清理 PID 37510）。

---

## 一、数据验证（独立复算，不采信 ops）

| 项 | 实测 | 判定 |
|:--|:-----|:--|
| git HEAD | `231452e`（ahead 4，工作树 clean） | ✅ 与基线一致 |
| 全量回归 | `PYTHONPATH=src python3 -m pytest tests/ -q` → **535 passed in 1.56s**（0 failed） | ✅ |
| `hs version` | `http-server v1.4.0` | ✅ |
| 三处版本 | `__init__.py:28` / `CHANGELOG.md:3` / `spec.yaml:2` 均 `1.4.0` | ✅ |
| spec.yaml | `yaml.safe_load` 通过，17 capability，`version: 1.4.0` | ✅ |
| 审计前 registry/services 快照 | registry 11 条 · services 11 条（存量 services 缺 `use_port/port` 字段 ⇒ 兼容路径成立） | ✅ 记录 |
| 审计后 registry/services 快照 | 11/11 条不变，cl003 残留 0；仅 8085 条 `last_access_at` 自然漂移（运行中服务活跃字段，非审计写入） | ✅ 无污染 |

---

## 二、逐项审计（实证命令 + 实测输出 + 判定）

### 1. `-p/--port` 面 + 不回写 config（D3）

- 读源码：`cli.py:245-246` `-p/--port`（type=int）+ `cli.py:239` `allow_abbrev=False`；`cli.py:286` 透传 `port=parsed.port`；`server.py:161` `default_port = port if port is not None else self.config.port`（不回写 config）。
- 实证：`hs /tmp/…/item1 -p 8099 -d --url` → rc=0，`http://jaden.local:8099`；随后 `config.json` 端口仍 `8080`。
- **判定：✅**。注意 commit body 写 `default_port = port or config.port`，实为 `port if port is not None else config.port`（后者更严谨，与设计 §4.1 一致；commit message 措辞不精确，无功能影响）。

### 2. 执行顺序链（F-1：幂等先于 `-p` 校验）

- 反例 1（同路径已运行 8098，再 `-p 8098`）：rc=0，返回 8098，**无**「已被占用」。
- 反例 2（同路径已运行 8098，再 `-p 8180`）：rc=0，返回 8098，stderr `ℹ️ 已运行在 8098（-p 8180 未生效；如需换端口请先 hs kill 8098）`，**无**「保留端口」。
- **判定：✅**（`server.py:173-234` 幂等分支位于 `-p` 校验块 `:236-269` 之前）。

### 3. fail-closed 三态（D1/D2/D4/D15/D16）

| 用例（独立目录） | 实测 | 判定 |
|:--|:--|:--|
| `-p 8401`（8401 被本审计服务占用） | rc=1，`端口 8401 已被占用（PID 37539 / /private/tmp/…/item3-occ）` + 换端口提示 | ✅ |
| `-p 8180`（dashboard 空闲态） | rc=1，`8180 为内置服务保留端口（dashboard=8180 / mcp=8181），如需启动请用 hs dashboard -p 8180` | ✅ 双态-空闲 |
| `-p 8180`（dashboard 在 8180 运行） | rc=1，`8180 为内置服务保留端口（dashboard 正在使用，PID 38562），请换端口` | ✅ 双态-占用 |
| `-p 99` | rc=2，`❌ Port must be between 1024-65535` | ✅ |
| `-p abc` | rc=2，`error: argument -p/--port: invalid int value: 'abc'` | ✅ |
| `-p 20000` | rc=0，`http://jaden.local:20000`（直绑越 MAX_PORT=10000） | ✅ D15 |

**判定：✅**（三态退出码 1/1/2 + 双态文案 + D15 直绑越界全部实测成立）。

### 4. 退出码三态与返回契约（D9e/D14）

| 命令 | 实测 | 判定 |
|:--|:--|:--|
| `hs /nonexistent-cl003-xyz` | rc=1 | ✅ |
| `hs kill 59999` | rc=1，`ℹ️ Port 59999 not registered` | ✅ |
| `hs status 59999` | rc=0（查询成功） | ✅ |

- 源码：`server.py` 各失败分支显式 `return False`（路径不存在 `:171` / 端口不可用 `:269` / 保留端口 `:259` / 启动异常 `:306-333`）；成功出口显式 `return True`（url `:358` / json `:393` / daemon-foreground 后 `:424` / 幂等 `:227`）；`kill()` 未注册/空参 `return False`（`:607/:619`）。cli 侧 `_cmd_start:294-295` `if result is False: sys.exit(1)`、`_cmd_kill:464-466` `if not ok: sys.exit(1)`。
- **判定：✅**。

### 5. 解析报错不再被吞（P4）

- `grep -n "parse_known_args\|except SystemExit" cli.py`：唯一 `except SystemExit` 位于 helper `_parse_known_args:66` 内（转 exit 2）；22 处 `parse_known_args` 全部经 helper（`main():1860` 用裸 `parser.parse_known_args()`，其 parser 仅 `command?`+`REMAINDER`，无报错路径，属设计 D6 注明的豁免）。
- 实证：`hs dashboard restart -p abc` → rc=2，`error: argument -p/--port: invalid int value: 'abc'`。
- **判定：✅**。

### 6. 未识别参数告警（D6）

| 命令 | 实测 | 判定 |
|:--|:--|:--|
| `hs <dir> --prot 8080 -p 8093 -d --url` | rc=0；stderr `未识别参数（已忽略）: --prot 8080` + `💡 指定端口: hs . -p <port>`；stdout 仅 URL 无告警文字 | ✅ |
| `hs list --prot` | rc=0；stderr 告警；stdout 服务列表无告警 | ✅ |
| `hs <dir> --json --prot x` | rc=0；JSON 信封可解析（`data.port=8093`），stderr 告警 | ✅ |
| `hs a.html b.html -p …`（allow_html 白名单） | **无**「未识别参数」告警（仅正常端口/启动路径） | ✅ |

- **判定：✅**（仅 stderr、退出码不变、stdout/JSON 零污染、allow_html/allow_positional 白名单不误报）。

### 7. 顶层归位（D8）

| 命令 | 实测 | 判定 |
|:--|:--|:--|
| `hs -p 8096 -d --url <dir>` | rc=0，`http://jaden.local:8096`，无 Unknown command | ✅ |
| `hs -i index.html -p 8095 -d --url <dir>` | rc=0，`:8095`，无 Unknown command，**但** stderr `未识别参数（已忽略）: <dir>` | 🟡 见 AUD-1 |
| `hs 8089` | rc=1，`❌ Unknown command: 8089` + help | ✅ |

- **判定：🟡 部分通过**。`-p` 单形态与裸数字归位正确；`-i <在 CWD 存在的文件>` 组合形态触发 AUD-1（详 §三）。

### 8. `--json` 信封 data.port（D7）

- 新建：`hs <dir> -p 8097 -d --json` → `data.port=8097`。
- 幂等：同目录再 `--json` → `data.port=8097`（`server.py:197-206` 与 `:363-372` 两条路径均带 port）。
- **判定：✅**。

### 9. dashboard restart --port（D9a）

- `hs dashboard -p 8280 -d` → status port=8280；`restart --port 8290` → status port=8290（修 8180 硬编码）；`restart`（无 port）→ status port=8290（沿用 entry 端口）。
- **判定：✅**（`cli.py:618-626` 子命令透传 `-p/--port` + 越界 exit 2；`_manage_dashboard:741` `restart_port = requested_port if ... else entry.get('port')`）。

### 10. `hs web --port / --no-port`（D9b）

| 命令 | 实测 | 判定 |
|:--|:--|:--|
| `web add cl003-audit --cmd true --port 9001` | `show --json` → `use_port:true, port:9001` | ✅ |
| `web cl003-audit --no-probe --json` | `cmd_effective: "true --port 9001"` | ✅ |
| `web update cl003-audit --no-port` | `use_port:false, port:null`（同清） | ✅ |
| `web add … --port 99` | 拒绝（无注册 + stderr `1024-65535`），rc=0 | ✅（拒绝路径）|
| `web add … --port 9001 --no-port` | 拒绝（`mutually exclusive`），rc=0 | ✅（拒绝路径）|

- 源码：`services.py` `use_port/port` 字段 + `validate_port`（1024-65535）+ 存量缺字段兼容（`get().get('use_port')` → None）；注入顺序 domain 先 port 后（`cli.py:1820-1825`）。
- **判定：✅**（软拒绝 rc=0 记 AUD-2，见 §三）。

### 11. 四同步以实测为准（版本非 v1.2.x）

- `hs version` = v1.4.0；`__init__.py`/CHANGELOG/spec.yaml 三处 1.4.0；README ×2 `hs version # → http-server v1.4.x`（非 v1.2.x）。
- **判定：✅**。

### 12. `-d` 文案如实化（D12）

- `grep -rn "不占用终端" src/ skills/ README.md README.zh.md` → **0 命中**（rc=1）；`documents/` 命中 10 处（留档豁免，O3 确认）。
- **判定：✅**。

### 13. spec.yaml 补域（5 capability + version）

- `port-04`（6 场景）/ `lifecycle-05`（4）/ `cli-04`（4）/ `dash-05`（4）/ `json-03`（2）均已补；`version: 1.4.0`；YAML 可解析。
- **判定：✅**。

### 14. 测试覆盖对齐设计 §7

- `tests/test_port_flag.py` 414 行覆盖：`-p` 绑定/json/幂等信封/缺路径/无 `-p` 漂移/`-p 20000`、fail-closed 三态、顺序链两反例、kill 契约、未识别参数 helper、顶层重组、退出码 4 例、dashboard restart、web `--port` 系列。全量 535 passed 复跑通过。
- **判定：✅**（注：顶层重组用例 `test_leaked_index_value_reaches_start` 用 `no-such-cl003.html` 规避了 AUD-1 的「值在 CWD 存在」场景，故未捕获该边界，见 AUD-1）。

### 15. CHANGELOG 语义承诺与实现一致

- `### Changed`「退出码 0→1」「参数错误 exit 2」与实测（§4/§5）一致；`### Notes` 含 `1.3.1（2026-09-04）…未单列 CHANGELOG 条目（F-12）`（`CHANGELOG.md:24`，位于 1.4.0 条目内）。
- **判定：✅**。

### 16. 全量回归

- `PYTHONPATH=src python3 -m pytest tests/ -q` → **535 passed，0 failed**（≥ 490）。
- **判定：✅**。

### 17. 观察项未被顺手改坏（O1）

- `git show --stat` 三笔实现 commit 仅动 cli.py / server.py / services.py / test_port_flag.py / test_web.py / 文档；**`utils.py` 零变更**。复核：`is_port_in_use`（裸 bind，无 SO_REUSEADDR，`utils.py:118-132`）、`find_available_port`（MAX_PORT=10000，`:166`）、`eprint`（写 stdout，无 `file=`，`:33-38`）均保持原样。
- **判定：✅**。

### 18. 真实数据目录无污染

- 审计前：registry 11 条 / services 11 条。审计后：11/11 条不变，cl003 残留 0；唯一差异为 8085 条 `last_access_at` 由运行中服务自然漂移（`17:44:08`→`17:46:04`，非审计写入）。
- 审计过程临时服务/条目全部清理；复现 AUD-3 时产生的孤儿进程 PID 37510 已 `kill` 并确认 8098 端口释放、无 cl003 runner 残留。
- **判定：✅**（两次快照差异已写明：仅 1 处活跃字段自然漂移）。

### 19. 设计 §13 偏差承认如实性

- §13.2「6 组 → 实际 3 笔」与 `git log`（feat@cli `3919da7` / tests@cli `484e0ec` / docs@sync `8f041cd`）一致。
- §13.1「`eprint` 实写 stdout，故新代码用 `print(file=sys.stderr)`」与 `utils.py:33-38`（eprint 无 file=）一致。
- **判定：✅**（偏差承认如实，无必改项）。

---

## 三、安全事项（findings）

| # | 级别 | 标题 | 落点 | 处置 |
|:--|:--|:--|:--|:--|
| AUD-1 | 🟡 P2 | 顶层 `-i <在 CWD 存在的文件>` + `-p` + `<dir>` 组合时，`main()` 的「路径快捷方式」分支（`cli.py:1898-1900`，`os.path.exists(cmd)`）先于 D8 重组分支（`cli.py:1905-1907`）触发 ⇒ `-i`（在 `unknown`）被丢弃、`<file>` 被当 path、`<dir>` 被当「未识别参数」忽略 ⇒ 服务落在 CWD 而非 `<dir>`（端口仍正确） | `cli.py:1898-1907` | 记录 + 建议随 O1 另批（见下） |

**AUD-1 详证**：本仓根目录存在 `index.html`（29387 B）。`hs -i index.html -p 8095 -d --url /tmp/xxx` 实测：rc=0、`:8095`，stderr `⚠️ 未识别参数（已忽略）: /tmp/xxx`；Python 追踪确认 `_cmd_start` 收到 `['index.html','-p','8095','-d','--url','/tmp/xxx']`（`-i` 已丢），`path='index.html'` → 服务目录 = CWD。

**性质判断**：非实现偏差。设计 D8/F-10 显式把重组规则收窄为「cmd 既非内置命令、非 bookmark、也**非存在的路径/globs** 时」，故 `index.html` 在 CWD 存在时走路径快捷方式分支是**设计既定行为**。但设计 §4.1 重组表的三条 `-i` 示例全部用「CWD 不存在」的文件名（`a.html`/`no-such`），未记录此边界；单测用 `no-such-cl003.html` 规避、ops A8-2 仅断言端口，均未捕获。**建议**：作为边界缺陷随 O1 另批评审（可选方向：路径快捷方式分支增加 `'-i' in unknown` 时仍走 D8 重组，或至少在 features/help 注明该限制）。

| AUD-2 | 🟢 | `hs web add/update --port 99` / `--port 9001 --no-port` 拒绝时 rc=0（stderr + 不注册），与 `hs start -p 99` rc=2 口径不一致；设计 §4.4 未对 web 子命令强制退出码，与既有 web name/cmd/url 校验同为软拒绝 | `cli.py:1429-1442,1702-1715` | 记录 |
| AUD-3 | 🟢 | 「stale registry entry」清理（`server.py:229-234`）只 `registry.remove` 不 kill 进程：服务启动后 bind 前（~50ms）`is_port_in_use` 为 False ⇒ 幂等检查 `is_process_alive AND is_port_in_use` 误判 stale ⇒ 留孤儿进程（无登记，`hs kill` 不可达） | `server.py:175-234`（既有） | 记录，O1 同源，建议并入 O1 |

---

## 四、评分

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 实现与设计一致性（§一 1–10） | 通过 | 核心 `-p` 面、顺序链、fail-closed、退出码、dashboard/web 端口面全部实测成立；仅 AUD-1 属设计显式收窄边界（非偏差） |
| 文档/规格同步真实性（§二 11–15） | 通过 | 四同步以实测核对为真，无「假同步」 |
| 回归与边界（§三 16–19） | 通过 | 535 passed 零回归；utils.py 零变更；数据目录无污染；§13 偏差承认如实 |
| 安全事项 | 1 🟡 + 2 🟢 | 均非阻断、无方向性冲突 |

**总分 95 / 100（Rating: A）**

---

## 五、结论

**PASS**。实现忠实落地设计 v1.1 全部 D 项，`hs start -p/--port` 三态 fail-closed、执行顺序链、退出码三态、dashboard/web 端口面、未识别参数告警、顶层归位（`-p` 形态）均已实测成立；四同步以实测为准、无「假同步」；全量 535 测试零回归；真实数据目录审计前后无污染。

遗留（非阻断，建议随 O1 另批）：AUD-1（顶层 `-i <CWD 存在文件>` + `-p` 边界缺陷）、AUD-2（web 软拒绝 rc=0 口径）、AUD-3（stale-entry 清理留孤儿，O1 同源）。
