#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hs-mcp-demo.py — MCP 集成示例 (Python 版本)

使用 Python 标准库 (urllib, subprocess, signal, json) 演示通过 HTTP POST
调用 MCP SSE 接口与 hs CLI 的 MCP 服务器交互。

演示流程:
  1. 检查环境依赖
  2. 启动 hs mcp (SSE 模式, 后台进程)
  3. 初始化握手 (POST /messages, method: initialize)
  4. 列出工具 (POST /messages, method: tools/list)
  5. 调用 hs_list (POST /messages, method: tools/call)
  6. 调用 hs_config (POST /messages, method: tools/call)
  7. 自动清理后台进程

用法:
  python3 scripts/hs-mcp-demo.py

依赖:
  - Python 3.8+
  - http_server_cli 模块 (pip install http-server-cli 或 pip install -e .)
  - 仅使用了标准库，无第三方依赖

MCP 协议:
  - HTTP POST 到 http://127.0.0.1:8181/messages
  - JSON-RPC 2.0 格式
  - id 从 1 递增

作者: hs CLI Team
"""

import json
import os
import platform
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Optional

# ── 配置 ──────────────────────────────────────────────────────────────────────
MCP_HOST = '127.0.0.1'
MCP_PORT = 8181
MCP_URL = f'http://{MCP_HOST}:{MCP_PORT}'
MCP_MESSAGES_URL = f'{MCP_URL}/messages'
MCP_SSE_URL = f'{MCP_URL}/sse'

# 项目根目录（脚本位于 scripts/ 下）
PROJECT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

# ── ANSI 颜色 ─────────────────────────────────────────────────────────────────
# 支持 Windows 10+ 的 VT 转义
if platform.system() == 'Windows':
    os.system('')  # 启用 ANSI 支持

RESET = '\033[0m'
BOLD = '\033[1m'
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
MAGENTA = '\033[0;35m'


# ── 输出辅助 ──────────────────────────────────────────────────────────────────

def info(msg: str) -> None:
    """蓝色 [INFO] 提示"""
    print(f'{BLUE}[INFO]{RESET} {msg}')


def ok(msg: str) -> None:
    """绿色 [✓] 成功"""
    print(f'{GREEN}[✓]{RESET} {msg}')


def warn(msg: str) -> None:
    """黄色 [!] 警告"""
    print(f'{YELLOW}[!]{RESET} {msg}')


def error(msg: str) -> None:
    """红色 [✗] 错误"""
    print(f'{RED}[✗]{RESET} {msg}')


def header(title: str) -> None:
    """带分隔线的章节标题"""
    sep = '━' * 60
    print(f'\n{CYAN}{BOLD}{sep}{RESET}')
    print(f'{CYAN}{BOLD}  {title}{RESET}')
    print(f'{CYAN}{BOLD}{sep}{RESET}\n')


def pretty_json(data: Any) -> str:
    """格式化 JSON 输出"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def show_request(method: str, url: str, body: dict) -> None:
    """友好打印请求内容"""
    print(f'{MAGENTA}> POST{RESET} {BLUE}{url}{RESET}')
    print(f'{MAGENTA}> Body:{RESET}')
    for line in pretty_json(body).split('\n'):
        print(f'  {line}')
    print()


# ── MCP HTTP 调用 ─────────────────────────────────────────────────────────────

