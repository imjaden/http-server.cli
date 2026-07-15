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
import glob

# ── 帮助文本 ──────────────────────────────────────────

_HELP = """http-server-cli v{version} — 忘记端口，只管预览

用法:  hs [command] [args]

━━━ 日常预览 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs -o                    当前目录启动 + 打开浏览器
  hs ~/my-site -o          指定目录启动 + 打开浏览器
  hs . -i app.html         指定首页文件
  hs . -d                  后台运行（不占用终端）
  hs . --url               仅返回服务 URL（与 --json 互斥）
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
  --url                    启动后仅输出完整 URL 字符串（仅 start，与 --json 互斥）

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
    import os
    parser = argparse.ArgumentParser(prog='hs start', add_help=False)
    parser.add_argument('path', nargs='?', default='.')
    parser.add_argument('-o', '--open', action='store_true')
    parser.add_argument('-d', '--daemon', action='store_true')
    parser.add_argument('-f', '--foreground', action='store_true')
    parser.add_argument('-i', '--index', nargs='*', default=None, help='首页文件名（默认 index.html）')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--url', action='store_true')
    try:
        parsed, unknown = parser.parse_known_args(args)
    except SystemExit:
        return
    # ── --url 与 --json 互斥 ──
    # 注: CLI 层互斥错误也走 stderr，保证 "$(hs . --url 2>/dev/null)" 不受污染
    if parsed.url and parsed.json:
        print('⚠️ --url and --json are mutually exclusive', file=sys.stderr)
        sys.exit(2)
    # 处理 --index 通配符展开（Shell 展开为多个文件时取最近修改的）
    index_page = parsed.index
    if isinstance(index_page, list):
        if len(index_page) == 1:
            index_page = index_page[0]
        else:
            existing = [f for f in index_page if os.path.exists(f)]
            if existing:
                index_page = max(existing, key=os.path.getmtime)
            else:
                index_page = index_page[0]
    if index_page:
        index_page = index_page.lstrip('./')

    # 处理 path 通配符展开：Shell 展开后收集所有 html 文件，取最近者
    path = parsed.path
    if path and os.path.isfile(path) and path.lower().endswith(('.html', '.htm')):
        all_html = [path] + [a for a in unknown if a.lower().endswith(('.html', '.htm'))]
        if len(all_html) > 1:
            existing = [f for f in all_html if os.path.exists(f)]
            if existing:
                path = max(existing, key=os.path.getmtime)
    result = manager.start(
        path=path,
        open_browser=parsed.open,
        daemon=parsed.daemon,
        foreground=parsed.foreground,
        json=parsed.json if not parsed.url else False,
        url_only=parsed.url,
        index_page=index_page,
    )
    # --url 模式根据返回值设置退出码
    if parsed.url:
        sys.exit(0 if result else 1)

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

    from http_server_cli.bookmark import BookmarkStore as BStore
    bm_store = BStore()

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
                'bookmark': bm_store.get_for_path(entry['path']),
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
        bm_name = bm_store.get_for_path(entry['path'])
        bm_label = f'  [{bm_name}]' if bm_name else ''
        if is_current:
            print(f'📍  http://{domain}:{port}{bm_label} （current）')
        else:
            status_icon = '✅' if alive else '❌'
            status_text = '' if alive else ' (stopped)'
            mode_tag = ' 🖥' if entry.get('daemon') else (' ⌨' if entry.get('foreground') else '')
            print(f'{status_icon}  http://{domain}:{port}{status_text}{mode_tag}{bm_label}')
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
    arg = parsed.arg
    # bookmark 名称解析：非 digit → 查 bookmark
    if arg and not arg.isdigit():
        from http_server_cli.bookmark import BookmarkStore
        bm = BookmarkStore().get(arg)
        if bm:
            arg = bm['path']
    manager.status(arg=arg, json=parsed.json)

@_register
def _cmd_kill(manager, args):
    parser = argparse.ArgumentParser(prog='hs kill', add_help=False)
    parser.add_argument('arg', nargs='?', default=None)
    parser.add_argument('--json', action='store_true')
    try:
        parsed, unknown = parser.parse_known_args(args)
    except SystemExit:
        return
    arg = parsed.arg
    # 通配符展开处理：收集 Shell 展开的 html 文件，取最近者
    if arg and arg.lower().endswith(('.html', '.htm')):
        all_html = [arg] + [a for a in unknown if a.lower().endswith(('.html', '.htm'))]
        if len(all_html) > 1:
            existing = [f for f in all_html if os.path.exists(f)]
            if existing:
                arg = max(existing, key=os.path.getmtime)
    if arg is None:
        manager.kill('', json=parsed.json)
    else:
        # bookmark 名称解析：非 digit 且非 html 文件 → 查 bookmark
        if arg and not arg.isdigit() and not arg.lower().endswith(('.html', '.htm')):
            from http_server_cli.bookmark import BookmarkStore
            bm = BookmarkStore().get(arg)
            if bm:
                arg = bm['path']
        manager.kill(arg, json=parsed.json)

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

# ── bookmark 子命令 ────────────────────────────────────

@_register
def _cmd_bookmark(manager, args):
    """hs bookmark — 书签管理"""
    sub = args[0] if args else None
    if sub == 'add':
        _bookmark_add(args[1:])
    elif sub == 'list':
        _bookmark_list(args[1:])
    elif sub == 'show':
        _bookmark_show(args[1:])
    elif sub == 'remove':
        _bookmark_remove(args[1:])
    elif sub in ('help', '-h', '--help'):
        _bookmark_help()
    else:
        print('❌ Usage: hs bookmark <add|list|show|remove> [args]', file=sys.stderr)
        _bookmark_help()


def _bookmark_help():
    print('━━━ hs bookmark ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('  hs bookmark add <name> [path] [-i index]     Add bookmark')
    print('  hs bookmark list                              List all')
    print('  hs bookmark show <name>                       Show details')
    print('  hs bookmark remove <name>                     Remove')
    print()
    print('  After adding, use the name directly:')
    print('    hs <name> --url        Get URL')
    print('    hs <name> -o           Start + open browser')
    print('    hs kill <name>         Stop service')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')


def _bookmark_add(args):
    parser = argparse.ArgumentParser(prog='hs bookmark add', add_help=False)
    parser.add_argument('name')
    parser.add_argument('path', nargs='?', default=None)
    parser.add_argument('-i', '--index', default=None)
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return

    from http_server_cli.bookmark import BookmarkStore
    from http_server_cli.server import _validate_index_page

    # 名称校验
    name_err = BookmarkStore.validate_name(parsed.name)
    if name_err:
        print(f'❌ {name_err}', file=sys.stderr)
        return
    if parsed.name in _COMMANDS:
        print(f"❌ '{parsed.name}' conflicts with built-in command", file=sys.stderr)
        return

    # index_page 校验
    if parsed.index:
        err = _validate_index_page(parsed.index)
        if err:
            print(f'❌ {err}', file=sys.stderr)
            return

    # 路径处理
    from http_server_cli.utils import resolve_path, format_path
    path = parsed.path or os.getcwd()
    abs_path = resolve_path(path)
    if not os.path.isdir(abs_path):
        print(f'❌ Path does not exist or is not a directory: {format_path(abs_path)}', file=sys.stderr)
        return

    store = BookmarkStore()
    try:
        store.add(parsed.name, abs_path, parsed.index)
        print(f"✅ Bookmark '{parsed.name}' → {format_path(abs_path)}")
        if parsed.index:
            print(f"   📄 Default index: {parsed.index}")
    except ValueError as e:
        print(f'❌ {e}', file=sys.stderr)


def _bookmark_list(args):
    from http_server_cli.bookmark import BookmarkStore
    from http_server_cli.utils import format_path
    store = BookmarkStore()
    bookmarks = store.list_all()
    if not bookmarks:
        print('No bookmarks registered')
        return
    print(f'📊 {len(bookmarks)} bookmark(s):')
    print()
    for bm in bookmarks:
        print(f"  📌 {bm['name']}")
        print(f"     📁 {format_path(bm['path'])}")
        if bm.get('index_page'):
            print(f"     📄 Default index: {bm['index_page']}")
        print()


def _bookmark_show(args):
    if not args:
        print('❌ Usage: hs bookmark show <name>', file=sys.stderr)
        return
    from http_server_cli.bookmark import BookmarkStore
    from http_server_cli.utils import format_path
    name = args[0]
    store = BookmarkStore()
    bm = store.get(name)
    if not bm:
        print(f"❌ bookmark '{name}' not found", file=sys.stderr)
        return
    print(f"📌 {bm['name']}")
    print(f"   📁 {format_path(bm['path'])}")
    if bm.get('index_page'):
        print(f"   📄 Default index: {bm['index_page']}")
    print(f"   🕐 Created: {bm.get('created_at', '-')}")


def _bookmark_remove(args):
    if not args:
        print('❌ Usage: hs bookmark remove <name>', file=sys.stderr)
        return
    from http_server_cli.bookmark import BookmarkStore
    name = args[0]
    store = BookmarkStore()
    if store.remove(name):
        print(f"✅ Bookmark '{name}' removed")
    else:
        print(f"❌ bookmark '{name}' not found", file=sys.stderr)

# ── main ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument('command', nargs='?', default=None)
    parser.add_argument('args', nargs=argparse.REMAINDER)
    parsed, unknown = parser.parse_known_args()

    cmd = parsed.command
    # 命令名规范化：连字符转下划线（仅对已知命令生效，不影响路径参数）
    if cmd and cmd.replace('-', '_') in _COMMANDS:
        cmd = cmd.replace('-', '_')
    if cmd in ('_h', '__help') or '-h' in unknown or '--help' in unknown:
        cmd = 'help'
    elif cmd in ('_v', '__version') or '-v' in unknown or '--version' in unknown:
        cmd = 'version'
    elif cmd is None:
        # 未输入命令名但有关键字（如 hs -o），视作 start 的参数
        if unknown:
            parsed.args = unknown[:]
        cmd = 'start'
    elif cmd not in _COMMANDS:
        # ➊ 先查 bookmark
        from http_server_cli.bookmark import BookmarkStore
        bm_store = BookmarkStore()
        bm = bm_store.get(cmd)
        if bm:
            implicit = [bm['path']]
            if bm.get('index_page'):
                implicit += ['-i', bm['index_page']]
            parsed.args = implicit + parsed.args
            cmd = 'start'
        # ➋ 回退到路径快捷方式
        elif (cmd.startswith(('.', '/', '~')) or cmd == '..'
                or os.path.exists(cmd) or glob.glob(cmd)):
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
