#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI 入口：argparse 解析 + 命令分派。
"""

import argparse
import os
import subprocess
import sys
import webbrowser

from http_server_cli import __version__
from http_server_cli.config import Config
from http_server_cli.server import ServerManager, UsageError
from http_server_cli.utils import eprint, ensure_storage
import glob

# ── 统一解析入口（D6 / D9e） ──────────────────────────

# 未识别参数的近形引导（typo → 正确用法）
_UNKNOWN_HINTS = (
    (('-p', '--port', '--prot', '--portt', '--prt', '--post'), '指定端口: hs . -p <port>'),
    (('-i', '--index', '--idx', '--indx'), '指定首页: hs . -i <file>'),
    (('-d', '--daemon', '--demon', '--deamon'), '后台运行: hs . -d（前台 tail 日志，Ctrl+C 仅退出 tail）'),
    (('-o', '--open', '--opne'), '启动后打开浏览器: hs . -o'),
    (('-f', '--foreground', '--fg'), '前台运行: hs . -f'),
    (('--json', '--jsonn'), 'JSON 输出: hs . --json'),
    (('--url', '--urll'), '仅输出 URL: hs . --url'),
)


def _warn_unknown_args(unknown, *, allow=(), allow_html: bool = False,
                       allow_positional: bool = False) -> list:
    """未识别参数告警（D6）：仅 stderr，stdout / JSON 信封零污染，退出码不变。

    allow            显式豁免的 token
    allow_html       豁免 *.html / *.htm（hs start 多文件通配的既有语义）
    allow_positional 豁免非 '-' 开头的 token（hs search 关键词等）
    """
    if not unknown:
        return []
    rest = [t for t in unknown
            if t not in allow
            and not (allow_html and str(t).lower().endswith(('.html', '.htm')))
            and not (allow_positional and not str(t).startswith('-'))]
    if not rest:
        return []
    print(f'⚠️ 未识别参数（已忽略）: {" ".join(rest)}', file=sys.stderr)
    for tokens, hint in _UNKNOWN_HINTS:
        if any(t in tokens for t in rest):
            print(f'    💡 {hint}', file=sys.stderr)
            break
    return rest


def _parse_known_args(parser, args, *, allow=(), allow_html: bool = False,
                      allow_positional: bool = False):
    """统一解析入口（D6 / D9e）：

    · 参数错误（非法值 / 缺值）不再静默成功 → exit 2（P4：消灭「假成功」）
    · 未识别参数告警到 stderr，不污染 stdout / JSON
    """
    try:
        parsed, unknown = parser.parse_known_args(args)
    except SystemExit as e:  # argparse 的报错路径（argparse 已打印具体错误）
        code = e.code if isinstance(e.code, int) and e.code else 2
        sys.exit(code)
    _warn_unknown_args(unknown, allow=allow, allow_html=allow_html,
                       allow_positional=allow_positional)
    return parsed, unknown

# ── 帮助文本 ──────────────────────────────────────────

_HELP = """http-server v{version} — 忘记端口，只管预览

用法:  hs [command] [args]

━━━ 日常预览 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs -o                    当前目录启动 + 打开浏览器
  hs ~/my-site -o          指定目录启动 + 打开浏览器
  hs . -i app.html         指定首页文件
  hs . -p 8099             指定端口（1024-65535；被占用即失败退出，不自动漂移）
  hs . -d                  后台运行 + 前台 tail 日志（Ctrl+C 仅退出 tail，服务仍在后台）
  hs . --url               仅返回服务 URL（与 --json 互斥）
  hs                       默认等于 hs .（当前目录启动）

  快捷方式: hs start [path]  启动服务;  -o 打开浏览器  -d 后台（前台 tail 日志）  -i <file> 首页  -p <port> 指定端口

━━━ 服务管理 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs list                  列出所有运行中的服务（端口/路径/PID/CPU/内存）
  hs list --port           仅打印端口号清单（布尔开关；指定启动端口用 hs start -p <N>）
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
  hs dashboard restart     重启仪表盘（未运行时提示 not running，不启动）
  hs dashboard restart -p 8290   用指定端口重启（未给 -p 则沿用当前端口）
  hs mcp                   启动 MCP Server（后台运行 SSE，AI Agent 集成）
  hs mcp stop              停止 MCP 服务
  hs mcp status            查看 MCP 状态
  hs prompt                列出可用技能（AI 对接，`hs prompt <name>` 输出全文）

━━━ 配置 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs config                查看当前配置（默认端口/域名）
  hs set port 3000         修改默认端口
  hs set domain 0.0.0.0    修改绑定域名

━━━ 书签 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs bookmark add <name> [path] [-i index]    注册书签（path 默认 CWD）
  hs bookmark update <name> [path] [-i index]  更新书签路径或首页
  hs bookmark list                             列出所有书签
  hs bookmark show <name>                      查看书签详情
  hs bookmark remove <name>                    删除书签

  注册后直接用名称启动:
    hs <name> --url        获取 URL
    hs <name> -o           启动 + 打开浏览器
    hs kill <name>         停止服务

━━━ Web 服务注册 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs web add <name> --cmd '<cmd>' [--url <url>] [--open cmd|url|both|none] [--domain]
  hs web list / show <name> / remove <name> / update <name>
  hs web <name> [--no-probe]      已运行→直接访问; 未运行→执行启动命令

  注册任意 web 服务启动命令（可跨项目），按名称快速启动/访问:
    hs web daily.checker        启动/访问 daily-checker 面板
    hs web jaden.tech           启动/访问 jaden.tech 站点
    hs web <name> --no-probe    跳过探测，强制重启
    --domain                    执行时注入 config.domain（--domain "<domain>"）

━━━ 其他 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hs version               显示版本号
  hs help                  显示此帮助

