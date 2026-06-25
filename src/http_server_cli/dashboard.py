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

_DASHBOARD_HTML = None

def _get_html() -> str:
    global _DASHBOARD_HTML
    if _DASHBOARD_HTML is None:
        html_path = os.path.join(SCRIPT_DIR, 'dashboard.html')
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                _DASHBOARD_HTML = f.read()
        except FileNotFoundError:
            _DASHBOARD_HTML = '<html><body><h1>Dashboard HTML not found</h1></body></html>'
    return _DASHBOARD_HTML


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

    # ── GET ──

    def do_GET(self) -> None:
        if self.path == '/':
            self._html(_get_html())
        elif self.path == '/api/servers':
            self._handle_get_servers()
        elif self.path.startswith('/api/status/'):
            port_str = self.path.split('/')[-1]
            if port_str.isdigit():
                self._handle_get_status(int(port_str))
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
            'duration': duration,
            'index_page': entry.get('index_page', 'index.html'),
            'stats': stats,
        }})

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
            print(f'📊  hs dashboard 已在运行')
            print(f'    🔧  http://127.0.0.1:{eport}  (PID: {epid})')
            cpu_s = stats.get('cpu', '-')
            mem_s = stats.get('memory', '-')
            print(f'    📊  时长: {duration}  |  CPU: {cpu_s}  |  内存: {mem_s}')
            if open_browser:
                webbrowser.open(f'http://127.0.0.1:{eport}')
                print('🌐  浏览器已打开')
            else:
                print(f'    💡  打开浏览器: hs dashboard -o')
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
            print(f'❌  端口 {port}-10000 已全部被占用')
            sys.exit(1)
        print(f'🔀  端口 {port} 已被占用，自动分配端口 {new_port}')
        port = new_port

    if daemon:
        # 后台守护模式：fork 子进程启动服务
        import subprocess as _sp
        hs_entry = os.path.join(os.path.dirname(__file__), '__main__.py')
        cmd = [sys.executable, hs_entry, 'dashboard', '-p', str(port)]
        proc = _sp.Popen(
            cmd,
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
        )
        # 注册 managed 条目
        mreg.add(name='dashboard', type_='http', port=port, pid=proc.pid)
        print(f'📊  hs dashboard (daemon) →  http://127.0.0.1:{port}  (PID: {proc.pid})')
        if open_browser:
            time.sleep(0.5)
            webbrowser.open(f'http://127.0.0.1:{port}')
            print('🌐  浏览器已打开')
        print(f'⏹  使用 hs kill {port} 或 kill {proc.pid} 停止')
        return

    # ── 前台模式 ──
    DashboardHandler.manager = manager
    server = HTTPServer(('127.0.0.1', port), DashboardHandler)
    url = f'http://127.0.0.1:{port}'

    # 注册 managed
    mreg.add(name='dashboard', type_='http', port=port, pid=os.getpid())
    print(f'📊  hs dashboard  →  {url}')

    if open_browser:
        webbrowser.open(url)
        print('🌐  浏览器已打开')

    print('⏹  按 Ctrl+C 停止\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        mreg.remove(name='dashboard')
        print('📊  仪表盘已停止')
        server.server_close()
