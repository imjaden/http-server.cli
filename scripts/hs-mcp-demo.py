#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hs-mcp-demo.py — MCP 集成验证脚本

可重复执行的 MCP 协议验证工具。每次运行独立完成指定场景，不自动启停 MCP 服务。
适用于集成调试、协议验证、AI Agent 配置参考。

用法:
  python3 scripts/hs-mcp-demo.py help        查看帮助 + 所有场景 + Agent 配置示例
  python3 scripts/hs-mcp-demo.py status      检查 MCP 服务是否在运行
  python3 scripts/hs-mcp-demo.py init        初始化握手 (initialize)
  python3 scripts/hs-mcp-demo.py tools       列出所有可用工具 (tools/list)
  python3 scripts/hs-mcp-demo.py hs_list     调用 hs_list 工具
  python3 scripts/hs-mcp-demo.py hs_status  调用 hs_status 工具 (需传端口)
  python3 scripts/hs-mcp-demo.py hs_config  调用 hs_config 工具
  python3 scripts/hs-mcp-demo.py all         完整验证流程 (status→init→tools→list→config)

场景示例:
  # 完整验证 MCP 服务是否正常工作
  python3 scripts/hs-mcp-demo.py all

  # 只查看工具有哪些
  python3 scripts/hs-mcp-demo.py tools

  # 查看 hs CLI 当前配置
  python3 scripts/hs-mcp-demo.py hs_config

环境:
  - Python 3.8+
  - 仅标准库 (urllib / json / subprocess)，零第三方依赖
  - MCP 服务需提前启动: hs mcp
