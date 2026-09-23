# -*- coding: utf-8 -*-
"""
服务管理核心：启动/停止/列表/状态。
"""

import os
import re
import signal
import subprocess
import sys
import time
import webbrowser
from urllib.parse import quote

from http_server_cli.config import Config
from http_server_cli.history import HistoryStore
from http_server_cli.registry import Registry
from http_server_cli.utils import (
    eprint,
    print_msg,
    format_path,
    is_port_in_use,
    find_available_port,
    is_process_alive,
    get_process_info,
    get_pid_by_lsof,
    resolve_path,
    LOG_DIR,
    MAX_PORT,
    SCRIPT_DIR,
    get_process_stats,
    format_duration,
    json_output,
    timestamp,
    acquire_start_lock,
    release_start_lock,
    lock_path,
    LOCK_POLL,
    LOCK_WAIT,
)

from typing import Optional

# ── CLI 用法错误（退出码 2） ──────────────────────────


class UsageError(Exception):
    """参数取值非法（如端口越界）——由 CLI 层转换为 exit 2（D4 / D9e）。"""


# 内置服务保留端口（D2 / D16：占用与空闲两种措辞）
RESERVED_PORTS = {8180: 'dashboard', 8181: 'mcp'}


def describe_port_occupant(registry: Registry, port: int) -> str:
    """端口占用者描述：'PID 1234 / ~/path'、'PID 1234' 或 '未知服务'（D1 / A3 文案口径）。"""
    entry = registry.find(port=port)
    if entry:
        pid, path = entry.get('pid'), entry.get('path')
        if pid and path:
            return f'PID {pid} / {format_path(path)}'
        if pid:
            return f'PID {pid}'
        if path:
            return format_path(path)
    pids = get_pid_by_lsof(port)
    if pids:
        return 'PID ' + '/'.join(str(p) for p in pids[:2])
    return '未知服务'


# ── stale 判定：启动宽限与归属校验（HTTP-SERVER-CL004 D4/D5/R-4/R-6/R-7） ──

START_GRACE_INTERVAL = 0.2   # 宽限轮询间隔（秒）
START_GRACE_ATTEMPTS = 5     # 宽限轮询次数（总上限 ≤ 1.0s）


def _is_our_runner(pid, abs_path) -> bool:
    """归属校验：进程命令行是否属于该目录的本工具 runner（防 pid 复用误杀）。

    与设计 §8 归属规则**同口径的 token 精确匹配**（F-4）：
    命令行按空白切分后，(1) 存在 token 其 basename == 'runner.py'；
    (2) 存在 token 与 abs_path **完全相等**（列表成员判定，非子串 `in`）。
    """
    info = get_process_info(pid)
    if not info:
        return False
    parts = (info.get('command') or '').split()
    return (any(os.path.basename(t) == 'runner.py' for t in parts)
            and abs_path in parts)


def _terminate_runner(pid) -> bool:
    """终止本工具服务的进程组（R-4：对齐 kill() 语义 SIGTERM → 0.5s → SIGKILL）。"""
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
        time.sleep(0.5)
        if is_process_alive(pid):
            os.killpg(pgid, signal.SIGKILL)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False

# ── index_page 校验 ──────────────────────────────────

# raw string 中 \u4e00 原样传给 re 引擎，re 支持 \uXXXX Unicode 转义
# 允许 / 用于子目录路径（如 skills-ref/hermes-skills.html）
_INDEX_RE = re.compile(r'^[a-zA-Z0-9\u4e00-\u9fff][a-zA-Z0-9\u4e00-\u9fff._/-]*$')


def _validate_index_page(name: str) -> Optional[str]:
    """校验 index_page 路径。返回错误消息或 None。

    允许: ASCII 字母数字 + 中文 + . _ - /（子目录）
    拒绝: 空字符串、绝对路径（以 / 开头）、含 .. 或 \\
    """
    if not name:
        return 'index_page cannot be empty'
    if name.startswith('/'):
        return f'index_page cannot be an absolute path: {name}'
    if '..' in name or '\\' in name:
        return f'index_page contains invalid path characters: {name}'
    if not _INDEX_RE.match(name):
        return f'index_page contains invalid characters: {name}'
    return None


def _build_url(domain: str, port: int, index_page: Optional[str] = None) -> str:
    """构建完整 URL。默认 index.html 不追加后缀，其他 index_page 经 URL 编码后追加。"""
    url = f'http://{domain}:{port}'
    if index_page and index_page != 'index.html':
        url += f'/{quote(index_page, safe="/")}'
    return url


