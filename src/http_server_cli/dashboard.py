#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hs dashboard — Web 仪表盘管理界面。

通过 REST API 提供图形化管理 HTTP 服务的功能。
零外部依赖，仅使用 Python 标准库。
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Optional

from http_server_cli.registry_managed import ManagedRegistry
from http_server_cli.server import ServerManager
from http_server_cli.utils import (
    LOG_DIR,
    format_path,
    get_process_stats,
    is_port_in_use,
    is_process_alive,
    json_output,
    SCRIPT_DIR,
)

# ── HTML 页面（从独立文件加载）─────────────────────────────

_DASHBOARD_CACHE: dict = {}

def _get_html(lang: str = 'zh') -> str:
    """加载 HTML 页面，支持 'zh' (中文) 和 'en' (英文)"""
    filename = 'dashboard.html' if lang == 'zh' else 'dashboard.en.html'
    if lang not in _DASHBOARD_CACHE:
        html_path = os.path.join(SCRIPT_DIR, filename)
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                _DASHBOARD_CACHE[lang] = f.read()
        except FileNotFoundError:
            _DASHBOARD_CACHE[lang] = f'<html><body><h1>Dashboard HTML ({filename}) not found</h1></body></html>'
    return _DASHBOARD_CACHE[lang]


# ── Dashboard HTTP Handler ─────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    """Web 仪表盘 HTTP 请求处理器。"""

    manager: ServerManager = None  # type: ignore[assignment]
    """在 HTTPServer 启动前设置"""

    # ── 通用 ──

    def _json(self, data: dict, status: int = 200) -> None:
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _html(self, content: str) -> None:
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def _error(self, msg: str, status: int = 404) -> None:
        self._json({'error': msg, 'success': False}, status)

    def log_message(self, format: str, *args) -> None:  # type: ignore[override]
        """静默日志 — 不污染 stdout"""
        pass

    def _detect_lang(self) -> str:
        """根据 Accept-Language 头自动检测语言，返回 'zh' 或 'en'
        优先检查 URL 查询参数 ?lang=zh / ?lang=en"""
        # 查询参数优先
        if '?lang=zh' in self.path or '&lang=zh' in self.path:
            return 'zh'
        if '?lang=en' in self.path or '&lang=en' in self.path:
            return 'en'
        # 后备：Accept-Language 头
        accept = self.headers.get('Accept-Language', '')
        for part in accept.split(','):
            lang = part.split(';')[0].strip().split('-')[0]
            if lang == 'en':
                return 'en'
            if lang == 'zh':
                return 'zh'
        return 'zh'

    # ── GET ──

    def do_GET(self) -> None:
        path = self.path.split('?')[0]
        if path == '/':
            lang = self._detect_lang()
            self._html(_get_html(lang))
        elif path == '/en':
            self._html(_get_html('en'))
        elif path == '/api/servers':
            self._handle_get_servers()
        elif path.startswith('/api/status/'):
            port_str = path.split('/')[-1]
            if port_str.isdigit():
                self._handle_get_status(int(port_str))
            else:
                self._error('invalid port', 400)
        elif path == '/api/info':
            self._handle_get_info()
        elif path.startswith('/api/ping/'):
            port_str = path.split('/')[-1]
            if port_str.isdigit():
                self._handle_ping(int(port_str))
            else:
                self._error('invalid port', 400)
        elif path.startswith('/api/log/'):
            port_str = path.split('/')[-1]
            if port_str.isdigit():
                self._handle_log(int(port_str))
            else:
                self._error('invalid port', 400)
        else:
            self._error('not found')

    def _get_server_list(self) -> dict:
        """获取服务列表，附带存活状态和资源统计。返回 dict 含 servers + managed"""
        # 每次创建新的 ServerManager 以读取最新 registry.json
        from http_server_cli.server import ServerManager
        sm = ServerManager()
        entries = sm.registry.active_servers()
        servers = []
        for entry in entries:
            pid = entry.get('pid')
            stats = get_process_stats(pid)
            started = entry.get('started_at', '')
            servers.append({
                'url': f"http://{entry.get('domain', 'localhost')}:{entry['port']}",
                'port': entry['port'],
                'path': entry['path'],
                'path_display': format_path(entry['path']),
                'pid': pid,
                'alive': entry['_alive'],
                'domain': entry.get('domain', 'localhost'),
                'mode': 'daemon' if entry.get('daemon') else
                        ('foreground' if entry.get('foreground') else 'normal'),
                'started_at': started,
                'last_access_at': entry.get('last_access_at', ''),
                'duration': self._format_duration(started),
                'log_path': format_path(os.path.join(LOG_DIR, f"{entry['port']}.log")),
                'index_page': entry.get('index_page', 'index.html'),
                'stats': stats,
            })

        # Managed services
        mreg = ManagedRegistry()
        managed = []
        for entry in mreg.active_servers():
            managed.append({
                'name': entry.get('name', ''),
                'port': entry['port'],
                'pid': entry.get('pid'),
                '_alive': entry['_alive'],
                'type': entry.get('type', ''),
                'transport': entry.get('transport', ''),
                'started_at': entry.get('started_at', ''),
                'stats': get_process_stats(entry.get('pid')),
            })

        return {'servers': servers, 'managed': managed}

    def _format_duration(self, started_at: str) -> str:
        """简易时长格式化"""
        from http_server_cli.utils import format_duration
        return format_duration(started_at)

    def _handle_get_servers(self) -> None:
        result = self._get_server_list()
        self._json({'success': True, 'command': 'list', 'data': {
            'count': len(result['servers']),
            'servers': result['servers'],
            'managed': result['managed'],
        }})

    def _handle_get_status(self, port: int) -> None:
        entry = self.manager.registry.find(port=port)
        if not entry:
            self._json({'success': True, 'command': 'status', 'data': {
                'found': False, 'port': port,
            }})
            return
        pid = entry.get('pid')
        alive = is_process_alive(pid)
        stats = get_process_stats(pid)
        duration = self._format_duration(entry.get('started_at', ''))
        self._json({'success': True, 'command': 'status', 'data': {
            'found': True,
            'port': port,
            'path': entry['path'],
            'path_display': format_path(entry['path']),
            'pid': pid,
            'alive': alive and is_port_in_use(port),
            'domain': entry.get('domain', 'localhost'),
            'mode': 'daemon' if entry.get('daemon') else
                    ('foreground' if entry.get('foreground') else 'normal'),
            'started_at': entry.get('started_at'),
            'last_access_at': entry.get('last_access_at', ''),
            'duration': duration,
            'log_path': format_path(os.path.join(LOG_DIR, f"{port}.log")),
            'index_page': entry.get('index_page', 'index.html'),
            'stats': stats,
        }})

    def _handle_get_info(self) -> None:
        """返回版本号与命令参考"""
        from http_server_cli import __version__
        commands = [
            {'cmd': 'hs . [-o] [-d] [-f]', 'desc': '快捷启动（等价 hs start .）'},
            {'cmd': 'hs start [path] [-o] [-d] [-f] [-i <file>]', 'desc': '启动 HTTP 服务'},
            {'cmd': 'hs list [--port|--path|--short] [--json]', 'desc': '列出运行中服务'},
            {'cmd': 'hs status <port|path> [--json]', 'desc': '查询服务状态'},
            {'cmd': 'hs kill <port|path> [--json]', 'desc': '关闭指定服务'},
            {'cmd': 'hs kill-all [--json]', 'desc': '关闭所有服务'},
            {'cmd': 'hs history [--json]', 'desc': '历史记录'},
            {'cmd': 'hs search <keyword> [--json]', 'desc': '搜索实例'},
            {'cmd': 'hs dashboard [-p <port>] [-o] [--json]', 'desc': 'Web 管理面板'},
            {'cmd': 'hs dashboard stop|status|restart|help', 'desc': 'dashboard 管理'},
            {'cmd': 'hs mcp [--transport stdio|sse] [--port PORT]', 'desc': 'MCP Server（AI 集成）'},
            {'cmd': 'hs mcp stop|status|restart|help', 'desc': 'MCP 管理'},
            {'cmd': 'hs config [--json]', 'desc': '显示配置'},
            {'cmd': 'hs set port|domain <value>', 'desc': '修改配置'},
            {'cmd': 'hs help', 'desc': '显示帮助'},
            {'cmd': 'hs version [--json]', 'desc': '版本号'},
        ]
        self._json({'success': True, 'version': __version__, 'commands': commands})

    def _handle_ping(self, port: int) -> None:
        """对实例发送 HTTP HEAD 健康检查（2s 超时）"""
        entry = self.manager.registry.find(port=port)
        if not entry:
            self._json({'success': True, 'port': port, 'alive': False,
                        'status_code': None, 'response_time_ms': None})
            return
        domain = entry.get('domain', 'localhost')
        url = f'http://{domain}:{port}/'
        start = time.time()
        try:
            req = urllib.request.Request(url, method='HEAD')
            resp = urllib.request.urlopen(req, timeout=2)
            elapsed = int((time.time() - start) * 1000)
            self._json({'success': True, 'port': port, 'alive': True,
                        'status_code': resp.getcode(), 'response_time_ms': elapsed})
        except urllib.error.HTTPError as e:
            elapsed = int((time.time() - start) * 1000)
            self._json({'success': True, 'port': port, 'alive': True,
                        'status_code': e.code, 'response_time_ms': elapsed})
        except Exception:
            self._json({'success': True, 'port': port, 'alive': False,
                        'status_code': None, 'response_time_ms': None})

    def _handle_log(self, port: int) -> None:
        """返回端口对应日志文件的最近 50 行"""
        log_path = os.path.join(LOG_DIR, f'{port}.log')
        if not os.path.exists(log_path):
            self._json({'success': True, 'port': port, 'log': '', 'lines': 0})
            return
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            tail = lines[-50:]
            self._json({'success': True, 'port': port,
                        'log': ''.join(tail), 'lines': len(tail)})
        except Exception as e:
            self._json({'success': True, 'port': port,
                        'log': f'[error reading log] {e}', 'lines': 0})

    # ── POST ──

    def do_POST(self) -> None:
        if self.path.startswith('/api/kill/'):
            port_str = self.path.split('/')[-1]
            if port_str.isdigit():
                self._handle_kill(int(port_str))
            else:
                self._error('invalid port', 400)
        elif self.path == '/api/kill-all':
            self._handle_kill_all()
        elif self.path.startswith('/api/restart/'):
            port_str = self.path.split('/')[-1]
            if port_str.isdigit():
                self._handle_restart(int(port_str))
            else:
                self._error('invalid port', 400)
        else:
            self._error('not found', 404)

    def _handle_kill(self, port: int) -> None:
        entry = self.manager.registry.find(port=port)
        if not entry:
            self._error(f'端口 {port} 未注册')
            return
        pid = entry.get('pid')
        killed = False
        if pid and is_process_alive(pid):
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(0.3)
                if is_process_alive(pid):
                    os.killpg(pgid, signal.SIGKILL)
                killed = True
            except (ProcessLookupError, PermissionError, OSError):
                pass
        self.manager.registry.remove(port=port)
        # 删除日志
        log_path = os.path.join(LOG_DIR, f'{port}.log')
        if os.path.isfile(log_path):
            try:
                os.remove(log_path)
            except OSError:
                pass
        self._json({'success': True, 'command': 'kill', 'data': {
            'port': port, 'path': entry['path'],
            'pid': pid, 'killed': killed,
        }})

    def _handle_kill_all(self) -> None:
        entries = self.manager.registry.all()
        count = 0
        for entry in list(entries):
            pid = entry.get('pid')
            port = entry['port']
            if pid and is_process_alive(pid):
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.2)
                    if is_process_alive(pid):
                        os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
            self.manager.registry.remove(port=port)
            log_path = os.path.join(LOG_DIR, f'{port}.log')
            if os.path.isfile(log_path):
                try:
                    os.remove(log_path)
                except OSError:
                    pass
            count += 1
        self._json({'success': True, 'command': 'kill-all', 'data': {
            'total': len(entries), 'killed': count,
        }})

    def _handle_restart(self, port: int) -> None:
        entry = self.manager.registry.find(port=port)
        if not entry:
            self._error(f'端口 {port} 未注册')
            return
        path = entry['path']
        # kill
        pid = entry.get('pid')
        if pid and is_process_alive(pid):
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(0.3)
                if is_process_alive(pid):
                    os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        self.manager.registry.remove(port=port)
        log_path = os.path.join(LOG_DIR, f'{port}.log')
        if os.path.isfile(log_path):
            try:
                os.remove(log_path)
            except OSError:
                pass
        # start (daemon mode)
        self.manager.start(path=path, daemon=True, json=False)
        # 获取新端口
        new_entry = self.manager.registry.find(path=path)
        new_port = new_entry['port'] if new_entry else None
        self._json({'success': True, 'command': 'restart', 'data': {
            'path': path, 'old_port': port,
            'new_port': new_port,
        }})

