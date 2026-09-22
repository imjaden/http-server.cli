# HTTP-SERVER-CL003 端口参数 + 未识别参数告警 + 周边端口面 — review报告 v1.0

> 评审日期: 2026-09-22 · 评审人: Security Reviewer (review profile) · Level: L2（设计评审，只读）
> 被审对象: `documents/http-server-port-flag-design-v1.0-20260922.md`（设计 v1.0）
> 基线: v1.3.1 · HEAD = `7f3376d`（docs@design，未 push）· `origin/main` = `1ff81e6`
> 结论: ⏳ CONDITIONAL PASS · 评分: 82 / 100（Rating B+）· 性质: 设计文档一致性/完备性修订（无决策重选）

---

## 一、结论

设计 v1.0 的**根因定位（P1–P4）、决策定案（D1–D13）、接口设计、测试清单**均经源码 + 实测逐条核对，**实质正确**：
P1（`parse_known_args` 静默丢弃）、P2（裸 bind 无 SO_REUSEADDR + `allow_reuse_address=1`）、P3（`-d` 服务侧生效 + 前台 `tail -f` + `_HELP` 文案不符）、P4（`except SystemExit: return` 致 EXIT=0）全部实测复现成立；
D1–D13 决策自洽、无互相矛盾，用户口径「全采推荐」得到完整覆盖。

但存在 **5 处必须在实现前修订的文档一致性/完备性缺口**（F-1~F-5，均为「设计文档需补写/勘误」，不涉及决策重选），
另有 9 处非阻断记录项（F-6~F-14）。按治理规范：**不回推决策，回 ops 出设计 v1.1 修复后走 rereview**。

---

## 二、数据验证（实测证据，只读）

| 验证项 | 命令 | 实测结果 | 结论 |
|:--|:--|:--|:--|
| P4 假成功 | `hs dashboard -p abc; echo $?` | 打印 `error: argument -p/--port: invalid int value: 'abc'`，`exit=0` | ✅ P4 成立 |
| P2 SO_REUSEADDR | `python3 -c "import http.server;print(http.server.HTTPServer.allow_reuse_address)"` | `1` | ✅ P2 成立 |
| 附带发现 D8 | `hs -p 8089` | `❌ Unknown command: 8089`，`exit=1` | ✅ D8 成立 |
| 路径不存在退出码 | `hs /nonexistent; echo $?` | 打印错误，`exit=0`（非 url/json 均 0） | ⚠️ 见 F-5 |
| parse_known_args 站点 | `grep -c parse_known_args cli.py` | **22** 处 | ✅ 与设计「22 处」一致 |
| 测试基线 | `PYTHONPATH=src python3 -m pytest tests/ --collect-only -q` | **490 tests collected**（`def test_` = 472） | ✅ A13 基线 490 与 features.md:126 一致 |
| `hs version` | `hs version` | `http-server v1.3.1` | ✅ 基线一致 |
| `_HELP` 文案 | cli.py:30 | `hs . -d  后台运行（不占用终端）` | ✅ P3 文案侧成立 |

版本链现状（待确认既有漂移）：`__init__=1.3.1`（2026-09-04）· `CHANGELOG top=1.3.0` · `spec.yaml:2 version=1.3.0`（见 F-13）。

---

## 三、审计项逐条结论

