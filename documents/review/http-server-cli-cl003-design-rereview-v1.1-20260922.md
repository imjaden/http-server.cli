# HTTP-SERVER-CL003 端口参数 + 未识别参数告警 + 周边端口面 — review报告 v1.1（rereview）

> 评审日期: 2026-09-22 · 评审人: Security Reviewer (review profile) · Level: L2（设计评审，只读）
> 被审对象: `documents/http-server-port-flag-design-v1.1-20260922.md`（设计 v1.1，389 行，commit `076d30b`；主体 `7d2b88c` + 勘误 `076d30b`）
> 基线: v1.3.1 · HEAD = `076d30b`（ahead 3，未 push）· `origin/main` = `1ff81e6`
> 上轮: CONDITIONAL PASS 82/100（F-1~F-5 必改 + F-6~F-14 记录 + 待确认 1/2/3）
> 结论: ✅ **PASS** · 评分: **96 / 100**（Rating A）· 性质: 设计 v1.1 一致性/完备性修订复审（无决策重选，无源码改动）

---

## 一、结论

设计 v1.1 对上轮 **5 处必改（F-1~F-5）全部闭合**、**9 处记录项（F-6~F-14）全部处置**、**3 处待确认（1/2/3）全部定案为 D14/D15/D16 且各有落点**。逐条核对源码 + 实测（本仓 HEAD 至 `origin/main` 之间仅 `documents/` 一处文件，`src/` 零变更），上轮实测事实沿用并快速复核成立。

剩余 1 处非阻断 🟡（D14 kill 半支缺函数级实现落点，详见 §六）与 2 处 🟢（§4.7 遗漏 line 185 成功出口枚举、§5 _web_list 起始行 9 行偏差），均不阻断实现，建议折入 Step 3 dev 一并落地。按治理规范判定 **PASS**，可进入 Step 3 实现。

---

## 二、数据验证（本轮复核，上轮事实沿用 + 快速复核）

| 验证项 | 命令 | 实测结果 | 结论 |
|:--|:--|:--|:--|
| 源码零变更 | `git diff --stat origin/main..HEAD` | 仅 `http-server-port-flag-design-v1.1-20260922.md` +389 行 | ✅ src/ 未动 |
| parse_known_args 站点 | `grep -c parse_known_args cli.py` | **22** | ✅ 沿用上轮，复核一致 |
| 测试基线 | `.venv/bin/python -m pytest tests/ --collect-only -q` | **490 collected** | ✅ 沿用上轮，复核一致 |
| 版本链漂移 | `__init__=1.3.1` · `CHANGELOG top=1.3.0` · `spec.yaml:2=1.3.0` | 三处漂移 | ✅ 与 §9 item 2 F-12 承诺一致 |
| kill 未注册端口现状 | `.venv/bin/python -m http_server_cli.cli kill 59999; echo $?` | `ℹ️ Port 59999 not registered` + **exit 0** | ✅ D14 依据成立（server.py:535 `return` None，cli.py:383-408 无 sys.exit） |
| status 未注册端口现状 | `... cli status 59999` | 同文案 + exit 0（查询命令） | ✅ §4.6 声明「status 保持 0」一致 |
| pyproject 版本 dynamic | pyproject.toml:7 | `dynamic = ["version"]`，无字面量 | ✅ A14 删 pyproject 正确 |

---

## 三、上轮必改（F-1~F-5）落点核对 — 全闭合 ✅

| # | 验证方法 | 结果 | 证据 |
|:--|:--|:--|:--|
| F-1 | 执行顺序链成文且与 server.py 事实一致；幂等先于 `-p` 校验 | ✅ PASS | §4.1 顺序链 0-4：argparse→路径存在性(126-134)→幂等(137-185)→`-p` 校验(替换 195)→启动(208-269)；两个反例说明（`-p 8099` 已运行该端口 / `-p 8180` 已运行别端口）成文于 §4.1 说明块；server.py 实测幂等检查(137-185)确在 find_available_port(194-206) 之前 |
| F-2 | §4.3 与 cli.py:610-616 / 678 逐字相符 | ✅ PASS | §4.3 现为「未运行 → `dashboard not running` 不启动（cli.py:610-616）；已运行 → 硬编码 `serve(port=8180,…)`（cli.py:678）」；源码逐字吻合（610-616 的 `not entry` → eprint 分支；678 的 `serve(port=8180, open_browser=False, daemon=True)`） |
| F-3 | A14 三条命令均可落地 | ✅ PASS | §8 A14 = `hs version` + `grep -n "1.4.0" __init__.py CHANGELOG.md` + `grep -n "^version:" spec.yaml`；`__init__.py:28` 有字面量、CHANGELOG 有 `## x.y.z` 头、spec.yaml:2 `version:` 均 grep 可达；pyproject 确为 dynamic 已删 |
| F-4 | 5 个 capability 与 spec.yaml 行号对应 | ✅ PASS | spec.yaml:34 `service-lifecycle` / 143 `port-allocation` / 268 `cli-interface` / 600 `dashboard` / 712 `json-output` 逐行吻合；§5/§9 item 4 均为 5 项 |
| F-5 | 三态表自洽 + 变更三处落地 | ✅ PASS | §4.6 表 exit 1 触发列现含「端口被占·保留端口·路径不存在·服务未找到」；§3 D14=改 1；§11 风险表加行「失败退出码 0→1」；§8 A15 断言；§9 item 2 CHANGELOG `### Changed` 承诺。表内「exit 1 触发」与「触发列」自洽 |

