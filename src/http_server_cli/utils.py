# -*- coding: utf-8 -*-
"""
工具函数集：路径、端口检测、JSON I/O、进程存活检查。
所有操作基于 Python 标准库，零外部依赖。
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

HOME = os.path.expanduser('~')
DATA_DIR = os.path.join(HOME, '.http-server-cli')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
REGISTRY_PATH = os.path.join(DATA_DIR, 'registry.json')
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

def ensure_storage() -> None:
    """确保数据目录和初始文件存在"""
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        from http_server_cli.config import DEFAULT_CONFIG
        write_json(CONFIG_PATH, dict(DEFAULT_CONFIG))
    if not os.path.exists(REGISTRY_PATH):
        write_json(REGISTRY_PATH, {'servers': []})

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

def _check_macos() -> bool:
    """非 macOS 平台给出 pending 提示"""
    if sys.platform != 'darwin':
        print('⚠️ http-server-cli 当前仅支持 macOS（依赖 lsof 命令）')
        print('   Linux/Windows 支持开发中，欢迎贡献 PR')
        print('   https://github.com/imjaden/http-server-cli')
        return False
    return True

def is_port_in_use(port: int) -> bool:
    """用 lsof 检测端口是否被占用（仅 macOS）"""
    if not _check_macos():
        return False
    result = subprocess.run(
        ['lsof', '-i', f':{port}', '-P', '-n', '-F', 'p'],
        capture_output=True, text=True,
        encoding='utf-8', errors='ignore',
    )
    return result.returncode == 0

def get_all_occupied_ports() -> set:
    """一次性获取所有 LISTEN 状态的端口号，减少 lsof 调用次数"""
    if not _check_macos():
        return set()
    try:
        result = subprocess.run(
            ['lsof', '-iTCP', '-sTCP:LISTEN', '-P', '-n'],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='ignore',
        )
    except subprocess.TimeoutExpired:
        return set()
    if result.returncode != 0:
        return set()
    ports: set = set()
    for line in result.stdout.strip().split('\n')[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 9:
            name = parts[8]  # "127.0.0.1:8080" or "*:8080" or "[::1]:8080"
            if ':' in name:
                port_str = name.rsplit(':', 1)[-1].rstrip(')')
                if port_str.isdigit():
                    ports.add(int(port_str))
    return ports

def find_available_port(start_port: int) -> Optional[int]:
    """从 start_port 递增查找空闲端口，MAX_PORT 封顶（批量 lsof 检测）"""
    occupied = get_all_occupied_ports()
    port = start_port
    while port <= MAX_PORT:
        if port not in occupied:
            return port
        port += 1
    return None

def get_pid_by_lsof(port: int) -> list:
    """通过 lsof 获取占用端口的 PID 列表（仅 macOS）"""
    if not _check_macos():
        return []
    result = subprocess.run(
        ['lsof', '-i', f':{port}', '-P', '-n', '-F', 'p'],
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

def which_python():
    """当前 Python 解释器路径"""
    return sys.executable
