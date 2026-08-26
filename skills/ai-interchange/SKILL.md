---
name: ai-interchange
description: AI 互通数据对接方法论 — 三通道框架（prompt 文档 / MCP 数据工具+Resources / 配置一键接入）+ hs 实证与坑。给 CLI/服务提供 AI 接入前先读此篇。
---

# ai-interchange — AI 互通数据对接

## 触发条件

- 项目要给 AI agent 提供数据读取或操作能力（CLI / 服务 / 数据文件）
- 评审其他项目的 AI 对接设计（对照本框架与验收清单）
- 复用 hs 的 AI 互通三通道模式（本 skill 由 CL-SEC20 沉淀，2026-08-26）

## 三通道框架

给 AI 提供"互通数据对接"有互补的三条通道，按需组合：

| 通道 | 形态 | AI 侧使用 | 典型场景 |
|------|------|-----------|----------|
| ① prompt 文档通道 | 项目 skills/ 目录 + CLI `prompt` 子命令输出使用说明 | 一条命令拿完整规范 | AI 需要知道"这个工具怎么用" |
| ② MCP 数据通道 | MCP Server：数据类工具（操作）+ Resources（只读数据） | 实时读数据 / 操作 | AI 需要读运行状态、配置、数据文件，或执行管理动作 |
| ③ 配置接入通道 | `mcp --config` 输出 mcpServers 配置片段 | 粘贴一行即接入 | 用户要把项目接入 Claude Code / Cursor / Hermes 等 AI 工具 |

### 决策矩阵

- AI 要了解工具用法 → 通道①（prompt 无参列清单 / <name> 全文 / --brief 摘要）
- AI 要读项目数据（运行状态/书签/配置）→ 通道② Resources（只读、容错）
- AI 要操作（启动/关闭/增删改）→ 通道② 工具（注意权限边界：只操作用户数据，不碰托管基础设施）
- 用户要接入具体 AI 工具 → 通道③（mcpServers 片段 + 备注 SSE/stdio 两种方式）
- 机器可读 → 所有输出带 `--json` 信封（{success, command, data, error} / {status, error, data}）

## 实践要点（hs CL-SEC20 实证）

### 1. skills/ 供给（通道①）

- SKILLS_DIR 定位：`Path(__file__).resolve().parents[N] / 'skills'`（从 cli.py 逐级向上到项目根，N=文件深度）
- 每篇 SKILL.md 带 YAML frontmatter（name/description），description 供 `prompt` 列表展示
- `prompt` 行为对齐：无参列出 name+description+references+用法 / `<name>` 输出全文+尾拼 references / `--brief` 仅 description+章节标题 / 不存在 → stderr 报错+可用列表+exit 1
- 新增 skill 是纯文档动作，CLI 自动扫描 —— 但**必须同步精确集合断言测试**（见验收）

### 2. MCP 数据工具与 Resources（通道②）

- 工具定义：`_TOOLS` MCPTool 定义 + `_TOOL_MAP`（模板列表, param_map）+ `_build_hs_args` 构建 CLI 参数
- 参数映射两类：短 flag 带值（`-i {index_page}`，值存在才追加两项）；布尔 flag（`--force` 对应 param True 才追加）
- Resources：capabilities 声明 resources + dispatch 加 resources/list + read；URI 约定 `hs://registry` / `hs://bookmarks` / `hs://config`；文件缺失返回空 JSON `{}` 不报错
- 能力扩展后 SERVER_VERSION 同步 bump（MCP 服务能力版本）
- 边界：数据工具只操作用户 registry/bookmark 数据，**不碰 registry-managed 托管基础设施**

### 3. 配置一键接入（通道③）

- `mcp --config` 输出 mcpServers YAML 片段 + `--json` 信封
- **args 必须含 `["mcp", "--transport", "stdio"]`** —— 缺 transport 时默认启动后台 SSE daemon，stdio 客户端无法 JSON-RPC 握手（CL-SEC20 🔴 P0 功能阻断，实测确认）
- 备注 SSE 方式 URL（如 http://127.0.0.1:8181/sse）与 stdio 二选一

## 验收清单（review 审计点）

1. `--stdio` 不存在 —— 只有 `--transport stdio`（文档/示例 grep 零残留）
2. 端口展示值与实际一致（8181 非 8765）—— 页面/README/skills 全清
3. 文档与实现逐字一致（MCP 工具模板、错误码、命令参数）
4. 错误码语义：未 initialize 调工具 → -32602（非 -32601 "Method not found"）
5. commit subject 计数写该 commit 实际增量，勿用批次总量
6. 测试断言同步：skills 精确集合（test_prompt.py EXPECTED_SKILLS）、页面计数哨兵（group-title/cmd-row）、文档特征串 —— 加内容必改断言
7. 全量测试零回归；`--json` 信封实测（status ok / error 路径 exit≠0）

## 跨项目参考

- html-gen：`cmd_prompt`（L683-787）同构实现，hs 参考其 prompt 行为
- 其他项目（llm-radar 等）给 AI 提供数据对接时可对照本框架：先列需求 → 决策矩阵选通道 → 按实践要点实施 → 按验收清单自查
- Hermes 本机：本 skill 镜像于 ~/.hermes/profiles/ops/skills/devops/ai-interchange/，各 profile 会话可 skill_view 加载