---

## 四、上轮记录项（F-6~F-14）处置核对 — 全处置 ✅

| # | v1.1 处置 | 结果 |
|:--|:--|:--|
| F-6 | §11 风险行「`-p` 占用检查继承 O1 假占用 → 刚释放端口假拒绝」+ §10 O1 补「并使 `-p` 占用检查可能假拒绝」 | ✅ |
| F-7 | §9 item 8 更正「skill 已含新式命名（SKILL.md:46-49），无需动作；跨仓/跨 profile 不在本仓范围」 | ✅ |
| F-8 | §6 + §10 O3 统一「`documents/` 全部历史留档豁免」，补列 `hs-cli-design-v1.0-20260624.md:506` | ✅ |
| F-9 | §4.4 明确 `use_port`(bool 默认 False) + `port`(int/None 默认 None) + `--no-port` 同清 | ✅ |
| F-10 | §4.1 顶层重组规则 `args = unknown + [cmd] + args` + 四形态实测表 + 有意排除 `-o/-d/-f` | ✅ |
| F-11 | §5 行号勘误（`_web_add`=1321-1408、`_web_list/_web_show`=1420-1527、`_web_update`=1574-1670） | ✅（见 §六-3 微小偏差） |
| F-12 | §9 item 2 CHANGELOG `### Notes` 补 1.3.1 patch 补注 + §8 A17 | ✅ |
| F-13 | §3 D15（维持 1024-65535）+ §4.1 区间/MAX_PORT 差异段 + §7 测试 4 `-p 20000` 守护 | ✅ |
| F-14 | §3 D16（保留端口双态）+ §4.1 双态文案 + §7 测试 3 + §8 A16 | ✅ |

---

## 五、新增内容核查（v1.1 新写）

### 5.1 §4.7 `ServerManager.start()` 返回契约 — ✅ PASS（1 🟢 记录）

- **失败路径枚举 121/134/204/229/238/247/256**：与 server.py 逐字吻合 —— 121（index_page 校验）、134（路径不存在）、204（端口全占用）、229/238/247/256（PermissionError/FileNotFoundError/OSError/Exception）；另有 116/129/199/224/233/242/251 为 url_only 分支已 `return False`，无需改。失败点无遗漏。
- **成功出口**：json 分支 314-315、daemon/foreground 之后、url 分支 281（保持）均成文。
- **两个调用方核实**：`cli.py:220`（`result = manager.start(...)`，本批处理）与 `dashboard.py:401`（`self.manager.start(path=path, daemon=True, json=False)`，**不接返回值**）——全仓仅此两处 `.start(` 调用（grep 复核，另有 dashboard.py:152/422 与 cli.py:1819 仅为 `ServerManager()` 实例化）。§4.5「仅两调用方」属实。
- 🟢 **遗漏 line 185**（非 url/json 幂等命中 `return` None → 应 `return True`）：合同语义「True=成功（含幂等命中）」+ §7 测试 7「幂等→True」已隐含，但成功出口枚举未点名 185。非阻断，建议补一行。

### 5.2 §4.6 退出码三态 + D14 — ✅ PASS（1 🟡 记录）

- 0/1/2 三态与 D14/D9e/D4/D1/D2 自洽；「status 保持 0（查询成功，无目标≠失败）」论证成立，与实测一致。
- **「服务未找到（hs kill 未注册端口）改 1」可达**：现状路径为 server.py:517-536 `kill()` 返回 None（未注册 531-536 eprint + `return`）→ cli.py:383-408 `_cmd_kill` 无 sys.exit → main 返回 → exit 0，实测确认 exit 0。改 1 可达、非恒真。
- 🟡 **D14 kill 半支缺函数级实现落点**（详见 §六-1）：有声明(§4.6)+断言(A15)+CHANGELOG(§9)+风险(§11)+Step 3 作用域(§12「退出码 1」)，但 §4.7 仅 start() 返回契约、§5 影响矩阵无 kill 退出码行、§7 无 kill 退出码单测。

### 5.3 §8 A15/A16/A17 — ✅ PASS

