#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI 入口：argparse 解析 + 命令分派。
"""

import argparse
import sys

from http_server_cli import __version__
from http_server_cli.config import Config
from http_server_cli.server import ServerManager
from http_server_cli.utils import eprint, ensure_storage

# ── 帮助文本 ──────────────────────────────────────────

_HELP = """http-server-cli v{version} — 忘记端口，只管预览

用法:  hs [command] [args]

快捷方式:
  hs . [-o] [-d] [-i <file>]  等价 hs start .
  hs                          等价 hs start .（当前目录启动）

命令:
  start [path] [-o] [-d] [-f] [-i <file>] [--json]  启动服务（path 默认 .）
  list [--json]                   列出所有运行中的服务
  status [--json] [port|path]     查询单个服务状态
  kill <port|path> [--json]       关闭指定服务
  dashboard [-p PORT] [-o] [-d] [--json]  Web 仪表盘（默认端口 8180）
  mcp [--transport stdio|sse] [--port PORT]  MCP Server（供 AI Agent 集成）
  kill-all [--json]               关闭所有服务
  config [--json]                 显示当前配置
  set port|domain <value> [--json]  修改配置
  help                            显示此帮助
  version [--json]                显示版本号

示例:
  hs . -o                 当前目录启动 + 打开浏览器
  hs . -i app.html        以 app.html 为首页
  hs ~/my-site            指定目录启动
  hs . --json             JSON 格式获取启动结果
  hs list --json          JSON 格式列出所有服务
  hs status 8080 --json   JSON 格式查询端口 8080 状态
  hs kill 8080 --json     JSON 格式获取关闭结果
  hs kill-all --json      JSON 格式获取关闭结果
  hs config --json        JSON 格式显示配置
  hs set port 3000 --json JSON 格式获取配置修改结果
  hs version --json       JSON 格式显示版本

