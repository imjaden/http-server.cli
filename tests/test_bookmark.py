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

    def test_add_duplicate_composite_key(self):
        """组合键唯一约束：同 path 同 index_page 冲突"""
        store = BookmarkStore()
        store.add('myapp', '/Users/test/project')
        with pytest.raises(ValueError, match="path\\+index already bookmarked"):
            store.add('other', '/Users/test/project')

    def test_add_same_path_different_index(self):
        """同 path 不同 index_page 可共存（TC-01）"""
        store = BookmarkStore()
        store.add('a', '/Users/test/project', index_page='a.html')
        store.add('b', '/Users/test/project', index_page='b.html')
        assert store.get('a') is not None
        assert store.get('b') is not None
        assert len(store.list_all()) == 2

    def test_add_force_overrides_composite_key(self):
        """force=True 覆盖组合键冲突（TC-03）"""
        store = BookmarkStore()
        store.add('old', '/Users/test/project', index_page='a.html')
        store.add('new', '/Users/test/project', index_page='a.html', force=True)
        assert store.get('old') is None
        bm = store.get('new')
        assert bm is not None
        assert bm['index_page'] == 'a.html'

    def test_add_force_does_not_override_name_conflict(self):
        """force 不覆盖 name 冲突（--force 边界）"""
        store = BookmarkStore()
        store.add('myapp', '/Users/test/project-a')
        with pytest.raises(ValueError, match="already exists"):
            store.add('myapp', '/Users/test/project-b', force=True)

    def test_add_legacy_no_index_uses_null_key(self):
        """存量无 index_page 条目组合键按 (path, null)（TC-08）"""
        store = BookmarkStore()
        store.add('legacy', '/Users/test/project')
        # 新增带 index 的同 path 条目应共存
        store.add('new', '/Users/test/project', index_page='a.html')
        assert store.get('legacy') is not None
        assert store.get('new') is not None
        # 新增不带 index 的同 path 条目应冲突
        with pytest.raises(ValueError, match="path\\+index already bookmarked"):
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
        assert store.get_for_path('/Users/test/project') == ['myapp']

    def test_get_for_path_none(self):
        store = BookmarkStore()
        assert store.get_for_path('/no/match') == []

    def test_get_for_path_multiple(self):
        """同 path 多条目返回 sorted 名称列表（TC-04）"""
        store = BookmarkStore()
        store.add('b', '/Users/test/project', index_page='b.html')
        store.add('a', '/Users/test/project', index_page='a.html')
        assert store.get_for_path('/Users/test/project') == ['a', 'b']

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


class TestBookmarkUpdate:
    """BookmarkStore.update 操作"""

    def test_update_path(self):
        store = BookmarkStore()
        store.add('myapp', '/tmp/old-path')
        assert store.update('myapp', path='/tmp/new-path') is True
        bm = store.get('myapp')
        assert bm['path'] == '/tmp/new-path'

    def test_update_index(self):
        store = BookmarkStore()
        store.add('myapp', '/tmp/project', index_page='old.html')
        assert store.update('myapp', index_page='new.html') is True
        bm = store.get('myapp')
        assert bm['index_page'] == 'new.html'

    def test_update_clear_index(self):
        """传空字符串清除 index_page"""
        store = BookmarkStore()
        store.add('myapp', '/tmp/project', index_page='app.html')
        store.update('myapp', index_page='')
        bm = store.get('myapp')
        assert bm['index_page'] is None

    def test_update_nonexistent(self):
        store = BookmarkStore()
        assert store.update('nope', path='/tmp/x') is False

    def test_update_path_conflict(self):
        """更新 path 时与其他书签冲突 → ValueError"""
        store = BookmarkStore()
        store.add('a', '/tmp/project-a')
        store.add('b', '/tmp/project-b')
        with pytest.raises(ValueError, match='already bookmarked'):
            store.update('a', path='/tmp/project-b')

    def test_update_same_path_ok(self):
        """更新为同一 path 应成功（不触发唯一约束）"""
        store = BookmarkStore()
        store.add('myapp', '/tmp/project')
        assert store.update('myapp', path='/tmp/project') is True

    def test_update_partial(self):
        """仅传 path 时 index_page 保持不变"""
        store = BookmarkStore()
        store.add('myapp', '/tmp/old', index_page='keep.html')
        store.update('myapp', path='/tmp/new')
        bm = store.get('myapp')
        assert bm['path'] == '/tmp/new'
        assert bm['index_page'] == 'keep.html'

    def test_update_index_composite_key_conflict(self):
        """update 改 index_page 到已占用组合 → ValueError（TC-10）"""
        store = BookmarkStore()
        store.add('a', '/tmp/project', index_page='a.html')
        store.add('b', '/tmp/project', index_page='b.html')
        with pytest.raises(ValueError, match='already bookmarked'):
            store.update('a', index_page='b.html')

    def test_update_same_path_different_index_ok(self):
        """update 同 path 不同 index_page 不冲突（组合键语义）"""
        store = BookmarkStore()
        store.add('a', '/tmp/project', index_page='a.html')
        store.add('b', '/tmp/project', index_page='b.html')
        # a 改 path 到同 path 但 index 保持 a.html → 不冲突
        assert store.update('a', path='/tmp/project') is True
        assert store.get('a')['index_page'] == 'a.html'