数据目录: ~/.http-server.cli/（config.json / registry.json / logs/）
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
        try:
            config.set_domain(value)
        except ValueError as e:
            if json_mode:
                from http_server_cli.utils import json_output
                json_output(False, 'set', error=str(e))
            else:
                eprint(str(e), '❌')
            return
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
    # allow_abbrev=False：避免 --prot 之类近形被当作 --port 缩写而静默生效（D6 告警需可命中）
    parser = argparse.ArgumentParser(prog='hs start', add_help=False, allow_abbrev=False)
    parser.add_argument('path', nargs='?', default='.')
    parser.add_argument('-o', '--open', action='store_true')
    parser.add_argument('-d', '--daemon', action='store_true')
    parser.add_argument('-f', '--foreground', action='store_true')
    parser.add_argument('-i', '--index', nargs='*', default=None, help='首页文件名（默认 index.html）')
    parser.add_argument('-p', '--port', type=int, default=None,
                        help='指定端口（1024-65535，一次性覆盖 config.port；被占用即失败退出）')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--url', action='store_true')
    parsed, unknown = _parse_known_args(parser, args, allow_html=True)
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
    try:
        result = manager.start(
            path=path,
            open_browser=parsed.open,
            daemon=parsed.daemon,
            foreground=parsed.foreground,
            json=parsed.json if not parsed.url else False,
            url_only=parsed.url,
            index_page=index_page,
            port=parsed.port,
        )
    except UsageError:
        sys.exit(2)  # 端口越界等用法错误（D4 / D9e）
    # --url 模式根据返回值设置退出码
    if parsed.url:
        sys.exit(0 if result else 1)
    # D14：运行期失败（路径不存在 / 端口不可用 / 启动失败）→ exit 1，不再「假成功」
    if result is False:
        sys.exit(1)

@_register
def _cmd_list(manager, args):
    parser = argparse.ArgumentParser(prog='hs list', add_help=False)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--port', action='store_true')
    parser.add_argument('--path', action='store_true')
    parser.add_argument('--short', action='store_true')
    parsed, _ = _parse_known_args(parser, args)
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
        bm_names = bm_store.get_for_path(entry['path'])
        bm_label = f'  [{",".join(bm_names)}]' if bm_names else ''
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
    parsed, _ = _parse_known_args(parser, args)
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
    parsed, unknown = _parse_known_args(parser, args, allow_html=True)
    arg = parsed.arg
    # 通配符展开处理：收集 Shell 展开的 html 文件，取最近者
    if arg and arg.lower().endswith(('.html', '.htm')):
        all_html = [arg] + [a for a in unknown if a.lower().endswith(('.html', '.htm'))]
        if len(all_html) > 1:
            existing = [f for f in all_html if os.path.exists(f)]
            if existing:
                arg = max(existing, key=os.path.getmtime)
    if arg is None:
        ok = manager.kill('', json=parsed.json)
    else:
        # bookmark 名称解析：非 digit 且非 html 文件 → 查 bookmark
        if arg and not arg.isdigit() and not arg.lower().endswith(('.html', '.htm')):
            from http_server_cli.bookmark import BookmarkStore
            bm = BookmarkStore().get(arg)
            if bm:
                arg = bm['path']
        ok = manager.kill(arg, json=parsed.json)
    if not ok:
        # D14：运行期失败不再返回 0（对齐 Unix `kill <不存在进程>` 语义）
        sys.exit(1)

@_register
def _cmd_kill_all(manager, args):
    parser = argparse.ArgumentParser(prog='hs kill-all', add_help=False)
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)
    manager.kill_all(json=parsed.json)

@_register
def _cmd_killall(manager, args):
    manager.kill_all(json='--json' in args)

@_register
def _cmd_config(manager, args):
    parser = argparse.ArgumentParser(prog='hs config', add_help=False)
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)
    Config().show(json=parsed.json)

@_register
def _cmd_history(manager, args):
    """显示所有历史记录（过滤掉系统临时目录条目）"""
    parser = argparse.ArgumentParser(prog='hs history', add_help=False)
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)
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
    parsed, _ = _parse_known_args(parser, args, allow_positional=True)
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
            'name': 'http-server',
            'python': sys.version.split()[0],
            'platform': sys.platform,
        }
        json_output(True, 'version', data=data)
    else:
        print(f'http-server v{__version__}')


@_register
def _cmd_dashboard(manager, args):
    """hs dashboard — Web 仪表盘（自动后台运行）"""
    # 子命令优先
    sub = args[0] if args else None
    if sub in ('help', 'stop', 'status', 'restart'):
        # D9a：restart 支持 -p/--port 透传；其余子命令只接 --json
        sp = argparse.ArgumentParser(prog=f'hs dashboard {sub}', add_help=False)
        if sub == 'restart':
            sp.add_argument('-p', '--port', type=int, default=None)
        parsed_sub, _ = _parse_known_args(sp, args[1:], allow=('--json',))
        sub_port = getattr(parsed_sub, 'port', None)
        if sub_port is not None and not (1024 <= sub_port <= 65535):
            eprint('Port must be between 1024-65535', '⚠️')
            sys.exit(2)
        _manage_dashboard(sub, json_mode=('--json' in args), port=sub_port)
        return

    parser = argparse.ArgumentParser(prog='hs dashboard', add_help=False)
    parser.add_argument('-p', '--port', type=int, default=8180)
    parser.add_argument('-o', '--open', action='store_true')
    parser.add_argument('-d', '--daemon', action='store_true')
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)
    from http_server_cli.dashboard import serve
    auto_daemon = parsed.daemon or parsed.open
    serve(port=parsed.port, open_browser=parsed.open,
          json_output_mode=parsed.json, daemon=auto_daemon)


