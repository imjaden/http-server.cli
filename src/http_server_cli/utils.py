# -*- coding: utf-8 -*-
"""
工具函数集：路径、端口检测、JSON I/O、进程存活检查。
所有操作基于 Python 标准库，零外部依赖。
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

HOME = os.path.expanduser('~')
# v1.1.0: 数据目录从 ~/.http-server-cli 迁移至 ~/.http-server.cli
LEGACY_DATA_DIR = os.path.join(HOME, '.http-server-cli')
DATA_DIR = os.path.join(HOME, '.http-server.cli')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
REGISTRY_PATH = os.path.join(DATA_DIR, 'registry.json')
HISTORY_PATH = os.path.join(DATA_DIR, 'history.json')
BOOKMARKS_PATH = os.path.join(DATA_DIR, 'bookmarks.json')
SERVICES_PATH = os.path.join(DATA_DIR, 'services.json')
LOG_DIR = os.path.join(DATA_DIR, 'logs')
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_PORT = 10000

# ── 打印 ────────────────────────────────────────────────

def eprint(msg: str, emoji: str = '') -> None:
    """智能打印，自动匹配 Emoji 前缀"""
    if emoji:
        print(f'{emoji} {msg}')
    else:
        print(msg)

def format_path(path: str) -> str:
    """路径格式化：HOME 替换为 ~"""
    if not isinstance(path, str):
        path = str(path)
    return path.replace(HOME, '~')

# ── 存储 ────────────────────────────────────────────────

def _migrate_legacy_data() -> None:
    """v1.1.0: 将旧数据目录 ~/.http-server-cli 迁移至 ~/.http-server.cli。

    - 新目录已存在 → 不迁移（可能是新装或已迁移过）。
    - 旧目录不存在 → 无事可做。
    - move 失败（权限/跨设备等）→ 回退复制旧目录内容到新目录，
      保留旧目录并在 stderr 提示；复制也失败 → 警告并继续（不中断）。
    """
    if not os.path.isdir(LEGACY_DATA_DIR):
        return
    if os.path.exists(DATA_DIR):
        # 新目录已存在：旧目录可能是残留，交给用户处理
        return
    try:
        os.makedirs(os.path.dirname(DATA_DIR), exist_ok=True)
        os.rename(LEGACY_DATA_DIR, DATA_DIR)
        eprint(f'Data directory migrated to {format_path(DATA_DIR)}', '🔀')
    except OSError as e:
        try:
            shutil.copytree(LEGACY_DATA_DIR, DATA_DIR)
            eprint(
                f'Data directory copied to {format_path(DATA_DIR)} '
                f'(move failed: {e}); legacy directory kept',
                '⚠️')
        except OSError as e2:
            eprint(
                f'Data directory migration failed ({e2}); '
                f'continuing with new empty directory', '⚠️')


def ensure_storage() -> None:
    """确保数据目录和初始文件存在"""
    _migrate_legacy_data()
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        from http_server_cli.config import DEFAULT_CONFIG
        write_json(CONFIG_PATH, dict(DEFAULT_CONFIG))
    if not os.path.exists(REGISTRY_PATH):
        write_json(REGISTRY_PATH, {'servers': []})
    if not os.path.exists(HISTORY_PATH):
        write_json(HISTORY_PATH, {'records': []})
    if not os.path.exists(BOOKMARKS_PATH):
        write_json(BOOKMARKS_PATH, {'bookmarks': []})
    if not os.path.exists(SERVICES_PATH):
        write_json(SERVICES_PATH, {'services': []})

def read_json(filepath: str) -> dict:
    """安全读 JSON，失败返回空 dict"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def write_json(filepath: str, data: dict) -> None:
    """原子写 JSON（write + newline + rename），防多进程并发脏读"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # 写临时文件，再原子 rename，防止写入中途崩溃留下半成品
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(filepath), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        os.replace(tmp, filepath)
    except BaseException:
        os.unlink(tmp)
        raise

# ── 端口检测 ────────────────────────────────────────────

def _listening_ports() -> Optional[set]:
    """darwin：一次性取「真实 LISTEN」端口集合；不可用返回 None（调用方回退 socket 探测）。

    失败与「无监听」必须区分：lsof 无匹配时 rc=1 且 stdout 为空 ⇒ 空集（合法结果）；
    lsof 缺失/超时/权限异常 ⇒ None ⇒ 调用方回退。
    """
    if sys.platform != 'darwin':
        return None
    try:
        result = subprocess.run(
            ['lsof', '-iTCP', '-sTCP:LISTEN', '-P', '-n'],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='ignore',
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        # 无匹配 ⇒ 空集；其余（stderr 有内容）⇒ 不可用
        return set() if not result.stdout.strip() and not result.stderr.strip() else None
    ports: set = set()
    for line in result.stdout.strip().split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 9:
            name = parts[8]
            if ':' in name:
                port_str = name.rsplit(':', 1)[-1].rstrip(')')
                if port_str.isdigit():
                    ports.add(int(port_str))
    return ports


def is_port_in_use(port: int) -> bool:
    """检测端口是否被占用。

    macOS（darwin）主路径：以 lsof 的 **LISTEN 集合**为准（`_listening_ports()`）。
    原因（HTTP-SERVER-CL004 实施实测）：BSD/macOS 的 `SO_REUSEADDR` 允许「不同本地地址
    同端口」共存——wildcard 监听时 bind('127.0.0.1', port) 仍会成功，反之亦然——故纯
    socket 探测会漏判「绑定地址与探测地址不同」的真实监听者（实测见设计 §13 偏差表）。
    lsof LISTEN 只反映真实监听者，天然不受 TIME_WAIT 残留影响（O1 根因）。

    回退路径（非 darwin 或 lsof 不可用）：socket 探测，同时覆盖 IPv4 与 IPv6，
    并开启 SO_REUSEADDR 使残留态端口（TIME_WAIT / FIN_WAIT_2）不再被误判为占用。
    对**同一地址上另一进程正在 LISTEN** 的端口，两族探测均会返回 EADDRINUSE（真占用不放宽）。
    """
    listening = _listening_ports()
    if listening is not None:
        return port in listening
    import socket
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.settimeout(0.5)
                s.bind(('', port))
        except OSError:
            return True
    return False

def get_all_occupied_ports() -> set:
    """一次性获取所有 LISTEN 状态的端口号（darwin 用 lsof；不可用/其他平台返回空集）

    macOS:  调用 lsof 快速批量获取（100ms 级）
    其他平台: 回退到空集（find_available_port 会逐个检测）
    """
    return _listening_ports() or set()

def find_available_port(start_port: int) -> Optional[int]:
    """从 start_port 递增查找空闲端口，MAX_PORT 封顶

    darwin 上优先用一次 lsof 快照比对（避免逐端口探测造成 N 次 lsof 调用）；
    lsof 不可用时回退逐端口 socket 探测。
    """
    occupied = _listening_ports()
    port = start_port
    while port <= MAX_PORT:
        if occupied is not None:
            if port not in occupied:
                return port
        elif not is_port_in_use(port):
            return port
        port += 1
    return None

def get_pid_by_lsof(port: int, listen_only: bool = False) -> list:
    """通过 lsof 获取占用端口的 PID 列表（仅 macOS）

    listen_only=True 时仅取 LISTEN 状态的监听进程（追加 -sTCP:LISTEN），
    用于监听者归属判定（HTTP-SERVER-CL004 D11）；默认 False 保持既有行为不变。
    """
    if sys.platform != 'darwin':
        return []
    cmd = ['lsof', '-i', f':{port}', '-P', '-n']
    if listen_only:
        cmd += ['-sTCP:LISTEN']
    cmd += ['-F', 'p']
    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        encoding='utf-8', errors='ignore',
    )
    if result.returncode != 0:
        return []
    pids = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if line.startswith('p'):
            try:
                pids.append(int(line[1:]))
            except ValueError:
                pass
    return pids

# ── 进程 ────────────────────────────────────────────────

def is_process_alive(pid):
    """信号 0 检测 PID 是否存活"""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def get_process_info(pid: int) -> Optional[dict]:
    """获取进程的用户和完整命令行（用于非本工具服务诊断）"""
    if not pid or not is_process_alive(pid):
        return None
    try:
        result = subprocess.run(
            ['ps', '-p', str(pid), '-o', 'user=,args='],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='ignore',
        )
        if result.returncode == 0:
            line = result.stdout.strip()
            if ' ' in line:
                user, cmd = line.split(' ', 1)
                return {'user': user.strip(), 'command': cmd.strip()}
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
        pass
    return None


def get_process_stats(pid) -> dict:
    """获取进程资源使用情况（CPU、内存）"""
    if not pid or not is_process_alive(pid):
        return {'cpu': '-', 'memory': '-', 'memory_percent': '-'}
    
    try:
        result = subprocess.run(
            ['ps', '-p', str(pid), '-o', 'pcpu,pmem,rss'],
            capture_output=True, text=True,
            encoding='utf-8', errors='ignore',
        )
        if result.returncode != 0:
            return {'cpu': '-', 'memory': '-', 'memory_percent': '-'}
        
        lines = result.stdout.strip().split('\n')
        if len(lines) < 2:
            return {'cpu': '-', 'memory': '-', 'memory_percent': '-'}
        
        # 解析输出: CPU%, MEM%, RSS
        parts = lines[1].strip().split()
        if len(parts) >= 3:
            cpu = parts[0]
            mem_percent = parts[1]
            rss_kb = int(parts[2])
            # 转换 RSS 为 MB
            rss_mb = rss_kb / 1024
            return {
                'cpu': f'{cpu}%',
                'memory': f'{rss_mb:.1f}MB',
                'memory_percent': f'{mem_percent}%',
            }
    except (ValueError, subprocess.SubprocessError):
        pass
    
    return {'cpu': '-', 'memory': '-', 'memory_percent': '-'}

# ── URL 探测 ────────────────────────────────────────────

def url_reachable(url: str, timeout: float = 1.0) -> bool:
    """探测 URL 是否可达（HTTP GET 成功且状态 < 500）。零依赖 urllib。"""
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


def wait_url_reachable(url: str, retries: int = 10, delay: float = 0.3) -> bool:
    """启动后等待 URL 就绪。返回最终是否可达（超时返回 False）。"""
    import time
    for _ in range(retries):
        if url_reachable(url):
            return True
        time.sleep(delay)
    return url_reachable(url)


# ── 路径 / 时间 ─────────────────────────────────────────

def resolve_path(path_str: str) -> str:
    """解析路径为绝对路径（展开 ~ 并解析符号链接）"""
    return str(Path(path_str).expanduser().resolve())

def timestamp() -> str:
    """当前 ISO 时间戳（到秒）"""
    return datetime.now().isoformat(timespec='seconds')

def format_duration(started_at: str) -> str:
    """计算并格式化运行时长
    
    Args:
        started_at: 启动时间，格式如 "2026-06-20T00:05:37" 或 "2026-06-20 00:05:37"
    
    Returns:
        时长字符串，如 "5 分钟"
    """
    if not started_at or started_at == '-':
        return '-'
    
    try:
        # 尝试解析 ISO 格式或空格分隔格式
        if 'T' in started_at:
            start_time = datetime.fromisoformat(started_at)
        else:
            start_time = datetime.strptime(started_at, '%Y-%m-%d %H:%M:%S')
        
        duration = datetime.now() - start_time
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 60:
            return '1分钟'
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f'{minutes}分钟'
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if minutes > 0:
                return f'{hours}小时{minutes}分钟'
            return f'{hours}小时'
    except (ValueError, TypeError):
        return '-'

# ── JSON 输出 ────────────────────────────────────────────

def json_output(success: bool, command: str, data: Any = None, error: Optional[str] = None) -> None:
    """统一 JSON 信封输出，供 API / MCP 消费者解析。

    Args:
        success: 操作是否成功
        command: 命令名（start/list/status/kill/kill-all/config/set/version）
        data: 业务数据 payload
        error: 失败时的错误描述，成功时为 None
    """
    import json
    payload = {
        'success': success,
        'command': command,
        'data': data,
        'error': error,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def which_python():
    """当前 Python 解释器路径"""
    return sys.executable
