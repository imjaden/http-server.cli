# -*- coding: utf-8 -*-
"""
Registry 管理：记录 port ↔ {path, pid, domain, started_at} 映射。

registry.json 结构：
{
  "servers": [
    {"port": 8081, "path": "/abs/path", "pid": 12345,
     "domain": "localhost", "started_at": "2026-06-17T17:30:00"}
  ]
}
"""

import os as _os
import time as _time
from typing import Any, Optional

from http_server_cli.utils import REGISTRY_PATH, read_json, write_json, is_process_alive, is_port_in_use

# ── P2: 模块级 mtime 懒加载缓存 ──────────────────────

_registry_cache: Optional[dict] = None
_registry_cache_mtime: float = 0.0


def _get_cached_data() -> dict:
    """惰性读取 registry，mtime 未变时复用缓存。"""
    global _registry_cache, _registry_cache_mtime
    try:
        mtime = _os.path.getmtime(REGISTRY_PATH)
    except OSError:
        mtime = 0.0
    if _registry_cache is not None and mtime == _registry_cache_mtime:
        return _registry_cache
    data = read_json(REGISTRY_PATH)
    if 'servers' not in data:
        data['servers'] = []
    _registry_cache = data
    _registry_cache_mtime = mtime
    return data


# ── P0: 内存级 access cache（60s 刷盘） ─────────────────

_last_access_cache: dict = {}       # {port: timestamp}
_last_flush_time: float = 0.0
_FLUSH_INTERVAL: float = 60.0       # Q1 决策: 60 秒


def _touch_memory(port: int) -> None:
    """内存级标记访问时间，不写盘。定期刷盘（60s 间隔）。"""
    global _last_flush_time
    _last_access_cache[port] = _time.time()
    if _time.time() - _last_flush_time >= _FLUSH_INTERVAL:
        _flush_access_cache()


def _flush_access_cache() -> None:
    """将缓存中的 last_access_at 批量写入 registry。"""
    global _last_flush_time
    if not _last_access_cache:
        return
    from datetime import datetime
    reg = Registry()
    for port, ts in list(_last_access_cache.items()):
        entry = reg.find(port=port)
        if entry:
            entry['last_access_at'] = datetime.fromtimestamp(ts).isoformat(
                timespec='seconds')
    reg.save()
    _last_access_cache.clear()
    _last_flush_time = _time.time()


# ── Registry 类 ─────────────────────────────────────────

class Registry:
    """端口 ↔ 项目注册表，变更即时持久化。"""

    def __init__(self) -> None:
        self._data: dict = _get_cached_data()  # P2: 走 mtime 缓存

    # ── 查询 ──

    def all(self) -> list:
        """返回所有条目（引用，修改需调用 save）"""
        return self._data['servers']

    def find(self, port: Optional[int] = None, path: Optional[str] = None) -> Optional[dict]:
        """查找条目，支持 port 或 path"""
        for entry in self._data['servers']:
            if port is not None and entry.get('port') == port:
                return entry
            if path is not None and entry.get('path') == path:
                return entry
        return None

    def active_servers(self) -> list:
        """返回存活状态装饰后的条目列表"""
        results = []
        for entry in self._data['servers']:
            pid = entry.get('pid')
            port = entry.get('port')
            alive = is_process_alive(pid)
            port_active = is_port_in_use(port) if port else False
            results.append({**entry, '_alive': alive and port_active})
        return results

    # ── 修改 ──

    def add(self, port: int, path: str, pid: int, domain: Optional[str] = None,
            started_at: Optional[str] = None, daemon: bool = False,
            foreground: bool = False, index_page: Optional[str] = None) -> None:
        """添加新条目"""
        from http_server_cli.utils import timestamp as _ts
        self._data['servers'].append({
            'port': port,
            'path': path,
            'pid': pid,
            'domain': domain or 'localhost',
            'daemon': daemon,
            'foreground': foreground,
            'started_at': started_at or _ts(),
            'last_access_at': started_at or _ts(),
            'index_page': index_page or 'index.html',
        })
        self.save()

    def remove(self, port: Optional[int] = None, path: Optional[str] = None) -> None:
        """删除匹配的条目"""
        self._data['servers'] = [
            s for s in self._data['servers']
            if not (port is not None and s.get('port') == port)
            and not (path is not None and s.get('path') == path)
        ]
        self.save()

    def clear(self) -> None:
        """清空所有条目"""
        self._data['servers'] = []
        self.save()

    def touch(self, port: int) -> None:
        """更新指定端口的 last_access_at（请求访问时调用）。

        保留此方法供 dashboard API 等非热路径调用方使用。
        handler 热路径请使用 _touch_memory()。
        """
        for entry in self._data['servers']:
            if entry.get('port') == port:
                from http_server_cli.utils import timestamp as _ts
                entry['last_access_at'] = _ts()
                self.save()
                return

    def save(self) -> None:
        """原子写 registry 并刷新模块缓存。"""
        global _registry_cache, _registry_cache_mtime
        write_json(REGISTRY_PATH, self._data)
        # P2: 写后同步刷新缓存
        _registry_cache = self._data
        try:
            _registry_cache_mtime = _os.path.getmtime(REGISTRY_PATH)
        except OSError:
            _registry_cache_mtime = 0.0

    def count(self) -> int:
        return len(self._data['servers'])