def _manage_dashboard(subcmd: str, json_mode: bool = False, port=None) -> None:
    """管理 dashboard 服务：stop / status / restart / help

    port 形参仅 restart 使用（D9a：--port N 优先，未给则沿用 entry['port']，不再硬编码 8180）。
    """
    requested_port = port
    from http_server_cli.registry_managed import ManagedRegistry
    from http_server_cli.utils import eprint, format_duration, get_process_stats, is_process_alive, is_port_in_use, json_output
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
        if json_mode:
            json_output(False, f'dashboard-{subcmd}',
                        error='dashboard not running')
        else:
            eprint('dashboard not running', 'ℹ️')
        return

    port = entry.get('port', '?')
    pid = entry.get('pid')

    if subcmd == 'status':
        alive = pid and is_process_alive(pid) and is_port_in_use(port)
        duration = format_duration(entry.get('started_at', ''))
        stats = get_process_stats(pid)
        from http_server_cli.utils import LOG_DIR, format_path
        dashboard_log = format_path(os.path.join(LOG_DIR, 'dashboard.log'))
        if json_mode:
            json_output(True, 'dashboard-status', data={
                'name': 'dashboard',
                'port': port,
                'pid': pid,
                'alive': bool(alive),
                'duration': duration,
                'log': dashboard_log,
            })
            return
        icon = '🟢' if alive else '🔴'
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
        if subcmd == 'stop':
            if json_mode:
                json_output(True, 'dashboard-stop', data={
                    'name': 'dashboard', 'port': port, 'stopped': True,
                })
            else:
                eprint(f'dashboard (port {port}) stopped', '🛑')

    if subcmd == 'restart':
        from http_server_cli.dashboard import serve
        if requested_port is not None:
            if requested_port == 8181:
                eprint('8181 为 mcp 保留端口；dashboard 请用 8180 或其他端口', '⚠️')
                sys.exit(1)
            if requested_port != 8180 and is_port_in_use(requested_port):
                eprint(f'端口 {requested_port} 已被占用，请换端口（或先 hs kill {requested_port}）', '⚠️')
                sys.exit(1)
        restart_port = requested_port if requested_port is not None else (entry.get('port') or 8180)
        serve(port=restart_port, open_browser=False, daemon=True)
        if json_mode:
            json_output(True, 'dashboard-restart', data={
                'name': 'dashboard', 'port': restart_port, 'restarted': True,
            })


@_register
def _cmd_prompt(manager, args):
    """hs prompt — 输出 skills/ 使用说明（AI 对接，参考 html-gen prompt）"""
    import json as _json
    from pathlib import Path as _Path

    SKILLS_DIR = _Path(__file__).resolve().parents[2] / 'skills'
    json_mode = '--json' in args
    brief = '--brief' in args
    skill_name = next((a for a in args if not a.startswith('-')), None)

    if not SKILLS_DIR.is_dir():
        if json_mode:
            print(_json.dumps({'status': 'error', 'data': None,
                               'error': 'skills/ 目录不存在'}, ensure_ascii=False))
        else:
            print('❌ skills/ 目录不存在', file=sys.stderr)
        sys.exit(1)

    def _skill_desc(smd):
        try:
            for _line in open(smd, encoding='utf-8'):
                if _line.startswith('description:'):
                    return _line.split(':', 1)[1].strip()
        except Exception:
            pass
        return ''

    skills = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if d.is_dir():
            smd = d / 'SKILL.md'
            if smd.exists():
                skills.append({'name': d.name, 'path': smd, 'dir': d})

    if not skills:
        if json_mode:
            print(_json.dumps({'status': 'error', 'data': None,
                               'error': '无可用 skill'}, ensure_ascii=False))
        else:
            print('❌ 无可用 skill', file=sys.stderr)
        sys.exit(1)

    # 无参: 列出所有
    if not skill_name:
        if json_mode:
            print(_json.dumps({'status': 'ok', 'error': '', 'data': [
                {'name': s['name'],
                 'description': _skill_desc(s['path']),
                 'references': [r.name for r in s['dir'].glob('references/*.md')]}
                for s in skills]}, ensure_ascii=False, indent=2))
            return
        print('可用 skills:\n')
        for s in skills:
            desc = _skill_desc(s['path'])
            refs = [r.name for r in s['dir'].glob('references/*.md')]
            print(f"  {s['name']}")
            if desc:
                print(f"    {desc}")
            if refs:
                print(f"    references: {', '.join(refs)}")
            print(f"    用法: hs prompt {s['name']}")
            print()
        return

    # 带参: 查找 skill
    target = next((s for s in skills if s['name'] == skill_name), None)
    if not target:
        if json_mode:
            print(_json.dumps({'status': 'error', 'data': None,
                               'error': f"skill '{skill_name}' 不存在"},
                              ensure_ascii=False, indent=2))
            sys.exit(1)
        print(f"❌ skill '{skill_name}' 不存在", file=sys.stderr)
        print(f"可用: {', '.join(s['name'] for s in skills)}")
        sys.exit(1)

    content_text = target['path'].read_text(encoding='utf-8')

    if json_mode:
        refs = sorted(target['dir'].glob('references/*.md'))
        print(_json.dumps({'status': 'ok', 'error': '', 'data': {
            'name': target['name'],
            'content': content_text,
            'references': {r.stem: r.read_text(encoding='utf-8') for r in refs},
        }}, ensure_ascii=False, indent=2))
        return

    if brief:
        lines = content_text.split('\n')
        desc = next((l.split(':', 1)[1].strip() for l in lines if l.startswith('description:')), '')
        headings = [l for l in lines if l.startswith('## ')]
        refs = [r.name for r in target['dir'].glob('references/*.md')]
        if desc:
            print(desc)
            print()
        if headings:
            print('章节:')
            for h in headings:
                print(f"  {h[3:]}")
            print()
        if refs:
            print(f"references: {', '.join(refs)}")
        return

    # 全文
    print(content_text)
    refs = sorted(target['dir'].glob('references/*.md'))
    if refs:
        print('\n---\n')
        for r in refs:
            print(f'## {r.stem}')
            print(r.read_text(encoding='utf-8'))
            print()


