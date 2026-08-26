# CL-SEC20 hs AI 对接批次一 — commit audit报告 v1.0

> 日期: 2026-08-26
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 待 push commit: 5e9f7aa, 6fafaa1, cf21184, 8aaca27, 3a82cd9（共 5 个）
> review维度: 提交审计（审计规范 §6 + commit规范 §5 + 命名规范 §1）
> 闭环: CL-SEC20 — hs AI 对接批次一（hs prompt 子命令 + MCP 数据工具/Resources + mcp --config）

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 未 push commit 恰为 5 个 | `git log origin/main..HEAD --oneline` | ✅ 5e9f7aa / 6fafaa1 / cf21184 / 8aaca27 / 3a82cd9 |
| diff 范围 = 设计文档 + cli/mcp/__init__ + skills/4 + tests/2 + CHANGELOG/features | `git diff origin/main..HEAD --stat` / `--name-status` | ✅ 12 文件,与预期清单逐一对应,无无关文件 |
| hs prompt 无参列表含 4 skill | 实测 `python -m http_server_cli prompt`（.venv） | ✅ hs-bookmark / hs-cli / hs-dashboard / hs-mcp 全部列出,各带 description + `用法: hs prompt <name>` |
| hs prompt <name> 详情全文 | 实测 `prompt hs-cli` | ✅ 输出 SKILL.md 全文（head/tail 抽验,含 frontmatter 与正文） |
| hs prompt --brief | 实测 `prompt hs-mcp --brief` | ✅ description + `章节:`（7 个 `## ` 标题）+ references |
| hs prompt --json 信封（正常） | 实测 `prompt --json` | ✅ `{status:'ok',error:'',data:[4×{name,description,references:[]}]}` |
| hs prompt --json 信封（错误） | 实测 `prompt nope --json` | ✅ `{status:'error',data:null,error:"skill 'nope' 不存在"}` + exit 1 |
| hs prompt 不存在 skill | 实测 `prompt nope` | ✅ stderr `❌ skill 'nope' 不存在` + stdout 可用列表 + exit=1 |
| MCP _TOOLS = 11 + _TOOL_MAP 覆盖 | 实测 stdio `tools/list` + 单测 | ✅ 11 工具（6 管理 + 5 数据）;`_TOOL_MAP.keys() == {t.name}` |
| _build_hs_args 回归 6 旧工具 | 单测 TestBuildArgs 既有 8 例 | ✅ hs_list/status/start/kill(port+path)/kill_all/config 参数形态不变;hs_kill port/path 特例保留（mcp.py:272-281） |
| bookmark_add 参数三形态 | 单测 3 例 | ✅ 全参 `['bookmark','add',name,path,'-i',index_page,'--force']` / 最小仅 name→path 默认 '.' / force=False 无 `--force` |
| resources/list 3 项 | 实测 stdio `resources/list` | ✅ hs://registry / hs://bookmarks / hs://config（uri/name/description/mimeType） |
| resources/read 缺失容错 '{}' | 单测 monkeypatch DATA_DIR + 实测 | ✅ 文件缺失返回 `'{}'` 不报错;真实内容可读;未知 URI 报 -32602 |
| initialize capabilities.resources | 实测 stdio `initialize` | ✅ capabilities{tools,resources} + serverInfo.version=1.1.0 |
| 新工具端到端 tools/call | 实测 5/5（隔离 HOME /tmp/hs-audit-home） | ✅ hs_history / hs_search / hs_bookmark_add(force) / hs_bookmark_list / hs_bookmark_remove 均返回 CLI JSON 信封 |
| hs mcp --config YAML + --json | 实测 | ✅ YAML 合法（mcpServers.hs.command/args/transport）、--json 信封 data.mcpServers —— 但语义不可用,见下行 |
| hs mcp --config 输出可用性（stdio 客户端） | 实测 `hs mcp`（= config 的 `args:["mcp"]`）管道握手 | ❌ stdout 输出 `📡 hs mcp (SSE daemon) -> http://127.0.0.1:8181/sse (PID ...)` 后退出,**无任何 JSON-RPC 响应**;后台 daemon 实测监听 8181（lsof + registry-managed.json 证实）→ SEC-020-1 🔴 |
| skills/ 4 篇 frontmatter | 单测 2 例 + 逐篇 read | ✅ name/description 合法,frontmatter name == 目录名 |
| skills 内容与源码一致 | 逐篇比对（命令/参数/边界） | ❌ 3 处硬性不符（`--stdio` ×3、端口 8765 ×4、错误码 -32601 ×1）→ SEC-020-2/3 🟡;1 处示例不符 → SEC-020-5 🟢 |
| 版本 1.2.0 一致性 | __init__/CHANGELOG/`hs version`/features.md/pyproject | ✅ `__version__='1.2.0'`;`hs version`→`http-server v1.2.0`;CHANGELOG 1.2.0 条目;features.md 378 tests/11 工具/+prompt;pyproject version 为 dynamic attr 同源,无二处 |
| 378 tests 全绿 | `pytest tests/ -q`（.venv） | ✅ **378 passed in 1.36s** |
| test_prompt 9 用例与实现一致 | 逐用例比对 | ✅ 9 例（frontmatter 2 + 行为 7）断言与 cli.py _cmd_prompt 实现一致;设计 §六 "skills 缺失场景" 未落地 → SEC-020-7 🟢 |
| test_mcp 扩展 12 用例 | `git show 8aaca27` diff 计数 | ✅ 29→41（+12:TestBuildArgs 7 + TestResources 5;`test_all_six_tools` 改名 `test_all_eleven_tools`） |
| 无敏感信息 / 无 /Users 字面路径 | diff grep（/Users /home /private key secret token passwd） | ✅ 0 hits（代码/配置/文档全查） |
| .hermes-project.yaml 未混入 | `git log --name-only` | ✅ 不在 5 commit 内;工作区当前 clean |
| commit 格式 | 逐 commit 核验 | ✅ 5/5 `type@scope: subject`;分组按属性（设计→skills→prompt→mcp→changelog）;subject 计数失实 1 处 → SEC-020-4 🟡 |

