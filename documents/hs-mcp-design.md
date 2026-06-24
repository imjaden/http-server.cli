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
3. **SSE 模式为默认** — 自动后台常驻，适合持续集成的 AI Agent 场景
4. **复用 --json 输出** — CLI 的 `--json` 输出格式就是 MCP Tool 的响应格式

---

## 二、用法

```bash
hs mcp                              # 默认 SSE 模式，自动后台运行（常驻服务）
hs mcp --port 8181                  # SSE 模式指定端口
hs mcp --transport stdio            # stdio 模式（一次性，AI Agent 原生支持）
hs mcp help                         # 显示 mcp 专属帮助
hs mcp status                       # 查询 MCP 服务运行状态（端口/PID/时长）
hs mcp stop                         # 停止 MCP 服务（查注册表 → 杀进程 → 清理记录）
hs mcp restart                      # 停止后重新启动 MCP 服务（端口 8181）
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
Command: hs mcp --transport stdio
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
| `hs_start` | 启动 HTTP 服务 | `{ path: string, open?: bool, index?: string }` |
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

## 四、实现方案：直接包装 CLI

### 架构

```
AI Agent                    MCP Server (hs mcp)
   │                              │
   │  JSON-RPC 2.0 over stdio     │
   │  or SSE / HTTP               │
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

**`src/http_server_cli/mcp.py`** (~500 行)：

```
mcp.py
  ├── MCPTool         # dataclass: name, description, input_schema
  ├── MCPServer       # 主类: 初始化, 请求循环, 分发
  │   ├── _read_request()      # 从 stdin 读取 JSON-RPC
  │   ├── _send_response()     # 写入 stdout
  │   ├── _handle_initialize() # 协议握手
  │   ├── _handle_list_tools() # 返回工具列表
  │   └── _handle_call_tool()  # 执行 hs 命令
  ├── serve_stdio()   # stdio 入口函数
  ├── serve_sse()     # SSE 入口函数（含 daemon 逻辑）
  └── _serve_sse()    # SSE 内部函数（HTTP 服务主循环）
```

### 工具到命令的映射

```python
_TOOL_MAP = {
    'hs_list':    (['list'], {}),
    'hs_status':  (['status', '{port}'], {'port': 'port'}),
    'hs_start':   (['start', '{path}'], {'path': 'path', 'open': 'open',
                   'index': 'index_page'}),
    'hs_kill':    (['kill', '{port}'], {'port': 'port', 'path': 'path'}),
    'hs_kill_all': (['kill-all'], {}),
    'hs_config':  (['config'], {}),
}
```

### 隔离性说明

采用子进程包装而非共享库调用，原因：
- **隔离性强** — MCP 层不影响业务进程状态
- **一致性** — 与用户手动执行 `hs ...` 行为完全一致
- **调试简单** — 独立进程，竞态风险低
- **响应速度** — 毫秒级子进程启动时间，可接受

---

## 五、传输模式对比

### SSE 模式（默认）

| 路由 | 功能 |
|------|------|
| `GET /sse` | SSE 事件流，服务端→客户端推送 |
| `POST /messages` | 客户端→服务端消息 |

SSE 模式复用 `MCPServer._dispatch()` 的消息分发逻辑，仅传输层不同。

### stdio 模式（显式指定）

```
hs mcp --transport stdio
```

直接在 stdin/stdout 上运行 JSON-RPC 2.0，适合 Claude Desktop 等原生支持 stdio 的客户端，无需 HTTP 端口。

### 对比表

| 维度 | SSE（默认） | stdio |
|------|:-----------:|:-----:|
| 默认值 | ✅ 是 | — |
| 后台常驻 | ✅ 自动 daemon | ❌ 占用终端 |
| 断线重连 | ✅ 可重连 | ❌ 进程结束即终止 |
| 端口占用 | 8181（可配） | 无 |
| 注册到管理表 | ✅ registry-managed.json | ❌ 无状态 |
| 重复运行检测 | ✅ 自动检测 + 提示 | ❌ 不适用 |
| AI Agent 适配 | 需 HTTP 地址 | 原生支持 |
| VS Code / Cursor | ℹ️ 需 HTTP 代理 | ✅ 直接配置 |
| 远程访问 | ✅ 可代理转发 | ❌ 本地进程 |
| 生命周期 | 独立进程，hs kill 可停 | 随父进程退出 |

### 何时使用哪种模式

**选 SSE（默认）：**
- 需要永久常驻的 MCP 服务
- 多人共享或远程开发环境
- 使用 VS Code 或 Cursor 等通过 HTTP 连接的 IDE
- 需要重复运行检测防止端口冲突

**选 stdio（`--transport stdio`）：**
- Claude Desktop 等原生支持 stdio 的客户端
- 临时使用，用完即止的场景
- 不希望占用端口的环境
- CI/CD pipeline 中的一次性工具调用

---

## 六、关键实现细节

### 1. SSE 自动 daemon 与 HS_MCP_WORKER 防循环

SSE 模式默认自动 daemon（后台运行），通过 `HS_MCP_WORKER` 环境变量防止无限子进程链：

