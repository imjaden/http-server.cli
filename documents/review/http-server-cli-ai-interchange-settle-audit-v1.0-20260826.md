# CL-SEC21 hs AI 互通沉淀三件套 — review报告 v1.0

> 日期: 2026-08-26
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 审计对象: 4 commits（efddb48, d5a3ce1, a156a89, 851bbf1），基底 origin/main 863b85c
> review维度: 提交审计（审计规范 §6 + commit规范 §5 + 命名规范 §1）+ 功能实测
> 闭环: CL-SEC21 — AI 互通沉淀三件套（skills/ai-interchange + index 内容重构 + README 重构）

## 数据验证（8 项全过）

| # | 验证项 | 方法 | 结果 |
|:--|:-------|:-----|:-----|
| 1 | skills/ai-interchange/SKILL.md 内容真实性 | 逐字对照 src/ 实现（11 条断言） | ✅ 全真（详见下表） |
| 2 | hs prompt 实测 | `.venv/bin/python -m http_server_cli prompt` 全路径 | ✅ 无参列表 **5 篇**（ai-interchange/hs-bookmark/hs-cli/hs-dashboard/hs-mcp）;`prompt ai-interchange` 全文输出与仓库文件逐字一致;`--json` 信封 `status: ok` + **5 项**;`--brief` 仅 description+章节;不存在 → stderr 报错 + 可用列表 + **exit 1** |
| 3 | index 双源防漂移 | grep 计数双页 + `pytest tests/test_index_sync.py` | ✅ 双页 group-title=**6**、cmd-row=**17**、code-block=**4**、`<tr`=**6** 全一致;test_index_sync **14 passed**;AI 互通组命令正确（`hs mcp --transport stdio` / `hs mcp --config` / SSE 8181）;data-copy 与显示命令逐字一致;`--stdio`/`8765` 双页零残留（ai-interchange skill 正文坑清单除外,属有意记录） |
| 4 | README EN/ZH 同步 | git show a156a89 + 当前文件 grep | ✅ YAML 片段 `args: ["mcp", "--transport", "stdio"]` 双文件 L77 一致;6 tools→11 双端修正（11 = 6 管理 + 5 数据,与 _TOOLS 逐名一致）+ 3 Resources;双对比表合并降级（Why hs 4 行 bullet）;`## Comparison`/`## 对比一览` 残留 0 hits;`hs version` 实测 `http-server v1.2.0` 与 README v1.2.x 一致;MCP 表新增 `--config`/`prompt` 行（EN/ZH） |
| 5 | features.md 同步 | git show 851bbf1 | ✅ AI 对接节 skills 4→5 篇（+ai-interchange）+ 新增 item 2（三通道框架/CL-SEC21 闭环） |
| 6 | subject 与 diff 一致 | `git show <commit> --stat` 逐 commit | ✅ 4/4（详见下表） |
| 7 | 全量测试 | `.venv/bin/python -m pytest tests/ -q` | ✅ **378 passed in 1.34s**（用例数不变,仅断言修改,零回归） |
| 8 | 无敏感信息 | git diff 863b85c..HEAD grep | ✅ 密钥/凭证/绝对路径 0 hits;`~/.hermes/profiles/ops/skills/devops/ai-interchange/` 为镜像说明（有意记录,非泄露）;cache/ 均 gitignored 不入 commit |

### 1a. SKILL.md 11 条断言对照实现

| 断言 | 实现证据 | 结果 |
|:-----|:---------|:-----|
| `--transport stdio`（无 `--stdio`） | cli.py:789 `--transport choices=['stdio','sse']`;cli.py:800 config args;全仓 grep `--stdio` = 0 hits（除 skill 正文坑清单） | ✅ |
| 端口 8181（无 8765） | cli.py:790 default 8181;cli.py:812 注释 `http://127.0.0.1:8181/sse`;全仓 grep 8765 = 0 hits | ✅ |
| 错误码 -32602 | mcp.py:207 `_ERR_PARAMS`;mcp.py:380-381 未 initialize → ValueError → mcp.py:370 映射 -32602;-32601 仅 unknown method | ✅ |
| _TOOL_MAP 参数映射 | mcp.py:172-185 dict[tuple[list, param_map]];mcp.py:299-314 短 flag 带值两段式（`-i {index_page}` 值存在才追加两项）;mcp.py:315-322 布尔 flag（`--force` param True 才追加） | ✅ |
| Resources 文件缺失容错 | mcp.py:426-445 except (OSError, IOError) → `text='{}'` | ✅ |
| registry-managed 边界 | _TOOL_MAP 11 项全部映射用户 registry 命令（list/status/start/kill/kill-all/config/bookmark/history/search）,无 managed/mcp 工具 | ✅ |
| 11 工具清单（6 管理 + 5 数据） | mcp.py:74-170 _TOOLS = 11:管理 hs_list/status/start/kill/kill_all/config;数据 hs_bookmark_list/add/remove/hs_history/hs_search | ✅ |
| `--json` 信封 | cli.py:709 prompt `{status,error,data}`;utils json_output `{success,command,data,error}` | ✅ |
| SKILLS_DIR `parents[N]` | cli.py:669 `parents[2]`（src/http_server_cli → src → 项目根,N=2=文件深度） | ✅ |
| prompt 行为对齐 | cli.py:706-776 无参 name+description+references+用法 / `<name>` 全文+尾拼 references / `--brief` / 不存在 exit 1;运行时实测 | ✅ |
| SERVER_VERSION bump + URI 约定 | mcp.py:27 `'1.1.0'`（CHANGELOG: 1.0.0→1.1.0）;mcp.py:33,39,45 `hs://registry|bookmarks|config` | ✅ |

