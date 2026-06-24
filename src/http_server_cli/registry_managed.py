#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Managed Registry — 工具基础设施服务注册表。

记录 dashboard、MCP（SSE 模式）等工具自身服务的运行信息。
与 registry.json 分离存储，hs list 合并展示，kill-all 不关。
"""

import os
from typing import Any, Optional

from http_server_cli.utils import (
    is_process_alive,
    is_port_in_use,
    read_json,
    write_json,
    timestamp,
)


def _get_path() -> str:
    from http_server_cli.utils import DATA_DIR
    return os.path.join(DATA_DIR, 'registry-managed.json')

class ManagedRegistry:
    """工具基础设施服务注册表，变更即时持久化。"""

    def __init__(self) -> None:
        self._data: dict = read_json(_get_path())
        if 'services' not in self._data:
            self._data['services'] = []

    # ── 查询 ──

    def all(self) -> list:
        """返回所有条目"""
        return list(self._data['services'])

    def find(self, name: Optional[str] = None, port: Optional[int] = None) -> Optional[dict]:
        """查找条目，支持 name 或 port"""
        for entry in self._data['services']:
            if name is not None and entry.get('name') == name:
                return entry
            if port is not None and entry.get('port') == port:
                return entry
        return None

    def active_servers(self) -> list:
        """返回存活状态装饰后的条目列表"""
        results = []
        for entry in self._data['services']:
            pid = entry.get('pid')
            port = entry.get('port')
            alive = is_process_alive(pid)
            port_active = is_port_in_use(port) if port else False
            results.append({**entry, '_alive': alive and port_active})
        return results

    def count(self) -> int:
        return len(self._data['services'])

    # ── 修改 ──

    def add(self, name: str, type_: str, port: int, pid: int,
            transport: Optional[str] = None,
            started_at: Optional[str] = None) -> None:
        """添加新服务条目"""
        # 先移除同 name 的旧记录（用于重启场景）
        self.remove(name=name)
        self._data['services'].append({
            'name': name,
            'type': type_,
            'port': port,
            'pid': pid,
            'transport': transport or '',
            'started_at': started_at or timestamp(),
        })
        self.save()

    def remove(self, name: Optional[str] = None,
               port: Optional[int] = None) -> None:
        """移除匹配的条目"""
        self._data['services'] = [
            s for s in self._data['services']
            if not (name is not None and s.get('name') == name)
            and not (port is not None and s.get('port') == port)
        ]
        self.save()

    def clear(self) -> None:
        """清空所有条目"""
        self._data['services'] = []
        self.save()

    def save(self) -> None:
        write_json(_get_path(), self._data)