| # | 审计项 | 结论 | 依据 |
|:--|:--|:--|:--|
| 1 | 根因定位 P1–P4 | ✅ PASS | 四条均源码 + 实测吻合（见上表） |
| 2 | `-p/--port` 接口完备性 | ⚠️ COND | 语法/优先级/三入口/兜底正确；但**校验顺序链未定义**（F-1）、D8 重组细节不精确（F-10）、区间与 MAX_PORT 差异未注明（F-13） |
| 3 | D1–D13 一致性与完整性 | ⚠️ COND | 无互相矛盾；但 **D5「幂等优先」vs §4.1 校验顺序** 的先后关系未解（F-1） |
| 4 | 未识别参数告警设计 | ✅ PASS | 22 站点实测；白名单覆盖 html 通配/kill·status 位置参数/search 关键词/web --cmd；stderr-only + 退出码不变 + main 层一次告警论证自洽 |
| 5 | 周边改动 dashboard/web | ⚠️ COND | (a) `dashboard restart` 现状描述「未运行回 8180」与源码不符（F-2）；(b) `use_port` 存储兼容 + domain 先/port 后注入自洽，但存储字段未完全明确（F-9） |
| 6 | 测试清单覆盖度 | ✅ PASS | 十三条覆盖 fail-closed/保留端口/区间/幂等/JSON port/顶层兜底/退出码 2/dashboard/web + 未给 `-p` 的 +1 漂移回归保护（§7-5）；conftest 隔离明确 |
| 7 | A 段断言可复跑性 | ⚠️ COND | A1–A13 均「命令 + 可观测 + 非恒真」；A2 修前反证成立；A13=490 与 features 一致；**A14 四同步 grep 无法落地**（F-3） |
| 8 | 文档/版本/发布四同步 | ⚠️ COND | 四同步清单完整；**A14 遗漏 spec.yaml/features**（F-3）；版本链既有 1.3.1 漂移未承认（F-12） |
| 9 | 观察项与出口判据 | ✅ PASS | O1 另批理由充分（非必要前置，但广波及）；O2 处置路径正确（D13 恢复）；O3 留档；遗留率 1/6=0.17 成立 |
| 10 | 风险与回滚 | ✅ PASS | fail-closed/退出码 2 风险说明充分；分组 commit 可回滚；services.json 兼容风险已列 |
| 11 | D13 命名口径 | ⚠️ COND | 新式命名 `HTTP-SERVER-CL{NNN}` 与 http-server-ops skill 口径一致；但 §9 item 8 的 skill 同步已满足且属跨仓（F-7） |
| 12 | 治理口径（spec capability） | ⚠️ COND | `spec.yaml:34/143/268` 三 capability 匹配；**遗漏 json-output（port 字段）+ dashboard（restart --port）**（F-4） |
| 13 | 范围控制 | ✅ PASS | §2.2 非目标 N1–N6 与 D1–D13 自洽，无「非目标但实际做了」 |

---

## 四、维度评估

- **合理性**: 根因到方案的因果链完整，fail-closed / 幂等优先 / CLI>config 不回写 / 保留端口硬拦四原则边界清晰。评分 9/10。
- **严格性**: 校验顺序链（路径→幂等→保留/占用）、退出码三态、A14 四同步落地存在缺口（F-1/F-5/F-3）。评分 7/10。
- **安全性**: 无新增攻击面（`-p` 为 int 参数无注入；未识别参数告警仅 stderr 零污染；web `--port` 注入沿用 `--domain` 既有 shell 边界，SEC-023-1 已拦）。评分 9/10。

---

## 五、发现清单

### 必改（阻断实现，5 条 — 设计 v1.1 修复后 rereview）

**F-1 🟡 校验顺序链未定义（审计项 2/3）**
设计 §4.1「校验顺序（1 非整数→2 区间→3 保留端口→4 占用）」与「幂等分支 D5（server.py:137-185）」的先后关系未明确，且未说明路径存在性检查（server.py:126）的相对位置。若按字面「校验先于一切」实现，将产生两个错误行为：
- `hs . -p 8099`（该路径已运行在 8099）→ 幂等命中前先触发占用检查，误报「8099 已被占用」而非幂等返回；
- `hs . -p 8180`（该路径已运行在别端口）→ 误报「保留端口」而非幂等返回。

最小修法：§4.1 增补一条明确的执行顺序链 —— **路径存在性检查（126）→ 幂等检查（137）→ 幂等命中则返回既有端口并忽略 `-p`（D5）→ 未命中才做 `-p` 非整数/区间/保留端口/占用校验（替换 195 行 `find_available_port`）**，并把 §4.1 首句「全部先于任何进程/写盘副作用」改为「校验均为只读，且排在幂等命中判断之后」。

**F-2 🟡 `dashboard restart` 现状描述失实（审计项 5a）**
设计 §4.3「port is None → 沿用 entry['port']（若未运行则回 8180，保持现行为）」与源码不符：
- 现状 `_manage_dashboard` 对 restart 在**未运行时返回 `dashboard not running` 且不启动**（cli.py:610-616），并非「回 8180」；
- 现状 restart **硬编码 `serve(port=8180, …)`**（cli.py:678），并不沿用 entry['port']（这正是 D9a 要修的）。

