# CL-SEC20 hs AI 对接批次一 — re-review报告 v1.1

> 日期: 2026-08-26
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 复审对象: 批次 6 commit（5e9f7aa, 6fafaa1, cf21184, 6371725, e693ba6, 7f0ab1c）+ review-fix f734042 + audit@review
> 首审: v1.0 CONDITIONAL PASS 70/100（documents/review/http-server-cli-ai-integration-audit-v1.0-20260825.md）
> review维度: 提交审计 re-review（审计规范 §6 + commit规范 §5 + 命名规范 §1）
> 闭环: CL-SEC20 — hs AI 对接批次一（hs prompt 子命令 + MCP 数据工具/Resources + mcp --config）

## 数据验证（re-review）

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| SEC-020-1 代码修复 | read cli.py:800-812 | ✅ config_data args `['mcp','--transport','stdio']`;YAML 输出同步;注释 8181 + `--transport stdio` |
| SEC-020-1 输出实测 | `.venv/bin/python -m http_server_cli mcp --config`（YAML + --json） | ✅ YAML `args: ["mcp", "--transport", "stdio"]`;--json 信封 data.mcpServers.hs.args 同步 |
| SEC-020-1 端到端握手 | 按 config args 启动子进程（隔离 HOME），stdio JSON-RPC | ✅ initialize → serverInfo hs-mcp 1.1.0 + capabilities{tools,resources};notifications/initialized 静默;tools/list → **11 工具**;resources/list → **3 项**（hs://registry\|bookmarks\|config） |
| SEC-020-2 修复 6 处 | read cli.py:812 / skills/hs-cli:55 / skills/hs-mcp:16,17 / design:64,115,116 | ✅ 全部 `--transport stdio` / `127.0.0.1:8181/sse`，无 --stdio、无 8765 |
| SEC-020-3 修复 | read skills/hs-mcp:73 | ✅ -32602（实测未 initialize 调 tools/list → -32602,与实现 mcp.py:370 一致） |
| SEC-020-4 修复 | git show 6371725 / e693ba6 | ✅ subject `tests (12)` 准确:test_mcp.py 29→41（+12:7 新增 BuildArgs + 5 Resources;`test_all_six_tools` 改名 `test_all_eleven_tools` 非新增）;e693ba6 docs@changelog（"378 tests" 与实测一致） |
| SEC-020-5 修复 | read skills/hs-bookmark:52 | ✅ JSON 示例 `command: "bookmark-list"`（与 cli.py:1035 一致） |
| SEC-020-6 修复 | read design §三:73 vs mcp.py:180-181 | ✅ 模板 `['bookmark','add','{name}','{path}','-i','{index_page}','--force']` + param_map `'index_page'→'index_page'` 与实现逐字一致 |
| SEC-020-7 记录 | review-log + test_prompt.py 9 例 | ✅ 记录接受:SKILLS_DIR 为 _cmd_prompt 函数内局部变量（cli.py:666）,monkeypatch 成本高;缺失路径代码存在且正确（cli.py:668-675） |
| **SEC-020-8（新发现）** | read design §四:111,114 + git show 7f0ab1c | 🟡 design doc §四 YAML 片段与 --json 信封描述残留 `args:["mcp"]`（7f0ab1c 仅勘误 115/116 备注行,未同步 111/114）→ **已由 review-fix f734042 闭环**（args `['mcp','--transport','stdio']`） |
| skills 残留扫描 | grep -rn '8765\|--stdio\|-32601' skills/ | ✅ 0 hits |
| 全量测试 | `.venv/bin/python -m pytest tests/ -q` | ✅ **378 passed in 1.30s** |
| commit 链完整 | git log --oneline | ✅ 6 批次（5e9f7aa, 6fafaa1, cf21184, 6371725, e693ba6, 7f0ab1c）+ f734042 + audit@review;baead3b **已在 origin/main**（简报中"7 个未 push"含 baead3b 为会话早期计数,实际批次 6 个,本轮新增 2 个） |
| subject 与内容一致 | git show 各 commit --stat | ✅ 6/6 批次 subject 与 diff 匹配（tests (12) / 378 tests / SEC-020 fixes 5 文件 12+/12-） |
| 无敏感信息 | 本批 diff grep | ✅ 沿用首审 0 hits,本批新增无密钥/凭证/路径泄露 |