# ── 入口 ───────────────────────────────────────────────

def serve(port: int = 8180, open_browser: bool = False,
          json_output_mode: bool = False, daemon: bool = False) -> None:
    """启动仪表盘服务。

    Args:
        port: 监听端口（默认 8180）
        open_browser: 是否自动打开浏览器
        json_output_mode: 仅输出 JSON 数据，不启动服务
        daemon: 后台守护模式
    """
    manager = ServerManager()
    mreg = ManagedRegistry()

    if json_output_mode:
        # 一次性查询模式 — 包含 managed 服务
        servers = []
        for entry in manager.registry.active_servers():
            servers.append({
                'port': entry['port'],
                'path': entry['path'],
                'pid': entry.get('pid'),
                'alive': entry['_alive'],
                'stats': get_process_stats(entry.get('pid')),
            })
        managed = []
        for entry in mreg.active_servers():
            managed.append({
                'name': entry.get('name', ''),
                'port': entry['port'],
                'pid': entry.get('pid'),
                'alive': entry['_alive'],
                'type': entry.get('type', ''),
                'transport': entry.get('transport', ''),
                'stats': get_process_stats(entry.get('pid')),
            })
        from http_server_cli.utils import json_output as _jout
        _jout(True, 'dashboard', data={
            'count': len(servers),
            'servers': servers,
            'managed': managed,
        })
        return

    # ── 重复执行检测 ──
    existing = mreg.find(name='dashboard')
    if existing:
        epid = existing.get('pid')
        eport = existing.get('port')
        if epid and is_process_alive(epid) and is_port_in_use(eport):
            from http_server_cli.utils import format_duration as _fd
            duration = _fd(existing.get('started_at', ''))
            stats = get_process_stats(epid)
            print(f'📊 hs dashboard already running')
            print(f'    🔧 http://127.0.0.1:{eport}  (PID: {epid})')
            cpu_s = stats.get('cpu', '-')
            mem_s = stats.get('memory', '-')
            print(f'    📊 Duration: {duration}  |  CPU: {cpu_s}  |  Memory: {mem_s}')
            if open_browser:
                webbrowser.open(f'http://127.0.0.1:{eport}')
                print('🌐 Browser opened')
            else:
                print(f'    💡 Open browser: hs dashboard -o')
            return
        else:
            # 残留记录，清理
            mreg.remove(name='dashboard')

    # 端口可用性检测
    from http_server_cli.utils import is_port_in_use as _port_check
    if _port_check(port):
        from http_server_cli.utils import find_available_port
        new_port = find_available_port(port + 1)
        if new_port is None:
            print(f'❌ Ports {port}-10000 are all occupied')
            sys.exit(1)
        print(f'🔀 Port {port} is in use, auto-assigned port {new_port}')
        port = new_port

    if daemon:
        # 后台守护模式：fork 子进程启动服务
        import subprocess as _sp
        hs_entry = os.path.join(os.path.dirname(__file__), '__main__.py')
        cmd = [sys.executable, hs_entry, 'dashboard', '-p', str(port)]
        # 将守护进程的输出重定向到日志文件
        os.makedirs(LOG_DIR, exist_ok=True)
        dashboard_log = os.path.join(LOG_DIR, 'dashboard.log')
        log_fh = open(dashboard_log, 'a', buffering=1)
        proc = _sp.Popen(
            cmd,
            stdout=log_fh,
            stderr=_sp.STDOUT,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
        )
        # 写入启动日志
        log_fh.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] hs dashboard started (PID: {proc.pid}) → http://127.0.0.1:{port}\n')
        log_fh.flush()
        # 注册 managed 条目
        mreg.add(name='dashboard', type_='http', port=port, pid=proc.pid)
        print(f'📊 hs dashboard (daemon) -> http://127.0.0.1:{port}  (PID: {proc.pid})')
        print(f'    📋 Log: {format_path(dashboard_log)}')
        if open_browser:
            time.sleep(0.5)
            webbrowser.open(f'http://127.0.0.1:{port}')
            print('🌐 Browser opened')
        print(f'⏹ Use hs kill {port} or kill {proc.pid} to stop')
        return

    # ── 前台模式 ──
    DashboardHandler.manager = manager
    server = HTTPServer(('127.0.0.1', port), DashboardHandler)
    url = f'http://127.0.0.1:{port}'

    # 注册 managed
    mreg.add(name='dashboard', type_='http', port=port, pid=os.getpid())
    print(f'📊 hs dashboard -> {url}')

    if open_browser:
        webbrowser.open(url)
        print('🌐 Browser opened')

    print('⏹ Press Ctrl+C to stop\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        mreg.remove(name='dashboard')
        print('📊 Dashboard stopped')
        server.server_close()