## 审计规范评估（§6）

| # | 检查项 | 结果 |
|:--|:-------|:-----|
| A1 | hs prompt 全路径实测 | ✅ 列表 4 skill / 详情全文 / --brief / --json 信封（正常+错误）/ 不存在 exit 1 —— 5/5 实测通过,与设计 §一 行为表逐项一致 |
| A2 | MCP 11 工具 + _TOOL_MAP 完整覆盖 + _build_hs_args 回归 + 新工具映射 | ✅ 旧 6 工具 8 例回归不变;bookmark_add 三形态 3 例;新 5 工具参数映射 7 例;端到端 tools/call 5/5 |
| A3 | MCP Resources 3 项 + 缺失容错 + initialize capabilities | ✅ resources/list 3 项;resources/read 缺失返回 '{}';capabilities.resources 声明;SERVER_VERSION 1.1.0 实测 |
| A4 | hs mcp --config 输出合法 YAML + --json 信封 | ❌ 形式合规（YAML/信封正确）;**语义不可用**:`args:["mcp"]` + transport stdio 实测启动后台 SSE daemon,stdio 客户端无法握手 → SEC-020-1 🔴 |
| A5 | skills/ 4 篇 frontmatter + 内容与源码一致 | ❌ frontmatter 4/4 合法;内容边界 3 处失实（--stdio/8765/-32601）→ SEC-020-2/3 🟡 |
| A6 | 版本 1.2.0 一致性 | ✅ __init__ / CHANGELOG / `hs version` / features.md / pyproject dynamic 全一致 |
| A7 | 378 tests 全绿 + 用例断言与实现一致 | ✅ 实测 378 passed;9 + 12 用例断言与实现一致;设计测试计划 1 项（skills 缺失 monkeypatch）未落地 → SEC-020-7 🟢 |
| A8 | 未触碰无关源码 | ✅ diff = 12 文件,无越界;src/ 仅 cli.py/mcp.py/__init__.py（+1 行版本号） |
| A9 | 无敏感信息 / 无 /Users 字面路径 | ✅ 0 hits |

## commit规范评估（§5）