最小修法：改写 §4.3 为「现状 restart 未运行 → `dashboard not running`（保持）；已运行 → 硬编码 8180（bug，D9a 修）。新行为：`restart --port N` 用 N（受 D2 约束）；`restart` 无 `--port` → 沿用 `entry['port']`；未运行仍返回 `dashboard not running` 不启动」。

**F-3 🟡 A14「四同步」grep 无法落地（审计项 7/8）**
A14 命令为 `grep version src/http_server_cli/__init__.py pyproject.toml CHANGELOG.md`，但：
- `pyproject.toml` 版本为 `dynamic = ["version"]`（无版本字面量），grep 永无 1.4.0 命中；
- 遗漏 `spec.yaml` 的 `version` 字段与 `features.md`（真正需要同步的对象）；
- `hs version` 与 `__init__.py` grep 冗余。

最小修法：A14 改为 `hs version`（打印 1.4.0）+ `grep -n "1.4.0" src/http_server_cli/__init__.py CHANGELOG.md` + `grep -n "^version:" http-server.cli.spec.yaml`（= 1.4.0），删除 pyproject.toml 项。

**F-4 🟡 spec.yaml 补 capability 遗漏（审计项 12）**
设计 §5/§9 仅补 `port-allocation`/`cli-interface`/`service-lifecycle` 三 capability，但：
- D7（start `--json` 增 `port` 字段）应补 `json-output` capability（spec.yaml:712）场景；
- D9a（dashboard restart --port）应补 `dashboard` capability（spec.yaml:600）场景。

最小修法：§9 item 4 清单扩为「port-allocation / cli-interface / service-lifecycle / json-output（start 信封含 port）/ dashboard（restart --port）」，并同步 features.md Web 节/服务管理节的 `--port` 描述。

**F-5 🟡 退出码表内部不一致 + 隐含行为变更未标注（审计项 6/§4.6）**
§4.6 exit 1 语义列「路径不存在 / 服务未找到」，但「触发」列仅 D1/D2（端口占用/保留）；且实测现状 `hs /nonexistent` 返回 **exit 0**（server.py:126-134 仅 `return`，非 url/json 均 0）。该表隐含「路径不存在 0→1」的行为变更，未在 §11 风险表或 CHANGELOG 计划（§9 item 2 的 Breaking 段）中显式标注。

最小修法：二选一 —— (a) 明确「路径不存在/服务未找到退出码 0→1」为新变更，补入 §11 风险表 + CHANGELOG `### Changed`；(b) 若保持现状 exit 0，则从 exit-1 行移除这两项（仅保留保留端口/占用，触发列 D1/D2 自洽）。

### 非阻断（记录项，9 条 — 可同批 v1.1 一并勘误）

**F-6 🟢 O1 假占用耦合未标注（审计项 9）**：`-p` 占用检查用 `is_port_in_use`（裸 bind 无 SO_REUSEADDR，O1 已另批），故 `hs . -p <刚释放端口>` 会假拒绝（实际 HTTPServer 可绑）。建议 §11 补一行「`-p` 占用检查继承 O1 假占用缺陷，刚释放端口可能假拒绝，待 O1 闭环」。

**F-7 🟢 http-server-ops skill 同步已满足且属跨仓（审计项 11/13）**：§9 item 8 称「skill http-server-ops 内 --usage-file 命名范式同步为新式」，但该 skill（`~/.hermes/profiles/ops/...`，跨 profile）**已含新式命名**（SKILL.md:46-49 实测），且超出「目标仓唯一对象」约束。建议改为「已满足/无需动作」或显式列为跨仓观察项。

**F-8 🟢 O3 枚举不完整（审计项 7）**：O3 仅列 `url-flag-design-v2.0:216`，但 `documents/hs-cli-design-v1.0-20260624.md:506` 亦含「不占用终端」（「日志分离…不占用终端」）。A12 已豁免 documents/ 全部故非阻断，建议 O3 补列或统一表述为「documents/ 全部豁免」。