def mcp_post_request(request_body: dict, step_name: str = '') -> dict:
    """发送 HTTP POST 请求到 MCP /messages 端点

    Args:
        request_body: JSON-RPC 2.0 请求体
        step_name: 当前步骤名称（用于错误提示）

    Returns:
        解析后的 JSON-RPC 响应 dict

    Raises:
        SystemExit: 网络错误、HTTP 错误、空响应时直接退出
    """
    show_request('POST', MCP_MESSAGES_URL, request_body)

    data = json.dumps(request_body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        MCP_MESSAGES_URL,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8')
    except urllib.error.URLError as e:
        error(f'{step_name} — 网络请求失败: {e}')
        sys.exit(1)
    except urllib.error.HTTPError as e:
        error(f'{step_name} — HTTP {e.code}: {e.reason}')
        sys.exit(1)
    except TimeoutError:
        error(f'{step_name} — 请求超时 (15s)')
        sys.exit(1)

    if not raw or not raw.strip():
        error(f'{step_name} — 收到空响应')
        sys.exit(1)

    try:
        response = json.loads(raw)
    except json.JSONDecodeError as e:
        error(f'{step_name} — 响应 JSON 解析失败: {e}')
        print(f'  原始响应: {raw[:500]}')
        sys.exit(1)

    print(pretty_json(response))
    print()

    # 检查 JSON-RPC 错误
    if 'error' in response and response['error'] is not None:
        err = response['error']
        warn(f'{step_name} — 返回错误: [{err.get("code")}] {err.get("message")}')
        if err.get('data'):
            print(f'  Data: {pretty_json(err["data"])}')

    return response


# ── 服务管理 ──────────────────────────────────────────────────────────────────

_mcp_process: Optional[subprocess.Popen] = None


def _find_hs_command() -> list[str]:
    """查找可用的 hs CLI 命令

    Returns:
        命令列表 (如 ['hs', 'mcp'] 或 ['python3', '-m', 'http_server_cli', 'mcp'])

    Raises:
        SystemExit: 如果找不到任何可用的 hs CLI
    """
    # 优先使用系统 hs 命令
    try:
        result = subprocess.run(
            ['hs', '--help'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return ['hs', 'mcp']
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 尝试使用 python -m 启动
    # 先尝试项目中的 src 目录
    src_dir = os.path.join(PROJECT_DIR, 'src')
    test_code = (
        'import sys; '
        f'sys.path.insert(0, {json.dumps(src_dir)}); '
        'from http_server_cli import __version__; '
        'print(__version__)'
    )
    try:
        result = subprocess.run(
            [sys.executable, '-c', test_code],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            ver = result.stdout.strip()
            return [sys.executable, '-c',
                    f'import sys; sys.path.insert(0, {json.dumps(src_dir)}); '
                    f'from http_server_cli.mcp import serve_sse; serve_sse(port={MCP_PORT})']
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 最后尝试 pip 安装的模块
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'http_server_cli', '--help'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return [sys.executable, '-m', 'http_server_cli', 'mcp']
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    error('找不到 hs CLI')
    print()
    print('  请先安装:')
    print('    pip install http-server-cli')
    print('  或从项目目录运行:')
    print('    pip install -e .')
    sys.exit(1)


def start_mcp_server() -> subprocess.Popen:
    """启动 hs mcp 服务器 (SSE 模式, 后台进程)

    Returns:
        子进程 Popen 对象

    Raises:
        SystemExit: 启动失败
    """
    global _mcp_process

    cmd = _find_hs_command()

    # 如果找到的是 hs mcp，需要添加 SSE 参数
    if cmd == ['hs', 'mcp']:
        cmd = ['hs', 'mcp', '--transport', 'sse', '-p', str(MCP_PORT)]
    elif cmd == [sys.executable, '-m', 'http_server_cli', 'mcp']:
        cmd = [sys.executable, '-m', 'http_server_cli', 'mcp',
               '--transport', 'sse', '-p', str(MCP_PORT)]

    cmd_display = ' '.join(cmd)
    info(f'启动命令: {cmd_display}')
    info(f'工作目录: {PROJECT_DIR}')

    try:
        _mcp_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_DIR,
        )
    except FileNotFoundError as e:
        error(f'无法启动 hs mcp: {e}')
        sys.exit(1)
    except OSError as e:
        error(f'系统错误: {e}')
        sys.exit(1)

    return _mcp_process


def wait_for_mcp(timeout: int = 15) -> bool:
    """等待 MCP 服务器就绪（轮询 /messages 端点）

    Args:
        timeout: 最大等待秒数

    Returns:
        就绪则 True，超时则 False
    """
    info(f'等待 MCP 服务器就绪 (超时 {timeout}s)...')
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        # 检查进程是否还活着
        if _mcp_process and _mcp_process.poll() is not None:
            # 进程已退出，读取 stderr 获取错误信息
            _, stderr = _mcp_process.communicate(timeout=2)
            error(f'hs mcp 进程已提前退出 (exit={_mcp_process.returncode})')
            if stderr:
                stderr_text = stderr.decode('utf-8', errors='replace')[:500]
                print(f'  stderr: {stderr_text}')
            return False

        # 尝试发送一个简单的 HTTP 请求来检查服务器是否就绪
        try:
            req = urllib.request.Request(
                MCP_MESSAGES_URL,
                data=b'{}',
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                # 只要连接成功就认为就绪（即使 400 响应也表明服务器在运行）
                _ = resp.read()
                return True
        except urllib.error.HTTPError as e:
            # HTTP 错误也说明服务器在运行
            if e.code in (400, 405, 500):
                return True
        except (urllib.error.URLError, TimeoutError, ConnectionRefusedError):
            pass

        # 没就绪，等待后重试
        time.sleep(0.5)

    return False


def stop_mcp_server() -> None:
    """停止 MCP 服务器后台进程"""
    global _mcp_process
    if _mcp_process is None:
        return

    info('正在停止 hs mcp...')

    # 先尝试 SIGTERM 优雅停止
    if _mcp_process.poll() is None:
        try:
            _mcp_process.terminate()
            _mcp_process.wait(timeout=5)
            ok('hs mcp 已停止 (SIGTERM)')
        except subprocess.TimeoutExpired:
            warn('SIGTERM 超时，发送 SIGKILL...')
            try:
                _mcp_process.kill()
                _mcp_process.wait(timeout=3)
                ok('hs mcp 已停止 (SIGKILL)')
            except Exception as e:
                warn(f'强制停止失败: {e}')

    _mcp_process = None


def cleanup() -> None:
    """清理函数 — 停止 MCP 服务器并打印完成信息"""
    stop_mcp_server()
    print()
    ok('演示脚本已清理完毕')


def signal_handler(signum: int, frame) -> None:
    """信号处理 — Ctrl+C 时的清理"""
    print()
    warn(f'收到信号 {signum}，正在清理...')
    cleanup()
    sys.exit(0)


# ── 主演示流程 ────────────────────────────────────────────────────────────────

def step_check_environment() -> None:
    """Step 1: 检查环境依赖"""
    header('Step 1: 检查环境依赖')

    # Python 版本检查
    py_ver = sys.version_info
    if py_ver.major < 3 or (py_ver.major == 3 and py_ver.minor < 8):
        error(f'Python 版本过低: {sys.version}')
        print('  需要 Python 3.8+')
        sys.exit(1)
    ok(f'Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')

    # 检查 http_server_cli 模块
    try:
        # 尝试从项目 src 导入
        src_dir = os.path.join(PROJECT_DIR, 'src')
        if os.path.isdir(src_dir):
            sys.path.insert(0, src_dir)
        from http_server_cli import __version__ as hs_ver  # noqa: F811
        ok(f'http_server_cli 模块可用 (version {hs_ver})')
    except ImportError:
        error('http_server_cli 模块未找到')
        print()
        print('  请先安装:')
        print('    pip install http-server-cli')
        print('  或从项目目录运行:')
        print('    pip install -e .')
        sys.exit(1)

    # 检查端口是否被占用
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((MCP_HOST, MCP_PORT))
        sock.close()
    except OSError:
        warn(f'端口 {MCP_PORT} 已被占用，跳过启动...')
        # 如果端口已被占用，测试是否真的是 MCP 服务
        try:
            test_body = json.dumps({
                'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                'params': {'protocolVersion': '2025-03-26', 'clientInfo': {'name': 'hs-mcp-demo', 'version': '1.0.0'}}
            }).encode('utf-8')
            req = urllib.request.Request(
                MCP_MESSAGES_URL, data=test_body,
                headers={'Content-Type': 'application/json'}, method='POST',
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read().decode('utf-8')
                init_resp = json.loads(raw)
                server_name = init_resp.get('result', {}).get('serverInfo', {}).get('name', '')
                if server_name == 'hs-mcp':
                    ok('检测到已在运行的 hs mcp 服务')
                else:
                    warn(f'端口 {MCP_PORT} 上运行的不是 hs mcp (server: {server_name})')
                    sys.exit(1)
        except Exception:
            error(f'端口 {MCP_PORT} 被占用但非 MCP 服务')
            sys.exit(1)
        print()


def step_start_server() -> None:
    """Step 2: 启动 hs mcp (SSE 模式)"""
    header(f'Step 2: 启动 hs mcp（SSE 模式，端口 {MCP_PORT}）')

    proc = start_mcp_server()

    # 等待就绪
    if wait_for_mcp():
        ok(f'hs mcp 已启动 (PID: {proc.pid})')
        info(f'SSE endpoint: {MCP_SSE_URL}')
        info(f'POST endpoint: {MCP_MESSAGES_URL}')
    else:
        # 检查进程是否已退出
        if proc.poll() is not None:
            _, stderr = proc.communicate(timeout=2)
            error(f'hs mcp 未能启动 (exit={proc.returncode})')
            if stderr:
                decoded = stderr.decode('utf-8', errors='replace')[:500]
                print(f'  stderr: {decoded}')
        else:
            error('hs mcp 启动超时')
            proc.kill()
            proc.wait(timeout=3)
        sys.exit(1)

    print()


def step_initialize() -> dict:
    """Step 3: MCP 初始化握手

    Returns:
        初始化响应 dict (包含 serverInfo, capabilities 等)
    """
    header('Step 3: 初始化握手 — POST /messages (method: initialize)')

    request = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'initialize',
        'params': {
            'protocolVersion': '2025-03-26',
            'clientInfo': {
                'name': 'hs-mcp-demo-py',
                'version': '1.0.0',
            },
        },
    }

    response = mcp_post_request(request, step_name='initialize')

    # 验证响应
    result = response.get('result', {})
    server_info = result.get('serverInfo', {})
    server_name = server_info.get('name', 'unknown')
    server_version = server_info.get('version', '?')

    if server_name == 'hs-mcp':
        ok(f'MCP 握手成功 — 已连接到 "{server_name}" v{server_version}')
    else:
        warn(f'服务器名称: {server_name} (期望: hs-mcp)')

    # 检查 capabilities
    capabilities = result.get('capabilities', {})
    if 'tools' in capabilities:
        ok('服务器支持 tools 能力')

    protocol_version = result.get('protocolVersion', '')
    info(f'协议版本: {protocol_version}')

    print()
    return response


def step_list_tools() -> dict:
    """Step 4: 列出工具

    Returns:
        tools/list 响应 dict
    """
    header('Step 4: 列出工具 — POST /messages (method: tools/list)')

    request = {
        'jsonrpc': '2.0',
        'id': 2,
        'method': 'tools/list',
    }

    response = mcp_post_request(request, step_name='tools/list')

    # 解析并展示工具列表
    result = response.get('result', {})
    tools = result.get('tools', [])

    if tools:
        ok(f'获取到 {len(tools)} 个工具:')
        print()
        for t in tools:
            name = t.get('name', '?')
            desc = t.get('description', '')
            schema = t.get('inputSchema', {})
            props = schema.get('properties', {})
            required = schema.get('required', [])
            has_params = bool(props)

            print(f'  {BOLD}{name}{RESET}')
            print(f'    描述: {desc}')
            if has_params:
                print(f'    参数:')
                for pname, pinfo in props.items():
                    req_mark = f' {RED}*{RESET}' if pname in required else ''
                    ptype = pinfo.get('type', 'any')
                    pdesc = pinfo.get('description', '')
                    print(f'      • {pname}{req_mark} ({ptype}): {pdesc}')
            print()
    else:
        warn('服务器未返回任何工具')

    return response


def step_call_hs_list() -> dict:
    """Step 5: 调用 hs_list 工具

    列出所有运行中的 HTTP 服务。

    Returns:
        tools/call 响应 dict
    """
    header('Step 5: 调用工具 — hs_list (列出所有 HTTP 服务)')

    request = {
        'jsonrpc': '2.0',
        'id': 3,
        'method': 'tools/call',
        'params': {
            'name': 'hs_list',
            'arguments': {},
        },
    }

    response = mcp_post_request(request, step_name='hs_list')

    # 检查结果
    result = response.get('result', {})
    is_error = result.get('isError', False)

    if is_error:
        warn('hs_list 返回了错误（可能当前没有运行中的服务）')
    else:
        # 提取 content 中的文本
        content_items = result.get('content', [])
        if content_items:
            for item in content_items:
                if item.get('type') == 'text':
                    text_content = item.get('text', '')
                    # 尝试解析内部 JSON
                    try:
                        parsed = json.loads(text_content)
                        if isinstance(parsed, list):
                            if parsed:
                                ok(f'运行中: {len(parsed)} 个服务')
                                for svc in parsed:
                                    port = svc.get('port', '?')
                                    path = svc.get('path', '?')
                                    pid = svc.get('pid', '?')
                                    status = svc.get('status', '?')
                                    print(f'    :{port}  {path}  PID:{pid}  [{status}]')
                            else:
                                info('当前没有运行中的 HTTP 服务')
                        else:
                            ok(f'hs_list 返回: {pretty_json(parsed)}')
                    except json.JSONDecodeError:
                        ok(f'hs_list 调用成功')
        else:
            ok('hs_list 调用成功')

    print()
    return response


def step_call_hs_config() -> dict:
    """Step 6: 调用 hs_config 工具

    显示当前 hs 配置。

    Returns:
        tools/call 响应 dict
    """
    header('Step 6: 调用工具 — hs_config (查看 hs 配置)')

    request = {
        'jsonrpc': '2.0',
        'id': 4,
        'method': 'tools/call',
        'params': {
            'name': 'hs_config',
            'arguments': {},
        },
    }

    response = mcp_post_request(request, step_name='hs_config')

    # 检查结果
    result = response.get('result', {})
    is_error = result.get('isError', False)

    if is_error:
        warn('hs_config 返回了错误')
    else:
        content_items = result.get('content', [])
        if content_items:
            for item in content_items:
                if item.get('type') == 'text':
                    text_content = item.get('text', '')
                    try:
                        parsed = json.loads(text_content)
                        ok('hs_config 调用成功')
                        print(f'  配置内容:')
                        for key, val in parsed.items():
                            print(f'    {BOLD}{key}{RESET}: {val}')
                    except json.JSONDecodeError:
                        ok(f'hs_config 返回: {text_content}')
        else:
            ok('hs_config 调用成功')

    print()
    return response


def print_summary() -> None:
    """打印演示完成摘要"""
    print()
    print(f'{GREEN}{BOLD}╔══════════════════════════════════════════════════════════════╗{RESET}')
    print(f'{GREEN}{BOLD}║                  演示完成！                                    ║{RESET}')
    print(f'{GREEN}{BOLD}║                  Demo Complete!                                ║{RESET}')
    print(f'{GREEN}{BOLD}╚══════════════════════════════════════════════════════════════╝{RESET}')
    print()
    print('  所有 MCP 协议步骤已成功演示:')
    print(f'  {BOLD}1.{RESET} 检查环境依赖')
    print(f'  {BOLD}2.{RESET} 启动 MCP Server (SSE 模式, 端口 {MCP_PORT})')
    print(f'  {BOLD}3.{RESET} 初始化握手 (POST /messages, method: initialize)')
    print(f'  {BOLD}4.{RESET} 列出工具 (POST /messages, method: tools/list)')
    print(f'  {BOLD}5.{RESET} 调用工具 hs_list (POST /messages, method: tools/call)')
    print(f'  {BOLD}6.{RESET} 调用工具 hs_config (POST /messages, method: tools/call)')
    print(f'  {BOLD}7.{RESET} 清理 MCP Server')
    print()
    print('  MCP 协议交互要点:')
    print(f'  • JSON-RPC 2.0 格式, id 从 1 递增')
    print(f'  • 首次需发送 initialize 握手')
    print(f'  • tools/list 获取可用工具列表')
    print(f'  • tools/call 携带 tool name + arguments')
    print(f'  • 所有响应包含 result 或 error 字段')
    print()


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main() -> None:
    """主函数 — 执行完整的 MCP 集成演示流程"""
    # ── 注册信号处理 ──
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ── 打印横幅 ──
    print()
    print(f'{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════╗{RESET}')
    print(f'{CYAN}{BOLD}║              hs MCP 集成示例 (Python)                        ║{RESET}')
    print(f'{CYAN}{BOLD}║              hs CLI MCP Integration Demo (Python)            ║{RESET}')
    print(f'{CYAN}{BOLD}╚══════════════════════════════════════════════════════════════╝{RESET}')
    print()

    try:
        # Step 1: 检查环境
        step_check_environment()

        # Step 2: 启动 MCP Server
        step_start_server()

        # Step 3: 初始化握手
        step_initialize()

        # Step 4: 列出工具
        step_list_tools()

        # Step 5: 调用 hs_list
        step_call_hs_list()

        # Step 6: 调用 hs_config
        step_call_hs_config()

        # 清理
        cleanup()

        # 打印摘要
        print_summary()

    except KeyboardInterrupt:
        print()
        warn('演示被用户中断')
        cleanup()
        sys.exit(0)
    except Exception as e:
        print()
        error(f'演示过程中发生异常: {e}')
        import traceback
        traceback.print_exc()
        cleanup()
        sys.exit(1)


if __name__ == '__main__':
    main()