## 安全事项（修复项逐条复核）

| # | 首审严重度 | 复核结论 | 证据 |
|:--|:--------|:--------|:-----|
| SEC-020-1 | 🔴 P0 | **PASS** — 已修 + 端到端实测 | config args 已含 `--transport stdio`;按该配置启动子进程 initialize/tools/list/resources/list 全应答（11 工具 / 3 resources / capabilities 双声明） |
| SEC-020-2 | 🟡 P1 | **PASS** — 已修 6 处 | --stdio/8765 全清;skills/ 0 残留 |
| SEC-020-3 | 🟡 P1 | **PASS** — 已修 | hs-mcp:73 → -32602 |
| SEC-020-4 | 🟡 P2 | **PASS** — 已修 | 8aaca27 amend → 6371725 subject `tests (12)` 与 diff 计数一致（29→41） |
| SEC-020-5 | 🟢 | **PASS** — 已修（顺手） | bookmark-list 示例与实现一致 |
| SEC-020-6 | 🟢 | **PASS** — 已修 | §三模板与 mcp.py:180-181 逐字一致 |
| SEC-020-7 | 🟢 | **PASS** — 记录接受 | 方案说明见数据验证行;如须补测:改 _cmd_prompt 为可注入 SKILLS_DIR 或 monkeypatch Path.is_dir |
| SEC-020-8 | 🟡（新） | **PASS** — review-fix 闭环 | design §四:111/114 残留 → f734042 修复,推前状态干净 |

## 评分

| 项目 | 扣分 |
|:-----|:----|
| Base | 100 |
| 🔴 SEC-020-1（已修+实测） | −0 |
| 🟡 SEC-020-2/3/4（已修） | −0 |
| 🟢 SEC-020-5/6/7（已修/记录） | −0 |
| 🟡 SEC-020-8（已由 f734042 闭环） | −0 |
| **得分** | **100 / 100 → Rating A** |

## 结论

**✅ PASS（100/100, A）** — 7 项首审条目逐条复核:SEC-020-1 功能修复经端到端 stdio 握手实测确认（initialize/tools-list-11/resources-list-3）;SEC-020-2/3/5/6 文档勘误 6+1+1 处全部到位,skills/ 残留扫描 0 hits;SEC-020-4 subject amend 与 diff 计数一致;SEC-020-7 记录接受。复查另发现 design doc §四:111/114 残留 `args:["mcp"]`（首审 P0 修复建议"设计文档 §四 勘误"未完全执行）,由 review-fix f734042 推前闭环。**push origin main**（baead3b 已在远端,实际推送批次 6 + 新增 2 = 8 commits）。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| ☑ | design §三:85 布尔机制示例用简写模板 `['bookmark','add','{name}','{path}','--force']` — 系机制说明非全量模板,与实现决策一致,不构成失实 | 已核销 |
| ☑ | index.html/index.zh.html:567 `8765` 展示值 — CL-SEC19 批次（a032a5e）预置,非本批残留;页面示例端口与默认 8181 不一致,可选跟进 | 已核销（不入本批） |
| ☑ | mcp.py:206 `_ERR_METHOD -32601` — JSON-RPC 标准 "Method not found",test_mcp.py:96 断言正确,与 SEC-020-3（未 initialize → -32602）无关 | 已核销 |
| ☑ | SEC-020-7 补测方案（如须）:改 _cmd_prompt 为可注入 SKILLS_DIR 或 monkeypatch Path.is_dir | 记录 |
