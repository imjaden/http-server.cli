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
from http_server_cli.registry import Registry
from http_server_cli.utils import (
    eprint,
    format_path,
    is_port_in_use,
    find_available_port,
    is_process_alive,
    resolve_path,
    LOG_DIR,
    MAX_PORT,
)

from typing import Optional

class ServerManager:
    """HTTP 服务全生命周期管理。"""

    def __init__(self) -> None:
        self.config = Config()
        self.registry = Registry()

    # ── start ──────────────────────────────────────────

    def start(self, path: Optional[str] = None, open_browser: bool = False,
              daemon: bool = False, foreground: bool = False) -> None:
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
            eprint(f'路径不存在或不是目录: {format_path(abs_path)}', '❌')
            return

        # ── 检查是否已注册且存活 ──
        entry = self.registry.find(path=abs_path)
        if entry:
            port = entry['port']
            if is_process_alive(entry.get('pid')) and is_port_in_use(port):
                eprint(f'服务已在运行: http://{domain}:{port}  →  {format_path(abs_path)}', 'ℹ️')
                if open_browser:
                    webbrowser.open(f'http://{domain}:{port}')
                return
            else:
                eprint('发现残留注册记录，清理后重新启动', '🔄')
                self.registry.remove(path=abs_path)

        # ── 查找可用端口 ──
        if is_port_in_use(default_port):
            port = find_available_port(default_port + 1)
            if port is None:
                eprint(f'端口 {default_port}-{MAX_PORT} 已全部被占用，无法启动', '❌')
                return
            eprint(f'端口 {default_port} 已被占用，自动分配端口 {port}', '🔀')
        else:
            port = default_port

        # ── 启动后台进程 ──
        log_path = os.path.join(LOG_DIR, f'{port}.log')
        try:
            with open(log_path, 'w') as log_f:
                proc = subprocess.Popen(
                    [sys.executable, '-m', 'http.server', str(port), '--bind', domain],
                    cwd=abs_path,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
                )
        except PermissionError as e:
            eprint(f'权限不足，无法写入日志或启动进程: {e}', '❌')
            return
        except FileNotFoundError as e:
            eprint(f'Python 解释器未找到: {e}', '❌')
            return
        except OSError as e:
            eprint(f'系统错误（端口/资源不可用）: {e}', '❌')
            return
        except Exception as e:
            eprint(f'启动失败: {e}', '❌')
            return

        # ── 注册 ──
        self.registry.add(
            port=port, path=abs_path, pid=proc.pid,
            domain=domain, daemon=daemon, foreground=foreground,
        )

        eprint(f'服务已启动: http://{domain}:{port} (PID: {proc.pid})', '✅')
        eprint(f'访问路径: {format_path(abs_path)}', '📁')
        eprint(f'日志文件: {format_path(log_path)}', '📋')

        if open_browser:
            time.sleep(0.5)
            webbrowser.open(f'http://{domain}:{port}')
            eprint('浏览器已打开', '🌐')

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

        if not servers:
            if json:
                import json as _json
                print(_json.dumps({'servers': [], 'count': 0}, ensure_ascii=False, indent=2))
            else:
                eprint('没有正在运行的 HTTP 服务', 'ℹ️')
                eprint('使用 hs start [path] -o 启动一个', '💡')
            return

        if json:
            import json as _json
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
                    }
                    for entry in servers
                ]
            }
            print(_json.dumps(data, ensure_ascii=False, indent=2))
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

            status_icon = '✅' if alive else '❌'
            status_text = '' if alive else ' (已停止)'
            mode_tag = ' 🖥' if daemon_mode else (' ⌨' if foreground_mode else '')
            print(f'  {status_icon}  http://{domain}:{port}{status_text}{mode_tag}')
            print(f'      📁  {path}')
            print(f'      🔧  PID: {pid}  |  启动时间: {started}')
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
                    import json as _json
                    print(_json.dumps({'found': False, 'port': port, 'occupied': bool(pids), 'pids': pids}, ensure_ascii=False, indent=2))
                else:
                    if pids:
                        eprint(f'端口 {port} 已被占用 (PID: {", ".join(str(p) for p in pids)})，但非本工具管理', '⚠️')
                    else:
                        eprint(f'端口 {port} 未注册', 'ℹ️')
                return
        else:
            abs_path = resolve_path(arg)
            entry = self.registry.find(path=abs_path)

        if not entry:
            if json:
                import json as _json
                print(_json.dumps({'found': False}, ensure_ascii=False, indent=2))
            else:
                eprint('未找到匹配的服务', 'ℹ️')
            return

        port = entry['port']
        pid = entry.get('pid')
        alive = is_process_alive(pid)
        port_active = is_port_in_use(port)
        ep = entry.get('domain', domain)

        if json:
            import json as _json
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
            }
            print(_json.dumps(data, ensure_ascii=False, indent=2))
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

    def kill(self, arg: str) -> None:
        """关闭指定服务（按端口或路径）"""
        if not arg:
            eprint('请指定端口或路径: kill <port|path>', '⚠️')
            return

        domain = self.config.domain

        if arg.isdigit():
            port = int(arg)
            entry = self.registry.find(port=port)
            if not entry:
                eprint(f'端口 {port} 未注册', 'ℹ️')
                return
        else:
            abs_path = resolve_path(arg)
            entry = self.registry.find(path=abs_path)
            if not entry:
                eprint(f'路径 {arg} 未注册', 'ℹ️')
                return
            port = entry['port']

        pid = entry.get('pid')
        path = format_path(entry['path'])

        if pid and is_process_alive(pid):
            try:
                # daemon 模式启动时 preexec_fn=os.setsid 创建了新进程组，
                # 使用 killpg 确保整个进程组（包括可能产生的子进程）被终止
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(0.5)
                if is_process_alive(pid):
                    eprint(f'进程组 {pgid} 未响应 SIGTERM，发送 SIGKILL', '⚠️')
                    os.killpg(pgid, signal.SIGKILL)
                eprint(f'已终止进程 PID: {pid}', '🛑')
            except ProcessLookupError:
                pass
            except PermissionError:
                eprint(f'无权限终止进程组 PID: {pid}，请手动执行 kill {pid}', '⚠️')
                return
        else:
            eprint(f'进程 {pid} 已不存在', 'ℹ️')

        self.registry.remove(port=port)
        eprint(f'服务已关闭: http://{domain}:{port}  →  {path}', '✅')

    # ── kill_all ───────────────────────────────────────

    def kill_all(self) -> None:
        """关闭所有已注册服务"""
        servers = self.registry.all()
        if not servers:
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

        eprint(f'已关闭 {count} 个服务', '✅')
