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


# ── 选择口径（CL006/A1 + A4）：同键多记录时的「存活优先 + 最近 started_at」 ──


def select_entry(candidates: list) -> Optional[dict]:
    """从同键候选条中选一条（D1/A1 口径）。

    优先级：存活（pid 活）→ 最近 started_at → 原始顺序（首个）。
    单条候选原样返回；空候选返回 None。
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    alive = [e for e in candidates if is_process_alive(e.get('pid'))]
    pool = alive or candidates
    if len(pool) == 1:
        return pool[0]
    return max(pool, key=lambda e: e.get('started_at') or '')


def select_display_entries(entries: list, key=None) -> list:
    """按 key（默认 port）分组，每组保留一条：存活优先 → 最近 started_at（A4 展示口径）。

    entries 为 active_servers() 装饰后的条目（含 '_alive'）。保持组首次出现顺序。
    """
    if key is None:
        key = lambda e: e.get('port')
    order, groups = [], {}
    for e in entries:
        k = key(e)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(e)
    out = []
    for k in order:
        group = groups[k]
        if len(group) == 1:
            out.append(group[0])
            continue
        alive = [e for e in group if e.get('_alive')]
        pool = alive or group
        out.append(max(pool, key=lambda e: e.get('started_at') or ''))
    return out


# ── Registry 类 ─────────────────────────────────────────

class Registry:
    """端口 ↔ 项目注册表，变更即时持久化。"""

    def __init__(self) -> None:
        self._data: dict = _get_cached_data()  # P2: 走 mtime 缓存

    # ── 查询 ──

    def all(self) -> list:
        """返回所有条目（引用，修改需调用 save）"""
        return self._data['servers']

    def find(self, port: Optional[int] = None, path: Optional[str] = None,
             prefer_alive: bool = True) -> Optional[dict]:
        """查找条目，支持 port 或 path。

        同键多条（历史沉积，D1/D2）时默认按「存活优先 + 最近 started_at」选择，
        使 `hs status` / `hs kill` / 访问记账与 `hs list` 口径一致；
        ``prefer_alive=False`` 退回旧「首个命中」语义（逃生口）。
        """
        candidates = [
            e for e in self._data['servers']
            if (port is not None and e.get('port') == port)
            or (path is not None and e.get('path') == path)
        ]
        if not prefer_alive:
            return candidates[0] if candidates else None
        return select_entry(candidates)

    def stale_entries(self) -> list:
        """pid 已不存活的条目（副本）——供 prune 预览，不修改数据。"""
        return [dict(e) for e in self._data['servers']
                if not is_process_alive(e.get('pid'))]

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

    def prune_stale(self) -> list:
        """删除 pid 已不存活的沉积记录，返回被删条目的副本（A4）。

        仅动 registry.json；history.json 为独立文件，语义不受影响。
        存活记录（即使同端口重复）一律保留。
        """
        kept, removed = [], []
        for entry in self._data['servers']:
            (kept if is_process_alive(entry.get('pid')) else removed).append(entry)
        if removed:
            self._data['servers'] = kept
            self.save()
        return [dict(e) for e in removed]

    def touch(self, port: int) -> None:
        """更新指定端口的 last_access_at（请求访问时调用）。

        A2：写入**存活实例**对应记录（同端口多条时按 find 口径选择），
        不再盲写同端口首条（旧实现会把访问记账刷到陈旧沉积条上）。
        保留此方法供 dashboard API 等非热路径调用方使用。
        handler 热路径请使用 _touch_memory()。
        """
        entry = self.find(port=port)
        if entry is not None:
            from http_server_cli.utils import timestamp as _ts
            entry['last_access_at'] = _ts()
            self.save()

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
