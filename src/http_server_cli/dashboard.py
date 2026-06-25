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
)

# ── HTML 页面（内联）─────────────────────────────────────

_HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>hs dashboard</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📊</text></svg>">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0d1117; color: #c9d1d9; min-height: 100vh; padding: 24px;
    }
    .container { max-width: 1200px; margin: 0 auto; }

    /* 头部行：标题 + 统计 + 工具栏 同一行 */
    .header-row {
      display: flex; align-items: center; gap: 16px; margin-bottom: 24px;
    }
    .header-row h1 {
      font-size: 20px; font-weight: 600; white-space: nowrap;
      display: flex; align-items: center; gap: 8px;
    }
    .header-row h1 small { font-size: 13px; font-weight: 400; color: #8b949e; }

    .header-stats {
      display: flex; gap: 10px; flex: 1; justify-content: center;
    }
    .stat-pill {
      background: #161b22; border: 1px solid #30363d; border-radius: 20px;
      padding: 6px 16px; display: flex; align-items: center; gap: 6px;
      font-size: 13px;
    }
    .stat-pill .num { font-weight: 700; font-size: 16px; }
    .stat-pill .num.green { color: #3fb950; }
    .stat-pill .num.red { color: #f85149; }
    .stat-pill .num.blue { color: #58a6ff; }
    .stat-pill .label { color: #8b949e; }

    .header-toolbar { margin-left: auto; }
    .btn-danger {
      background: #21262d; color: #f85149; border: 1px solid #f85149; border-radius: 8px;
      padding: 7px 16px; cursor: pointer; font-size: 13px; transition: all 0.15s;
      display: flex; align-items: center; gap: 5px; white-space: nowrap;
    }
    .btn-danger:hover { background: #f85149; color: #fff; }
    .btn-danger:disabled { opacity: 0.4; cursor: not-allowed; }

    table {
      width: 100%; border-collapse: collapse; background: #161b22;
      border: 1px solid #30363d; border-radius: 8px; overflow: hidden;
    }
    thead { background: #21262d; }
    th {
      padding: 12px 16px; text-align: left; font-size: 12px; font-weight: 600;
      color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px;
      border-bottom: 1px solid #30363d;
    }
    td {
      padding: 12px 16px; font-size: 14px; border-bottom: 1px solid #21262d;
      vertical-align: middle;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #1c2128; }
    .url-cell { font-family: 'SF Mono', Monaco, monospace; color: #58a6ff; font-size: 13px; }
    .path-cell { font-family: 'SF Mono', Monaco, monospace; font-size: 13px; color: #c9d1d9; }
    .pid-cell { font-family: 'SF Mono', Monaco, monospace; font-size: 13px; color: #8b949e; }
    .status-badge {
      display: inline-flex; align-items: center; gap: 4px;
      padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 500;
    }
    .status-badge.alive { background: rgba(63, 185, 80, 0.15); color: #3fb950; }
    .status-badge.dead { background: rgba(248, 81, 73, 0.15); color: #f85149; }
    .stats-cell { font-family: 'SF Mono', Monaco, monospace; font-size: 12px; color: #8b949e; }
    .action-btn {
      border: none; cursor: pointer; padding: 4px 12px; border-radius: 6px;
      font-size: 13px; transition: all 0.15s;
    }
    .action-btn.stop { background: rgba(248, 81, 73, 0.15); color: #f85149; }
    .action-btn.stop:hover { background: #f85149; color: #fff; }
    .action-btn.start { background: rgba(63, 185, 80, 0.15); color: #3fb950; }
    .action-btn.start:hover { background: #3fb950; color: #fff; }
    .action-btn:disabled { opacity: 0.3; cursor: not-allowed; }

    .empty-state {
      text-align: center; padding: 60px 20px; color: #8b949e;
    }
    .empty-state p { margin-bottom: 8px; }
    .empty-state .hint { font-size: 13px; color: #484f58; }

    #toast {
      position: fixed; top: 20px; right: 20px;
      padding: 12px 20px; border-radius: 8px; font-size: 14px;
      transition: opacity 0.3s; opacity: 0; pointer-events: none;
      z-index: 999;
    }
    #toast.success { background: rgba(63, 185, 80, 0.2); border: 1px solid #3fb950; color: #3fb950; opacity: 1; }
    #toast.error { background: rgba(248, 81, 73, 0.2); border: 1px solid #f85149; color: #f85149; opacity: 1; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header-row">
      <h1>📊 hs dashboard <small>HTTP 服务管理面板</small></h1>
      <div class="header-stats" id="stats">
        <span class="stat-pill"><span class="num green" id="count-instances">—</span> <span class="label">Total Instances</span></span>
        <span class="stat-pill"><span class="num blue" id="count-ports">—</span> <span class="label">Total Ports</span></span>
        <span class="stat-pill"><span class="num orange" id="count-paths">—</span> <span class="label">Total Paths</span></span>
        <span class="stat-pill"><span class="num purple" id="count-memory">—</span> <span class="label">Total Memory</span></span>
      </div>
      <div class="header-toolbar">
        <button class="btn-danger" id="btn-kill-all" onclick="killAll()">🛑 关闭全部</button>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>URL (Port)</th>
          <th>路径</th>
          <th>PID</th>
          <th>状态</th>
          <th>CPU</th>
          <th>内存</th>
          <th>启动时间</th>
          <th>最新访问</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody id="servers-tbody">
        <tr><td colspan="7" class="empty-state">
          <p>加载中...</p>
          <p class="hint">正在获取服务列表</p>
        </td></tr>
      </tbody>
    </table>
  </div>

  <div id="toast"></div>

  <script>
    function showToast(msg, type) {
      var t = document.getElementById('toast');
      t.textContent = msg; t.className = type;
      setTimeout(function(){ t.className = ''; }, 3000);
    }

    function fetchAPI(url, method, cb) {
      fetch(url, { method: method || 'GET' })
        .then(function(r){ return r.json(); })
        .then(function(d){ cb(null, d); })
        .catch(function(e){ cb(e, null); });
    }

    function render(servers, managed) {
      var tbody = document.getElementById('servers-tbody');
      var alive = 0, dead = 0;
      servers.forEach(function(s){ if (s.alive) alive++; else dead++; });

      document.getElementById('count-alive').textContent = alive;
      document.getElementById('count-dead').textContent = dead;
      document.getElementById('count-total').textContent = servers.length + managed.length;

      var html = '';

      // Managed services section
      if (managed.length > 0) {
        html += '<tr class="managed-header"><td colspan="7">🔧 基础设施服务</td></tr>';
        managed.forEach(function(s) {
          var isAlive = s._alive;
          var stats = s.stats || {};
          var cpu = '—';
          var mem = '—';
          html += '<tr>' +
            '<td class="url-cell"> http://localhost:' + s.port + '</td>' +
            '<td class="path-cell">' + esc(s.name) + (s.transport ? ' (' + s.transport + ')' : '') + '</td>' +
            '<td class="pid-cell">' + (s.pid || '-') + '</td>' +
            '<td><span class="status-badge ' + (isAlive ? 'alive' : 'dead') + '">' + (isAlive ? '🟢' : '🔴') + ' ' + (isAlive ? '运行中' : '已停止') + '</span></td>' +
            '<td class="stats-cell">' + cpu + '</td>' +
            '<td class="stats-cell">' + mem + '</td>' +
            '<td>—</td></tr>';
        });
      }

      if (servers.length === 0 && managed.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">' +
          '<p>没有正在运行的 HTTP 服务</p>' +
          '<p class="hint">使用 <code>hs . -o</code> 启动一个服务</p></td></tr>';
        return;
      }

      // User services
      var totalMemory = 0;
      servers.forEach(function(s) {
        var isAlive = s.alive;
        var statusClass = isAlive ? 'alive' : 'dead';
        var statusIcon = isAlive ? '🟢' : '🔴';
        var statusText = isAlive ? '运行中' : '已停止';
        var stats = s.stats || {};
        var cpu = stats.cpu || '-';
        var mem = stats.memory || '-';
        var memoryNum = parseFloat(stats.memory_num) || 0;
        if (isAlive) totalMemory += memoryNum;
        var started = s.started_at ? s.started_at.slice(0, 19).replace('T', ' ') : '-';
        var lastAccess = s.last_access_at ? s.last_access_at.slice(0, 19).replace('T', ' ') : '-';
        var btnClass = isAlive ? 'stop' : 'start';
        var btnIcon = isAlive ? '⏹' : '▶';
        var btnText = isAlive ? '关闭' : '启动';
        var btnDisabled = '';
        var btnAction = isAlive ? "confirmClose(" + s.port + ")" : '';

        html += '<tr>' +
          '<td class="url-cell"><a href="http://localhost:' + s.port + '" target="_blank">http://localhost:' + s.port + '</a></td>' +
          '<td class="path-cell">' + esc(s.path_display || s.path) + '</td>' +
          '<td class="pid-cell">' + (s.pid || '-') + '</td>' +
          '<td><span class="status-badge ' + statusClass + '">' + statusIcon + ' ' + statusText + '</span></td>' +
          '<td class="stats-cell">' + cpu + '</td>' +
          '<td class="stats-cell">' + mem + '</td>' +
          '<td class="time-cell">' + started + '</td>' +
          '<td class="time-cell">' + lastAccess + '</td>' +
          '<td><button class="action-btn ' + btnClass + '" ' + btnDisabled +
          ' onclick="' + btnAction + '">' + btnIcon + ' ' + btnText + '</button></td>' +
          '</tr>';
      });
      tbody.innerHTML = html;

      // Update stats cards
      var paths = [...new Set(servers.map(function(s) { return s.path; }))];
      var ports = servers.filter(function(s) { return s.alive; }).length;
      document.getElementById('count-instances').textContent = servers.length;
      document.getElementById('count-ports').textContent = ports;
      document.getElementById('count-paths').textContent = paths.length;
      document.getElementById('count-memory').textContent = totalMemory.toFixed(1) + ' MB';
    }

    function esc(s) {
      var d = document.createElement('div');
      d.appendChild(document.createTextNode(s || ''));
      return d.innerHTML;
    }

    function loadServers() {
      fetchAPI('/api/servers', 'GET', function(err, data) {
        if (err) { showToast('获取服务列表失败', 'error'); return; }
        var servers = (data.data && data.data.servers) || [];
        var managed = (data.data && data.data.managed) || [];
        render(servers, managed);
      });
    }

    function confirmClose(port) {
      fetchAPI('/api/status/' + port, 'GET', function(err, data) {
        if (err || !data.success) { showToast('获取服务信息失败', 'error'); return; }
        var info = data.data || {};
        var msg = '确定关闭此服务？\n\n'
          + '端口: ' + info.port + '\n'
          + '路径: ' + (info.path || '-') + '\n'
          + 'PID: ' + (info.pid || '-') + '\n'
          + '内存: ' + (info.stats ? (info.stats.memory || '-') : '-') + '\n'
          + '启动时间: ' + (info.started_at ? info.started_at.slice(0, 19) : '-');
        if (confirm(msg)) {
          killServer(port);
        }
      });
    }

    function killServer(port) {
      var btn = event && event.target;
      if (btn) btn.disabled = true;
      fetchAPI('/api/kill/' + port, 'POST', function(err, data) {
        if (btn) btn.disabled = false;
        if (err || !data.success) { showToast('关闭端口 ' + port + ' 失败', 'error'); return; }
        showToast('端口 ' + port + ' 已关闭', 'success');
        loadServers();
      });
    }

    function killAll() {
      if (!confirm('确定关闭所有 HTTP 服务？')) return;
      var btn = document.getElementById('btn-kill-all');
      btn.disabled = true;
      fetchAPI('/api/kill-all', 'POST', function(err, data) {
        btn.disabled = false;
        if (err || !data.success) { showToast('关闭全部失败', 'error'); return; }
        showToast('所有服务已关闭', 'success');
        loadServers();
      });
    }

    loadServers();
    setInterval(loadServers, 5000);
  </script>
</body>
</html>"""

# ── HTTP Handler ────────────────────────────────────────

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
            self._html(_HTML_PAGE)
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