**F-9 🟢 services.py 存储字段未完全明确（审计项 5b）**：§5 仅列「use_port 字段」，§4.4 提及「store 中记录了 port」——即另有 port int 字段。建议明确两个字段 `use_port(bool, 默认 False)` + `port(int, 默认 None)`，及 update 的 `--no-port` 清除语义（两者同清）。

**F-10 🟢 D8「等价于 1781-1785 推广」不精确（审计项 2）**：实测 `hs -p 8089` 时 `command='8089'`（端口值泄漏到 command 位，非 cmd=None）、`unknown=['-p']`；现有 1781-1785 分支仅覆盖 `cmd is None`。建议补充重组逻辑：检测 `unknown` 含 `-p/--port` 且 `command` 为泄漏端口值时，重组 `args = unknown + [command] + args`，cmd='start'。

**F-11 🟢 §5 影响矩阵行号漂移（审计项 1）**：cli.py 行号「1284-1330、1450-1520」实为 `_cmd_web/_web_help` 与 `_web_list/_web_show`；`_web_add`=1321-1408、`_web_update`=1574-1670。不影响实施，标注即可。

**F-12 🟢 版本链既有 1.3.1 漂移（审计项 8）**：`__init__=1.3.1`（2026-09-04）但 CHANGELOG top=1.3.0、spec.yaml=1.3.0。设计目标 1.4.0 将跳过 1.3.1 的 CHANGELOG 记录，建议在 1.4.0 CHANGELOG 中补注「1.3.1 为 patch 发布（2026-09-04），未单列 CHANGELOG 条目」或说明。

**F-13 🟢 D4 区间与 MAX_PORT 差异（审计项 2）**：D4 区间 1024-65535，但 `utils.py:29 MAX_PORT=10000` 是 `find_available_port` 漂移上限。`-p` 直绑可超 10000，自动分配仍封顶 10000，非 bug，建议注明既有差异。

**F-14 🟢 幂等 + `-p` 保留端口的提示措辞（审计项 3）**：`hs . -p 8180`（dashboard 实际占用）将报「保留端口」而非「已被占用」（因保留检查先于占用检查），语义准确但未区分「保留未占用」vs「保留且占用」。可选优化，非阻断。

---

## 六、修复清单（回 ops，设计 v1.1 最小修法）

| # | 文件位置 | 最小修法 |
|:--|:--|:--|
| F-1 | 设计 §4.1 | 补执行顺序链「路径(126)→幂等(137)→幂等命中忽略 `-p`→`-p` 校验(195)」，修正「全部先于」措辞 |
| F-2 | 设计 §4.3 | 勘误 restart 现状为「未运行 → not running；已运行 → 硬编码 8180（bug）」，明确新行为 |
| F-3 | 设计 §8 A14 | grep 目标改 `__init__.py`+`CHANGELOG.md`+`spec.yaml version`，删 pyproject.toml |
| F-4 | 设计 §9 item 4 | capability 清单补 `json-output`（port 字段）+ `dashboard`（restart --port） |
| F-5 | 设计 §4.6 + §11 | 明确路径不存在退出码 0→1 变更并纳入 CHANGELOG Changed（或从 exit-1 移除） |
| F-6~F-14 | 各 § | 记录项，同批勘误（见 §五） |

rereview 验证要求：F-1 执行顺序链在 §4.1 成文；F-2 §4.3 与 cli.py:610-616/678 事实一致；F-3 A14 三目标 grep 均可落地；F-4 spec capability 清单含 json-output/dashboard；F-5 退出码表与 CHANGELOG Changed 自洽。

---

## 七、待确认清单

1. F-5 出口判据：路径不存在/服务未找到的退出码是「保持 0」还是「改 1」？（推荐改 1 对齐 G4「消灭假成功」，需用户拍板）
2. F-13：D4 区间是否应随 MAX_PORT 收敛为 1024-10000，或维持 1024-65535（推荐维持，直绑超 10000 合法）？
3. F-14：`-p 8180` 且 dashboard 实际占用时，是否需区分「保留未占用」vs「保留且占用」提示（推荐可选优化）？
