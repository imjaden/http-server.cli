#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hs mcp — MCP 协议服务器。

基于 Model Context Protocol (MCP) 的 AI Agent 集成层。
通过 JSON-RPC 2.0 over stdio/SSE 提供 hs CLI 的工具调用接口。

方案 A：直接包装 CLI，每个 tools/call 通过子进程执行 hs 命令。
零外部依赖，仅使用 Python 标准库。
"""

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from http_server_cli.utils import is_port_in_use, is_process_alive

# ── MCP 协议常量 ───────────────────────────────────────

MCP_PROTOCOL_VERSION = '2025-03-26'
SERVER_NAME = 'hs-mcp'
SERVER_VERSION = '1.0.0'

# ── Tool 定义 ──────────────────────────────────────────

@dataclass
class MCPTool:
    """MCP 工具描述"""
    name: str
    description: str
    input_schema: dict = field(default_factory=lambda: {'type': 'object', 'properties': {}})

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'description': self.description,
            'inputSchema': self.input_schema,
        }

_TOOLS = [
    MCPTool(
        name='hs_list',
        description='列出所有运行中的 HTTP 服务，包含端口、路径、PID、状态、资源占用',
        input_schema={'type': 'object', 'properties': {}},
    ),
    MCPTool(
        name='hs_status',
        description='查询单个 HTTP 服务的状态（端口或路径）',
        input_schema={
            'type': 'object',
            'properties': {
                'port': {'type': 'number', 'description': '端口号'},
            },
            'required': ['port'],
        },
    ),
    MCPTool(
        name='hs_start',
        description='启动 HTTP 服务（默认 daemon 模式）',
        input_schema={
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': '项目路径（默认当前目录）'},
                'open': {'type': 'boolean', 'description': '自动打开浏览器'},
                'index': {'type': 'string', 'description': '首页文件名'},
            },
        },
    ),
    MCPTool(
        name='hs_kill',
        description='关闭指定端口或路径的 HTTP 服务',
        input_schema={
            'type': 'object',
            'properties': {
                'port': {'type': 'number', 'description': '端口号'},
                'path': {'type': 'string', 'description': '项目路径'},
            },
        },
    ),
    MCPTool(
        name='hs_kill_all',
        description='关闭所有运行中的 HTTP 服务',
        input_schema={'type': 'object', 'properties': {}},
    ),
    MCPTool(
        name='hs_config',
        description='显示当前 hs 配置（默认端口、域名）',
        input_schema={'type': 'object', 'properties': {}},
    ),
]

_TOOL_MAP: dict[str, tuple[list[str], dict[str, str]]] = {
    'hs_list':    (['list'], {}),
    'hs_status':  (['status', '{port}'], {'port': 'port'}),
    'hs_start':   (['start', '{path}'], {'path': 'path', 'open': 'open', 'index': 'index_page'}),
    'hs_kill':    (['kill', '{port}'], {'port': 'port', 'path': 'path'}),
    'hs_kill_all': (['kill-all'], {}),
    'hs_config':  (['config'], {}),
}

# ── JSON-RPC 2.0 ───────────────────────────────────────

def _make_response(id: Any, result: Any = None, error: Optional[dict] = None) -> dict:
    """构造 JSON-RPC 2.0 响应"""
    resp: dict = {'jsonrpc': '2.0', 'id': id}
    if error:
        resp['error'] = error
    else:
        resp['result'] = result
    return resp

def _make_error(code: int, message: str, data: Any = None) -> dict:
    err: dict = {'code': code, 'message': message}
    if data is not None:
        err['data'] = data
    return err

_ERR_PARSE      = _make_error(-32700, 'Parse error')
_ERR_INVALID    = _make_error(-32600, 'Invalid Request')
_ERR_METHOD     = _make_error(-32601, 'Method not found')
_ERR_PARAMS     = _make_error(-32602, 'Invalid params')
_ERR_INTERNAL   = _make_error(-32603, 'Internal error')
_ERR_TOOL_EXEC  = _make_error(-32000, 'Tool execution failed')

# ── CLI 调用封装 ────────────────────────────────────────

def _get_hs_module() -> str:
    """获取 hs CLI 的 Python 模块路径"""
    return os.path.join(os.path.dirname(__file__), '__main__.py')

def _execute_hs(args: list[str], timeout: int = 30) -> dict:
    """执行 hs 命令并返回 JSON 结果

    Args:
        args: hs 子命令参数列表（不含 --json）
        timeout: 超时秒数

    Returns:
        JSON-RPC 结果 dict

    Raises:
        RuntimeError: 执行失败或输出非 JSON
    """
    cmd = [sys.executable, _get_hs_module()] + args + ['--json']
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace',
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'命令超时 ({timeout}s): {" ".join(cmd)}')
    except FileNotFoundError:
        raise RuntimeError(f'Python 解释器未找到: {sys.executable}')
    except OSError as e:
        raise RuntimeError(f'系统错误: {e}')

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f'命令失败 (exit={result.returncode}): {stderr or result.stdout[:500]}')

    # 解析 stdout 中的 JSON 输出
    # hs CLI 的 json_output() 输出到 stdout，可能有尾随换行/其他输出
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue

    raise RuntimeError(f'无法解析命令输出: {result.stdout[:500]}')

def _build_hs_args(tool_name: str, params: dict) -> list[str]:
    """根据工具名和参数构建 hs CLI 参数列表"""
    if tool_name not in _TOOL_MAP:
        raise ValueError(f'未知工具: {tool_name}')

    # 特殊处理：hs_kill 支持 port 或 path 二选一
    if tool_name == 'hs_kill':
        port_val = params.get('port')
        path_val = params.get('path')
        if port_val is not None:
            return ['kill', str(port_val)]
        elif path_val is not None:
            return ['kill', str(path_val)]
        else:
            return ['kill']

    template, param_map = _TOOL_MAP[tool_name]
    args = []
    for item in template:
        if item.startswith('{') and item.endswith('}'):
            key = item[1:-1]
            mapped_key = param_map.get(key, key)
            val = params.get(mapped_key)
            if val is None:
                val = params.get(key)
            if val is None and key == 'path':
                val = '.'
            if val is not None:
                args.append(str(val))
        else:
            args.append(item)

    return args

# ── MCP Server ─────────────────────────────────────────

class MCPServer:
    """MCP 协议服务器（stdio 模式）"""

    def __init__(self) -> None:
        self._session_id: Optional[str] = None
        self._initialized = False

    # ── 请求循环 ──

    def run(self) -> None:
        """主循环：从 stdin 读取 JSON-RPC 请求并响应到 stdout"""
        self._send_event('started', {'server': SERVER_NAME, 'version': SERVER_VERSION})
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._send(_make_response(None, error=_ERR_PARSE))
                continue

            # 静默处理空请求
            if not isinstance(request, dict):
                self._send(_make_response(None, error=_ERR_INVALID))
                continue

            rid = request.get('id')
            method = request.get('method', '')
            params = request.get('params', {})

            # notification（无 id）— 静默处理
            if rid is None:
                self._handle_notification(method, params)
                continue

            try:
                result = self._dispatch(method, params)
                self._send(_make_response(rid, result=result))
            except ValueError as e:
                self._send(_make_response(rid, error=_make_error(-32602, str(e))))
            except RuntimeError as e:
                self._send(_make_response(rid, error=_make_error(-32000, str(e))))
            except Exception as e:
                self._send(_make_response(rid, error=_make_error(-32603, str(e))))

    def _dispatch(self, method: str, params: dict) -> Any:
        """分发 JSON-RPC 方法"""
        if method == 'initialize':
            return self._handle_initialize(params)
        elif method == 'tools/list':
            return self._handle_list_tools()
        elif method == 'tools/call':
            return self._handle_call_tool(params)
        elif method == 'notifications/initialized':
            self._initialized = True
            return {}
        else:
            raise ValueError(f'Unknown method: {method}')

    def _handle_notification(self, method: str, params: dict) -> None:
        """处理 notification（无响应）"""
        if method == 'notifications/initialized':
            self._initialized = True
        # 其他 notification 静默忽略

    # ── 方法处理器 ──

    def _handle_initialize(self, params: dict) -> dict:
        """MCP 初始化握手"""
        version = params.get('protocolVersion', '')
        # 记录客户端信息
        client_info = params.get('clientInfo', {})
        self._session_id = f'{client_info.get("name", "unknown")}-{id(self)}'
        return {
            'protocolVersion': MCP_PROTOCOL_VERSION,
            'serverInfo': {
                'name': SERVER_NAME,
                'version': SERVER_VERSION,
            },
            'capabilities': {
                'tools': {},
            },
        }

    def _handle_list_tools(self) -> dict:
        """返回工具列表"""
        return {
            'tools': [t.to_dict() for t in _TOOLS],
        }

    def _handle_call_tool(self, params: dict) -> dict:
        """执行工具调用"""
        name = params.get('name', '')
        arguments = params.get('arguments', {})

        if not name:
            raise ValueError('Missing tool name')

        if name not in _TOOL_MAP:
            raise ValueError(f'Unknown tool: {name}')

        # 构建 hs CLI 参数
        hs_args = _build_hs_args(name, arguments)

        # 特殊处理 hs_start：强制 daemon 模式
        if name == 'hs_start' and 'foreground' not in hs_args:
            hs_args.insert(1, '--daemon')

        # 执行
        try:
            result = _execute_hs(hs_args)
        except RuntimeError as e:
            return {
                'content': [{'type': 'text', 'text': f'Error: {e}'}],
                'isError': True,
            }

        # 格式化输出
        text = json.dumps(result, ensure_ascii=False, indent=2)
        return {
            'content': [{'type': 'text', 'text': text}],
        }

    # ── 消息收发 ──

    def _send(self, msg: dict) -> None:
        """发送 JSON-RPC 消息到 stdout"""
        line = json.dumps(msg, ensure_ascii=False)
        sys.stdout.write(line + '\n')
        sys.stdout.flush()

    def _send_event(self, event: str, data: dict) -> None:
        """发送事件通知（非标准 JSON-RPC）"""
        msg = {
            'jsonrpc': '2.0',
            'method': 'notifications/event',
            'params': {'event': event, 'data': data},
        }
        self._send(msg)

# ── SSE 传输模式 ───────────────────────────────────────

def _serve_sse(port: int = 8181) -> None:
    """SSE 模式 MCP Server（HTTP 传输），注册到 managed registry"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from http_server_cli.registry_managed import ManagedRegistry

    # ── 重复执行检测 ──
    mreg = ManagedRegistry()
    existing = mreg.find(name='mcp')
    if existing:
        epid = existing.get('pid')
        eport = existing.get('port')
        if epid and is_process_alive(epid) and is_port_in_use(eport):
            from http_server_cli.utils import format_duration as _fd
            duration = _fd(existing.get('started_at', ''))
            print(f'📡  hs mcp 已在运行')
            print(f'    🔧  http://127.0.0.1:{eport}/sse  (PID: {epid})')
            print(f'    📊  时长: {duration}')
            print(f'    💡  SSE endpoint: http://127.0.0.1:{eport}/sse')
            return
        else:
            mreg.remove(name='mcp')

    _sse_clients: list[threading.Event] = []
    _sse_lock = threading.Lock()

    class SSEHandler(BaseHTTPRequestHandler):
        server_instance: MCPServer = MCPServer()

        def do_GET(self) -> None:
            if self.path == '/sse':
                self._handle_sse()
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self) -> None:
            if self.path == '/messages':
                self._handle_message()
            else:
                self.send_response(404)
                self.end_headers()

        def _handle_sse(self) -> None:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            session_id = f'sse-{id(self)}'
            self.wfile.write(f'event: start\ndata: {json.dumps({"sessionId": session_id})}\n\n'.encode())
            self.wfile.flush()

            event = threading.Event()
            with _sse_lock:
                _sse_clients.append(event)
            try:
                event.wait()
            except KeyboardInterrupt:
                pass
            finally:
                with _sse_lock:
                    if event in _sse_clients:
                        _sse_clients.remove(event)

        def _handle_message(self) -> None:
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            try:
                request = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"Invalid JSON"}')
                return

            rid = request.get('id')
            method = request.get('method', '')
            params = request.get('params', {})

            try:
                result = self.server_instance._dispatch(method, params)
                response = _make_response(rid, result=result)
            except Exception as e:
                response = _make_response(rid, error=_make_error(-32603, str(e)))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())

            msg = json.dumps(response, ensure_ascii=False)
            with _sse_lock:
                for client in _sse_clients[:]:
                    try:
                        pass
                    except Exception:
                        _sse_clients.remove(client)

        def log_message(self, format: str, *args) -> None:
            pass

    server = HTTPServer(('127.0.0.1', port), SSEHandler)
    # 注册 managed
    mreg.add(name='mcp', type_='sse', port=port, pid=os.getpid(), transport='sse')
    print(f'📡  hs mcp (SSE)  →  http://127.0.0.1:{port}/sse')
    print('⏹  按 Ctrl+C 停止\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        mreg.remove(name='mcp')
        print('📡  MCP SSE 服务已停止')
        server.server_close()

# ── 入口函数 ───────────────────────────────────────────

def serve_stdio() -> None:
    """启动 MCP Server（stdio 模式）"""
    server = MCPServer()
    server.run()

def serve_sse(port: int = 8181, daemon: bool = False) -> None:
    """启动 MCP Server（SSE 模式）

    Args:
        port: 监听端口
        daemon: 后台守护模式
    """
    if daemon:
        import subprocess as _sp
        hs_entry = os.path.join(os.path.dirname(__file__), '__main__.py')
        cmd = [sys.executable, hs_entry, 'mcp', '--transport', 'sse', '-p', str(port)]
        proc = _sp.Popen(
            cmd,
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
        )
        # 父进程注册 managed
        from http_server_cli.registry_managed import ManagedRegistry
        mreg = ManagedRegistry()
        mreg.add(name='mcp', type_='sse', port=port, pid=proc.pid, transport='sse')
        print(f'📡  hs mcp (SSE daemon) →  http://127.0.0.1:{port}/sse  (PID: {proc.pid})')
        print(f'⏹  使用 hs kill {port} 或 kill {proc.pid} 停止')
        return
    _serve_sse(port=port)
