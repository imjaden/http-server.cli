# -*- coding: utf-8 -*-
"""
书签持久化存储：BookmarkStore。

用法:
    store = BookmarkStore()
    store.add('myapp', '/path/to/project', index_page='app.html')
    bm = store.get('myapp')
"""

import os
import re
from typing import Optional

from http_server_cli.utils import (
    BOOKMARKS_PATH, read_json, write_json, resolve_path, timestamp,
)

MAX_BOOKMARK_NAME_LEN = 128
_BOOKMARK_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$')


class DataCorruptionError(RuntimeError):
    """书签文件损坏异常。"""
    pass


class BookmarkStore:
    """书签持久化存储。

    存储文件: ~/.http-server-cli/bookmarks.json
    路径唯一约束: 不同 name 不可指向同一 path。
    损坏检测: 非空文件 JSON 解析失败抛出 DataCorruptionError。
    """

    def __init__(self) -> None:
        self._path = BOOKMARKS_PATH
        self._ensure_file()

    # ── 内部 I/O ──

    def _ensure_file(self) -> None:
        if not os.path.exists(self._path):
            write_json(self._path, {'bookmarks': []})

    def _read_all(self) -> list:
        """读取所有书签。损坏文件抛出 DataCorruptionError。"""
        raw = read_json(self._path)
        if not raw and os.path.getsize(self._path) > 0:
            raise DataCorruptionError(
                f'{self._path} is corrupted. '
                f'Please check the file or restore from backup.'
            )
        return raw.get('bookmarks', [])

    def _write_all(self, bookmarks: list) -> None:
        write_json(self._path, {'bookmarks': bookmarks})

    # ── 校验 ──

    @staticmethod
    def validate_name(name: str) -> Optional[str]:
        """校验书签名。返回错误消息或 None。

        >>> BookmarkStore.validate_name('myapp')
        >>> BookmarkStore.validate_name('')
        'bookmark name cannot be empty'
        """
        if not name:
            return 'bookmark name cannot be empty'
        if len(name) > MAX_BOOKMARK_NAME_LEN:
            return f'bookmark name exceeds {MAX_BOOKMARK_NAME_LEN} characters'
        if not _BOOKMARK_NAME_RE.match(name):
            return 'bookmark name must match [a-zA-Z0-9][a-zA-Z0-9._-]*'
        return None

    # ── CRUD ──

    def add(self, name: str, path: str, index_page: Optional[str] = None) -> None:
        """添加书签。

        Raises:
            ValueError: name 已存在或 path 已被其他书签绑定。
        """
        bookmarks = self._read_all()
        if any(b['name'] == name for b in bookmarks):
            raise ValueError(f"bookmark '{name}' already exists")
        if any(b['path'] == path for b in bookmarks):
            existing = next(b['name'] for b in bookmarks if b['path'] == path)
            raise ValueError(f"path already bookmarked as '{existing}'")
        bookmarks.append({
            'name': name,
            'path': path,
            'index_page': index_page,
            'created_at': timestamp(),
        })
        self._write_all(bookmarks)

    def remove(self, name: str) -> bool:
        """删除书签。返回 True 表示删除成功，False 表示未找到。"""
        bookmarks = self._read_all()
        new_list = [b for b in bookmarks if b['name'] != name]
        if len(new_list) == len(bookmarks):
            return False
        self._write_all(new_list)
        return True

    def get(self, name: str) -> Optional[dict]:
        """根据名称获取书签，未找到返回 None。"""
        for b in self._read_all():
            if b['name'] == name:
                return b
        return None

    def list_all(self) -> list[dict]:
        """列出所有书签，按 created_at 排序（缺字段排末尾）。"""
        return sorted(self._read_all(),
                      key=lambda x: x.get('created_at', '9999-12-31T23:59:59'))

    def get_for_path(self, path: str) -> Optional[str]:
        """根据路径查找书签名。路径唯一约束保证最多一个匹配。"""
        for b in self._read_all():
            if b['path'] == path:
                return b['name']
        return None

    def names(self) -> set[str]:
        """返回所有书签名的集合。"""
        return {b['name'] for b in self._read_all()}