class ServerManager:
    """HTTP 服务全生命周期管理。"""

    def __init__(self) -> None:
        self.config = Config()
        self.registry = Registry()

    # ── start ──────────────────────────────────────────

    def start(self, path: Optional[str] = None, open_browser: bool = False,
              daemon: bool = False, foreground: bool = False, json: bool = False,
              url_only: bool = False, index_page: Optional[str] = None,
              port: Optional[int] = None) -> Optional[bool]:
        """
        启动 HTTP 服务。

        返回值契约（D14）：True = 成功（含幂等命中 / JSON / URL / daemon 各模式）；
                            False = 运行期失败（CLI 层据此 exit 1）；端口越界抛 UsageError（CLI 层 exit 2）。

        执行顺序链（CL003 §4.1：顺序即语义，不可重排）：
        1. 路径存在性检查 → 不存在即失败
        2. registry 中该路径是否已注册且存活 → 是则幂等返回既有端口（忽略 port 参数）
        3. port 参数校验：区间(1024-65535) → 保留端口(8180/8181) → 占用（fail-closed，不漂移）
           未给 port 时保持 config.port 递增查找
        4. 启动 python3 -m http.server 后台进程
        5. 写入 registry / history
        6. 可选打开浏览器
        7. daemon 模式：前台 tail -f 日志，Ctrl+C 仅停止日志查看
        8. foreground 模式：前台运行服务，Ctrl+C 终止服务进程
        """
        abs_path, index_page, ok = self._prepare_start_target(
            path, index_page, json, url_only)
        if not ok:
            return False

        # ── 启动锁（CL005 D3）：目录级互斥，防同目录并发启动残留孤儿 runner ──
        #    放置：路径/index 校验之后、registry.find（幂等判定）之前 —— 用法错误优先于锁
        state, holder, lockfile = acquire_start_lock(abs_path)
        if state != 'hit':
            outcome = self._await_start_lock(abs_path)
            if outcome != 'timeout':
                # 刷新自身快照（同上）：重试获取成功后的幂等判定、以及 'ready' 快径都要看到他人刚写入的条目
                self.registry = Registry()
                state, holder, lockfile = acquire_start_lock(abs_path)
            if state == 'hit':
                pass
            elif outcome == 'ready':
                # 另一实例已就绪且仍持锁（--daemon tail / foreground）⇒ 只读幂等快径，rc=0
                return self._start_locked(abs_path, index_page, open_browser, daemon,
                                          foreground, json, url_only, port,
                                          idempotent_only=True)
            else:
                # 超时/重试仍被占：先做 `-p` 纯语法校验（用法错误优先于「正在启动」，F-1③）
                if port is not None and (port < 1024 or port > 65535):
                    msg = 'Port must be between 1024-65535'
                    if json:
                        json_output(False, 'start', error=msg)
                    else:
                        eprint(msg, '❌')
                    raise UsageError(msg)
                holder_pid = (holder or {}).get('pid')
                where = f'（pid {holder_pid}）' if holder_pid else ''
                eprint(f'另一实例正在启动{where}，请稍后重试或先 hs kill {format_path(abs_path)}', '⚠️')
                return False

        try:
            return self._start_locked(abs_path, index_page, open_browser, daemon,
                                      foreground, json, url_only, port)
        finally:
            release_start_lock(lockfile)

    def _await_start_lock(self, abs_path: str) -> str:
        """有效锁期间的等待路径（CL005 D3.4）。

        返回 'ready'（另一实例已就绪）/ 'released'（锁已释放 ⇒ 上层重试整链）/ 'timeout'。
        就绪判据与顺序链第 2 步①同口径：登记 pid 存活 **且** 端口已监听。
        """
        deadline = time.time() + LOCK_WAIT
        while time.time() < deadline:
            # 必须新建实例：Registry 的 `_data` 是构造期快照（P2 mtime 缓存），
            # 比他人登记更早创建的实例永远看不到新条目 ⇒ 等待路径会误判「未就绪」。
            entry = Registry().find(path=abs_path)
            if entry and is_process_alive(entry.get('pid')) and is_port_in_use(entry.get('port')):
                return 'ready'
            if not os.path.exists(lock_path(abs_path)):
                return 'released'
            time.sleep(LOCK_POLL)
        return 'timeout'

    def _prepare_start_target(self, path, index_page, json, url_only):
        """路径归一 + index_page 校验 + 目录存在性校验（CL005 D3.2：锁之前的用法校验面）。

        返回 (abs_path, index_page, ok)；ok=False 时已按 url/json/默认三态输出错误。
        注意：html 文件路径在此已归一到其父目录（⇒ 与目录入口共用同一把锁，F-1①）。
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

        # ── 校验 index_page（L0） ──
        if index_page:
            err = _validate_index_page(index_page)
            if err:
                if url_only:
                    print(f'❌ {err}', file=sys.stderr)
                    return abs_path, index_page, False
                elif json:
                    json_output(False, 'start', error=err)
                else:
                    eprint(err, '❌')
                return abs_path, index_page, False

        if not os.path.isdir(abs_path):
            if url_only:
                print(f'❌ Path does not exist or is not a directory: {format_path(abs_path)}', file=sys.stderr)
                return abs_path, index_page, False
            elif json:
                json_output(False, 'start', error=f'Path does not exist or is not a directory: {format_path(abs_path)}')
            else:
                eprint(f'Path does not exist or is not a directory: {format_path(abs_path)}', '❌')
            return abs_path, index_page, False

        return abs_path, index_page, True

    def _start_locked(self, abs_path: str, index_page, open_browser: bool, daemon: bool,
                      foreground: bool, json: bool, url_only: bool, port,
                      idempotent_only: bool = False):
        """临界区主体（CL005 D3.5）：持锁执行 —— 幂等判定 / -p 校验 / 启动 / 登记 / 信息块 /
        daemon tail / foreground 长阻塞；`finally` 由 `start()` 负责释放锁。

        idempotent_only=True 时仅走只读幂等快径（等待路径命中「另一实例已就绪」时使用）。
        """

        domain = self.config.domain
        # CLI -p/--port 优先（一次性生效，不回写 config.json；D3）
        requested_port = port
        default_port = port if port is not None else self.config.port
        # ── 检查是否已注册且存活 ──
        entry = self.registry.find(path=abs_path)
        if entry is None and idempotent_only:
            return False   # CL005 D3.4① 幂等快径：本调用未持锁，不在此启动
        if entry:
            port = entry['port']
            entry_pid = entry.get('pid')
            ready = False
            others_own_port = False

            # ① 幂等判定（零等待，顺序链第 2 步；CL003 F-1 语义不回退）
            if is_process_alive(entry_pid) and is_port_in_use(port):
                ready = True
            # ② 「启动中」宽限（D4/D5）：pid 活但端口尚未监听 → 轮询 ≤1.0s
            elif is_process_alive(entry_pid):
                for _ in range(START_GRACE_ATTEMPTS):
                    if not is_process_alive(entry_pid):
                        break
                    if is_port_in_use(port):
                        listeners = get_pid_by_lsof(port, listen_only=True)
                        if (not listeners) or entry_pid in listeners:
                            ready = True
                        else:
                            others_own_port = True   # R-7：端口被他人占用
                        break
                    time.sleep(START_GRACE_INTERVAL)
                # R-5：宽限结束、kill 之前再判一次（防慢绑定刚就绪的 runner 被误杀）
                if (not ready and not others_own_port
                        and is_process_alive(entry_pid) and is_port_in_use(port)):
                    listeners = get_pid_by_lsof(port, listen_only=True)
                    if (not listeners) or entry_pid in listeners:
                        ready = True
                    else:
                        others_own_port = True

            if ready:
                # 幂等优先（D5）：命中即返回既有端口，-p 被忽略（顺序链第 2 步先于第 3 步校验）
                if requested_port is not None and requested_port != port:
                    print(f'ℹ️ 已运行在 {port}（-p {requested_port} 未生效；如需换端口请先 hs kill {port}）',
                          file=sys.stderr)
                started_at = entry.get('started_at', '-')
                duration = format_duration(started_at)
                stats = get_process_stats(entry.get('pid'))
                log_path = os.path.join(LOG_DIR, f'{port}.log')
                
                if url_only:
                    url = _build_url(domain, port, index_page or entry.get('index_page'))
                    print(url)
                    if open_browser:
                        webbrowser.open(url)
                    return True
                elif json:
                    url = f'http://{domain}:{port}'
                    if index_page:
                        url += f'/{index_page}'
                    json_output(True, 'start', data={
                        'url': url,
                        'port': port,
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
                return True

            elif idempotent_only:
                return False   # CL005 D3.4① 幂等快径：未就绪且未持锁 ⇒ 不清理、不启动
            else:
                # ③ stale 清理（D4/AUD-3）：进程已死 → 仅删登记；进程仍活（宽限后仍未监听）→
                #    归属校验通过则**先终止进程组**再删登记，杜绝「登记已删但进程在跑」的孤儿。
                #    文案三态（url/json/默认）一律 stderr（D6），不污染 stdout / JSON 信封。
                stale_msg = 'Found stale registry entry, cleaning up before restart'
                if others_own_port:
                    stale_msg += '（端口已被其他进程占用）'
                elif is_process_alive(entry_pid):
                    if _is_our_runner(entry_pid, abs_path):
                        _terminate_runner(entry_pid)
                        stale_msg = (f'Found stale registry entry (pid {entry_pid}, 已终止), '
                                     'cleaning up before restart')
                    else:
                        stale_msg = ('Found stale registry entry, cleaning up before restart'
                                     '（登记 pid 非本工具服务，仅清理登记）')
                print(f'🔄 {stale_msg}', file=sys.stderr)
                self.registry.remove(path=abs_path)

        # ── -p/--port 校验（顺序链第 3 步：仅在第 2 步幂等未命中时执行）──
        if requested_port is not None:
            # 3a 区间（D4 / D15：直绑上限 65535；自动漂移扫描另有 MAX_PORT=10000 上限，口径不同）
            if requested_port < 1024 or requested_port > 65535:
                msg = 'Port must be between 1024-65535'
                if json:
                    json_output(False, 'start', error=msg)
                else:
                    print(f'❌ {msg}', file=sys.stderr)
                raise UsageError(msg)
            # 3b 保留端口（D2 / D16：占用态与空闲态两种措辞）
            if requested_port in RESERVED_PORTS:
                role = RESERVED_PORTS[requested_port]
                if is_port_in_use(requested_port):
                    msg = (f'{requested_port} 为内置服务保留端口（{role} 正在使用，'
                           f'{describe_port_occupant(self.registry, requested_port)}），请换端口')
                else:
                    msg = (f'{requested_port} 为内置服务保留端口（dashboard=8180 / mcp=8181），'
                           f'如需启动请用 hs dashboard -p {requested_port}')
                if json:
                    json_output(False, 'start', error=msg)
                else:
                    print(f'⚠️ {msg}', file=sys.stderr)
                return False
            # 3c 占用（D1：fail-closed，不漂移）
            if is_port_in_use(requested_port):
                msg = (f'端口 {requested_port} 已被占用'
                       f'（{describe_port_occupant(self.registry, requested_port)}）')
                if json:
                    json_output(False, 'start', error=msg)
                else:
                    print(f'⚠️ {msg}', file=sys.stderr)
                    print(f'    💡 换端口: hs . -p <port>；或关闭: hs kill {requested_port}', file=sys.stderr)
                return False

        # ── 查找可用端口 ──
        port = requested_port if requested_port is not None else find_available_port(default_port)
        if port is None:
            if url_only:
                print(f'❌ Ports {default_port}-{MAX_PORT} all in use, cannot start', file=sys.stderr)
                return False
            elif json:
                json_output(False, 'start', error=f'Ports {default_port}-{MAX_PORT} all in use, cannot start')
            else:
                eprint(f'Ports {default_port}-{MAX_PORT} all in use, cannot start', '❌')
            return False
        if not json and not url_only and requested_port is None and port != default_port:
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
            if url_only:
                print(f'❌ Permission denied writing log or starting process: {e}', file=sys.stderr)
                return False
            elif json:
                json_output(False, 'start', error=f'Permission denied writing log or starting process: {e}')
            else:
                eprint(f'Permission denied writing log or starting process: {e}', '❌')
            return False
        except FileNotFoundError as e:
            if url_only:
                print(f'❌ Python interpreter not found: {e}', file=sys.stderr)
                return False
            elif json:
                json_output(False, 'start', error=f'Python interpreter not found: {e}')
            else:
                eprint(f'Python interpreter not found: {e}', '❌')
            return False
        except OSError as e:
            if url_only:
                print(f'❌ System error (port/resource unavailable): {e}', file=sys.stderr)
                return False
            elif json:
                json_output(False, 'start', error=f'System error (port/resource unavailable): {e}')
            else:
                eprint(f'System error (port/resource unavailable): {e}', '❌')
            return False
        except Exception as e:
            if url_only:
                print(f'❌ Start failed: {e}', file=sys.stderr)
                return False
            elif json:
                json_output(False, 'start', error=f'Start failed: {e}')
            else:
                eprint(f'Start failed: {e}', '❌')
            return False

        # ── 注册 + 历史（CL005 D3.5：写盘失败 ⇒ 先终止本次 runner 再报错，杜绝
        #    「运行中 + 未登记 + 占端口」的孤儿；锁由 start() 的 finally 释放）──
        started_at = timestamp()
        try:
            self.registry.add(
                port=port, path=abs_path, pid=proc.pid,
                domain=domain, daemon=daemon, foreground=foreground,
                started_at=started_at, index_page=index,
            )

            # ── 写入历史记录 ──
            history = HistoryStore()
            history.add(port=port, path=abs_path, started_at=started_at,
                        domain=domain, daemon=daemon, foreground=foreground)
        except Exception as e:
            _terminate_runner(proc.pid)
            if url_only:
                print(f'❌ Registry write failed (runner terminated): {e}', file=sys.stderr)
            elif json:
                json_output(False, 'start', error=f'Registry write failed: {e}')
            else:
                eprint(f'Registry write failed (runner terminated): {e}', '❌')
            return False

        stats = get_process_stats(proc.pid)
        duration = format_duration(started_at)
        log_path_display = format_path(log_path)

        if url_only:
            url = _build_url(domain, port, index if index != 'index.html' else None)
            print(url)
            if open_browser:
                time.sleep(0.5)
                webbrowser.open(url)
            return True
        elif json:
            url = f'http://{domain}:{port}'
            if index:
                url += f'/{index}'
            json_output(True, 'start', data={
                'url': url,
                'port': port,
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
            return True  # JSON mode skips interactive behavior

        if url_only:
            return True  # URL mode skips interactive behavior

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

        return True


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
                print_msg('No running HTTP services', 'ℹ️')
                print_msg('Use hs start [path] -o to start one', '💡')
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

        print_msg(f'Total {len(servers)} HTTP services:', '📊')
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
                        print_msg(f'Port {port} not registered', 'ℹ️')
                return
        else:
            abs_path = resolve_path(arg)
            entry = self.registry.find(path=abs_path)

        if not entry:
            if json:
                json_output(True, 'status', data={'found': False})
            else:
                print_msg('No matching service found', 'ℹ️')
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
            print_msg(f'http://{ep}:{port}  ✅ running', '🔍')
        else:
            print_msg(f'http://{ep}:{port}  ❌ stopped', '🔍')

        print(f'  Path:  {format_path(entry["path"])}')
        print(f'  PID:   {pid}')
        print(f'  Process: {"alive" if alive else "exited"}')
        print(f'  Port:  {"in use" if port_active else "free"}')
        mode = '🖥 daemon' if entry.get('daemon', False) else ('⌨ foreground' if entry.get('foreground', False) else 'normal')
        print(f'  Mode:  {mode}')
        print(f'  Started:  {entry.get("started_at", "-")}')

    # ── kill ───────────────────────────────────────────

    def kill(self, arg: str, json: bool = False) -> bool:
        """Stop specified service (by port or path)

        返回值（D14）：True = 已处理（含进程已消失仅清登记）；False = 运行期失败（CLI 层据此 exit 1）。
        """
        if not arg:
            if json:
                json_output(False, 'kill', error='Please specify a port or path: kill <port|path>')
            else:
                eprint('Please specify a port or path: kill <port|path>', '⚠️')
            return False

        domain = self.config.domain

        if arg.isdigit():
            port = int(arg)
            entry = self.registry.find(port=port)
            if not entry:
                if json:
                    json_output(False, 'kill', error=f'Port {port} not registered')
                else:
                    eprint(f'Port {port} not registered', 'ℹ️')
                return False
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
                return False
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
                return False
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
        return True

    # ── kill_all ───────────────────────────────────────

    def kill_all(self, json: bool = False) -> None:
        """关闭所有已注册服务"""
        servers = self.registry.all()
        if not servers:
            if json:
                json_output(True, 'kill-all', data={'total': 0, 'killed': 0, 'entries': []})
            else:
                print_msg('No running services', 'ℹ️')
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
            print_msg(f'{count} service(s) closed', '✅')
