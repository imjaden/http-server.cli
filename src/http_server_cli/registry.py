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

from typing import Any, Optional

from http_server_cli.utils import REGISTRY_PATH, read_json, write_json, is_process_alive, is_port_in_use

class Registry:
    """端口 ↔ 项目注册表，变更即时持久化。"""

    def __init__(self) -> None:
        self._data: dict = read_json(REGISTRY_PATH)
        if 'servers' not in self._data:
            self._data['servers'] = []

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
        """更新指定端口的 last_access_at（请求访问时调用）"""
        for entry in self._data['servers']:
            if entry.get('port') == port:
                from http_server_cli.utils import timestamp as _ts
                entry['last_access_at'] = _ts()
                self.save()
                return

    def save(self) -> None:
        write_json(REGISTRY_PATH, self._data)

    def count(self) -> int:
        return len(self._data['servers'])
