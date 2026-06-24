# hs mcp — 设计文档

> 基于 Model Context Protocol (MCP) 的 AI Agent 集成层，零外部依赖。

---

## 一、概述

`hs mcp` 启动一个 MCP 协议服务器，让 AI Agent（Claude Desktop, Cursor, VS Code 等）通过工具调用直接管理 `hs` 服务。

### MCP 协议简介

MCP (Model Context Protocol) 是 Anthropic 提出的开放协议，定义了 AI 应用与外部工具/数据源的交互标准。MCP Server 通过 **stdio** 或 **SSE** 两种传输方式暴露工具。

### 设计原则

1. **零外部依赖** — MCP 协议基于 JSON-RPC 2.0，直接用 stdio 通信，无需 SDK
2. **薄封装层** — MCP Server 不实现任何业务逻辑，仅将 `hs --json` 命令包装为 MCP Tool
3. **优先 stdio 模式** — AI Agent 原生支持，无需启动独立 HTTP 服务
4. **复用 --json 输出** — CLI 的 `--json` 输出格式就是 MCP Tool 的响应格式

---

## 二、用法

```bash
hs mcp                     # 启动 MCP Server（stdio 模式）
hs mcp --transport sse     # SSE 模式（HTTP 服务）
hs mcp --port 8181         # SSE 模式指定端口
```

### AI Agent 配置示例

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hs": {
      "command": "hs",
      "args": ["mcp", "--port", "8181"]
    }
  }
}
```

**Cursor**:

```
Command: hs mcp
```

---

## 三、MCP 协议

### 协议基础

MCP 基于 JSON-RPC 2.0，通过 stdio 的 stdin/stdout 通信。

**初始化请求：**

```json
// → Client sends:
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
  "protocolVersion": "2025-03-26",
  "clientInfo": {"name": "claude-ai", "version": "1.0.0"}
}}

// ← Server responds:
{"jsonrpc": "2.0", "id": 1, "result": {
  "protocolVersion": "2025-03-26",
  "serverInfo": {"name": "hs-mcp", "version": "1.0.0"},
  "capabilities": {"tools": {}}
}}
```

### 工具列表

| 工具名 | 描述 | 参数 |
|--------|------|------|
| `hs_list` | 列出所有运行中的服务 | `{}` |
| `hs_status` | 查询单个服务状态 | `{ port: number }` |
| `hs_start` | 启动 HTTP 服务 | `{ path: string, open?: bool, daemon?: bool, foreground?: bool, index?: string }` |
| `hs_kill` | 关闭指定服务 | `{ port?: number, path?: string }` |
| `hs_kill_all` | 关闭所有服务 | `{}` |
| `hs_config` | 显示当前配置 | `{}` |

### 工具注册

```json
// → Client calls tools/list:
{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}

// ← Server responds:
{"jsonrpc": "2.0", "id": 2, "result": {
  "tools": [
    {
      "name": "hs_list",
      "description": "列出所有运行中的 HTTP 服务",
      "inputSchema": {
        "type": "object",
        "properties": {}
      }
    },
    {
      "name": "hs_kill",
      "description": "关闭指定端口或路径的服务",
      "inputSchema": {
        "type": "object",
        "properties": {
          "port": {"type": "number", "description": "端口号"},
          "path": {"type": "string", "description": "项目路径"}
        }
      }
    }
  ]
}}
```

---

## 四、实现方案 A：直接包装 CLI（推荐）

### 架构

```
AI Agent                    MCP Server (hs mcp)
   │                              │
   │  JSON-RPC 2.0 over stdio     │
   ├─────────────────────────────▶│
   │  tools/call hs_kill          │
   │                              ├─▶ subprocess hs kill 8080 --json
   │                              │◀─ {"success": true, ...}
   │◀─────────────────────────────│
   │  JSON-RPC 响应               │
```

### 核心逻辑

MCP Server 对每个 `tools/call` 请求，构造对应的 `hs <command> --json` 命令并执行：

```python
def _execute_hs(args: list) -> dict:
    """执行 hs 命令并返回 JSON 结果"""
    import subprocess, json
    cmd = [sys.executable, '-m', 'http_server_cli'] + args + ['--json']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)
