#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI 入口：argparse 解析 + 命令分派。
"""

import argparse
import os
import sys

from http_server_cli import __version__
from http_server_cli.config import Config
from http_server_cli.server import ServerManager
from http_server_cli.utils import eprint, ensure_storage

# ── 帮助文本 ──────────────────────────────────────────

_HELP = """http-server-cli v{version} — 忘记端口，只管预览

用法:  hs [command] [args]

━━━ 日常预览 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs . -o                  当前目录启动 + 打开浏览器
  hs ~/my-site -o          指定目录启动 + 打开浏览器
  hs . -i app.html         指定首页文件
  hs . -d                  后台运行（不占用终端）
  hs                       默认等于 hs .（当前目录启动）

  快捷方式: hs start [path]  启动服务;  -o 打开浏览器  -d 后台  -i <file> 首页

━━━ 服务管理 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs list                  列出所有运行中的服务（端口/路径/PID/CPU/内存）
  hs status 8080           查询端口 8080 状态
  hs kill 8080             关闭端口 8080 的服务
  hs kill ~/my-site        关闭指定路径的服务
  hs kill-all              一键关闭所有服务

  --json                   所有命令后追加此参数可获取结构化 JSON 输出

━━━ 图形与集成 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs dashboard -o          打开 Web 管理面板（默认端口 8180）
  hs dashboard --json      一次性查询服务列表
  hs mcp                   启动 MCP Server（后台运行 SSE，AI Agent 集成）

━━━ 配置 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs config                查看当前配置（默认端口/域名）
  hs set port 3000         修改默认端口
  hs set domain 0.0.0.0    修改绑定域名

━━━ 其他 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs version               显示版本号
  hs help                  显示此帮助

数据目录: ~/.http-server-cli/（config.json / registry.json / logs/）
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
    _list_servers(manager, json=parsed.json)


def _list_servers(manager, json: bool = False) -> None:
    """列出所有服务（用户服务 + managed 基础设施服务）"""
    from http_server_cli.registry_managed import ManagedRegistry
    from http_server_cli.utils import (
        eprint, format_path, format_duration, get_process_stats, json_output,
    )
    config = manager.config

    user_servers = manager.registry.active_servers()
    user_servers = sorted(user_servers, key=lambda x: x['port'])

    mreg = ManagedRegistry()
    managed_servers = mreg.active_servers()

    if json:
        user_data = []
        for entry in user_servers:
            stats = get_process_stats(entry.get('pid'))
            user_data.append({
                'url': f"http://{entry.get('domain', config.domain)}:{entry['port']}",
                'port': entry['port'], 'path': entry['path'],
                'pid': entry.get('pid'),
                'alive': entry['_alive'],
                'mode': 'daemon' if entry.get('daemon') else ('foreground' if entry.get('foreground') else 'normal'),
                'started_at': entry.get('started_at'),
                'stats': stats,
                'duration': format_duration(entry.get('started_at', '')),
            })
        managed_data = []
        for entry in managed_servers:
            managed_data.append({
                'name': entry.get('name'),
                'port': entry['port'], 'pid': entry.get('pid'),
                'alive': entry['_alive'],
                'type': entry.get('type'),
                'transport': entry.get('transport', ''),
                'started_at': entry.get('started_at'),
            })
        json_output(True, 'list', data={
            'count': len(user_servers),
            'servers': user_data,
            'managed': managed_data,
        })
        return

    total = len(user_servers) + len(managed_servers)
    if total == 0:
        eprint('没有正在运行的 HTTP 服务', 'ℹ️')
        eprint('使用 hs start [path] -o 启动一个', '💡')
        return

    # 用户服务
    eprint(f'共 {len(user_servers)} 个 HTTP 服务:', '📊')
    print()
    for entry in user_servers:
        alive = entry['_alive']
        port = entry['port']
        domain = entry.get('domain', config.domain)
        path = format_path(entry['path'])
        pid = entry.get('pid', '-')
        started = entry.get('started_at', '-')
        is_current = entry['path'] == os.getcwd()
        if is_current:
            print(f'📍  http://{domain}:{port} （current）')
        else:
            status_icon = '✅' if alive else '❌'
            status_text = '' if alive else ' (已停止)'
            mode_tag = ' 🖥' if entry.get('daemon') else (' ⌨' if entry.get('foreground') else '')
            print(f'{status_icon}  http://{domain}:{port}{status_text}{mode_tag}')
        print(f'    📁  {path}')
        stats = get_process_stats(entry.get('pid'))
        duration = format_duration(started)
        print(f'    🔧  PID: {pid}  |  启动时间: {started}')
        print(f'    📊  CPU: {stats["cpu"]}  |  内存: {stats["memory"]} ({stats["memory_percent"]}) | 时长: {duration}')
        print()

    # Managed 基础设施服务
    if managed_servers:
        eprint(f'共 {len(managed_servers)} 个基础设施服务:', '🔧')
        print()
        for entry in managed_servers:
            port = entry['port']
            alive = entry['_alive']
            name = entry.get('name', '')
            transport = entry.get('transport', '')
            pid = entry.get('pid', '-')
            started = entry.get('started_at', '-')
            tag = f' ({transport})' if transport else ''
            icon = '🟢' if alive else '🔴'
            print(f'{icon}  {name}{tag}  →  http://127.0.0.1:{port}')
            print(f'    🔧  PID: {pid}  |  启动时间: {started}')
            print()

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
    """hs mcp — MCP Server（自动后台运行 SSE）"""
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
        # SSE 模式 — 自动后台运行（常驻服务，不占用终端）
        from http_server_cli.mcp import serve_sse
        serve_sse(port=parsed.port, daemon=True)

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
