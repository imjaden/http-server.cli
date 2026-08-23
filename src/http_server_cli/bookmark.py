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

    存储文件: ~/.http-server.cli/bookmarks.json
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

    def add(self, name: str, path: str, index_page: Optional[str] = None,
            force: bool = False) -> None:
        """添加书签。

        唯一键为 (path, index_page) 组合，同 path 不同 index_page 可共存。
        force=True 时覆盖组合键冲突的旧条目（不覆盖 name 冲突）。

        Raises:
            ValueError: name 已存在；或 (path, index_page) 已被其他书签绑定且未 force。
        """
        bookmarks = self._read_all()
        if any(b['name'] == name for b in bookmarks):
            raise ValueError(f"bookmark '{name}' already exists")
        # 归一化: '' 与 None 语义等价（均表示默认 index.html），统一组合键
        index_page = index_page or None
        # 组合唯一键: (path, index_page)。index_page None 表示默认 index.html
        conflict = next(
            (b for b in bookmarks
             if b['path'] == path and (b.get('index_page') or None) == index_page),
            None)
        if conflict:
            if not force:
                existing = conflict['name']
                raise ValueError(
                    f"path+index already bookmarked as '{existing}'")
            # force: 删除旧条目，替换为新条目
            bookmarks = [b for b in bookmarks
                         if not (b['path'] == path
                                 and (b.get('index_page') or None) == index_page)]
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

    def update(self, name: str, path: Optional[str] = None,
               index_page: Optional[str] = None) -> bool:
        """更新书签的 path 或 index_page。返回 True 表示成功，False 表示未找到。

        - path=None: 保持原值
        - index_page=None: 保持原值。传空字符串 '' 清除 index_page。

        冲突校验基于 (path, index_page) 组合键，不提供 --force（defer，
        先 remove + add 代替）。
        """
        bookmarks = self._read_all()
        for b in bookmarks:
            if b['name'] == name:
                new_path = path if path is not None else b['path']
                new_index = index_page if index_page is not None else b.get('index_page')
                new_index = new_index or None
                # 组合键冲突校验：目标组合是否已被其它 name 占用
                if any(b2['name'] != name
                       and b2['path'] == new_path
                       and (b2.get('index_page') or None) == new_index
                       for b2 in bookmarks):
                    existing = next(
                        b2['name'] for b2 in bookmarks
                        if b2['name'] != name
                        and b2['path'] == new_path
                        and (b2.get('index_page') or None) == new_index)
                    raise ValueError(
                        f"path+index already bookmarked as '{existing}'")
                b['path'] = new_path
                b['index_page'] = new_index
                self._write_all(bookmarks)
                return True
        return False

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

    def get_for_path(self, path: str) -> list[str]:
        """根据路径查找书签名。同 path 可有多条，返回全部名称列表（sorted）。"""
        return sorted(
            b['name'] for b in self._read_all() if b['path'] == path)

    def names(self) -> set[str]:
        """返回所有书签名的集合。"""
        return {b['name'] for b in self._read_all()}