| # | 检查项 | 结果 |
|:--|:-------|:-----|
| C1 | subject 格式 `type@scope: subject` | ✅ 5/5:docs@design / docs@skills / feat@prompt / feat@mcp / docs@changelog,scope 均非空 |
| C2 | 分组按属性 | ✅ 设计文档→skills 文档→prompt 功能→mcp 功能→changelog+版本,各归其位;`__init__.py` 版本 bump 位于 docs@changelog（subject 明示 "version 1.2.0",语义自含,不构成违规） |
| C3 | .hermes-project.yaml 未混入 | ✅ 不在 5 commit 内,工作区 clean |
| C4 | 无敏感信息 | ✅ diff 无密钥/凭证/token |
| C5 | subject 内容准确性 | ❌ 8aaca27 subject 尾部 "tests (21)" 失实:该 commit 实测新增 12 用例（21 = 批次总量 prompt 9 + mcp 12）→ SEC-020-4 🟡 |

附注:5 commit body 均为空 — 与本项目既有历史惯例一致,不构成违规。

## 命名规范评估（§1）

- ✅ skills/ 4 篇:目录名 kebab-case,frontmatter `name:` 与目录名一致（hs-cli / hs-bookmark / hs-mcp / hs-dashboard）
- ✅ MCP 工具:hs_ 前缀 snake_case（hs_bookmark_list / hs_bookmark_add / hs_bookmark_remove / hs_history / hs_search）;Resources URI `hs://` scheme 小写;SERVER_VERSION 1.0.0→1.1.0 语义化 minor
- ✅ 新文件:design 文档 `hs-ai-integration-design-v1.0-20260825.md`（kebab-case + v{major}.{minor} + 8 位日期）;测试 `test_prompt.py` / `test_mcp.py`（test_ 前缀）
- ✅ 新函数 `_cmd_prompt` 与既有 `_cmd_*` 命名一致;`_register` 注册名 'prompt' 与 `_HELP` 一致

## 安全事项

🔴 **SEC-020-1 — `hs mcp --config` 输出的 stdio 接入配置不可用（功能阻断,批次核心交付物）**
- 位置: src/http_server_cli/cli.py:800（config_data args）,cli.py:809（YAML 输出）,cli.py:812（注释）
- 证据: 实测 `hs mcp`（= config 输出 `command: hs / args: ["mcp"] / transport: stdio`）在管道 stdio 下: stdout 输出 `📡 hs mcp (SSE daemon) -> http://127.0.0.1:8181/sse  (PID: 58085)` 后退出,rc=0,**无任何 JSON-RPC 握手响应**;后台 daemon 实测监听 8181（lsof + registry-managed.json 双证）;对照 `hs mcp --transport stdio` 正常应答 initialize/tools/list/resources/list/tools/call。
- 根因: cli.py:789 仅识别 `--transport`（默认 'sse' + daemon=True）;config 输出 args 缺 `--transport stdio`。设计文档 §四:116 基于错误前提 "`hs mcp --stdio` 已存在（serve_stdio）" —— 该 flag 实际不存在,实现照抄了设计前提。
- 影响: 粘贴该片段到 Claude Code / Cursor / Hermes 的 MCP stdio 客户端会连接失败（子进程 stdout 无 JSON-RPC）。
- 修复建议: cli.py:800 与 cli.py:809 的 args 改为 `["mcp", "--transport", "stdio"]`;cli.py:812 注释同步;设计文档 §四 勘误。
- 优先级: **P0（必改,阻断 push）**

🟡 **SEC-020-2 — 文档声称 `--stdio` flag 与端口 8765,均与实现不符**
- 位置: src/http_server_cli/cli.py:812;skills/hs-cli/SKILL.md:55;skills/hs-mcp/SKILL.md:16,17;documents/hs-ai-integration-design-v1.0-20260825.md:64,115,116
- 证据: `--stdio` 不存在 —— 仅 `--transport stdio`（cli.py:789）;`hs mcp --stdio` 经 parse_known_args 忽略未知 flag 后按默认启动后台 SSE daemon。端口默认 8181（cli.py:790;实测 lsof;旧文档 hs-mcp-design-v1.0-20260624.md 亦为 8181）,8765 系本批新引入笔误（`git log -S 8765 -- cli.py` 仅命中 8aaca27）。
- 影响: AI 按 skill 文档执行 `hs mcp --stdio` 会启动 SSE daemon 而非 stdio,行为与文档预期相反。
- 修复建议: 6 处统一改为 `--transport stdio` / `127.0.0.1:8181/sse`。
- 优先级: P1（必改）

