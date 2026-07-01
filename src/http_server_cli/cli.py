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
  hs list --port           仅打印端口号清单
  hs list --path           仅打印路径清单
  hs list --short          打印"端口:路径"清单
  hs status 8080           查询端口 8080 状态
  hs kill 8080             关闭端口 8080 的服务
  hs kill ~/my-site        关闭指定路径的服务
  hs kill-all              一键关闭所有服务
  hs history               显示所有历史启动记录
  hs history --json        JSON 格式输出历史记录
  hs search <keyword>      搜索实例（按端口或路径模糊匹配，忽略大小写）

  --json                   所有命令后追加此参数可获取结构化 JSON 输出

━━━ 图形与集成 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs dashboard -o          打开 Web 管理面板（自动后台运行，默认端口 8180）
  hs dashboard --json      一次性查询服务列表
  hs dashboard stop        停止仪表盘
  hs dashboard status      查看仪表盘状态
  hs mcp                   启动 MCP Server（后台运行 SSE，AI Agent 集成）
  hs mcp stop              停止 MCP 服务
  hs mcp status            查看 MCP 状态

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
            json_output(False, 'set', error='Usage: set <port|domain> <value>')
        else:
            eprint('Usage: set <port|domain> <value>', '⚠️')
            eprint('  set port 8080      Set default port', '💡')
            eprint('  set domain 0.0.0.0 Set bind domain', '💡')
        return

    key, value = clean_args[0], clean_args[1]
    config = Config()

    if key == 'port':
        try:
            port = int(value)
            if port < 1024 or port > 65535:
                if json_mode:
                    from http_server_cli.utils import json_output
                    json_output(False, 'set', error='Port must be between 1024-65535')
                else:
                    eprint('Port must be between 1024-65535', '⚠️')
                return
            old_value = config.port
            config.set_port(port)
            if json_mode:
                from http_server_cli.utils import json_output
                json_output(True, 'set', data={'key': 'port', 'old_value': old_value, 'new_value': port})
            else:
                eprint(f'Default port set to {port}', '✅')
        except ValueError:
            if json_mode:
                from http_server_cli.utils import json_output
                json_output(False, 'set', error=f'Invalid port number: {value}')
            else:
                eprint(f'Invalid port number: {value}', '❌')
    elif key == 'domain':
        old_value = config.domain
        config.set_domain(value)
        if json_mode:
            from http_server_cli.utils import json_output
            json_output(True, 'set', data={'key': 'domain', 'old_value': old_value, 'new_value': value})
        else:
            eprint(f'Default domain set to {value}', '✅')
    else:
        if json_mode:
            from http_server_cli.utils import json_output
            json_output(False, 'set', error=f'Unknown config key: {key} (supported: port, domain)')
        else:
            eprint(f'Unknown config key: {key} (supported: port, domain)', '⚠️')

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
    parser.add_argument('--port', action='store_true')
    parser.add_argument('--path', action='store_true')
    parser.add_argument('--short', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    _list_servers(manager, json=parsed.json, port_only=parsed.port,
                  path_only=parsed.path, short=parsed.short)


def _list_servers(manager, json: bool = False, port_only: bool = False,
                  path_only: bool = False, short: bool = False) -> None:
    """列出所有服务（用户服务 + managed 基础设施服务）"""
    from http_server_cli.registry_managed import ManagedRegistry
    from http_server_cli.utils import (
        eprint, format_path, format_duration, get_process_stats, json_output,
    )
    config = manager.config

    user_servers = manager.registry.active_servers()
    user_servers = sorted(user_servers, key=lambda x: x['port'])
    # 仅显示运行中的实例
    user_servers = [s for s in user_servers if s.get('_alive')]

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
        eprint('No running HTTP services', 'ℹ️')
        eprint('Use hs start [path] -o to start one', '💡')
        return

    # 过滤输出模式（优先级: --port > --path > --short）
    if port_only:
        for entry in user_servers:
            print(entry['port'])
        return
    if path_only:
        for entry in user_servers:
            print(format_path(entry['path']))
        return
    if short:
        for entry in user_servers:
            print(f"{entry['port']}:{format_path(entry['path'])}")
        return

    # 用户服务
    eprint(f'Total {len(user_servers)} HTTP services:', '📊')
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
            status_text = '' if alive else ' (stopped)'
            mode_tag = ' 🖥' if entry.get('daemon') else (' ⌨' if entry.get('foreground') else '')
            print(f'{status_icon}  http://{domain}:{port}{status_text}{mode_tag}')
        print(f'    📁  {path}')
        stats = get_process_stats(entry.get('pid'))
        duration = format_duration(started)
        print(f'    🔧  PID: {pid}  |  Started: {started}')
        print(f'    📊  CPU: {stats["cpu"]}  |  Memory: {stats["memory"]} ({stats["memory_percent"]}) | Duration: {duration}')
        print()

    # Managed 基础设施服务
    if managed_servers:
        eprint(f'Total {len(managed_servers)} infrastructure services:', '🔧')
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
            print(f'    🔧  PID: {pid}  |  Started: {started}')
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
def _cmd_history(manager, args):
    """显示所有历史记录（过滤掉系统临时目录条目）"""
    parser = argparse.ArgumentParser(prog='hs history', add_help=False)
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    from http_server_cli.history import HistoryStore
    from http_server_cli.utils import json_output, eprint
    history = HistoryStore()
    all_records = history.records()
    # 过滤掉系统临时目录的条目（当 hs 在没有指定项目路径或某些工具创建临时服务器时
    # 会自动使用系统临时目录，这些条目对用户没有意义）
    temp_prefixes = ('/tmp/', '/private/var/folders/')
    records = [r for r in all_records
               if not r.get('path', '').startswith(temp_prefixes)]
    filtered_count = len(all_records) - len(records)
    if parsed.json:
        data = {'count': len(records), 'records': records}
        if filtered_count:
            data['filtered_temp_count'] = filtered_count
            data['filtered_temp_note'] = (
                f'{filtered_count} system temp directory entr'
                f'{"y" if filtered_count == 1 else "ies"} excluded '
                f'(paths starting with {temp_prefixes})'
            )
        json_output(True, 'history', data=data)
        return
    if not records:
        if filtered_count:
            eprint(f'No meaningful history records ('
                   f'{filtered_count} temp entr'
                   f'{"y" if filtered_count == 1 else "ies"} filtered out)', 'ℹ️')
        else:
            eprint('No history records', 'ℹ️')
        return
    eprint(f'Total {len(records)} history records:', '📊')
    if filtered_count:
        eprint(f'  ({filtered_count} system temp entr'
               f'{"y" if filtered_count == 1 else "ies"} excluded'
               f' — they appear when `hs` runs without a project path'
               f' or when external tools create temporary servers)', '🔎')
    print()
    for r in records:
        port = r.get('port', '-')
        path = r.get('path', '-')
        started = r.get('started_at', '-')[:19]
        ended = r.get('ended_at', '-')[:19] if r.get('ended_at') else 'running'
        mem = r.get('memory_mb', 0)
        print(f'  {port}:{path}')
        print(f'    Start: {started}  End: {ended}  Memory: {mem} MB')
        print()

@_register
def _cmd_set(manager, args):
    _handle_set(args)

@_register
def _cmd_search(manager, args):
    """搜索实例（按端口或路径模糊匹配）"""
    parser = argparse.ArgumentParser(prog='hs search', add_help=False)
    parser.add_argument('keyword', nargs='?', default=None)
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    if not parsed.keyword:
        from http_server_cli.utils import eprint
        eprint('Usage: hs search <keyword>', '⚠️')
        return

    # 从 registry 中搜索匹配项（仅搜索运行中的服务）
    servers = manager.registry.active_servers()
    servers = [s for s in servers if s.get('_alive')]
    keyword = parsed.keyword.lower()
    matches = [s for s in servers
               if keyword in str(s.get('port', ''))
               or keyword in s.get('path', '').lower()]

    from http_server_cli.utils import format_path, json_output, eprint
    from http_server_cli.config import Config
    config = Config()

    if parsed.json:
        json_output(True, 'search', data={
            'keyword': parsed.keyword,
            'count': len(matches),
            'servers': matches,
        })
        return

    if not matches:
        eprint(f'No services matching "{parsed.keyword}"', 'ℹ️')
        return

    eprint(f'Found {len(matches)} matching "{parsed.keyword}":', '📊')
    print()
    for entry in matches:
        port = entry['port']
        path = format_path(entry['path'])
        domain = entry.get('domain', config.domain)
        alive = entry['_alive']
        icon = '✅' if alive else '❌'
        print(f'  {icon}  http://{domain}:{port}')
        print(f'      📁  {path}')
        print()

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
    """hs dashboard — Web 仪表盘（自动后台运行）"""
    # 子命令优先
    sub = args[0] if args else None
    if sub in ('help', 'stop', 'status', 'restart'):
        _manage_dashboard(sub)
        return

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
    auto_daemon = parsed.daemon or parsed.open
    serve(port=parsed.port, open_browser=parsed.open,
          json_output_mode=parsed.json, daemon=auto_daemon)


def _manage_dashboard(subcmd: str) -> None:
    """管理 dashboard 服务：stop / status / restart / help"""
    from http_server_cli.registry_managed import ManagedRegistry
    from http_server_cli.utils import eprint, format_duration, get_process_stats, is_process_alive, is_port_in_use
    import os, signal, time

    mreg = ManagedRegistry()
    entry = mreg.find(name='dashboard')

    if subcmd == 'help':
        print('━━━ hs dashboard ━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        print('  hs dashboard              Foreground start (debug mode)')
        print('  hs dashboard -o           Background + open browser')
        print('  hs dashboard -d           Background daemon')
        print('  hs dashboard -p PORT      Specify port')
        print('  hs dashboard --json       One-shot server list')
        print('  hs dashboard stop         Stop dashboard')
        print('  hs dashboard status       View status')
        print('  hs dashboard restart      Restart dashboard')
        print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        return

    if subcmd in ('stop', 'status', 'restart') and not entry:
        eprint('dashboard not running', 'ℹ️')
        return

    port = entry.get('port', '?')
    pid = entry.get('pid')

    if subcmd == 'status':
        alive = pid and is_process_alive(pid) and is_port_in_use(port)
        duration = format_duration(entry.get('started_at', ''))
        stats = get_process_stats(pid)
        icon = '🟢' if alive else '🔴'
        from http_server_cli.utils import LOG_DIR, format_path
        dashboard_log = format_path(os.path.join(LOG_DIR, 'dashboard.log'))
        print(f'{icon}  hs dashboard  →  http://127.0.0.1:{port}')
        print(f'    🔧  PID: {pid}  |  Duration: {duration}')
        print(f'    📊  CPU: {stats["cpu"]}  |  Memory: {stats["memory"]} ({stats["memory_percent"]})')
        print(f'    📋  Log: {dashboard_log}')
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
        mreg.remove(name='dashboard')
        # 清理日志
        log_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),  # src/http_server_cli
            '..', 'logs', f'{port}.log'
        )
        from http_server_cli.utils import LOG_DIR
        dlog = os.path.join(LOG_DIR, f'{port}.log')
        for lp in (log_path, dlog):
            if os.path.isfile(lp):
                try:
                    os.remove(lp)
                except OSError:
                    pass
        eprint(f'dashboard (port {port}) stopped', '🛑')

    if subcmd == 'restart':
        from http_server_cli.dashboard import serve
        serve(port=8180, open_browser=False, daemon=True)