@_register
def _cmd_mcp(manager, args):
    """hs mcp — MCP Server（自动后台运行 SSE）"""
    # 子命令优先
    sub = args[0] if args else None
    if sub in ('help', 'stop', 'status', 'restart'):
        _manage_mcp(sub, json_mode=('--json' in args))
        return

    parser = argparse.ArgumentParser(prog='hs mcp', add_help=False)
    parser.add_argument('--transport', choices=['stdio', 'sse'], default='sse')
    parser.add_argument('--port', type=int, default=8181)
    parser.add_argument('--config', action='store_true')
    parsed, _ = _parse_known_args(parser, args)
    if parsed.config:
        # 输出 mcpServers 接入配置片段（AI 工具一行接入）
        from http_server_cli.utils import json_output
        config_data = {'mcpServers': {
            'hs': {'command': 'hs', 'args': ['mcp', '--transport', 'stdio'], 'transport': 'stdio'},
        }}
        if '--json' in args:
            json_output(True, 'mcp-config', data=config_data)
        else:
            print('# hs MCP Server 接入配置 — 粘贴到 Claude Code / Cursor / Hermes 的 MCP 配置')
            print('mcpServers:')
            print('  hs:')
            print('    command: hs')
            print('    args: ["mcp", "--transport", "stdio"]')
            print('    transport: stdio')
            print()
            print('# 注: hs mcp 默认后台 SSE → http://127.0.0.1:8181/sse; --transport stdio 前台 stdio 模式')
        return
    if parsed.transport == 'stdio':
        from http_server_cli.mcp import serve_stdio
        serve_stdio()
    else:
        from http_server_cli.mcp import serve_sse
        serve_sse(port=parsed.port, daemon=True)


