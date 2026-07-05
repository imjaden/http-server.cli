# -*- coding: utf-8 -*-
"""
服务管理核心：启动/停止/列表/状态。
"""

import os
import signal
import subprocess
import sys
import time
import webbrowser

from http_server_cli.config import Config
from http_server_cli.history import HistoryStore
from http_server_cli.registry import Registry
from http_server_cli.utils import (
    eprint,
    format_path,
    is_port_in_use,
    find_available_port,
    is_process_alive,
    get_process_info,
    resolve_path,
    LOG_DIR,
    MAX_PORT,
    SCRIPT_DIR,
    get_process_stats,
    format_duration,
    json_output,
    timestamp,
)

from typing import Optional

class ServerManager:
    """HTTP 服务全生命周期管理。"""

    def __init__(self) -> None:
        self.config = Config()
        self.registry = Registry()

    # ── start ──────────────────────────────────────────

    def start(self, path: Optional[str] = None, open_browser: bool = False,
              daemon: bool = False, foreground: bool = False, json: bool = False,
              index_page: Optional[str] = None) -> None:
        """
        启动 HTTP 服务。

        1. 检查 registry 中该路径是否已注册且存活 → 是则直接打开浏览器
        2. 从默认端口递增查找空闲端口
        3. 启动 python3 -m http.server 后台进程
        4. 写入 registry
        5. 可选打开浏览器
        6. daemon 模式：前台 tail -f 日志，Ctrl+C 仅停止日志查看
        7. foreground 模式：前台运行服务，Ctrl+C 终止服务进程
        """
        path = path or '.'
        abs_path = resolve_path(path)

        # 若传入的是 html 文件路径，提取目录 + 设 index_page
        if os.path.isfile(abs_path) and abs_path.lower().endswith(('.html', '.htm')):
            index_page = os.path.basename(abs_path)
            abs_path = os.path.dirname(abs_path)
            path = abs_path

        # 通配符解析：--index 含 * 时取最近修改的文件
        if index_page and '*' in index_page:
            import glob
            pattern = os.path.join(abs_path, index_page)
            matches = glob.glob(pattern)
            if matches:
                latest = max(matches, key=os.path.getmtime)
                index_page = os.path.relpath(latest, abs_path)

        domain = self.config.domain
        default_port = self.config.port

        if not os.path.isdir(abs_path):
            if json:
                json_output(False, 'start', error=f'Path does not exist or is not a directory: {format_path(abs_path)}')
            else:
                eprint(f'Path does not exist or is not a directory: {format_path(abs_path)}', '❌')
            return

        # ── 检查是否已注册且存活 ──
        entry = self.registry.find(path=abs_path)
        if entry:
            port = entry['port']
            if is_process_alive(entry.get('pid')) and is_port_in_use(port):
                started_at = entry.get('started_at', '-')
                duration = format_duration(started_at)
                stats = get_process_stats(entry.get('pid'))
                log_path = os.path.join(LOG_DIR, f'{port}.log')
                
                if json:
                    url = f'http://{domain}:{port}'
                    if index_page:
                        url += f'/{index_page}'
                    json_output(True, 'start', data={
                        'url': url,
                        'path': abs_path,
                        'pid': entry.get('pid'),
                        'started_at': started_at,
                        'index_page': entry.get('index_page', 'index.html'),
                        'stats': stats,
                        'duration': duration,
                    })
                else:
                    entry_index = entry.get('index_page', '')
                    url = f'http://{domain}:{port}'
                    if index_page:
                        url += f'/{index_page}'
                    elif entry_index and entry_index != 'index.html':
                        url += f'/{entry_index}'
                    print(f'✅  {url}')
                    print(f'    📁  {format_path(abs_path)}')
                    print(f'    🔧  PID: {entry.get("pid")}  |  Started: {started_at}')
                    print(f'    📊  CPU: {stats["cpu"]}  |  Memory: {stats["memory"]} ({stats["memory_percent"]}) | Duration: {duration}')
                    print(f'    📋  Log: {format_path(log_path)}')
                
                if open_browser:
                    url = f'http://{domain}:{port}'
                    if index_page:
                        url += f'/{index_page}'
                    elif entry.get('index_page') and entry.get('index_page') != 'index.html':
                        url += f'/{entry["index_page"]}'
                    webbrowser.open(url)
                return

            else:
                eprint('Found stale registry entry, cleaning up before restart', '🔄')
                self.registry.remove(path=abs_path)

        # ── 查找可用端口 ──
        port = find_available_port(default_port)
        if port is None:
            if json:
                json_output(False, 'start', error=f'Ports {default_port}-{MAX_PORT} all in use, cannot start')
            else:
                eprint(f'Ports {default_port}-{MAX_PORT} all in use, cannot start', '❌')
            return
        if not json and port != default_port:
            eprint(f'Port {default_port} in use, auto-assigned port {port}', '🔀')

        # ── 启动后台进程 ──
        log_path = os.path.join(LOG_DIR, f'{port}.log')
        runner_path = os.path.join(SCRIPT_DIR, 'runner.py')
        try:
            index = index_page or 'index.html'
            with open(log_path, 'w') as log_f:
                proc = subprocess.Popen(
                    [sys.executable, runner_path, str(port), abs_path, '--bind', domain, '--index', index],
                    cwd=abs_path,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
                )
        except PermissionError as e:
            if json:
                json_output(False, 'start', error=f'Permission denied writing log or starting process: {e}')
            else:
                eprint(f'Permission denied writing log or starting process: {e}', '❌')
            return
        except FileNotFoundError as e:
            if json:
                json_output(False, 'start', error=f'Python interpreter not found: {e}')
            else:
                eprint(f'Python interpreter not found: {e}', '❌')
            return
        except OSError as e:
            if json:
                json_output(False, 'start', error=f'System error (port/resource unavailable): {e}')
            else:
                eprint(f'System error (port/resource unavailable): {e}', '❌')
            return
        except Exception as e:
            if json:
                json_output(False, 'start', error=f'Start failed: {e}')
            else:
                eprint(f'Start failed: {e}', '❌')
            return

        # ── 注册 ──
        started_at = timestamp()
        self.registry.add(
            port=port, path=abs_path, pid=proc.pid,
            domain=domain, daemon=daemon, foreground=foreground,
            started_at=started_at, index_page=index,
        )

        # ── 写入历史记录 ──
        history = HistoryStore()
        history.add(port=port, path=abs_path, started_at=started_at,
                    domain=domain, daemon=daemon, foreground=foreground)

        stats = get_process_stats(proc.pid)
        duration = format_duration(started_at)
        log_path_display = format_path(log_path)

        if json:
            url = f'http://{domain}:{port}'
            if index:
                url += f'/{index}'
            json_output(True, 'start', data={
                'url': url,
                'path': abs_path,
                'pid': proc.pid,
                'started_at': started_at,
                'index_page': index,
                'stats': stats,
                'duration': duration,
            })
        else:
            url = f'http://{domain}:{port}'
            if index:
                url += f'/{index}'
            print(f'✅  {url}')
            print(f'    📁  {format_path(abs_path)}')
            print(f'    🔧  PID: {proc.pid}  |  Started: {started_at}')
            print(f'    📊  CPU: {stats["cpu"]}  |  Memory: {stats["memory"]} ({stats["memory_percent"]}) | Duration: {duration}')
            print(f'    📋  Log: {log_path_display}')

        if open_browser:
            time.sleep(0.5)  # wait for service to start
            url = f'http://{domain}:{port}'
            if index_page:
                url += f'/{index_page}'
            webbrowser.open(url)
            if not json:
                eprint('Browser opened', '🌐')

        if json:
            return  # JSON mode skips interactive behavior

        if daemon:
            eprint(f'Press Ctrl+C to stop log tail, service still running in background', '🔄')
            try:
                subprocess.run(['tail', '-f', log_path])
            except KeyboardInterrupt:
                print()
                eprint(f'Log tail stopped, service http://{domain}:{port} still running in background', 'ℹ️')

        if foreground:
            eprint(f'Foreground mode: press Ctrl+C to stop the service', '🔄')
            try:
                proc.wait()
            except KeyboardInterrupt:
                print()
                eprint(f'Interrupt received, stopping service...', '🛑')
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.5)
                    if is_process_alive(proc.pid):
                        os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                self.registry.remove(port=port)
                eprint(f'Service closed', '✅')

    # ── list ───────────────────────────────────────────

    def list(self, json: bool = False) -> None:
        """列出所有已注册服务及其存活状态"""
        servers = self.registry.active_servers()

        # 按端口排序
        servers = sorted(servers, key=lambda x: x['port'])

        # 只显示存活的正在运行的服务
        servers = [s for s in servers if s.get('_alive', False)]

        # 获取当前目录
        current_dir = os.getcwd()

        if not servers:
            if json:
                json_output(True, 'list', data={'servers': [], 'count': 0})
            else:
                eprint('No running HTTP services', 'ℹ️')
                eprint('Use hs start [path] -o to start one', '💡')
            return

        if json:
            data = {
                'count': len(servers),
                'servers': [
                    {
                        'url': f"http://{entry.get('domain', self.config.domain)}:{entry['port']}",
                        'port': entry['port'],
                        'path': entry['path'],
                        'pid': entry.get('pid'),
                        'domain': entry.get('domain', self.config.domain),
                        'mode': 'daemon' if entry.get('daemon') else ('foreground' if entry.get('foreground') else 'normal'),
                        'alive': entry['_alive'],
                        'started_at': entry.get('started_at'),
                        'current': entry['path'] == current_dir,
                        'index_page': entry.get('index_page', 'index.html'),
                    }
                    for entry in servers
                ]
            }
            json_output(True, 'list', data=data)
            return

        eprint(f'Total {len(servers)} HTTP services:', '📊')
        print()

        for entry in servers:
            alive = entry['_alive']
            port = entry['port']
            domain = entry.get('domain', self.config.domain)
            path = format_path(entry['path'])
            pid = entry.get('pid', '-')
            started = entry.get('started_at', '-')
            daemon_mode = entry.get('daemon', False)
            foreground_mode = entry.get('foreground', False)
            is_current = entry['path'] == current_dir

            # 当前目录服务使用 📍 标记
            if is_current:
                print(f'📍  http://{domain}:{port} （current）')
            else:
                status_icon = '✅' if alive else '❌'
                status_text = '' if alive else ' (stopped)'
                mode_tag = ' 🖥' if daemon_mode else (' ⌨' if foreground_mode else '')
                print(f'{status_icon}  http://{domain}:{port}{status_text}{mode_tag}')
            
            print(f'    📁  {path}')
            
            # 计算时长
            duration = format_duration(started)
            
            # 进程资源使用情况
            stats = get_process_stats(entry.get('pid'))
            print(f'    🔧  PID: {pid}  |  Started: {started}')
            print(f'    📊  CPU: {stats["cpu"]}  |  Memory: {stats["memory"]} ({stats["memory_percent"]}) | Duration: {duration}')
            print()

    # ── status ─────────────────────────────────────────

    def status(self, arg: Optional[str] = None, json: bool = False) -> None:
        """查询单个服务状态"""
        if not arg:
            self.list(json=json)
            return

        domain = self.config.domain

        if arg.isdigit():
            port = int(arg)
            entry = self.registry.find(port=port)
            if not entry:
                from http_server_cli.utils import get_pid_by_lsof
                pids = get_pid_by_lsof(port)
                if json:
                    info = get_process_info(max(pids)) if pids else None
                    data = {
                        'found': False, 'port': port,
                        'occupied': bool(pids), 'pids': pids,
                    }
                    if info:
                        data['process'] = info
                    json_output(True, 'status', data=data)
                else:
                    if pids:
                        pid = max(pids)
                        eprint(f'Port {port} is in use (PID: {pid}) but not managed by this tool', '⚠️')
                        info = get_process_info(pid)
                        if info:
                            print()
                            print(f'👤 USER: {info["user"]}')
                            print(f'⚙️ CMD: {info["command"]}')
                            print(f'🛑 kill: kill -KILL {pid}')
                            print()
                    else:
                        eprint(f'Port {port} not registered', 'ℹ️')
                return
        else:
            abs_path = resolve_path(arg)
            entry = self.registry.find(path=abs_path)

        if not entry:
            if json:
                json_output(True, 'status', data={'found': False})
            else:
                eprint('No matching service found', 'ℹ️')
            return

        port = entry['port']
        pid = entry.get('pid')
        alive = is_process_alive(pid)
        port_active = is_port_in_use(port)
        ep = entry.get('domain', domain)

        if json:
            duration = format_duration(entry.get('started_at', ''))
            stats = get_process_stats(pid)
            data = {
                'found': True,
                'url': f"http://{ep}:{port}",
                'port': port,
                'path': entry['path'],
                'pid': pid,
                'domain': ep,
                'alive': alive and port_active,
                'port_active': port_active,
                'mode': 'daemon' if entry.get('daemon') else ('foreground' if entry.get('foreground') else 'normal'),
                'started_at': entry.get('started_at'),
                'index_page': entry.get('index_page', 'index.html'),
                'stats': stats,
                'duration': duration,
            }
            json_output(True, 'status', data=data)
            return

        if alive and port_active:
            eprint(f'http://{ep}:{port}  ✅ running', '🔍')
        else:
            eprint(f'http://{ep}:{port}  ❌ stopped', '🔍')

        print(f'  Path:  {format_path(entry["path"])}')
        print(f'  PID:   {pid}')
        print(f'  Process: {"alive" if alive else "exited"}')
        print(f'  Port:  {"in use" if port_active else "free"}')
        mode = '🖥 daemon' if entry.get('daemon', False) else ('⌨ foreground' if entry.get('foreground', False) else 'normal')
        print(f'  Mode:  {mode}')
        print(f'  Started:  {entry.get("started_at", "-")}')

    # ── kill ───────────────────────────────────────────

    def kill(self, arg: str, json: bool = False) -> None:
        """Stop specified service (by port or path)"""
        if not arg:
            if json:
                json_output(False, 'kill', error='Please specify a port or path: kill <port|path>')
            else:
                eprint('Please specify a port or path: kill <port|path>', '⚠️')
            return

        domain = self.config.domain

        if arg.isdigit():
            port = int(arg)
            entry = self.registry.find(port=port)
            if not entry:
                if json:
                    json_output(False, 'kill', error=f'Port {port} not registered')
                else:
                    eprint(f'Port {port} not registered', 'ℹ️')
                return
        else:
            abs_path = resolve_path(arg)
            # html 文件路径 → 取其所在目录（registry 存的是目录路径）
            if os.path.isfile(abs_path) and abs_path.lower().endswith(('.html', '.htm')):
                abs_path = os.path.dirname(abs_path)
            entry = self.registry.find(path=abs_path)
            if not entry:
                if json:
                    json_output(False, 'kill', error=f'Path {arg} not registered')
                else:
                    eprint(f'Path {arg} not registered', 'ℹ️')
                return
            port = entry['port']

        pid = entry.get('pid')
        path = format_path(entry['path'])
        started_at = entry.get('started_at', '-')
        duration = format_duration(started_at)
        log_path = os.path.join(LOG_DIR, f'{port}.log')
        killed = False

        if pid and is_process_alive(pid):
            try:
                # daemon 模式启动时 preexec_fn=os.setsid 创建了新进程组，
                # 使用 killpg 确保整个进程组（包括可能产生的子进程）被终止
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(0.5)
                if is_process_alive(pid):
                    if not json:
                        eprint(f'Process group {pgid} didn\'t respond to SIGTERM, sending SIGKILL', '⚠️')
                    os.killpg(pgid, signal.SIGKILL)
                killed = True
                if json:
                    pass  # will output below
                else:
                    print(f'🛑 Terminated PID: {pid}')
                    print(f'🛑 http://{domain}:{port}')
                    print(f'    📁  {path}')
                    print(f'    🔧  Started: {started_at}  |  Duration: {duration}')
                    print(f'    📋  Log: {format_path(log_path)}')
            except ProcessLookupError:
                pass
            except PermissionError:
                if json:
                    json_output(False, 'kill', error=f'No permission to kill process group PID: {pid}, manually run kill {pid}')
                else:
                    eprint(f'No permission to kill process group PID: {pid}, manually run kill {pid}', '⚠️')
                return
        else:
            if not json:
                eprint(f'Process {pid} no longer exists', 'ℹ️')

        self.registry.remove(port=port)
        
        # ── 关闭历史记录 ──
        from http_server_cli.history import HistoryStore
        history = HistoryStore()
        history.close(port=port, path=entry['path'])
        
        # 删除日志文件
        log_removed = False
        if os.path.isfile(log_path):
            try:
                os.remove(log_path)
                log_removed = True
                if not json:
                    eprint(f'Log deleted: {format_path(log_path)}', '🗑️')
            except OSError as e:
                if not json:
                    eprint(f'Failed to delete log: {e}', '⚠️')

        if json:
            json_output(True, 'kill', data={
                'port': port,
                'path': entry['path'],
                'pid': pid,
                'killed': killed,
                'log_removed': log_removed,
            })

    # ── kill_all ───────────────────────────────────────

    def kill_all(self, json: bool = False) -> None:
        """关闭所有已注册服务"""
        servers = self.registry.all()
        if not servers:
            if json:
                json_output(True, 'kill-all', data={'total': 0, 'killed': 0, 'entries': []})
            else:
                eprint('No running services', 'ℹ️')
            return

        count = 0
        for entry in list(servers):
            pid = entry.get('pid')
            port = entry['port']
            if pid and is_process_alive(pid):
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.3)
                    if is_process_alive(pid):
                        os.killpg(pgid, signal.SIGKILL)
                    count += 1
                except (ProcessLookupError, PermissionError):
                    pass
            self.registry.remove(port=port)

        if json:
            json_output(True, 'kill-all', data={
                'total': len(servers),
                'killed': count,
                'entries': [
                    {'port': s['port'], 'path': s['path']}
                    for s in servers
                ],
            })
        else:
            eprint(f'{count} service(s) closed', '✅')
