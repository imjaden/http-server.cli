---
name: hs-mcp
description: MCP 服务对接 — SSE/stdio 双传输、11 工具清单、Resources 3 项、mcpServers 接入配置（Claude Code/Cursor/Hermes）。
---

# hs-mcp — MCP 服务对接

## 简介

hs 内置 MCP (Model Context Protocol) 服务器，让 AI Agent 直接管理 HTTP 服务。
零外部依赖（纯标准库实现），JSON-RPC 2.0，stdio/SSE 双传输。

## 启动

```bash
hs mcp                    # 后台运行 SSE → http://127.0.0.1:8765/sse（registry-managed 托管）
hs mcp --stdio            # 前台 stdio 模式（AI 工具子进程方式）
hs mcp status             # 查看状态
hs mcp stop               # 停止
hs mcp restart            # 重启
hs mcp --config           # 输出 mcpServers 接入配置
```

## AI 工具接入（hs mcp --config）

输出 mcpServers 配置片段，粘贴到 Claude Code / Cursor / Hermes 的 MCP 配置：

```yaml
mcpServers:
  hs:
    command: hs
    args: ["mcp"]
    transport: stdio
```

## 工具清单（11 个）

### 服务管理（6）

| 工具 | 说明 |
|------|------|
| hs_list | 列出所有运行中的 HTTP 服务（端口/路径/PID/状态/资源占用） |
| hs_status | 查询单服务状态（port 必填） |
| hs_start | 启动服务（path/open/index；强制 daemon） |
| hs_kill | 关闭指定端口或路径的服务 |
| hs_kill_all | 关闭所有运行中的服务 |
| hs_config | 显示当前配置（默认端口/域名） |

### 数据（5，批次一新增）

| 工具 | 说明 |
|------|------|
| hs_bookmark_list | 列出所有书签 |
| hs_bookmark_add | 注册书签（name 必填/path/index_page/force 布尔） |
| hs_bookmark_remove | 删除书签（name 必填） |
| hs_history | 历史启动记录 |
| hs_search | 模糊搜索服务（keyword 必填） |

## Resources（3 项，只读）

| URI | 内容 |
|-----|------|
| hs://registry | 运行中服务注册表（registry.json） |
| hs://bookmarks | 书签数据（bookmarks.json） |
| hs://config | 当前配置（hs config --json） |

AI 可直接读取资源，无需工具调用。

## 边界

- 只操作用户 registry/bookmark 数据；registry-managed（dashboard/MCP 自身）不参与 kill-all
- 工具调用通过子进程执行 `hs ... --json`，解析结构化输出
- 未 initialize 前 tools/list 与 tools/call 拒绝（-32601）

## 关联文档

- documents/hs-mcp-design-v1.0-20260624.md
- documents/hs-ai-integration-design-v1.0-20260825.md