### 6a. subject vs diff 逐 commit

| commit | subject 声称 | diff 实测 | 结果 |
|:-------|:------------|:---------|:-----|
| efddb48 | ai-interchange skill + test_prompt 5 篇同步 | skill 69 行新增 + test_prompt.py 断言 4→5（EXPECTED_SKILLS、docstring、--json 4→5 项、not-found 输出 +ai-interchange） | ✅ |
| d5a3ce1 | 6 groups / 17 cmd-rows | test_index_sync.py: group-title 5→6、cmd-row 14→17（+4 AI 组、−1 Manage 去 hs mcp）、STRUCTURE_FEATURES +hs prompt/+hs mcp --config;index 双页各 +25 行（AI 组 4 cmd-row、badge、8181、Manage 去 mcp 行） | ✅ |
| a156a89 | AI 互通节 + 双表合并 + 11 工具与版本同步 | README.md / README.zh.md 各 61 行增、双端对称（AI Interchange/互通 3 小节、YAML 片段、Why hs 4 bullet、v1.2.x、MCP 表 +2 行） | ✅ |
| 851bbf1 | skills 5 篇 + ai-interchange | features.md 3+/2−（item1 skills 4→5 篇、新增 item2 ai-interchange、批次二顺延 item3） | ✅ |

## 维度评估

**commit 规范 §5** — 4/4 合规:
- efddb48 `docs@skills:`、d5a3ce1 `feat@index:`、a156a89 `docs@readme:`、851bbf1 `docs@features:` — type@scope 格式正确,scope 非空
- 分组按属性无混批:skills/test 断言 → docs@skills;index+断言 → feat@index;README 双端 → docs@readme;features → docs@features
- 断言变更随所属 feature commit（非独立混批）

**命名规范 §1** — 合规:
- 新增 `skills/ai-interchange/` 目录 kebab-case + 标准 SKILL.md（YAML frontmatter）
- 报告文件名 `http-server-cli-ai-interchange-settle-audit-v1.0-20260826.md` kebab-case
- 未新增测试文件（断言修改,沿用 pytest 约定）

## 安全事项

| # | 严重度 | 说明 | 状态 |
|:--|:------|:-----|:-----|
| SEC-021-1 | 🟢（记录） | CHANGELOG.md v1.2.0 条目 L6 "无参列出 4 篇" — 本批新增第 5 篇 ai-interchange 且按决策不 bump 版本,changelog 保留发布时点快照;README/skills/features 已 5 篇,changelog 未同步 | 记录,待确认是否后续 docs@changelog 顺手同步 |
| SEC-021-2 | 🟢（记录） | documents/hs-ai-integration-design-v1.0-20260825.md:10,143 "6 工具" — 设计时点快照（批次一设计先于实现扩展为 11）;本批未触碰 design doc | 记录,保持不动 |

🔴 0 项 / 🟡 0 项 / 🟢 2 项（记录,不扣分）。无跨域/认证/数据流缺陷,不触发人工通知规则。

## 评分

| 项目 | 扣分 |
|:-----|:----|
| Base | 100 |
| 🔴 | −0 |
| 🟡 | −0 |
| 🟢（SEC-021-1/2 记录） | −0 |
| **得分** | **100 / 100 → Rating A** |

## 结论

**✅ PASS（100/100, A）** — 8 项审计全过。SKILL.md 与 CL-SEC20 实现逐字一致（11 条断言含 -32602 错误码路径、_TOOL_MAP 双类参数映射、Resources 缺失 '{}' 容错、registry-managed 边界、11=6+5 工具清单,全部有 src/ 行号证据）;hs prompt 四行为 + 5 篇供给运行时实测;index 双页 6/17/4/6 对称 + 14 断言绿 + 8765/--stdio 零残留;README EN/ZH 双端对称（YAML 片段 / 11 工具 / 双表合并 / v1.2.x 与实测 v1.2.0 一致）;features 同步;4 subject 与 diff 计数一致;全量 378 passed 零回归;无敏感信息。2×🟢 记录项不扣分。**push origin main（efddb48..851bbf1, 4 commits）**。

## 待确认清单

| □ | 项 | 类别 |
|:--|:---|:-----|
| □ | SEC-021-1:CHANGELOG v1.2.0 L6 "无参列出 4 篇" 是否要后续 docs@changelog 同步为 5 篇（本批按"不 bump 版本"决策未动） | 记录项 |
| □ | SEC-021-2:design doc "6 工具" 历史快照保持不动 | 记录项 |