🟡 **SEC-020-3 — hs-mcp SKILL.md:73 边界错误码 -32601 与实现不符**
- 位置: skills/hs-mcp/SKILL.md:73
- 证据: 实测未 initialize 调 tools/list → error code **-32602**（mcp.py:370 ValueError→-32602）;SKILL.md 声称 -32601。
- 修复建议: SKILL.md:73 改为 -32602。
- 优先级: P1（必改）

🟡 **SEC-020-4 — commit 8aaca27 subject "tests (21)" 计数失实**
- 位置: commit 8aaca27 subject
- 证据: 该 commit 实测新增 12 用例（test_mcp 29→41;`test_all_six_tools` 改名 `test_all_eleven_tools` 属改名非新增）;21 = 批次总量（prompt 9 + mcp 12）,CHANGELOG 口径正确（+21:test_prompt 9 / test_mcp 12）,subject 复用总量误导。
- 处理建议: 尚未 push,可 `git commit --amend` 改 subject 为 "tests (12)";或接受记录。
- 优先级: P2

🟢 **SEC-020-5 — hs-bookmark SKILL.md:52 JSON 示例 command 值 "bookmark" 与实现不符** — 实现 `hs bookmark list --json` 输出 `command: "bookmark-list"`（cli.py:1035）;示例文案,记录不扣分。

🟢 **SEC-020-6 — design doc §三:76,85 hs_bookmark_add 模板示例与实现漂移** — 表格模板写 `['bookmark','add','{name}','{path}']`、param_map 写 `'index'→'index_page'`,实现为 `['bookmark','add','{name}','{path}','-i','{index_page}','--force']` + `'index_page'→'index_page'`（mcp.py:180-181）;决策 9"与 CLI 同构"级一致,实现为超集,记录不扣分。

🟢 **SEC-020-7 — design doc §六:126 测试计划 "skills 缺失场景（monkeypatch SKILLS_DIR）" 未落地** — test_prompt.py 9 例无此场景;SKILLS_DIR 为 _cmd_prompt 函数内局部变量（cli.py:666）,monkeypatch 需改实现或 patch Path.is_dir;代码路径存在且行为正确（cli.py:668-675）;记录不扣分。

## 评分

| 项目 | 扣分 |
|:-----|:----|
| Base | 100 |
| 🔴 HIGH × 1（SEC-020-1） | −15 |
| 🟡 MEDIUM × 3（SEC-020-2/3/4） | −15 |
| 🟢 LOW × 3（SEC-020-5/6/7） | −0 |
| **得分** | **70 / 100 → Rating B** |

## 结论

**⚠️ CONDITIONAL PASS（70/100, B）** — 批次功能主体核验通过:hs prompt 全路径 5/5 实测、MCP 11 工具 + Resources + initialize 实测、新工具端到端 5/5、378 tests 全绿（.venv）、版本 1.2.0 五处一致、diff 12 文件无越界、commit 格式与命名规范合规、无敏感信息。但 **🔴 SEC-020-1 `hs mcp --config` 输出配置不可用**（stdio 客户端按 config 启动 `hs mcp` 得到的是后台 SSE daemon,无 JSON-RPC 握手）——批次核心交付物"一行接入"功能阻断,连带 3 处文档失实（🟡 SEC-020-2/3）。**未 push**,修复清单回 ops,复审通过后由 review 执行 push。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | SEC-020-1 修复:cli.py:800/809 args → `["mcp","--transport","stdio"]`;cli.py:812 注释同步 | 必改 P0 |
| □ | SEC-020-2 修复:skills/hs-cli/SKILL.md:55、skills/hs-mcp/SKILL.md:16-17 → `--transport stdio` / 端口 8181;design doc:64,115,116 勘误 | 必改 P1 |
| □ | SEC-020-3 修复:skills/hs-mcp/SKILL.md:73 → -32602 | 必改 P1 |
| □ | SEC-020-4 处理:8aaca27 subject amend "tests (12)"（未 push 可改）或接受记录 | 建议 P2 |
| □ | SEC-020-5/6/7 可选修订 | 可选 |
| □ | 复审 → PASS → push origin main | 复审后 |
