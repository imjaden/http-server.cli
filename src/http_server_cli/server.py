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
        domain = self.config.domain
        default_port = self.config.port

        if not os.path.isdir(abs_path):
            if json:
                json_output(False, 'start', error=f'路径不存在或不是目录: {format_path(abs_path)}')
            else:
                eprint(f'路径不存在或不是目录: {format_path(abs_path)}', '❌')
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
                    json_output(True, 'start', data={
                        'url': f'http://{domain}:{port}',
                        'port': port,
                        'path': abs_path,
                        'pid': entry.get('pid'),
                        'domain': domain,
                        'mode': 'daemon' if entry.get('daemon') else ('foreground' if entry.get('foreground') else 'normal'),
                        'started_at': started_at,
                        'browser_opened': False,
                        'already_running': True,
                        'index_page': entry.get('index_page', 'index.html'),
                        'stats': stats,
                        'duration': duration,
                    })
                else:
                    print(f'✅  http://{domain}:{port}')
                    print(f'    📁  {format_path(abs_path)}')
                    print(f'    🔧  PID: {entry.get("pid")}  |  启动时间: {started_at}')
                    print(f'    📊  CPU: {stats["cpu"]}  |  内存: {stats["memory"]} ({stats["memory_percent"]}) | 时长: {duration}')
                    print(f'    📋  日志文件: {format_path(log_path)}')
                
                if open_browser:
                    webbrowser.open(f'http://{domain}:{port}')
                return
            else:
                eprint('发现残留注册记录，清理后重新启动', '🔄')
                self.registry.remove(path=abs_path)

        # ── 查找可用端口 ──
        port = find_available_port(default_port)
        if port is None:
            if json:
                json_output(False, 'start', error=f'端口 {default_port}-{MAX_PORT} 已全部被占用，无法启动')
            else:
                eprint(f'端口 {default_port}-{MAX_PORT} 已全部被占用，无法启动', '❌')
            return
        if not json and port != default_port:
            eprint(f'端口 {default_port} 已被占用，自动分配端口 {port}', '🔀')

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
                json_output(False, 'start', error=f'权限不足，无法写入日志或启动进程: {e}')
            else:
                eprint(f'权限不足，无法写入日志或启动进程: {e}', '❌')
            return
        except FileNotFoundError as e:
            if json:
                json_output(False, 'start', error=f'Python 解释器未找到: {e}')
            else:
                eprint(f'Python 解释器未找到: {e}', '❌')
            return
        except OSError as e:
            if json:
                json_output(False, 'start', error=f'系统错误（端口/资源不可用）: {e}')
            else:
                eprint(f'系统错误（端口/资源不可用）: {e}', '❌')
            return
        except Exception as e:
            if json:
                json_output(False, 'start', error=f'启动失败: {e}')
            else:
                eprint(f'启动失败: {e}', '❌')
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
            json_output(True, 'start', data={
                'url': f'http://{domain}:{port}',
                'port': port,
                'path': abs_path,
                'pid': proc.pid,
                'domain': domain,
                'mode': 'daemon' if daemon else ('foreground' if foreground else 'normal'),
                'started_at': started_at,
                'browser_opened': bool(open_browser),
                'already_running': False,
                'index_page': index,
                'stats': stats,
                'duration': duration,
            })
        else:
            print(f'✅  http://{domain}:{port}')
            print(f'    📁  {format_path(abs_path)}')
            print(f'    🔧  PID: {proc.pid}  |  启动时间: {started_at}')
            print(f'    📊  CPU: {stats["cpu"]}  |  内存: {stats["memory"]} ({stats["memory_percent"]}) | 时长: {duration}')
            print(f'    📋  日志文件: {log_path_display}')

        if open_browser:
            time.sleep(0.5)  # 等待服务完全启动
            webbrowser.open(f'http://{domain}:{port}')
            if not json:
                eprint('浏览器已打开', '🌐')

        if json:
            return  # JSON 模式跳过交互行为

        if daemon:
            eprint(f'按 Ctrl+C 停止日志查看，服务仍在后台运行', '🔄')
            try:
                subprocess.run(['tail', '-f', log_path])
            except KeyboardInterrupt:
                print()
                eprint(f'日志查看已停止，服务 http://{domain}:{port} 仍在后台运行', 'ℹ️')

        if foreground:
            eprint(f'前台运行模式：按 Ctrl+C 终止服务', '🔄')
            try:
                proc.wait()
            except KeyboardInterrupt:
                print()
                eprint(f'收到中断信号，正在终止服务...', '🛑')
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.5)
                    if is_process_alive(proc.pid):
                        os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                self.registry.remove(port=port)
                eprint(f'服务已关闭', '✅')

    # ── list ───────────────────────────────────────────

    def list(self, json: bool = False) -> None:
        """列出所有已注册服务及其存活状态"""
        servers = self.registry.active_servers()

        # 按端口排序
        servers = sorted(servers, key=lambda x: x['port'])

        # 获取当前目录
        current_dir = os.getcwd()

        if not servers:
            if json:
                json_output(True, 'list', data={'servers': [], 'count': 0})
            else:
                eprint('没有正在运行的 HTTP 服务', 'ℹ️')
                eprint('使用 hs start [path] -o 启动一个', '💡')
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

        eprint(f'共 {len(servers)} 个 HTTP 服务:', '📊')
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
                status_text = '' if alive else ' (已停止)'
                mode_tag = ' 🖥' if daemon_mode else (' ⌨' if foreground_mode else '')
                print(f'{status_icon}  http://{domain}:{port}{status_text}{mode_tag}')
            
            print(f'    📁  {path}')
            
            # 计算时长
            duration = format_duration(started)
            
            # 进程资源使用情况
            stats = get_process_stats(entry.get('pid'))
            print(f'    🔧  PID: {pid}  |  启动时间: {started}')
            print(f'    📊  CPU: {stats["cpu"]}  |  内存: {stats["memory"]} ({stats["memory_percent"]}) | 时长: {duration}')
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
                        eprint(f'端口 {port} 已被占用 (PID: {pid})，但非本工具管理', '⚠️')
                        info = get_process_info(pid)
                        if info:
                            print()
                            print(f'👤 USER: {info["user"]}')
                            print(f'⚙️ CMD: {info["command"]}')
                            print(f'🛑 kill: kill -KILL {pid}')
                            print()
                    else:
                        eprint(f'端口 {port} 未注册', 'ℹ️')
                return
        else:
            abs_path = resolve_path(arg)
            entry = self.registry.find(path=abs_path)

        if not entry:
            if json:
                json_output(True, 'status', data={'found': False})
            else:
                eprint('未找到匹配的服务', 'ℹ️')
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
            eprint(f'http://{ep}:{port}  ✅ 运行中', '🔍')
        else:
            eprint(f'http://{ep}:{port}  ❌ 已停止', '🔍')

        print(f'  路径:  {format_path(entry["path"])}')
        print(f'  PID:   {pid}')
        print(f'  进程:  {"存活" if alive else "已退出"}')
        print(f'  端口:  {"占用中" if port_active else "空闲"}')
        mode = '🖥 daemon' if entry.get('daemon', False) else ('⌨ foreground' if entry.get('foreground', False) else '普通')
        print(f'  模式:  {mode}')
        print(f'  启动:  {entry.get("started_at", "-")}')

    # ── kill ───────────────────────────────────────────

    def kill(self, arg: str, json: bool = False) -> None:
        """关闭指定服务（按端口或路径）"""
        if not arg:
            if json:
                json_output(False, 'kill', error='请指定端口或路径: kill <port|path>')
            else:
                eprint('请指定端口或路径: kill <port|path>', '⚠️')
            return

        domain = self.config.domain

        if arg.isdigit():
            port = int(arg)
            entry = self.registry.find(port=port)
            if not entry:
                if json:
                    json_output(False, 'kill', error=f'端口 {port} 未注册')
                else:
                    eprint(f'端口 {port} 未注册', 'ℹ️')
                return
        else:
            abs_path = resolve_path(arg)
            entry = self.registry.find(path=abs_path)
            if not entry:
                if json:
                    json_output(False, 'kill', error=f'路径 {arg} 未注册')
                else:
                    eprint(f'路径 {arg} 未注册', 'ℹ️')
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
                        eprint(f'进程组 {pgid} 未响应 SIGTERM，发送 SIGKILL', '⚠️')
                    os.killpg(pgid, signal.SIGKILL)
                killed = True
                if json:
                    pass  # will output below
                else:
                    print(f'🛑 已终止进程 PID: {pid}')
                    print(f'🛑 http://{domain}:{port}')
                    print(f'    📁  {path}')
                    print(f'    🔧  启动时间: {started_at}  |  时长: {duration}')
                    print(f'    📋  日志文件: {format_path(log_path)}')
            except ProcessLookupError:
                pass
            except PermissionError:
                if json:
                    json_output(False, 'kill', error=f'无权限终止进程组 PID: {pid}，请手动执行 kill {pid}')
                else:
                    eprint(f'无权限终止进程组 PID: {pid}，请手动执行 kill {pid}', '⚠️')
                return
        else:
            if not json:
                eprint(f'进程 {pid} 已不存在', 'ℹ️')

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
                    eprint(f'日志文件已删除: {format_path(log_path)}', '🗑️')
            except OSError as e:
                if not json:
                    eprint(f'删除日志文件失败: {e}', '⚠️')

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
                eprint('没有正在运行的服务', 'ℹ️')
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
            eprint(f'已关闭 {count} 个服务', '✅')
