# -*- coding: utf-8 -*-
"""
History 管理：记录所有 http-server 实例的启动/关闭历史。
持久化至 ~/.http-server-cli/history.json。
"""

import os
from typing import Any, Optional
from http_server_cli.utils import HISTORY_PATH, read_json, write_json, timestamp


class HistoryStore:
    """HTTP 实例历史记录，以项目路径为键。"""

    def __init__(self) -> None:
        self._data: dict = read_json(HISTORY_PATH)
        # 兼容旧格式：如果没有顶层键，包裹一下
        if 'records' not in self._data:
            self._data = {'records': self._data.get('records', [])}

    def records(self) -> list:
        """返回所有历史记录列表"""
        return self._data.get('records', [])

    def add(self, port: int, path: str, started_at: str, domain: str = 'localhost',
            daemon: bool = False, foreground: bool = False,
            bookmark: Optional[str] = None) -> None:
        """添加一条历史记录（服务关闭时更新 ended_at 和 memory）"""
        from http_server_cli.utils import get_process_stats
        # 先查一下是否已有同 port+path 的未结束记录
        existing = None
        for r in self._data['records']:
            if r['port'] == port and r['path'] == path and r.get('ended_at') is None:
                existing = r
                break
        if existing:
            # 已有未结束记录，更新结束信息
            stats = get_process_stats(0)  # process may be dead
            existing['ended_at'] = timestamp()
            existing['memory_mb'] = stats.get('memory_num', 0)
        else:
            # 新增记录
            stats = get_process_stats(0)
            self._data['records'].append({
                'port': port,
                'path': path,
                'started_at': started_at,
                'ended_at': None,
                'memory_mb': 0,
                'domain': domain,
                'bookmark': bookmark,
            })
        self.save()

    def close(self, port: int, path: str) -> None:
        """标记一条记录为已结束（服务关闭时调用）"""
        for r in self._data['records']:
            if r['port'] == port and r['path'] == path and r.get('ended_at') is None:
                from http_server_cli.utils import get_process_stats
                stats = get_process_stats(0)
                r['ended_at'] = timestamp()
                r['memory_mb'] = stats.get('memory_num', 0)
                self.save()
                return

    def save(self) -> None:
        write_json(HISTORY_PATH, self._data)

    def clear(self) -> None:
        self._data['records'] = []
        self.save()
