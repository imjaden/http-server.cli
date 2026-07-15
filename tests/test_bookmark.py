# -*- coding: utf-8 -*-
"""
BookmarkStore 单元测试 — CRUD / 校验 / 损坏检测。
"""

import json
import os
import pytest

from http_server_cli.bookmark import (
    BookmarkStore, DataCorruptionError, MAX_BOOKMARK_NAME_LEN,
)
from http_server_cli.utils import BOOKMARKS_PATH


class TestBookmarkCRUD:
    """基本 CRUD 操作"""

    def test_add_and_get(self):
        store = BookmarkStore()
        store.add('myapp', '/Users/test/my-project', index_page='app.html')
        bm = store.get('myapp')
        assert bm is not None
        assert bm['name'] == 'myapp'
        assert bm['path'] == '/Users/test/my-project'
        assert bm['index_page'] == 'app.html'
        assert 'created_at' in bm

    def test_add_duplicate_name(self):
        store = BookmarkStore()
        store.add('myapp', '/Users/test/project-a')
        with pytest.raises(ValueError, match="already exists"):
            store.add('myapp', '/Users/test/project-b')

    def test_add_duplicate_path(self):
        """路径唯一约束：同一路径只能一个书签"""
        store = BookmarkStore()
        store.add('myapp', '/Users/test/project')
        with pytest.raises(ValueError, match="path already bookmarked"):
            store.add('other', '/Users/test/project')

    def test_add_with_index(self):
        store = BookmarkStore()
        store.add('docs', '/tmp/docs', index_page='guide.html')
        bm = store.get('docs')
        assert bm['index_page'] == 'guide.html'

    def test_add_without_index(self):
        store = BookmarkStore()
        store.add('simple', '/tmp/simple')
        bm = store.get('simple')
        assert bm['index_page'] is None

    def test_remove_existing(self):
        store = BookmarkStore()
        store.add('myapp', '/tmp/project')
        assert store.remove('myapp') is True
        assert store.get('myapp') is None

    def test_remove_nonexistent(self):
        store = BookmarkStore()
        assert store.remove('nope') is False

    def test_list_all_sorted(self):
        store = BookmarkStore()
        store.add('b', '/tmp/b')
        store.add('a', '/tmp/a')
        store.add('c', '/tmp/c')
        bookmarks = store.list_all()
        # 顺序: a, b, c (按 created_at)
        assert [b['name'] for b in bookmarks] == ['b', 'a', 'c']

    def test_list_all_missing_created_at(self):
        """缺 created_at 字段的记录应排在末尾（epoch 作为默认值）"""
        from http_server_cli.utils import write_json
        store = BookmarkStore()
        store.add('normal', '/tmp/normal')
        # 手动注入一条缺 created_at 的记录
        raw = store._read_all()
        raw.append({
            'name': 'old',
            'path': '/tmp/old',
            'index_page': None,
        })
        write_json(store._path, {'bookmarks': raw})

        bookmarks = store.list_all()
        assert bookmarks[-1]['name'] == 'old'

    def test_get_for_path(self):
        store = BookmarkStore()
        store.add('myapp', '/Users/test/project')
        assert store.get_for_path('/Users/test/project') == 'myapp'

    def test_get_for_path_none(self):
        store = BookmarkStore()
        assert store.get_for_path('/no/match') is None

    def test_names(self):
        store = BookmarkStore()
        store.add('a', '/tmp/a')
        store.add('b', '/tmp/b')
        assert store.names() == {'a', 'b'}


class TestBookmarkValidation:
    """名称校验"""

    def test_validate_name_valid(self):
        assert BookmarkStore.validate_name('myapp') is None
        assert BookmarkStore.validate_name('my-app') is None
        assert BookmarkStore.validate_name('my.app') is None
        assert BookmarkStore.validate_name('my_app') is None
        assert BookmarkStore.validate_name('App123') is None

    def test_validate_name_empty(self):
        err = BookmarkStore.validate_name('')
        assert 'cannot be empty' in err

    def test_validate_name_too_long(self):
        name = 'a' * (MAX_BOOKMARK_NAME_LEN + 1)
        err = BookmarkStore.validate_name(name)
        assert 'exceeds' in err

    def test_validate_name_at_limit(self):
        name = 'a' * MAX_BOOKMARK_NAME_LEN
        assert BookmarkStore.validate_name(name) is None

    def test_validate_name_special_chars(self):
        err = BookmarkStore.validate_name('my app')
        assert 'must match' in err

    def test_validate_name_starts_with_dash(self):
        err = BookmarkStore.validate_name('-myapp')
        assert 'must match' in err

    def test_validate_name_unicode(self):
        err = BookmarkStore.validate_name('中文')
        assert 'must match' in err


class TestBookmarkCorruption:
    """JSON 损坏检测"""

    def test_corrupted_json_raises(self, tmp_path):
        """损坏的 JSON 文件 → DataCorruptionError"""
        bad_path = tmp_path / 'bookmarks.json'
        bad_path.write_text('{this is not json')

        import http_server_cli.bookmark as bm_mod
        original_path = bm_mod.BOOKMARKS_PATH
        bm_mod.BOOKMARKS_PATH = str(bad_path)
        try:
            store = BookmarkStore()
            with pytest.raises(DataCorruptionError, match='corrupted'):
                store._read_all()
        finally:
            bm_mod.BOOKMARKS_PATH = original_path

    def test_empty_file_ok(self, tmp_path):
        """空文件 → 正常返回 []"""
        good_path = tmp_path / 'bookmarks.json'
        good_path.write_text('')

        import http_server_cli.bookmark as bm_mod
        original_path = bm_mod.BOOKMARKS_PATH
        bm_mod.BOOKMARKS_PATH = str(good_path)
        try:
            store = BookmarkStore()
            result = store._read_all()
            assert result == []
        finally:
            bm_mod.BOOKMARKS_PATH = original_path

    def test_corruption_prevents_add(self, tmp_path):
        """损坏文件阻止 add 操作，保护已有数据"""
        bad_path = tmp_path / 'bookmarks.json'
        bad_path.write_text('this is not json')

        import http_server_cli.bookmark as bm_mod
        original_path = bm_mod.BOOKMARKS_PATH
        bm_mod.BOOKMARKS_PATH = str(bad_path)
        try:
            store = BookmarkStore()
            with pytest.raises(DataCorruptionError):
                store.add('myapp', '/tmp/project')
        finally:
            bm_mod.BOOKMARKS_PATH = original_path


class TestBookmarkPersistence:
    """数据持久化（通过 isolate_data_dir fixture 自动隔离）"""

    def test_add_persists_to_disk(self):
        store = BookmarkStore()
        store.add('myapp', '/tmp/project')
        # 重新创建 store，数据应仍然存在
        store2 = BookmarkStore()
        assert store2.get('myapp') is not None
        assert store2.get('myapp')['path'] == '/tmp/project'

    def test_remove_persists_to_disk(self):
        store = BookmarkStore()
        store.add('myapp', '/tmp/project')
        store.remove('myapp')
        store2 = BookmarkStore()
        assert store2.get('myapp') is None
