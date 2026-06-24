# -*- coding: utf-8 -*-
"""Tests for registry_managed module."""

import os
import tempfile

import pytest

from http_server_cli.registry_managed import ManagedRegistry


@pytest.fixture(autouse=True)
def _setup_isolated_env():
    """每个测试使用独立的文件"""
    tmpdir = tempfile.mkdtemp()
    import http_server_cli.utils as utils_mod
    import http_server_cli.registry_managed as mreg_mod
    orig = utils_mod.DATA_DIR
    utils_mod.DATA_DIR = tmpdir
    # Reset module cache
    mreg_mod.ManagedRegistry._data = {}
    yield
    utils_mod.DATA_DIR = orig


class TestManagedRegistryBasics:
    def test_empty(self):
        reg = ManagedRegistry()
        assert reg.count() == 0
        assert reg.all() == []

    def test_add_and_find_by_name(self):
        reg = ManagedRegistry()
        reg.add(name='dashboard', type_='http', port=8180, pid=10001)
        entry = reg.find(name='dashboard')
        assert entry is not None
        assert entry['port'] == 8180
        assert entry['pid'] == 10001
        assert entry['type'] == 'http'

    def test_find_by_port(self):
        reg = ManagedRegistry()
        reg.add(name='mcp', type_='sse', port=8181, pid=10002, transport='sse')
        entry = reg.find(port=8181)
        assert entry is not None
        assert entry['name'] == 'mcp'
        assert entry['transport'] == 'sse'

    def test_find_nonexistent(self):
        reg = ManagedRegistry()
        assert reg.find(name='nonexistent') is None
        assert reg.find(port=9999) is None

    def test_remove_by_name(self):
        reg = ManagedRegistry()
        reg.add(name='dashboard', type_='http', port=8180, pid=10001)
        reg.add(name='mcp', type_='sse', port=8181, pid=10002)
        assert reg.count() == 2
        reg.remove(name='dashboard')
        assert reg.count() == 1
        assert reg.find(name='mcp') is not None

    def test_remove_by_port(self):
        reg = ManagedRegistry()
        reg.add(name='dashboard', type_='http', port=8180, pid=10001)
        reg.remove(port=8180)
        assert reg.count() == 0

    def test_clear(self):
        reg = ManagedRegistry()
        reg.add(name='a', type_='http', port=8180, pid=1)
        reg.add(name='b', type_='sse', port=8181, pid=2)
        reg.clear()
        assert reg.count() == 0

    def test_add_replaces_existing(self):
        """同名 add 覆盖旧记录"""
        reg = ManagedRegistry()
        reg.add(name='dashboard', type_='http', port=8180, pid=10001)
        reg.add(name='dashboard', type_='http', port=8180, pid=20002)
        assert reg.count() == 1
        assert reg.find(name='dashboard')['pid'] == 20002

    def test_persist_to_disk(self):
        """数据持久化到文件"""
        reg1 = ManagedRegistry()
        reg1.add(name='dashboard', type_='http', port=8180, pid=10001)
        reg1.save()
        reg2 = ManagedRegistry()
        assert reg2.count() == 1
        assert reg2.find(name='dashboard')['pid'] == 10001


class TestActiveServers:
    def test_active_with_dead_pid(self):
        reg = ManagedRegistry()
        reg.add(name='dashboard', type_='http', port=29999, pid=9999999)
        servers = reg.active_servers()
        assert len(servers) == 1
        assert servers[0]['_alive'] is False

    def test_active_decorates_entries(self):
        reg = ManagedRegistry()
        reg.add(name='mcp', type_='sse', port=29998, pid=9999998, transport='sse')
        servers = reg.active_servers()
        assert '_alive' in servers[0]
        assert 'type' in servers[0]
        assert 'transport' in servers[0]
