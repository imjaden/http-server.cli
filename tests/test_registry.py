# -*- coding: utf-8 -*-
"""
Registry 模块测试 — OpenSpec: reg-01 ~ reg-03
"""

import json
import os

import pytest

from http_server_cli.registry import Registry
import http_server_cli.utils as hs_utils

def _registry_path():
    return hs_utils.REGISTRY_PATH

pytestmark = pytest.mark.spec("registry")

class TestRegistryBasics:
    """reg-01: 写入与持久化"""

    def test_empty_registry(self, fresh_registry):
        assert fresh_registry.count() == 0
        assert fresh_registry.all() == []

    def test_add_entry(self, fresh_registry):
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345, domain='localhost')
        assert fresh_registry.count() == 1
        entry = fresh_registry.find(port=8080)
        assert entry['path'] == '/tmp/foo'
        assert entry['pid'] == 12345
        assert entry['domain'] == 'localhost'
        assert entry['daemon'] is False

    def test_add_entry_daemon_true(self, fresh_registry):
        """daemon=True 的条目应记录 daemon 字段"""
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345, domain='localhost', daemon=True)
        entry = fresh_registry.find(port=8080)
        assert entry['daemon'] is True

    def test_add_without_domain(self, fresh_registry):
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345)
        entry = fresh_registry.find(port=8080)
        assert entry['domain'] == 'localhost'
        assert entry['daemon'] is False

    def test_find_by_path(self, fresh_registry):
        fresh_registry.add(port=8081, path='/tmp/alpha', pid=10001)
        entry = fresh_registry.find(path='/tmp/alpha')
        assert entry['port'] == 8081

    def test_remove_by_port(self, fresh_registry):
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345)
        fresh_registry.remove(port=8080)
        assert fresh_registry.count() == 0

    def test_remove_by_path(self, fresh_registry):
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345)
        fresh_registry.remove(path='/tmp/foo')
        assert fresh_registry.count() == 0

    def test_clear(self, pre_filled_registry):
        assert pre_filled_registry.count() == 2
        pre_filled_registry.clear()
        assert pre_filled_registry.count() == 0

    def test_persist_to_disk(self, fresh_registry):
        """reg-01: add 应即时写入磁盘"""
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345)
        with open(_registry_path(), 'r') as f:
            on_disk = json.load(f)
        assert len(on_disk['servers']) == 1
        assert on_disk['servers'][0]['port'] == 8080

class TestRegistryPreFilled:

    def test_two_servers(self, pre_filled_registry):
        assert pre_filled_registry.count() == 2
        ports = {e['port'] for e in pre_filled_registry.all()}
        assert ports == {8081, 8082}

    def test_find_existing(self, pre_filled_registry):
        e = pre_filled_registry.find(port=8081)
        assert e['path'] == '/tmp/project-alpha'

    def test_find_nonexistent(self, pre_filled_registry):
        assert pre_filled_registry.find(port=9999) is None

class TestRegistryCornerCases:

    def test_remove_nonexistent(self, fresh_registry):
        fresh_registry.remove(port=9999)
        assert fresh_registry.count() == 0

    def test_duplicate_entries(self, fresh_registry):
        fresh_registry.add(port=8080, path='/tmp/a', pid=1)
        fresh_registry.add(port=8080, path='/tmp/a', pid=2)
        assert fresh_registry.count() == 2

    def test_empty_registry_json(self):
        reg = Registry()
        reg.save()
        with open(_registry_path(), 'r') as f:
            data = json.load(f)
        assert data == {'servers': []}

class TestIndexPage:
    """index_page 字段存储"""

    def test_add_stores_default_index_page(self, fresh_registry):
        """未指定 index_page 时默认存 index.html"""
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345)
        entry = fresh_registry.find(port=8080)
        assert entry.get('index_page') == 'index.html'

    def test_add_stores_custom_index_page(self, fresh_registry):
        """指定 index_page 应被正确存储"""
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345, index_page='app.html')
        entry = fresh_registry.find(port=8080)
        assert entry.get('index_page') == 'app.html'

    def test_index_page_persists_to_disk(self, fresh_registry):
        """index_page 应持久化到磁盘 JSON"""
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345, index_page='dashboard.html')
        with open(_registry_path(), 'r') as f:
            on_disk = json.load(f)
        assert on_disk['servers'][0]['index_page'] == 'dashboard.html'


class TestActiveServers:
    """reg-02/03: 存活检测 + 残留清理"""

    def test_active_with_dead_pid(self, monkeypatch, pre_filled_registry):
        """PID 不存在时 _alive 应为 False"""
        monkeypatch.setattr('http_server_cli.registry.is_process_alive', lambda pid: False)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda port: False)
        active = pre_filled_registry.active_servers()
        for a in active:
            assert a['_alive'] is False

    def test_active_with_alive(self, monkeypatch, pre_filled_registry):
        """PID 存活 + 端口占用时 _alive 应为 True"""
        monkeypatch.setattr('http_server_cli.registry.is_process_alive', lambda pid: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda port: True)
        active = pre_filled_registry.active_servers()
        for a in active:
            assert a['_alive'] is True
