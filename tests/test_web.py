# -*- coding: utf-8 -*-
"""
Web 服务注册（hs web）测试 — ServiceStore 存储 + _cmd_web CLI。

覆盖:
- ServiceStore CRUD / 校验 / 损坏检测 / 持久化
- _cmd_web add/list/show/remove/update + --json 信封
- _web_run 执行三分支: url 可达跳过 / 不可达执行 / --no-probe 强制
- 找不到 name → exit 1 + 可用列表
"""

import json
import os
import pytest
from unittest.mock import patch

from http_server_cli.services import (
    ServiceStore, DataCorruptionError,
)
from http_server_cli.cli import _COMMANDS
from http_server_cli import services as svc_mod


# ── ServiceStore ────────────────────────────────────────

class TestServiceCRUD:
    """基本 CRUD 操作"""

    def test_add_and_get(self):
        store = ServiceStore()
        store.add('daily.checker', cmd='dk server start --daemon --open',
                  url='http://127.0.0.1:5001')
        svc = store.get('daily.checker')
        assert svc['name'] == 'daily.checker'
        assert svc['cmd'] == 'dk server start --daemon --open'
        assert svc['url'] == 'http://127.0.0.1:5001'
        assert svc['open'] == 'url'
        assert svc['created_at']

    def test_add_default_open_mode_url(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        assert store.get('a')['open'] == 'url'
        assert store.get('a')['url'] is None

    def test_add_duplicate_name(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        with pytest.raises(ValueError):
            store.add('a', cmd='echo b')

    def test_add_force_overrides_name(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        store.add('a', cmd='echo b', force=True)
        assert store.get('a')['cmd'] == 'echo b'

    def test_add_empty_url_normalized(self):
        store = ServiceStore()
        store.add('a', cmd='echo a', url='')
        assert store.get('a')['url'] is None

    def test_add_open_mode_none(self):
        store = ServiceStore()
        store.add('a', cmd='echo a', open_mode='none')
        assert store.get('a')['open'] == 'none'

    def test_add_invalid_cmd_empty(self):
        store = ServiceStore()
        with pytest.raises(ValueError):
            store.add('a', cmd='')

    def test_add_invalid_open_mode(self):
        store = ServiceStore()
        with pytest.raises(ValueError):
            store.add('a', cmd='echo a', open_mode='bogus')

    def test_add_invalid_url(self):
        store = ServiceStore()
        with pytest.raises(ValueError):
            store.add('a', cmd='echo a', url='notaurl')

    def test_remove_existing(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        assert store.remove('a') is True
        assert store.get('a') is None

    def test_remove_nonexistent(self):
        store = ServiceStore()
        assert store.remove('a') is False

    def test_list_all_sorted_by_created_at(self):
        store = ServiceStore()
        store.add('b', cmd='echo b')
        store.add('a', cmd='echo a')
        assert [s['name'] for s in store.list_all()] == ['b', 'a']

    def test_names(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        store.add('b', cmd='echo b')
        assert store.names() == {'a', 'b'}


class TestServiceUpdate:
    """update 操作"""

    def test_update_cmd(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        assert store.update('a', cmd='echo b') is True
        assert store.get('a')['cmd'] == 'echo b'

    def test_update_url(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        store.update('a', url='http://127.0.0.1:8080')
        assert store.get('a')['url'] == 'http://127.0.0.1:8080'

    def test_update_clear_url(self):
        store = ServiceStore()
        store.add('a', cmd='echo a', url='http://127.0.0.1:8080')
        store.update('a', url='')
        assert store.get('a')['url'] is None

    def test_update_open_mode(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        store.update('a', open_mode='none')
        assert store.get('a')['open'] == 'none'

    def test_update_nonexistent(self):
        store = ServiceStore()
        assert store.update('a', cmd='echo b') is False

    def test_update_invalid_url(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        with pytest.raises(ValueError):
            store.update('a', url='bad')

    def test_update_invalid_open_mode(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        with pytest.raises(ValueError):
            store.update('a', open_mode='bad')


class TestServiceValidation:
    """校验函数"""

    def test_validate_name_valid(self):
        assert ServiceStore.validate_name('daily.checker') is None
        assert ServiceStore.validate_name('jaden.tech') is None
        assert ServiceStore.validate_name('a-b') is None

    def test_validate_name_empty(self):
        assert ServiceStore.validate_name('') == 'service name cannot be empty'

    def test_validate_name_special_chars(self):
        assert 'must match' in ServiceStore.validate_name('a b')
        assert 'must match' in ServiceStore.validate_name('中')

    def test_validate_cmd_empty(self):
        assert ServiceStore.validate_cmd('') == 'service cmd cannot be empty'
        assert ServiceStore.validate_cmd('  ') == 'service cmd cannot be empty'
        assert ServiceStore.validate_cmd('echo hi') is None

    def test_validate_open_mode(self):
        assert ServiceStore.validate_open_mode('cmd') is None
        assert ServiceStore.validate_open_mode('url') is None
        assert ServiceStore.validate_open_mode('both') is None
        assert ServiceStore.validate_open_mode('none') is None
        assert 'open mode' in ServiceStore.validate_open_mode('bogus')

    def test_validate_url(self):
        assert ServiceStore.validate_url('http://x') is None
        assert ServiceStore.validate_url('https://x') is None
        assert ServiceStore.validate_url(None) is None
        assert ServiceStore.validate_url('') is None
        assert 'http' in ServiceStore.validate_url('ftp://x')
        assert 'http' in ServiceStore.validate_url('127.0.0.1:5001')


class TestServiceCorruption:
    """损坏检测"""

    def test_corrupted_json_raises(self):
        with open(svc_mod.SERVICES_PATH, 'w', encoding='utf-8') as f:
            f.write('{broken')
        store = ServiceStore()
        with pytest.raises(DataCorruptionError):
            store.list_all()

    def test_corruption_prevents_add(self):
        with open(svc_mod.SERVICES_PATH, 'w', encoding='utf-8') as f:
            f.write('{broken')
        store = ServiceStore()
        with pytest.raises(DataCorruptionError):
            store.add('a', cmd='echo a')

    def test_empty_file_ok(self):
        with open(svc_mod.SERVICES_PATH, 'w', encoding='utf-8') as f:
            f.write('')
        store = ServiceStore()
        assert store.list_all() == []


class TestServicePersistence:
    """磁盘持久化"""

    def test_add_persists_to_disk(self):
        store = ServiceStore()
        store.add('daily.checker', cmd='dk server start --daemon --open')
        raw = json.load(open(svc_mod.SERVICES_PATH, encoding='utf-8'))
        assert raw['services'][0]['name'] == 'daily.checker'

    def test_remove_persists_to_disk(self):
        store = ServiceStore()
        store.add('a', cmd='echo a')
        store.remove('a')
        raw = json.load(open(svc_mod.SERVICES_PATH, encoding='utf-8'))
        assert raw['services'] == []


# ── _cmd_web CLI ────────────────────────────────────────

class TestWebCliAdd:
    """hs web add"""

    def test_add_text(self, capsys):
        _COMMANDS['web'](None, ['add', 'daily.checker', '--cmd',
                                'dk server start --daemon --open',
                                '--url', 'http://127.0.0.1:5001'])
        out = capsys.readouterr().out
        assert "Service 'daily.checker' registered" in out
        assert ServiceStore().get('daily.checker') is not None

    def test_add_json(self, capsys):
        _COMMANDS['web'](None, ['add', 'a', '--cmd', 'echo a', '--json'])
        result = json.loads(capsys.readouterr().out)
        assert result['success'] is True
        assert result['command'] == 'web-add'
        assert result['data']['name'] == 'a'

    def test_add_missing_cmd(self, capsys):
        _COMMANDS['web'](None, ['add', 'a'])
        assert '--cmd is required' in capsys.readouterr().err

    def test_add_conflicts_with_builtin(self, capsys):
        _COMMANDS['web'](None, ['add', 'list', '--cmd', 'echo a'])
        assert 'conflicts' in capsys.readouterr().err

    def test_add_invalid_url(self, capsys):
        _COMMANDS['web'](None, ['add', 'a', '--cmd', 'echo a', '--url', 'nope'])
        assert 'url must start' in capsys.readouterr().err

    def test_add_invalid_open_mode(self, capsys):
        _COMMANDS['web'](None, ['add', 'a', '--cmd', 'echo a', '--open', 'bogus'])
        assert 'open mode' in capsys.readouterr().err

    def test_add_duplicate(self, capsys):
        _COMMANDS['web'](None, ['add', 'a', '--cmd', 'echo a'])
        capsys.readouterr()
        _COMMANDS['web'](None, ['add', 'a', '--cmd', 'echo b'])
        assert 'already exists' in capsys.readouterr().err

    def test_add_force_overrides(self, capsys):
        _COMMANDS['web'](None, ['add', 'a', '--cmd', 'echo a'])
        capsys.readouterr()
        _COMMANDS['web'](None, ['add', 'a', '--cmd', 'echo b', '--force'])
        assert ServiceStore().get('a')['cmd'] == 'echo b'


class TestWebCliListShowRemoveUpdate:
    """hs web list/show/remove/update"""

    def test_list_empty(self, capsys):
        _COMMANDS['web'](None, ['list'])
        assert 'No services registered' in capsys.readouterr().out

    def test_list_text(self, capsys):
        ServiceStore().add('a', cmd='echo a')
        _COMMANDS['web'](None, ['list'])
        out = capsys.readouterr().out
        assert '1 service' in out
        assert 'a' in out

    def test_list_json(self, capsys):
        ServiceStore().add('a', cmd='echo a')
        _COMMANDS['web'](None, ['list', '--json'])
        result = json.loads(capsys.readouterr().out)
        assert result['command'] == 'web-list'
        assert result['data']['count'] == 1

    def test_show(self, capsys):
        ServiceStore().add('a', cmd='echo a', url='http://x')
        _COMMANDS['web'](None, ['show', 'a'])
        out = capsys.readouterr().out
        assert 'a' in out
        assert 'http://x' in out

    def test_show_not_found(self, capsys):
        _COMMANDS['web'](None, ['show', 'a'])
        assert 'not found' in capsys.readouterr().err

    def test_show_json(self, capsys):
        ServiceStore().add('a', cmd='echo a')
        _COMMANDS['web'](None, ['show', 'a', '--json'])
        result = json.loads(capsys.readouterr().out)
        assert result['command'] == 'web-show'
        assert result['data']['name'] == 'a'

    def test_remove_text(self, capsys):
        ServiceStore().add('a', cmd='echo a')
        _COMMANDS['web'](None, ['remove', 'a'])
        assert "Service 'a' removed" in capsys.readouterr().out
        assert ServiceStore().get('a') is None

    def test_remove_not_found(self, capsys):
        _COMMANDS['web'](None, ['remove', 'a'])
        assert 'not found' in capsys.readouterr().err

    def test_remove_json(self, capsys):
        ServiceStore().add('a', cmd='echo a')
        _COMMANDS['web'](None, ['remove', 'a', '--json'])
        result = json.loads(capsys.readouterr().out)
        assert result['success'] is True

    def test_update_cmd(self, capsys):
        ServiceStore().add('a', cmd='echo a')
        _COMMANDS['web'](None, ['update', 'a', '--cmd', 'echo b'])
        assert ServiceStore().get('a')['cmd'] == 'echo b'
        assert 'updated' in capsys.readouterr().out

    def test_update_clear_url(self, capsys):
        ServiceStore().add('a', cmd='echo a', url='http://x')
        _COMMANDS['web'](None, ['update', 'a', '--url', ''])
        assert ServiceStore().get('a')['url'] is None

    def test_update_nothing(self, capsys):
        ServiceStore().add('a', cmd='echo a')
        _COMMANDS['web'](None, ['update', 'a'])
        assert 'Nothing to update' in capsys.readouterr().err

    def test_update_not_found(self, capsys):
        _COMMANDS['web'](None, ['update', 'a', '--cmd', 'echo b'])
        assert 'not found' in capsys.readouterr().err


class TestWebCliRun:
    """hs web <name> 执行"""

    def test_not_found_exits_1(self, capsys):
        with pytest.raises(SystemExit) as e:
            _COMMANDS['web'](None, ['nonexist'])
        assert e.value.code == 1
        assert 'not found' in capsys.readouterr().err

    def test_no_name_shows_help(self, capsys):
        _COMMANDS['web'](None, [])
        assert 'hs web' in capsys.readouterr().out

    def test_running_skips_cmd(self, capsys):
        """url 可达 → 直接访问，不执行 cmd"""
        ServiceStore().add('a', cmd='echo SHOULD_NOT_RUN',
                           url='http://127.0.0.1:1')
        with patch('http_server_cli.utils.url_reachable', return_value=True), \
             patch('http_server_cli.cli.webbrowser.open') as mock_open, \
             patch('http_server_cli.cli.subprocess.run') as mock_run:
            _COMMANDS['web'](None, ['a'])
        out = capsys.readouterr().out
        assert 'already running' in out
        mock_run.assert_not_called()
        mock_open.assert_called_once_with('http://127.0.0.1:1')

    def test_unreachable_executes_cmd(self, capsys):
        """url 不可达 → 执行 cmd + 启动后 open"""
        ServiceStore().add('a', cmd='true', url='http://127.0.0.1:1')
        with patch('http_server_cli.utils.url_reachable', return_value=False), \
             patch('http_server_cli.utils.wait_url_reachable', return_value=True), \
             patch('http_server_cli.cli.webbrowser.open') as mock_open, \
             patch('http_server_cli.cli.subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            _COMMANDS['web'](None, ['a'])
        out = capsys.readouterr().out
        assert 'started' in out
        mock_run.assert_called_once()
        mock_open.assert_called_once_with('http://127.0.0.1:1')

    def test_no_url_skips_probe(self, capsys):
        """无 url（动态端口）→ 不探测直接执行"""
        ServiceStore().add('a', cmd='true')
        with patch('http_server_cli.utils.url_reachable') as mock_probe, \
             patch('http_server_cli.cli.subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            _COMMANDS['web'](None, ['a'])
        mock_probe.assert_not_called()
        mock_run.assert_called_once()
        assert 'started' in capsys.readouterr().out

    def test_no_probe_always_executes(self, capsys):
        """--no-probe → 跳过探测，总是执行 cmd（强制重启）"""
        ServiceStore().add('a', cmd='true', url='http://127.0.0.1:1')
        with patch('http_server_cli.utils.url_reachable') as mock_probe, \
             patch('http_server_cli.utils.wait_url_reachable', return_value=True), \
             patch('http_server_cli.cli.webbrowser.open'), \
             patch('http_server_cli.cli.subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            _COMMANDS['web'](None, ['a', '--no-probe'])
        mock_probe.assert_not_called()
        mock_run.assert_called_once()

    def test_run_json_started(self, capsys):
        ServiceStore().add('a', cmd='true')
        with patch('http_server_cli.cli.subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            _COMMANDS['web'](None, ['a', '--json'])
        result = json.loads(capsys.readouterr().out)
        assert result['command'] == 'web-run'
        assert result['data']['status'] == 'started'
        assert result['data']['name'] == 'a'

    def test_run_json_running(self, capsys):
        ServiceStore().add('a', cmd='true', url='http://127.0.0.1:1')
        with patch('http_server_cli.utils.url_reachable', return_value=True), \
             patch('http_server_cli.cli.webbrowser.open'), \
             patch('http_server_cli.cli.subprocess.run') as mock_run:
            _COMMANDS['web'](None, ['a', '--json'])
        result = json.loads(capsys.readouterr().out)
        assert result['data']['status'] == 'running'
        mock_run.assert_not_called()

    def test_open_mode_none_no_open(self, capsys):
        """open=none → 探测命中也不开浏览器"""
        ServiceStore().add('a', cmd='true', url='http://127.0.0.1:1',
                           open_mode='none')
        with patch('http_server_cli.utils.url_reachable', return_value=True), \
             patch('http_server_cli.cli.webbrowser.open') as mock_open, \
             patch('http_server_cli.cli.subprocess.run'):
            _COMMANDS['web'](None, ['a'])
        mock_open.assert_not_called()

    def test_open_mode_cmd_no_web_open(self, capsys):
        """open=cmd → 依赖命令自带 -o，web 不开"""
        ServiceStore().add('a', cmd='true', url='http://127.0.0.1:1',
                           open_mode='cmd')
        with patch('http_server_cli.utils.url_reachable', return_value=True), \
             patch('http_server_cli.cli.webbrowser.open') as mock_open:
            _COMMANDS['web'](None, ['a'])
        mock_open.assert_not_called()
        assert 'already running' in capsys.readouterr().out

    def test_open_mode_both_running_opens(self, capsys):
        """open=both → 探测命中也 open url"""
        ServiceStore().add('a', cmd='true', url='http://127.0.0.1:1',
                           open_mode='both')
        with patch('http_server_cli.utils.url_reachable', return_value=True), \
             patch('http_server_cli.cli.webbrowser.open') as mock_open, \
             patch('http_server_cli.cli.subprocess.run'):
            _COMMANDS['web'](None, ['a'])
        mock_open.assert_called_once_with('http://127.0.0.1:1')

    def test_cmd_nonzero_exit_warns(self, capsys):
        ServiceStore().add('a', cmd='false')
        with patch('http_server_cli.cli.subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1
            _COMMANDS['web'](None, ['a'])
        assert 'exited with code 1' in capsys.readouterr().err