```
用户执行 hs mcp（默认 SSE）
  │
  ├─ 检查 HS_MCP_WORKER=1？
  │   └─ 否 → 进入 daemon 分支
  │       ├─ 设置 HS_MCP_WORKER=1 环境变量
  │       ├─ 通过 subprocess.Popen 启动子进程（后台）
  │       │   └─ 子进程：HS_MCP_WORKER=1 → 直接进入 _serve_sse()
  │       ├─ 注册到 ManagedRegistry（PID 为子进程 PID）
  │       ├─ 输出提示信息到终端
  │       └─ 父进程退出（终端归还原用户）
  │
  └─ 是 → 直接执行 _serve_sse() 进入 HTTP 主循环
```

**为什么需要 HS_MCP_WORKER：**
- `hs mcp` 本身就是一个 `hs` 命令的子进程（通过子进程调用）
- 如果 daemon 分支再次调用 `hs mcp`，会形成无限循环
- `HS_MCP_WORKER=1` 标记子进程已脱离 daemon 流程，直接启动服务

### 2. 重复运行检测

SSE 模式在 `_serve_sse()` 启动前检查 `registry-managed.json`：

```python
mreg = ManagedRegistry()
existing = mreg.find(name='mcp')
if existing:
    # 验证 PID 存活 + 端口可用
    if is_process_alive(epid) and is_port_in_use(eport):
        # 输出已有服务信息并返回，不启动新进程
        return
    else:
        # 进程已死，清理旧记录后继续启动
        mreg.remove(name='mcp')
```

### 3. Managed Registry 注册

SSE 模式在 HTTP 服务器启动后立即注册到 `registry-managed.json`：

```python
mreg.add(name='mcp', type_='sse', port=port, pid=os.getpid(), transport='sse')
```

- daemon 模式：父进程注册，PID 指向子进程
- 前台模式（HS_MCP_WORKER=1）：当前进程注册

注销发生在 `KeyboardInterrupt` 时自动清理，或通过 `hs list` 查看状态。

### 4. hs start 强制 daemon 模式

MCP 场景下 `hs_start` 工具的 `foreground` 参数被忽略，始终以 daemon 方式启动：

```python
if name == 'hs_start' and 'foreground' not in hs_args:
    hs_args.insert(1, '--daemon')
```

确保 AI Agent 发起的服务启动不会阻塞 MCP 连接。

---

## 七、MCP 与 Dashboard 的关系

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
- **数据源相同**：都通过子进程调用 `hs --json`
- **可独立部署**：dashboard 不依赖 MCP，MCP 不依赖 dashboard
- **共享注册表**：两者都注册到 `registry-managed.json`，`hs list` 合并展示

---

## 八、代码路径

| 文件 | 职责 | 代码量 |
|------|------|--------|
| `src/http_server_cli/mcp.py` | MCP 协议层 + SSE HTTP 服务 | ~510 行 |
| `src/http_server_cli/cli.py` | CLI 入口 `_cmd_mcp` + `_manage_mcp` | ~50 行 |
| `src/http_server_cli/registry_managed.py` | ManagedRegistry 持久化注册 | ~100 行 |

`_cmd_mcp` 与 `_manage_mcp` 在 `cli.py`：

```python
@_register
def _cmd_mcp(manager, args):
    """hs mcp — MCP Server（自动后台运行 SSE）"""
    sub = args[0] if args else None
    if sub in ('help', 'stop', 'status', 'restart'):
        _manage_mcp(sub)
        return

    parser = argparse.ArgumentParser(prog='hs mcp', add_help=False)
    parser.add_argument('--transport', choices=['stdio', 'sse'], default='sse')
    parser.add_argument('--port', type=int, default=8181)
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    if parsed.transport == 'stdio':
        from http_server_cli.mcp import serve_stdio
        serve_stdio()
    else:
        from http_server_cli.mcp import serve_sse
        serve_sse(port=parsed.port, daemon=True)


def _manage_mcp(subcmd: str) -> None:
    """管理 MCP 服务：stop / status / restart / help"""
    from http_server_cli.registry_managed import ManagedRegistry
    from http_server_cli.utils import (eprint, format_duration,
                                        is_process_alive, is_port_in_use)
    import os, signal, time

    mreg = ManagedRegistry()
    entry = mreg.find(name='mcp')

    if subcmd == 'help':
        print('━━━ hs mcp ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        print('  hs mcp                    后台运行 SSE（默认）')
        print('  hs mcp --transport stdio  前台运行 stdio 模式')
        print('  hs mcp --port PORT        指定端口')
        print('  hs mcp stop               停止 MCP 服务')
        print('  hs mcp status             查看运行状态')
        print('  hs mcp restart            重启 MCP 服务')
        print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        return

    if subcmd in ('stop', 'status', 'restart') and not entry:
        eprint('MCP 未在运行', 'ℹ️')
        return

    port = entry.get('port', '?')
    pid = entry.get('pid')

    if subcmd == 'status':
        alive = (pid and is_process_alive(pid)
                 and is_port_in_use(port))
        duration = format_duration(entry.get('started_at', ''))
        icon = '🟢' if alive else '🔴'
        print(f'{icon}  hs mcp (SSE)  →  http://127.0.0.1:{port}/sse')
        print(f'    🔧  PID: {pid}  |  时长: {duration}')
        return

    if subcmd in ('stop', 'restart'):
        if pid and is_process_alive(pid):
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(0.3)
                if is_process_alive(pid):
                    os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        mreg.remove(name='mcp')
        eprint(f'MCP (端口 {port}) 已停止', '🛑')

    if subcmd == 'restart':
        from http_server_cli.mcp import serve_sse
        serve_sse(port=8181, daemon=True)
```