数据目录: ~/.http-server-cli/
"""

# ── Set 子命令 ─────────────────────────────────────────

def _handle_set(args):
    """set port|domain <value>"""
    json_mode = '--json' in args
    clean_args = [a for a in args if a != '--json']

    if len(clean_args) < 2:
        if json_mode:
            from http_server_cli.utils import json_output
            json_output(False, 'set', error='用法: set <port|domain> <值>')
        else:
            eprint('用法: set <port|domain> <值>', '⚠️')
            eprint('  set port 8080      设置默认端口', '💡')
            eprint('  set domain 0.0.0.0 设置绑定域名', '💡')
        return

    key, value = clean_args[0], clean_args[1]
    config = Config()

    if key == 'port':
        try:
            port = int(value)
            if port < 1024 or port > 65535:
                if json_mode:
                    from http_server_cli.utils import json_output
                    json_output(False, 'set', error='端口号应在 1024-65535 之间')
                else:
                    eprint('端口号应在 1024-65535 之间', '⚠️')
                return
            old_value = config.port
            config.set_port(port)
            if json_mode:
                from http_server_cli.utils import json_output
                json_output(True, 'set', data={'key': 'port', 'old_value': old_value, 'new_value': port})
            else:
                eprint(f'默认端口已设置为 {port}', '✅')
        except ValueError:
            if json_mode:
                from http_server_cli.utils import json_output
                json_output(False, 'set', error=f'无效端口号: {value}')
            else:
                eprint(f'无效端口号: {value}', '❌')
    elif key == 'domain':
        old_value = config.domain
        config.set_domain(value)
        if json_mode:
            from http_server_cli.utils import json_output
            json_output(True, 'set', data={'key': 'domain', 'old_value': old_value, 'new_value': value})
        else:
            eprint(f'默认域名已设置为 {value}', '✅')
    else:
        if json_mode:
            from http_server_cli.utils import json_output
            json_output(False, 'set', error=f'未知配置项: {key}（支持: port, domain）')
        else:
            eprint(f'未知配置项: {key}（支持: port, domain）', '⚠️')

# ── 命令分派 ──────────────────────────────────────────

_COMMANDS = {}

def _register(func):
    """装饰器：注册命令处理函数"""
    _COMMANDS[func.__name__.replace('_cmd_', '')] = func
    return func

@_register
def _cmd_start(manager, args):
    parser = argparse.ArgumentParser(prog='hs start', add_help=False)
    parser.add_argument('path', nargs='?', default='.')
    parser.add_argument('-o', '--open', action='store_true')
    parser.add_argument('-d', '--daemon', action='store_true')
    parser.add_argument('-f', '--foreground', action='store_true')
    parser.add_argument('-i', '--index', default=None, help='首页文件名（默认 index.html）')
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    manager.start(
        path=parsed.path,
        open_browser=parsed.open,
        daemon=parsed.daemon,
        foreground=parsed.foreground,
        json=parsed.json,
        index_page=parsed.index,
    )

@_register
def _cmd_list(manager, args):
    parser = argparse.ArgumentParser(prog='hs list', add_help=False)
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    manager.list(json=parsed.json)

@_register
def _cmd_status(manager, args):
    parser = argparse.ArgumentParser(prog='hs status', add_help=False)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('arg', nargs='?', default=None)
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    manager.status(arg=parsed.arg, json=parsed.json)

@_register
def _cmd_kill(manager, args):
    parser = argparse.ArgumentParser(prog='hs kill', add_help=False)
    parser.add_argument('arg', nargs='?', default=None)
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    if parsed.arg is None:
        manager.kill('', json=parsed.json)
    else:
        manager.kill(parsed.arg, json=parsed.json)

@_register
def _cmd_kill_all(manager, args):
    parser = argparse.ArgumentParser(prog='hs kill-all', add_help=False)
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    manager.kill_all(json=parsed.json)

@_register
def _cmd_killall(manager, args):
    manager.kill_all(json='--json' in args)

@_register
def _cmd_config(manager, args):
    parser = argparse.ArgumentParser(prog='hs config', add_help=False)
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    Config().show(json=parsed.json)

@_register
def _cmd_set(manager, args):
    _handle_set(args)

@_register
def _cmd_help(manager, args):
    print(_HELP.format(version=__version__))

@_register
def _cmd_version(manager, args):
    if '--json' in args or (args and args[0] == '--json'):
        from http_server_cli.utils import json_output
        import sys
        data = {
            'version': __version__,
            'name': 'http-server-cli',
            'python': sys.version.split()[0],
            'platform': sys.platform,
        }
        json_output(True, 'version', data=data)
    else:
        print(f'http-server-cli v{__version__}')


@_register
def _cmd_dashboard(manager, args):
    """hs dashboard — Web 仪表盘"""
    parser = argparse.ArgumentParser(prog='hs dashboard', add_help=False)
    parser.add_argument('-p', '--port', type=int, default=8180)
    parser.add_argument('-o', '--open', action='store_true')
    parser.add_argument('-d', '--daemon', action='store_true')
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    from http_server_cli.dashboard import serve
    serve(port=parsed.port, open_browser=parsed.open,
          json_output_mode=parsed.json, daemon=parsed.daemon)


@_register
def _cmd_mcp(manager, args):
    """hs mcp — MCP Server"""
    parser = argparse.ArgumentParser(prog='hs mcp', add_help=False)
    parser.add_argument('--transport', choices=['stdio', 'sse'], default='stdio')
    parser.add_argument('--port', type=int, default=8181)
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    if parsed.transport == 'sse':
        from http_server_cli.mcp import serve_sse
        serve_sse(port=parsed.port)
    else:
        from http_server_cli.mcp import serve_stdio
        serve_stdio()

# ── main ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument('command', nargs='?', default=None)
    parser.add_argument('args', nargs=argparse.REMAINDER)
    parsed, unknown = parser.parse_known_args()

    cmd = parsed.command
    # 命令名规范化：连字符转下划线
    if cmd:
        cmd = cmd.replace('-', '_')
    if cmd in ('_h', '__help') or '-h' in unknown or '--help' in unknown:
        cmd = 'help'
    elif cmd in ('_v', '__version') or unknown:
        cmd = 'version'
    elif cmd is None:
        cmd = 'start'
    elif cmd not in _COMMANDS:
        # 快捷方式：路径（如 .、~/site）隐式作为 start 的 path 参数
        if cmd.startswith(('.', '/', '~')) or cmd == '..':
            parsed.args = [parsed.command] + parsed.args
            cmd = 'start'
        else:
            eprint(f'未知命令: {cmd}', '❌')
            _cmd_help(None, [])
            sys.exit(1)

    ensure_storage()
    manager = ServerManager()
    _COMMANDS[cmd](manager, parsed.args)

if __name__ == '__main__':
    main()