@_register
def _cmd_mcp(manager, args):
    """hs mcp — MCP Server（自动后台运行 SSE）"""
    # 子命令优先
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
    from http_server_cli.utils import eprint, format_duration, get_process_stats, is_process_alive, is_port_in_use
    import os, signal, time

    mreg = ManagedRegistry()
    entry = mreg.find(name='mcp')

    if subcmd == 'help':
        print('━━━ hs mcp ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        print('  hs mcp                    Background SSE (default)')
        print('  hs mcp --transport stdio  Foreground stdio mode')
        print('  hs mcp --port PORT        Specify port')
        print('  hs mcp stop               Stop MCP service')
        print('  hs mcp status             View status')
        print('  hs mcp restart            Restart MCP service')
        print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        return

    if subcmd in ('stop', 'status', 'restart') and not entry:
        eprint('MCP not running', 'ℹ️')
        return

    port = entry.get('port', '?')
    pid = entry.get('pid')

    if subcmd == 'status':
        alive = pid and is_process_alive(pid) and is_port_in_use(port)
        duration = format_duration(entry.get('started_at', ''))
        icon = '🟢' if alive else '🔴'
        print(f'{icon}  hs mcp (SSE)  →  http://127.0.0.1:{port}/sse')
        print(f'    🔧  PID: {pid}  |  Duration: {duration}')
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
        eprint(f'MCP (port {port}) stopped', '🛑')

    if subcmd == 'restart':
        from http_server_cli.mcp import serve_sse
        serve_sse(port=8181, daemon=True)

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
            eprint(f'Unknown command: {cmd}', '❌')
            _cmd_help(None, [])
            sys.exit(1)

    ensure_storage()
    manager = ServerManager()
    _COMMANDS[cmd](manager, parsed.args)

if __name__ == '__main__':
    main()