"""

import json
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Optional

# ── 配置 ──────────────────────────────────────────────────────────────────────
MCP_HOST = '127.0.0.1'
MCP_PORT = 8181
MCP_URL = f'http://{MCP_HOST}:{MCP_PORT}'
MCP_MESSAGES_URL = f'{MCP_URL}/messages'

# ── ANSI ──────────────────────────────────────────────────────────────────────
if platform.system() == 'Windows':
    os.system('')
RESET = '\033[0m'
BOLD = '\033[1m'
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
MAGENTA = '\033[0;35m'


# ── 输出 ──────────────────────────────────────────────────────────────────────

def info(msg: str) -> None:
    print(f'{BLUE}[INFO]{RESET} {msg}')

def ok(msg: str) -> None:
    print(f'{GREEN}[OK]{RESET} {msg}')

def warn(msg: str) -> None:
    print(f'{YELLOW}[!]{RESET} {msg}')

def err(msg: str) -> None:
    print(f'{RED}[✗]{RESET} {msg}')

def divider(title: str = '') -> None:
    sep = '━' * 58
    if title:
        print(f'\n{CYAN}{BOLD}{sep}{RESET}')
        print(f'{CYAN}{BOLD}  {title}{RESET}')
        print(f'{CYAN}{BOLD}{sep}{RESET}\n')
    else:
        print(f'\n{CYAN}{BOLD}{sep}{RESET}\n')

def pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── MCP 连通性 ────────────────────────────────────────────────────────────────

def mcp_is_alive() -> bool:
    """检查 MCP 服务是否在运行"""
    try:
        req = urllib.request.Request(
            MCP_MESSAGES_URL, data=b'{}',
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp.read()
            return True
    except urllib.error.HTTPError:
        return True  # HTTP 错误也说明服务器在运行
    except (urllib.error.URLError, TimeoutError, ConnectionRefusedError):
        return False

def require_mcp() -> None:
    """如果 MCP 不在运行，打印启动命令后退出"""
    if mcp_is_alive():
        return
    err('MCP 服务未在运行')
    print()
    info('请先启动 MCP 服务:')
    print()
    print(f'  {BOLD}hs mcp{RESET}             启动 MCP（后台运行 SSE，默认端口 8181）')
    print(f'  {BOLD}hs mcp stop{RESET}         停止 MCP')
    print(f'  {BOLD}hs mcp status{RESET}       查看 MCP 状态')
    print()
    info('验证服务启动成功:')
    print(f'  {BOLD}python3 scripts/hs-mcp-demo.py status{RESET}')
    sys.exit(1)


# ── MCP 协议调用 ──────────────────────────────────────────────────────────────

_next_id = 1

def _call_mcp(method: str, params: Any = None) -> dict:
    """发送 JSON-RPC 2.0 请求到 MCP 服务"""
    global _next_id
    req_id = _next_id
    _next_id += 1
    body = {'jsonrpc': '2.0', 'id': req_id, 'method': method}
    if params is not None:
        body['params'] = params
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        MCP_MESSAGES_URL, data=data,
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8')
    except urllib.error.URLError as e:
        err(f'网络请求失败: {e}')
        sys.exit(1)
    except urllib.error.HTTPError as e:
        err(f'HTTP {e.code}: {e.reason}')
        sys.exit(1)
    except TimeoutError:
        err('请求超时 (15s)')
        sys.exit(1)
    if not raw or not raw.strip():
        err('收到空响应')
        sys.exit(1)
    try:
        resp_data = json.loads(raw)
    except json.JSONDecodeError as e:
        err(f'JSON 解析失败: {e}')
        sys.exit(1)
    return resp_data


# ── 子命令 ────────────────────────────────────────────────────────────────────

def cmd_help() -> None:
    """显示帮助 + 所有场景 + AI Agent 配置示例"""
    print()
    print(f'{BOLD}hs-mcp-demo.py — MCP 集成验证脚本{RESET}')
    print()
    print(f'用法:  python3 scripts/hs-mcp-demo.py {CYAN}<command>{RESET} [{CYAN}[args]{RESET}]')
    print()
    print(f'  {BOLD}help{RESET}        显示此帮助 + 配置示例')
    print(f'  {BOLD}status{RESET}      检查 MCP 服务是否在运行')
    print(f'  {BOLD}init{RESET}        初始化握手 (initialize)')
    print(f'  {BOLD}tools{RESET}       列出所有可用工具 (tools/list)')
    print(f'  {BOLD}hs_list{RESET}     调用 hs_list（列出运行中服务）')
    print(f'  {BOLD}hs_status{RESET}   调用 hs_status（例: hs_status 8080）')
    print(f'  {BOLD}hs_start{RESET}    调用 hs_start（例: hs_start /path/to/project）')
    print(f'  {BOLD}hs_kill{RESET}     调用 hs_kill（例: hs_kill 8080 或 hs_kill /path）')
    print(f'  {BOLD}hs_config{RESET}   调用 hs_config（查看配置）')
    print(f'  {BOLD}all{RESET}         完整验证流程 (status→init→tools→list→config)')
    print()
    print(f'{BOLD}━━━ 使用场景 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}')
    print()
    print(f'  {BOLD}场景 1: 完整验证 MCP 是否正常工作{RESET}')
    print(f'    python3 scripts/hs-mcp-demo.py all')
    print()
    print(f'  {BOLD}场景 2: 查看 MCP 服务状态{RESET}')
    print(f'    hs mcp status')
    print(f'    python3 scripts/hs-mcp-demo.py status')
    print()
    print(f'  {BOLD}场景 3: 查看 hs CLI 暴露了哪些工具{RESET}')
    print(f'    python3 scripts/hs-mcp-demo.py tools')
    print()
    print(f'  {BOLD}场景 4: 查询某个端口的服务状态{RESET}')
    print(f'    python3 scripts/hs-mcp-demo.py hs_status 8080')
    print()
    print(f'  {BOLD}场景 5: 启动一个新服务 (AI Agent 集成验证){RESET}')
    print(f'    python3 scripts/hs-mcp-demo.py hs_start /path/to/project')
    print()
    print(f'{BOLD}━━━ AI Agent 配置对接 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}')
    print()
    print(f'  {BOLD}Claude Desktop{RESET}')
    print(f'  claude_desktop_config.json:')
    print(f'  {{{{')
    print(f'    "mcpServers": {{')
    print(f'      "hs": {{')
    print(f'        "command": "hs",')
    print(f'        "args": ["mcp", "--transport", "sse"]')
    print(f'      }}')
    print(f'    }}')
    print(f'  }}}}')
    print()
    print(f'  {BOLD}Cursor{RESET}')
    print(f'  Settings → MCP Server → 添加:')
    print(f'    {BOLD}Type:{RESET}    SSE')
    print(f'    {BOLD}URL:{RESET}     http://127.0.0.1:8181/sse')
    print()
    print(f'  {BOLD}VS Code (GitHub Copilot){RESET}')
    print(f'  settings.json:')
    print(f'  {{{{')
    print(f'    \"mcp\": {{')
    print(f'      \"servers\": {{')
    print(f'        \"hs\": {{')
    print(f'          \"type\": \"sse\",')
    print(f'          \"url\": \"http://127.0.0.1:8181/sse\"')
    print(f'        }}')
    print(f'      }}')
    print(f'    }}')
    print(f'  }}}}')
    print()
    print(f'  {BOLD}hs CLI 工具映射{RESET}')
    print(f'  ┌────────────────────┬──────────────────────────────────────┐')
    print(f'  │  MCP Tool          │ 等价 hs 命令                        │')
    print(f'  ├────────────────────┼──────────────────────────────────────┤')
    print(f'  │ hs_list            │ hs list --json                      │')
    print(f'  │ hs_status          │ hs status <port> --json             │')
    print(f'  │ hs_start           │ hs start <path> --daemon --json     │')
    print(f'  │ hs_kill            │ hs kill <port|path> --json          │')
    print(f'  │ hs_kill_all        │ hs kill-all --json                  │')
    print(f'  │ hs_config          │ hs config --json                    │')
    print(f'  └────────────────────┴──────────────────────────────────────┘')
    print()


def cmd_status() -> None:
    """检查 MCP 服务连通性"""
    divider('MCP 服务状态检查')
    alive = mcp_is_alive()
    if alive:
        ok(f'MCP 服务运行中  →  {MCP_URL}/sse')
        print(f'    POST: {MCP_MESSAGES_URL}')
    else:
        err('MCP 服务未在运行')
        print()
        info('请启动 MCP 服务:')
        print(f'  {BOLD}hs mcp{RESET}         后台启动 SSE (默认端口 8181)')
        print(f'  {BOLD}hs mcp stop{RESET}     停止 MCP')
        print(f'  {BOLD}hs mcp status{RESET}   查看 MCP 状态')
    print()


def cmd_init() -> None:
    """初始化握手"""
    require_mcp()
    divider('MCP 初始化握手 (initialize)')
    resp = _call_mcp('initialize', {
        'protocolVersion': '2025-03-26',
        'clientInfo': {'name': 'hs-mcp-demo', 'version': '1.0.0'},
    })
    result = resp.get('result', {})
    si = result.get('serverInfo', {})
    print(f'  服务器:  {BOLD}{si.get("name")}{RESET} v{si.get("version")}')
    print(f'  协议:    {result.get("protocolVersion")}')
    print(f'  能力:    {pretty(result.get("capabilities", {}))}')
    print()
    ok('握手成功')


def cmd_tools() -> None:
    """列出所有工具"""
    require_mcp()
    divider('列出工具 (tools/list)')
    resp = _call_mcp('tools/list')
    tools = resp.get('result', {}).get('tools', [])
    print(f'  共 {len(tools)} 个工具:\n')
    for t in tools:
        name = t.get('name', '?')
        desc = t.get('description', '')
        schema = t.get('inputSchema', {})
        props = schema.get('properties', {})
        required = schema.get('required', [])
        print(f'  {BOLD}{name}{RESET}')
        print(f'    描述: {desc}')
        if props:
            for pn, pi in props.items():
                req = f' {RED}*{RESET}' if pn in required else ''
                print(f'    参数: {pn}{req} ({pi.get("type", "any")})')
        if not props:
            print(f'    参数: 无')
        print()
    ok(f'获取到 {len(tools)} 个工具')


def cmd_call_tool(name: str, tool_args: Optional[dict] = None) -> dict:
    """调用指定工具并打印结果"""
    require_mcp()
    divider(f'调用工具 ({name})')
    params = {'name': name}
    if tool_args:
        params['arguments'] = tool_args
    resp = _call_mcp('tools/call', params)
    result = resp.get('result', {})
    content = result.get('content', [])
    print(f'  isError: {result.get("isError", False)}\n')
    for item in content:
        if item.get('type') == 'text':
            text = item.get('text', '')
            try:
                parsed = json.loads(text)
                print(pretty(parsed))
            except json.JSONDecodeError:
                print(text)
    print()
    if not result.get('isError'):
        ok(f'{name} 调用成功')
    else:
        warn(f'{name} 返回错误')
    return resp


def cmd_hs_list() -> None:
    """调用 hs_list"""
    cmd_call_tool('hs_list')


def cmd_hs_config() -> None:
    """调用 hs_config"""
    cmd_call_tool('hs_config')


def cmd_hs_status(port_str: str) -> None:
    """调用 hs_status <port>"""
    cmd_call_tool('hs_status', {'port': int(port_str)})


def cmd_hs_start(path: str) -> None:
    """调用 hs_start <path>"""
    cmd_call_tool('hs_start', {'path': path})


def cmd_hs_kill(target: str) -> None:
    """调用 hs_kill <port|path>"""
    if target.isdigit():
        cmd_call_tool('hs_kill', {'port': int(target)})
    else:
        cmd_call_tool('hs_kill', {'path': target})


def cmd_all() -> None:
    """完整验证流程"""
    cmd_status()
    if not mcp_is_alive():
        return
    cmd_init()
    cmd_tools()
    cmd_hs_list()
    cmd_hs_config()
    divider()
    print(f'  {GREEN}{BOLD}完整验证通过{RESET}')
    print(f'  所有 MCP 协议步骤正常: status → init → tools → hs_list → hs_config')
    print()


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        cmd_help()
        return

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    dispatch = {
        'help':      lambda: cmd_help(),
        'status':    lambda: cmd_status(),
        'init':      lambda: cmd_init(),
        'tools':     lambda: cmd_tools(),
        'hs_list':   lambda: cmd_hs_list(),
        'hs_config': lambda: cmd_hs_config(),
        'hs_status': lambda: cmd_hs_status(rest[0]) if rest else (err('需要端口号') or cmd_help()),
        'hs_start':  lambda: cmd_hs_start(rest[0]) if rest else (err('需要路径') or cmd_help()),
        'hs_kill':   lambda: cmd_hs_kill(rest[0]) if rest else (err('需要端口或路径') or cmd_help()),
        'all':       lambda: cmd_all(),
    }

    handler = dispatch.get(cmd)
    if handler:
        handler()
    else:
        err(f'未知命令: {cmd}')
        cmd_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