def _manage_mcp(subcmd: str, json_mode: bool = False) -> None:
    """管理 MCP 服务：stop / status / restart / help"""
    from http_server_cli.registry_managed import ManagedRegistry
    from http_server_cli.utils import eprint, format_duration, get_process_stats, is_process_alive, is_port_in_use, json_output
    import os, signal, time

    mreg = ManagedRegistry()
    entry = mreg.find(name='mcp')

    if subcmd == 'help':
        print('━━━ hs mcp ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        print('  hs mcp                    Background SSE (default)')
        print('  hs mcp --transport stdio  Foreground stdio mode')
        print('  hs mcp --port PORT        Specify port')
        print('  hs mcp stop               Stop MCP service')
        print('  hs mcp status             View status')
        print('  hs mcp restart            Restart MCP service')
        print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        return

    if subcmd in ('stop', 'status', 'restart') and not entry:
        if json_mode:
            json_output(False, f'mcp-{subcmd}', error='MCP not running')
        else:
            eprint('MCP not running', 'ℹ️')
        return

    port = entry.get('port', '?')
    pid = entry.get('pid')
    transport = entry.get('transport', '')

    if subcmd == 'status':
        alive = pid and is_process_alive(pid) and is_port_in_use(port)
        duration = format_duration(entry.get('started_at', ''))
        if json_mode:
            json_output(True, 'mcp-status', data={
                'name': 'mcp',
                'port': port,
                'pid': pid,
                'alive': bool(alive),
                'transport': transport,
                'duration': duration,
            })
            return
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
        if subcmd == 'stop':
            if json_mode:
                json_output(True, 'mcp-stop', data={
                    'name': 'mcp', 'port': port, 'stopped': True,
                })
            else:
                eprint(f'MCP (port {port}) stopped', '🛑')

    if subcmd == 'restart':
        from http_server_cli.mcp import serve_sse
        serve_sse(port=8181, daemon=True)
        if json_mode:
            json_output(True, 'mcp-restart', data={
                'name': 'mcp', 'port': port, 'restarted': True,
            })

# ── bookmark 子命令 ────────────────────────────────────

@_register
def _cmd_bookmark(manager, args):
    """hs bookmark — 书签管理"""
    sub = args[0] if args else None
    if sub == 'add':
        _bookmark_add(args[1:])
    elif sub == 'update':
        _bookmark_update(args[1:])
    elif sub == 'list':
        _bookmark_list(args[1:])
    elif sub == 'show':
        _bookmark_show(args[1:])
    elif sub == 'remove':
        _bookmark_remove(args[1:])
    elif sub in ('help', '-h', '--help'):
        _bookmark_help()
    else:
        print('❌ Usage: hs bookmark <add|update|list|show|remove> [args]', file=sys.stderr)
        _bookmark_help()


def _bookmark_help():
    print('━━━ hs bookmark ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('  hs bookmark add <name> [path] [-i index]     Add bookmark')
    print('  hs bookmark update <name> [path] [-i index]   Update path and/or index')
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
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.bookmark import BookmarkStore, DataCorruptionError
    from http_server_cli.server import _validate_index_page
    from http_server_cli.utils import resolve_path, format_path, json_output

    json_mode = parsed.json
    cmd = 'bookmark-add'

    # 名称校验
    name_err = BookmarkStore.validate_name(parsed.name)
    if name_err:
        if json_mode:
            json_output(False, cmd, error=name_err)
        else:
            print(f'❌ {name_err}', file=sys.stderr)
        return
    if parsed.name in _COMMANDS:
        err = f"'{parsed.name}' conflicts with built-in command"
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    # 路径处理（提前，因为通配符展开需要 abs_path）
    path = parsed.path or os.getcwd()
    abs_path = resolve_path(path)
    if not os.path.isdir(abs_path):
        err = f'Path does not exist or is not a directory: {format_path(abs_path)}'
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    # index_page 处理：含 * 的通配符保留原样（运行时解析），字面量立即校验
    index_page = parsed.index
    if index_page:
        if '*' in index_page:
            # 通配符模式：不展开、不校验，原样存储。运行时每次实时解析取最新文件。
            pass
        else:
            err = _validate_index_page(index_page)
            if err:
                if json_mode:
                    json_output(False, cmd, error=err)
                else:
                    print(f'❌ {err}', file=sys.stderr)
                return

    store = BookmarkStore()
    try:
        store.add(parsed.name, abs_path, index_page, force=parsed.force)
        bm = store.get(parsed.name)
        if json_mode:
            json_output(True, cmd, data={
                'name': bm['name'],
                'path': bm['path'],
                'index_page': bm.get('index_page'),
                'created_at': bm.get('created_at'),
            })
        else:
            print(f"✅ Bookmark '{parsed.name}' → {format_path(abs_path)}")
            if index_page:
                print(f"   📄 Default index: {index_page}")
    except ValueError as e:
        if json_mode:
            json_output(False, cmd, error=str(e))
        else:
            print(f'❌ {e}', file=sys.stderr)
    except DataCorruptionError:
        if json_mode:
            json_output(False, cmd, error='bookmarks file corrupted')
        else:
            print('❌ bookmarks file corrupted', file=sys.stderr)


def _bookmark_list(args):
    parser = argparse.ArgumentParser(prog='hs bookmark list', add_help=False)
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.bookmark import BookmarkStore, DataCorruptionError
    from http_server_cli.utils import format_path, json_output

    cmd = 'bookmark-list'
    store = BookmarkStore()
    try:
        bookmarks = store.list_all()
    except DataCorruptionError:
        if parsed.json:
            json_output(False, cmd, error='bookmarks file corrupted')
        else:
            print('❌ bookmarks file corrupted', file=sys.stderr)
        return

    if parsed.json:
        json_output(True, cmd, data={
            'count': len(bookmarks),
            'bookmarks': bookmarks,
        })
        return

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
    parser = argparse.ArgumentParser(prog='hs bookmark show', add_help=False)
    parser.add_argument('name', nargs='?', default=None)
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.bookmark import BookmarkStore, DataCorruptionError
    from http_server_cli.utils import format_path, json_output

    cmd = 'bookmark-show'
    if not parsed.name:
        err = 'Usage: hs bookmark show <name>'
        if parsed.json:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    store = BookmarkStore()
    try:
        bm = store.get(parsed.name)
    except DataCorruptionError:
        if parsed.json:
            json_output(False, cmd, error='bookmarks file corrupted')
        else:
            print('❌ bookmarks file corrupted', file=sys.stderr)
        return

    if not bm:
        err = f"bookmark '{parsed.name}' not found"
        if parsed.json:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    if parsed.json:
        json_output(True, cmd, data={
            'name': bm['name'],
            'path': bm['path'],
            'index_page': bm.get('index_page'),
            'created_at': bm.get('created_at'),
        })
        return

    print(f"📌 {bm['name']}")
    print(f"   📁 {format_path(bm['path'])}")
    if bm.get('index_page'):
        print(f"   📄 Default index: {bm['index_page']}")
    print(f"   🕐 Created: {bm.get('created_at', '-')}")


def _bookmark_remove(args):
    parser = argparse.ArgumentParser(prog='hs bookmark remove', add_help=False)
    parser.add_argument('name', nargs='?', default=None)
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.bookmark import BookmarkStore, DataCorruptionError
    from http_server_cli.utils import json_output

    cmd = 'bookmark-remove'
    if not parsed.name:
        err = 'Usage: hs bookmark remove <name>'
        if parsed.json:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    store = BookmarkStore()
    try:
        removed = store.remove(parsed.name)
    except DataCorruptionError:
        if parsed.json:
            json_output(False, cmd, error='bookmarks file corrupted')
        else:
            print('❌ bookmarks file corrupted', file=sys.stderr)
        return

    if parsed.json:
        if removed:
            json_output(True, cmd, data={'name': parsed.name})
        else:
            json_output(False, cmd, error=f"bookmark '{parsed.name}' not found")
        return

    if removed:
        print(f"✅ Bookmark '{parsed.name}' removed")
    else:
        print(f"❌ bookmark '{parsed.name}' not found", file=sys.stderr)


def _bookmark_update(args):
    parser = argparse.ArgumentParser(prog='hs bookmark update', add_help=False)
    parser.add_argument('name')
    parser.add_argument('path', nargs='?', default=None)
    parser.add_argument('-i', '--index', default=None)
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.bookmark import BookmarkStore, DataCorruptionError
    from http_server_cli.server import _validate_index_page
    from http_server_cli.utils import resolve_path, format_path, json_output

    json_mode = parsed.json
    cmd = 'bookmark-update'

    store = BookmarkStore()
    try:
        existing = store.get(parsed.name)
    except DataCorruptionError:
        if json_mode:
            json_output(False, cmd, error='bookmarks file corrupted')
        else:
            print('❌ bookmarks file corrupted', file=sys.stderr)
        return

    if not existing:
        err = f"bookmark '{parsed.name}' not found"
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    # 路径处理
    path = None
    if parsed.path is not None:
        abs_path = resolve_path(parsed.path)
        if not os.path.isdir(abs_path):
            err = f'Path does not exist: {format_path(abs_path)}'
            if json_mode:
                json_output(False, cmd, error=err)
            else:
                print(f'❌ {err}', file=sys.stderr)
            return
        path = abs_path

    # index_page 处理：含 * 的通配符保留原样，字面量立即校验
    index_page = parsed.index
    if index_page is not None:
        if '*' in index_page:
            # 通配符模式：不展开、不校验，原样存储
            pass
        elif index_page:
            err = _validate_index_page(index_page)
            if err:
                if json_mode:
                    json_output(False, cmd, error=err)
                else:
                    print(f'❌ {err}', file=sys.stderr)
                return
        else:
            index_page = ''  # 空字符串 → 清除

    try:
        store.update(parsed.name, path=path, index_page=index_page)
        updated = store.get(parsed.name)
        if json_mode:
            json_output(True, cmd, data={
                'name': updated['name'],
                'path': updated['path'],
                'index_page': updated.get('index_page'),
            })
        else:
            print(f"✅ Bookmark '{parsed.name}' updated")
            print(f"   📁 {format_path(updated['path'])}")
            if updated.get('index_page'):
                print(f"   📄 Default index: {updated['index_page']}")
    except ValueError as e:
        if json_mode:
            json_output(False, cmd, error=str(e))
        else:
            print(f'❌ {e}', file=sys.stderr)
    except DataCorruptionError:
        if json_mode:
            json_output(False, cmd, error='bookmarks file corrupted')
        else:
            print('❌ bookmarks file corrupted', file=sys.stderr)

# ── Web 服务注册（hs web）──────────────────────────────

_WEB_SUBCOMMANDS = frozenset({'add', 'update', 'list', 'show', 'remove', 'help'})


@_register
def _cmd_web(manager, args):
    """hs web — 跨项目 Web 服务注册管理"""
    sub = args[0] if args else None
    if sub == 'add':
        _web_add(args[1:])
    elif sub == 'update':
        _web_update(args[1:])
    elif sub == 'list':
        _web_list(args[1:])
    elif sub == 'show':
        _web_show(args[1:])
    elif sub == 'remove':
        _web_remove(args[1:])
    elif sub in ('help', '-h', '--help'):
        _web_help()
    else:
        # 未识别子命令 → 视为执行: hs web <name> [--no-probe]
        _web_run(args)


def _web_help():
    print('━━━ hs web ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('  注册任意 web 服务启动命令，按名称快速启动/访问')
    print()
    print("  hs web add <name> --cmd '<cmd>' [--url <url>] [--open cmd|url|both|none] [--domain] [--port <N>]")
    print('      --cmd  启动命令（如 dk server start --daemon --open）')
    print('      --url  服务 URL（固定端口必填；动态端口不填，启动前未知）')
    print('      --open 开浏览器策略（默认 url: web 统一开; cmd: 命令自带 -o; both: 都试; none: 不开）')
    print('      --domain 执行时注入 config.domain 到 cmd 末尾（--domain "<domain>"）')
    print('      --port 执行时注入 --port <N> 到 cmd 末尾（1024-65535；与 --domain 同时开启时顺序为 domain 先 port 后）')
    print('      --no-port 清除端口注入')
    print('  hs web update <name> [--cmd ...] [--url ...] [--open ...] [--domain|--no-domain] [--port <N>|--no-port]')
    print('  hs web list [--json|--plain] [--sort-by name|cmd+url] / show <name> / remove <name>')
    print('  hs web <name> [--no-probe]   执行：已运行→直接访问；未运行→执行启动命令')
    print('      --no-probe 跳过探测，总是执行启动命令（强制重启）')
    print('  hs web help')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')


def _web_add(args):
    parser = argparse.ArgumentParser(prog='hs web add', add_help=False)
    parser.add_argument('name')
    parser.add_argument('--cmd', default=None)
    parser.add_argument('--url', default=None)
    parser.add_argument('--open', dest='open_mode', default=None)
    parser.add_argument('--domain', action='store_true',
                        help='执行时注入 config.domain 到 cmd 末尾（--domain "<domain>"）')
    parser.add_argument('--port', type=int, default=None,
                        help='执行时注入 --port <N> 到 cmd 末尾（1024-65535，D9b）')
    parser.add_argument('--no-port', dest='no_port', action='store_true',
                        help='不注入端口（清除既有 port 配置）')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.services import ServiceStore, DataCorruptionError
    from http_server_cli.utils import json_output

    json_mode = parsed.json
    cmd = 'web-add'

    if not parsed.cmd:
        err = "--cmd is required (e.g. --cmd 'dk server start --daemon --open')"
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    name_err = ServiceStore.validate_name(parsed.name)
    if name_err:
        if json_mode:
            json_output(False, cmd, error=name_err)
        else:
            print(f'❌ {name_err}', file=sys.stderr)
        return
    if parsed.name in _COMMANDS or parsed.name in _WEB_SUBCOMMANDS:
        err = f"'{parsed.name}' conflicts with built-in command"
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    open_mode = parsed.open_mode or 'url'
    err = ServiceStore.validate_open_mode(open_mode)
    if err:
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return
    err = ServiceStore.validate_url(parsed.url)
    if err:
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return
    if parsed.no_port and parsed.port is not None:
        err = '--port and --no-port are mutually exclusive'
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return
    err = ServiceStore.validate_port(parsed.port)
    if err:
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    store = ServiceStore()
    try:
        store.add(parsed.name, parsed.cmd, url=parsed.url,
                  open_mode=open_mode, use_domain=parsed.domain,
                  use_port=parsed.port is not None and not parsed.no_port,
                  port=parsed.port,
                  force=parsed.force)
        svc = store.get(parsed.name)
        if svc is None:  # pragma: no cover - add 成功后必然存在
            return
        if json_mode:
            json_output(True, cmd, data=svc)
        else:
            print(f"✅ Service '{parsed.name}' registered")
            print(f"   🚀 Cmd: {svc['cmd']}")
            if svc.get('url'):
                print(f"   🌐 URL: {svc['url']}")
            print(f"   👁  Open: {svc.get('open', 'url')}")
            if svc.get('use_domain'):
                print('   🏷  Domain: on (inject config.domain at run)')
            if svc.get('use_port'):
                print(f"   🔌 Port: on (inject --port {svc.get('port')} at run)")
    except ValueError as e:
        if json_mode:
            json_output(False, cmd, error=str(e))
        else:
            print(f'❌ {e}', file=sys.stderr)
    except DataCorruptionError:
        if json_mode:
            json_output(False, cmd, error='services file corrupted')
        else:
            print('❌ services file corrupted', file=sys.stderr)


def _web_list(args):
    parser = argparse.ArgumentParser(prog='hs web list', add_help=False)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--plain', action='store_true')
    parser.add_argument('--sort-by', dest='sort_by', default=None,
                        choices=['name', 'cmd+url'],
                        help='排序键（默认 name → cmd+url，a-z）')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.services import ServiceStore, DataCorruptionError
    from http_server_cli.utils import json_output

    cmd = 'web-list'
    if parsed.json and parsed.plain:
        parser.error('--json and --plain are mutually exclusive')
    store = ServiceStore()
    try:
        services = store.list_all()
    except DataCorruptionError:
        if parsed.json:
            json_output(False, cmd, error='services file corrupted')
        else:
            print('❌ services file corrupted', file=sys.stderr)
        return

    # 排序（大小写不敏感 a-z）：默认 name → cmd → url；cmd+url 时以 name 兜底
    def sort_key(s):
        name, cmd_l, url = s['name'].lower(), s['cmd'].lower(), (s.get('url') or '').lower()
        if parsed.sort_by == 'cmd+url':
            return (cmd_l, url, name)
        return (name, cmd_l, url)

    services.sort(key=sort_key)

    if parsed.json:
        json_output(True, cmd, data={
            'count': len(services),
            'services': services,
        })
        return

    if not services:
        print('No services registered')
        return
    total = len(services)
    if parsed.plain:
        for i, svc in enumerate(services, 1):
            print(f"{i}/{total} {svc['name']}: {svc['cmd']}")
        return
    print(f'📊 {total} service(s):')
    print()
    for i, svc in enumerate(services, 1):
        print(f"{i}/{total} 🌐 {svc['name']}")
        print(f"     🚀 {svc['cmd']}")
        if svc.get('url'):
            print(f"     🌍 {svc['url']}")
        line = f"     👁  Open: {svc.get('open', 'url')}"
        if svc.get('use_domain'):
            line += ' 🏷  Domain: on'
        if svc.get('use_port'):
            line += f" 🔌 Port: {svc.get('port')}"
        print(line)
        print()


def _web_show(args):
    parser = argparse.ArgumentParser(prog='hs web show', add_help=False)
    parser.add_argument('name', nargs='?', default=None)
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.services import ServiceStore, DataCorruptionError
    from http_server_cli.utils import json_output

    cmd = 'web-show'
    if not parsed.name:
        err = 'Usage: hs web show <name>'
        if parsed.json:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    store = ServiceStore()
    try:
        svc = store.get(parsed.name)
    except DataCorruptionError:
        if parsed.json:
            json_output(False, cmd, error='services file corrupted')
        else:
            print('❌ services file corrupted', file=sys.stderr)
        return

    if not svc:
        err = f"service '{parsed.name}' not found"
        if parsed.json:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    if parsed.json:
        json_output(True, cmd, data=svc)
        return

    print(f"🌐 {svc['name']}")
    print(f"   🚀 Cmd: {svc['cmd']}")
    if svc.get('url'):
        print(f"   🌍 URL: {svc['url']}")
    print(f"   👁  Open: {svc.get('open', 'url')}")
    if svc.get('use_domain'):
        print('   🏷  Domain: on (inject config.domain at run)')
    if svc.get('use_port'):
        print(f"   🔌 Port: on (inject --port {svc.get('port')} at run)")
    print(f"   🕐 Created: {svc.get('created_at', '-')}")


def _web_remove(args):
    parser = argparse.ArgumentParser(prog='hs web remove', add_help=False)
    parser.add_argument('name', nargs='?', default=None)
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.services import ServiceStore, DataCorruptionError
    from http_server_cli.utils import json_output

    cmd = 'web-remove'
    if not parsed.name:
        err = 'Usage: hs web remove <name>'
        if parsed.json:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    store = ServiceStore()
    try:
        removed = store.remove(parsed.name)
    except DataCorruptionError:
        if parsed.json:
            json_output(False, cmd, error='services file corrupted')
        else:
            print('❌ services file corrupted', file=sys.stderr)
        return

    if parsed.json:
        if removed:
            json_output(True, cmd, data={'name': parsed.name})
        else:
            json_output(False, cmd, error=f"service '{parsed.name}' not found")
        return

    if removed:
        print(f"✅ Service '{parsed.name}' removed")
    else:
        print(f"❌ service '{parsed.name}' not found", file=sys.stderr)


def _web_update(args):
    parser = argparse.ArgumentParser(prog='hs web update', add_help=False)
    parser.add_argument('name')
    parser.add_argument('--cmd', default=None)
    parser.add_argument('--url', default=None)
    parser.add_argument('--open', dest='open_mode', default=None)
    parser.add_argument('--domain', action='store_true')
    parser.add_argument('--no-domain', dest='no_domain', action='store_true')
    parser.add_argument('--port', type=int, default=None,
                        help='执行时注入 --port <N> 到 cmd 末尾（1024-65535，D9b）')
    parser.add_argument('--no-port', dest='no_port', action='store_true',
                        help='不注入端口（同时清除 port 值）')
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.services import ServiceStore, DataCorruptionError
    from http_server_cli.utils import json_output

    json_mode = parsed.json
    cmd = 'web-update'

    store = ServiceStore()
    try:
        existing = store.get(parsed.name)
    except DataCorruptionError:
        if json_mode:
            json_output(False, cmd, error='services file corrupted')
        else:
            print('❌ services file corrupted', file=sys.stderr)
        return

    if not existing:
        err = f"service '{parsed.name}' not found"
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    if (parsed.cmd is None and parsed.url is None and parsed.open_mode is None
            and not parsed.domain and not parsed.no_domain
            and parsed.port is None and not parsed.no_port):
        err = ('Nothing to update: pass --cmd / --url / --open / --domain / --no-domain '
               '/ --port / --no-port')
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    if parsed.open_mode is not None:
        err = ServiceStore.validate_open_mode(parsed.open_mode)
        if err:
            if json_mode:
                json_output(False, cmd, error=err)
            else:
                print(f'❌ {err}', file=sys.stderr)
            return
    if parsed.url is not None:
        err = ServiceStore.validate_url(parsed.url)
        if err:
            if json_mode:
                json_output(False, cmd, error=err)
            else:
                print(f'❌ {err}', file=sys.stderr)
            return
    if parsed.no_port and parsed.port is not None:
        err = '--port and --no-port are mutually exclusive'
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return
    err = ServiceStore.validate_port(parsed.port)
    if err:
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
        return

    # --no-domain 优先（清除语义，对齐 --url ''）
    use_domain = None
    if parsed.no_domain:
        use_domain = False
    elif parsed.domain:
        use_domain = True

    # --no-port 优先（清除：use_port=False 且 port 同清，D9b / F-9）
    use_port = None
    if parsed.no_port:
        use_port = False
    elif parsed.port is not None:
        use_port = True

    try:
        store.update(parsed.name, cmd=parsed.cmd, url=parsed.url,
                     open_mode=parsed.open_mode, use_domain=use_domain,
                     use_port=use_port, port=parsed.port)
        updated = store.get(parsed.name)
        if updated is None:  # pragma: no cover - update 成功后必然存在
            return
        if json_mode:
            json_output(True, cmd, data=updated)
        else:
            print(f"✅ Service '{parsed.name}' updated")
            print(f"   🚀 Cmd: {updated['cmd']}")
            if updated.get('url'):
                print(f"   🌍 URL: {updated['url']}")
            print(f"   👁  Open: {updated.get('open', 'url')}")
            if updated.get('use_domain'):
                print('   🏷  Domain: on (inject config.domain at run)')
            if updated.get('use_port'):
                print(f"   🔌 Port: on (inject --port {updated.get('port')} at run)")
    except ValueError as e:
        if json_mode:
            json_output(False, cmd, error=str(e))
        else:
            print(f'❌ {e}', file=sys.stderr)
    except DataCorruptionError:
        if json_mode:
            json_output(False, cmd, error='services file corrupted')
        else:
            print('❌ services file corrupted', file=sys.stderr)


def _web_run(args):
    parser = argparse.ArgumentParser(prog='hs web', add_help=False)
    parser.add_argument('name', nargs='?', default=None)
    parser.add_argument('--no-probe', action='store_true')
    parser.add_argument('--json', action='store_true')
    parsed, _ = _parse_known_args(parser, args)

    from http_server_cli.services import ServiceStore, DataCorruptionError
    from http_server_cli.utils import (
        json_output, url_reachable, wait_url_reachable,
    )

    cmd = 'web-run'
    json_mode = parsed.json
    if not parsed.name:
        _web_help()
        return

    store = ServiceStore()
    try:
        svc = store.get(parsed.name)
    except DataCorruptionError:
        if json_mode:
            json_output(False, cmd, error='services file corrupted')
        else:
            print('❌ services file corrupted', file=sys.stderr)
        return

    if not svc:
        err = f"service '{parsed.name}' not found"
        if json_mode:
            json_output(False, cmd, error=err)
        else:
            print(f'❌ {err}', file=sys.stderr)
            available = sorted(store.names())
            if available:
                print(f'   Available: {", ".join(available)}')
        sys.exit(1)

    url = svc.get('url') or None
    open_mode = svc.get('open') or 'url'

    # 探测阶段：url 已配置且未跳过 → 可达则直接访问（幂等）
    if url and not parsed.no_probe:
        if url_reachable(url):
            if open_mode in ('url', 'both'):
                webbrowser.open(url)
            if json_mode:
                json_output(True, cmd, data={
                    'name': parsed.name, 'url': url, 'status': 'running',
                })
            else:
                print(f"✅ Service '{parsed.name}' already running")
                print(f"   🌐 {url}")
            return

    # 执行阶段：执行启动命令（透传，cmd 需为守护/后台形式）
    cmd_line = svc['cmd']
    if svc.get('use_domain'):
        from http_server_cli.config import Config
        cmd_line = f"{cmd_line} --domain \"{Config().domain}\""
    # D9b：固定顺序 domain 先、port 后
    if svc.get('use_port') and svc.get('port') is not None:
        cmd_line = f"{cmd_line} --port {svc['port']}"
    result = subprocess.run(cmd_line, shell=True)

    # 启动后确认 + open（url/both 策略）
    if url and open_mode in ('url', 'both'):
        reachable = wait_url_reachable(url)
        if reachable:
            webbrowser.open(url)
        elif not json_mode:
            print(f'   ⚠️ URL not ready yet: {url}', file=sys.stderr)

    if json_mode:
        json_output(True, cmd, data={
            'name': parsed.name,
            'cmd': svc['cmd'],
            'cmd_effective': cmd_line,
            'url': url,
            'open': open_mode,
            'status': 'started',
            'exit_code': result.returncode,
        })
    else:
        print(f"✅ Service '{parsed.name}' started")
        if url:
            print(f"   🌐 {url}")
        if result.returncode != 0:
            print(f'   ⚠️ Cmd exited with code {result.returncode}', file=sys.stderr)


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
                idx = bm['index_page']
                if '*' in idx:
                    # 通配符模式：运行时实时解析取最近修改的文件
                    pattern = os.path.join(bm['path'], idx)
                    matches = glob.glob(pattern)
                    if matches:
                        latest = max(matches, key=os.path.getmtime)
                        idx = os.path.relpath(latest, bm['path'])
                    else:
                        idx = None  # 无匹配文件 → 不传 -i，用默认 index.html
                if idx:
                    implicit += ['-i', idx]
            parsed.args = implicit + parsed.args
            cmd = 'start'
        # ➋ 回退到路径快捷方式
        elif (cmd.startswith(('.', '/', '~')) or cmd == '..'
                or os.path.exists(cmd) or glob.glob(cmd)):
            parsed.args = [parsed.command] + parsed.args
            cmd = 'start'
        # ➌ 取值型 flag 的值被 argparse 误判为 positional（D8）：
        #     hs -p 8089 → command='8089'/unknown=['-p']；hs -i a.html -p 8089 → command='a.html'/unknown=['-i']
        #     按原顺序重组回 start 参数；有意不含 -o/-d/-f（布尔 flag 无「值泄漏」场景）
        elif unknown and any(t in ('-p', '--port', '-i', '--index') for t in unknown):
            parsed.args = unknown + [parsed.command] + parsed.args
            cmd = 'start'
        else:
            eprint(f'Unknown command: {cmd}', '❌')
            _cmd_help(None, [])
            sys.exit(1)

    # 未识别参数告警（D6）：start 由子命令层负责（其 unknown 承载多 html 文件通配语义）
    if cmd in _COMMANDS and cmd != 'start' and unknown:
        _warn_unknown_args(unknown, allow=('-h', '--help', '-v', '--version'))

    ensure_storage()
    manager = ServerManager()
    _COMMANDS[cmd](manager, parsed.args)

if __name__ == '__main__':
    main()