- A15（`hs /nonexistent; echo $?`、`hs kill 59999; echo $?` → 均 1）：可复跑、非恒真（修前均 0，实测确认）、与 §4.6/§9 CHANGELOG Changed 自洽。
- A16（`hs . -p 8180` dashboard 在跑/未跑 → 双态文案）：与 §4.4/§4.1 双态文案、§7 测试 3 自洽。
- A17（`grep -n "1.3.1" CHANGELOG.md` → 命中 1.4.0 条目内补注）：落地、与 §9 item 2 Notes 承诺自洽。

### 5.4 §7 测试 6/7/11 — ✅ PASS

- 测试 6 覆盖 F-1 两反例（已运行 + `-p` 同端口 → 幂等不报占用；已运行 + `-p 8180` → 幂等不报保留）。
- 测试 7 覆盖 §4.7 返回契约（不存在→False；成功/幂等/JSON/URL→True）。
- 测试 11 覆盖退出码（非法 `-p abc`→2；`hs <不存在路径>`→1）。注：未含 kill 退出码单测（见 §六-1）。

### 5.5 §5 行号抽查 — ✅ PASS（1 🟢 记录）

cli.py 30/34/181-192/195-197/215/220-231/565-571/676-685/1321-1408/1574-1670/1732-1740/1767-1816、server.py 78-80/124/126-134/136-192/195-206/275-301/314-318、services.py add(118-156)/update(167-199) 均与源码逐行吻合（见 §六-3 的 1420 偏差）。

### 5.6 D14/D15/D16 与待确认 1/2/3 对应 — ✅ PASS

| 待确认 | 定案 | 实现落点（结论 + 落点齐备） |
|:--|:--|:--|
| 1（路径/服务未找到退出码） | D14 改 1 | §4.6 表 + §4.7 返回契约(start) + A15 + §9 CHANGELOG + §11 风险 + §12 Step3 |
| 2（区间 vs MAX_PORT） | D15 维持 1024-65535 | §3 D15 + §4.1 差异段 + §7 测试 4 `-p 20000` |
| 3（保留端口提示） | D16 双态 | §3 D16 + §4.1 双态文案 + §7 测试 3 + §8 A16 |

---

## 六、剩余风险 / 新发现（均非阻断）

| # | 级别 | 发现 | 落点 | 最小修法 |
|:--|:--|:--|:--|:--|
| R-1 | 🟡 | D14「服务未找到（`hs kill <未注册端口>`）改 1」有声明+断言+CHANGELOG+风险+Step3 作用域，但无**函数级实现落点**：§4.7 仅 start() 返回契约；§5 影响矩阵无 kill 退出码行；§7 无 kill 退出码单测。现状 server.py `kill()` 返回 None、cli.py `_cmd_kill`(383-408) 无 sys.exit | §4.7 / §5 / §7 | §4.7 补一句「kill() 同构返回 True/False（未注册/未找到 → False）」或 cli `_cmd_kill` 未命中时 `sys.exit(1)`；§5 补 kill 行；§7 补一条 kill 未注册 → exit 1 单测。建议折入 Step 3 `fix@cli` 一并落地 |
| R-2 | 🟢 | §4.7 成功出口枚举遗漏 server.py:185（非 url/json 幂等命中 `return` None → 应 `return True`）；合同「含幂等命中」+ §7 测试 7 已隐含 | §4.7 | 成功出口枚举补 185，或保留「等」字并明确幂等命中同属成功出口 |
| R-3 | 🟢 | §5 `_web_list/_web_show` 标注「1420-1527」，实为 `def _web_list` 起于 1411（1420 为 except SystemExit 行），9 行偏差系沿用 F-11 建议值 | §5 | 可改 1411-1527（非阻断，行号近似准确） |

**遗留率**：升级项 0 / 非阻断 3。无 🔴、无决策级缺口，不影响 Step 3 开工。

---

## 七、维度评估

- **合理性**: 顺序链（路径→幂等→`-p` 校验→启动）、fail-closed、幂等优先、CLI>config 不回写、保留端口硬拦四原则边界清晰，两个 F-1 反例说明到位。评分 10/10。
- **严格性**: F-1~F-5 全部闭合、F-6~F-14 全处置、待确认 1/2/3 全定案；仅存 R-1（kill 实现落点未函数化）一处 🟡。评分 9/10。
- **安全性**: 无新增攻击面（`-p` int 参数无注入；告警 stderr-only；web `--port` 注入沿用 `--domain` 既有 shell 边界，SEC-023-1 已拦）。评分 9/10。

---

## 八、评分与结论

- **总评**: 96 / 100（Rating A）
- **结论**: ✅ **PASS** — F-1~F-14 全闭合，D14/D15/D16 定案且落点齐备，可进入 Step 3 实现。R-1（🟡）+ R-2/R-3（🟢）折入 Step 3 一并落地，不阻断。
- **下一步**: 出实现 prompt（Step 3 dev），本地全量 pytest 零回归后走 Step 4 ops 核查（A1–A17）。