```

### 文件结构

**新增 `src/http_server_cli/mcp.py`** (~150 行)：

```
mcp.py
  ├── MCPTool         # dataclass: name, description, input_schema
  ├── MCPServer       # 主类: 初始化, 请求循环, 分发
  │   ├── _read_request()      # 从 stdin 读取 JSON-RPC
  │   ├── _send_response()     # 写入 stdout
  │   ├── _handle_initialize() # 协议握手
  │   ├── _handle_list_tools() # 返回工具列表
  │   └── _handle_call_tool()  # 执行 hs 命令
  └── serve_stdio()   # 入口函数
```

### 工具到命令的映射

```python
_TOOL_MAP = {
    'hs_list':    (['list'], {}),
    'hs_status':  (['status', '{port}'], {'port': 'port'}),
    'hs_start':   (['start', '{path}'], {'path': 'path', 'open': 'open_browser',
                   'daemon': 'daemon', 'foreground': 'foreground',
                   'index': 'index_page'}),
    'hs_kill':    (['kill', '{port}'], {'port': 'port', 'path': 'path'}),
    'hs_kill_all': (['kill-all'], {}),
    'hs_config':  (['config'], {}),
}
```

---

## 五、实现方案 B：共享库调用（备选）

### 架构

```
MCP Server
   │
   ├─▶ from http_server_cli.server import ServerManager
   │
   ├─▶ mgr = ServerManager()
   ├─▶ mgr.list(json=True)     # 直接调用
   ├─▶ mgr.kill('8080', json=True)
   └─▶ ...
```

### 优缺点对比

| 维度 | 方案 A：包装 CLI | 方案 B：共享库 |
|------|:---:|:---:|
| 实现复杂度 | ★☆☆ | ★★☆ |
| 隔离性（MCP 层不影响业务状态） | ✅ 强 | ⚠️ 共享进程状态 |
| 跨版本兼容 | ✅ CLI 接口稳定 | ⚠️ 内部 API 可能变 |
| 调试难度 | ★☆☆ 独立进程 | ★★☆ 同进程竞态 |
| 响应速度 | 毫秒级（子进程启动时间） | 微秒级（直接调用） |

**推荐方案 A**：隔离性好，与 CLI 行为一致，调试简单。

---

## 六、SSE 模式（可选）

SSE 模式通过 HTTP 提供 MCP 服务，适合远程访问。

```
hs mcp --transport sse --port 8181
```

相比 stdio 模式新增：

| 路由 | 功能 |
|------|------|
| `GET /sse` | SSE 事件流，服务端→客户端消息 |
| `POST /messages` | 客户端→服务端消息 |

实现上，SSE 模式复用 `MCPServer` 的消息分发逻辑，仅传输层不同。

---

## 七、工作量估算

### 方案 A（推荐）

| 模块 | 文件 | 代码量 | 时间 |
|------|------|--------|------|
| MCP 协议处理 | `mcp.py` | ~120 行 | 2h |
| CLI 入口 | `cli.py` | +5 行 | 0.5h |
| 测试 | `tests/test_mcp.py` | ~80 行 | 1.5h |
| **合计** | | **~205 行** | **~0.5 天** |

### 方案 B（备选）

| 模块 | 代码量 | 时间 |
|------|--------|------|
| MCP 协议 + 业务逻辑 | ~180 行 | 3h |
| **合计** | | **~0.5 天** |

---

## 八、MCP 与 Dashboard 的关系

```
hs CLI (--json)
   │
   ├── hs dashboard  →  REST API  →  Browser UI
   │                      (人用)
   │
   └── hs mcp        →  JSON-RPC  →  AI Agent
                           (机用)
```

两者独立：
- **Dashboard** 提供可视化页面给人看，需要 HTML/CSS/JS
- **MCP Server** 提供结构化接口给 AI 用，纯 JSON，不需要 UI
- **数据源相同**：都通过 `ServerManager`（方案 B）或子进程调用（方案 A）操作
- **可独立部署**：dashboard 不依赖 MCP，MCP 不依赖 dashboard
