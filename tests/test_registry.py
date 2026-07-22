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


class TestTouchMemory:
    """P0: _touch_memory + _flush_access_cache 内存级访问时间标记"""

    def _reset_cache(self):
        """重置模块级缓存状态"""
        import time
        import http_server_cli.registry as reg_mod
        reg_mod._last_access_cache.clear()
        reg_mod._last_flush_time = time.time()  # 当前时间，防止立即触发 flush

    def test_touch_memory_stores_timestamp(self):
        """_touch_memory 应在内存中记录端口时间戳"""
        import http_server_cli.registry as reg_mod
        self._reset_cache()
        reg_mod._touch_memory(8080)
        assert 8080 in reg_mod._last_access_cache
        assert isinstance(reg_mod._last_access_cache[8080], float)

    def test_touch_memory_multiple_ports(self):
        """_touch_memory 应支持多端口独立记录"""
        import http_server_cli.registry as reg_mod
        self._reset_cache()
        reg_mod._touch_memory(8080)
        reg_mod._touch_memory(8081)
        assert 8080 in reg_mod._last_access_cache
        assert 8081 in reg_mod._last_access_cache

    def test_flush_access_cache_writes_to_registry(self, fresh_registry):
        """_flush_access_cache 应将缓存的访问时间写入 registry"""
        import http_server_cli.registry as reg_mod
        self._reset_cache()
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345)
        # 模拟缓存中有访问记录
        import time
        reg_mod._last_access_cache[8080] = time.time()
        reg_mod._flush_access_cache()
        # 验证 registry 中的 last_access_at 已更新
        entry = fresh_registry.find(port=8080)
        assert entry is not None
        assert entry.get('last_access_at') is not None

    def test_flush_access_cache_clears_after_flush(self):
        """_flush_access_cache 刷盘后应清空缓存"""
        import http_server_cli.registry as reg_mod
        self._reset_cache()
        reg_mod._last_access_cache[8080] = 1234567890.0
        reg_mod._flush_access_cache()
        assert len(reg_mod._last_access_cache) == 0

    def test_flush_access_cache_empty_noop(self):
        """空缓存时 _flush_access_cache 应为 no-op"""
        import http_server_cli.registry as reg_mod
        self._reset_cache()
        # 不应抛出异常
        reg_mod._flush_access_cache()

    def test_flush_access_cache_skips_missing_entry(self):
        """缓存中的端口在 registry 中不存在时应跳过不崩溃"""
        import http_server_cli.registry as reg_mod
        self._reset_cache()
        # 缓存中有记录但 registry 中无对应条目
        reg_mod._last_access_cache[9999] = 1234567890.0
        reg_mod._flush_access_cache()  # 不抛异常
        assert len(reg_mod._last_access_cache) == 0

    def test_touch_memory_respects_flush_interval(self, monkeypatch):
        """_touch_memory 仅在超过 _FLUSH_INTERVAL 后才触发刷盘"""
        import http_server_cli.registry as reg_mod
        self._reset_cache()  # _last_flush_time = time.time()
        # 将间隔设大，防止自动刷盘
        monkeypatch.setattr(reg_mod, '_FLUSH_INTERVAL', 9999.0)
        # _reset_cache 已将 _last_flush_time 设为当前时间，不覆盖
        reg_mod._touch_memory(8080)
        # 不应触发刷盘（间隔未到）
        assert 8080 in reg_mod._last_access_cache

    def test_touch_memory_flushes_when_interval_exceeded(self, monkeypatch, fresh_registry):
        """超过 _FLUSH_INTERVAL 时 _touch_memory 应触发刷盘"""
        import http_server_cli.registry as reg_mod
        self._reset_cache()
        fresh_registry.add(port=8080, path='/tmp/foo', pid=12345)
        # 将间隔设 0，强制触发
        monkeypatch.setattr(reg_mod, '_FLUSH_INTERVAL', 0.0)
        import time
        reg_mod._last_flush_time = time.time() - 1.0  # 确保已过期
        reg_mod._touch_memory(8080)
        # 应触发刷盘，缓存清空
        assert len(reg_mod._last_access_cache) == 0


class TestRegistryCache:
    """P2: Registry 懒初始化 — mtime 缓存"""

    def _reset_cache(self):
        """重置模块级缓存"""
        import http_server_cli.registry as reg_mod
        reg_mod._registry_cache = None
        reg_mod._registry_cache_mtime = 0.0

    def test_second_init_reuses_cache(self, fresh_registry):
        """同一 mtime 时第二次 Registry() 应复用缓存数据"""
        self._reset_cache()
        # 第一次构造：读取文件（_registry_cache 应被设置）
        reg1 = Registry()
        reg1.add(port=8080, path='/tmp/foo', pid=12345)

        # 第二次构造：mtime 未变，应复用缓存
        reg2 = Registry()
        assert reg2.count() == 1
        assert reg2.find(port=8080)['path'] == '/tmp/foo'

    def test_cache_invalidates_on_save(self, fresh_registry):
        """save() 后缓存应更新为最新数据"""
        self._reset_cache()
        reg1 = Registry()
        reg1.add(port=8080, path='/tmp/foo', pid=12345)

        # save 后缓存应已刷新
        reg2 = Registry()
        assert reg2.count() == 1

        # 添加新条目
        reg2.add(port=8081, path='/tmp/bar', pid=12346)
        reg3 = Registry()
        assert reg3.count() == 2

    def test_cache_invalidates_on_mtime_change(self, fresh_registry):
        """文件 mtime 变化时缓存应失效并重新加载"""
        self._reset_cache()
        reg1 = Registry()
        reg1.add(port=8080, path='/tmp/foo', pid=12345)
        assert reg1.count() == 1

        # 手动修改 mtime 缓存为过期值，模拟外部修改
        import http_server_cli.registry as reg_mod
        reg_mod._registry_cache_mtime = 0.0  # 强制失效

        # 重新构造应重新读取
        reg2 = Registry()
        assert reg2.count() == 1  # 从文件重新加载
