# -*- coding: utf-8 -*-
"""
HTTP-SERVER-CL003：`hs start -p/--port` + 保留端口/区间 fail-closed + 顺序链 + 未识别参数告警 + 退出码。

对应设计 §7 测试清单（`documents/http-server-port-flag-design-v1.1-20260922.md`）。
"""

import json
import os
import sys
import types

import pytest
from unittest.mock import MagicMock

import http_server_cli.cli as cli
from http_server_cli.server import ServerManager, UsageError
from http_server_cli.services import ServiceStore

pytestmark = pytest.mark.spec("port-allocation")


# ── 夹具：mock 有副作用的系统调用（按值导入陷阱 → 补丁打在消费者命名空间）──

@pytest.fixture(autouse=True)
def _mock_system_calls(monkeypatch):
    monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: False)
    monkeypatch.setattr('http_server_cli.server.is_process_alive', lambda pid: True)
    monkeypatch.setattr('http_server_cli.server.find_available_port', lambda sp: sp)
    monkeypatch.setattr('http_server_cli.server.get_pid_by_lsof', lambda p: [])
    monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: False)
    monkeypatch.setattr('http_server_cli.registry.is_process_alive', lambda pid: True)
    mock_proc = MagicMock()
    mock_proc.pid = 99999
    monkeypatch.setattr('http_server_cli.server.subprocess.Popen', lambda *a, **kw: mock_proc)
    monkeypatch.setattr('http_server_cli.server.subprocess.run', lambda *a, **kw: None)
    monkeypatch.setattr('http_server_cli.server.webbrowser.open', lambda url: True)
    monkeypatch.setattr('http_server_cli.server.time.sleep', lambda s: None)


def _abs(path):
    return os.path.realpath(path)


# ── start -p 基本契约 ───────────────────────────────────

class TestStartPortFlag:

    def test_binds_requested_port(self, temp_project, capsys):
        mgr = ServerManager()
        assert mgr.start(path=temp_project, port=8099, url_only=True) is True
        assert 'http://localhost:8099' in capsys.readouterr().out
        entry = mgr.registry.find(path=_abs(temp_project))
        assert entry is not None and entry['port'] == 8099

    def test_json_envelope_adds_port(self, temp_project, capsys):
        mgr = ServerManager()
        assert mgr.start(path=temp_project, port=8099, json=True) is True
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is True
        assert payload['data']['port'] == 8099

    def test_json_envelope_port_on_idempotent_hit(self, monkeypatch, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project, port=8099, json=True)
        capsys.readouterr()
        # 第二次：端口占用 + 进程存活 → 幂等命中，信封仍带 port
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p == 8099)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: p == 8099)
        assert mgr.start(path=temp_project, json=True) is True
        payload = json.loads(capsys.readouterr().out)
        assert payload['data']['port'] == 8099

    def test_missing_path_returns_false(self):
        assert ServerManager().start(path='/nonexistent-cl003-xyz') is False

    def test_without_port_keeps_auto_increment(self, monkeypatch, temp_project, capsys):
        monkeypatch.setattr('http_server_cli.server.find_available_port', lambda sp: sp + 3)
        mgr = ServerManager()
        assert mgr.start(path=temp_project, url_only=True) is True
        assert ':8083' in capsys.readouterr().out

    def test_above_max_port_allowed(self, temp_project, capsys):
        # D15：-p 直绑上限 65535；MAX_PORT=10000 只约束自动漂移扫描
        assert ServerManager().start(path=temp_project, port=20000, url_only=True) is True
        assert ':20000' in capsys.readouterr().out


# ── fail-closed：占用 / 保留端口 / 区间 ─────────────────

class TestFailClosed:

    def test_port_in_use_fails_closed(self, monkeypatch, temp_project, capsys):
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p == 8450)
        mgr = ServerManager()
        assert mgr.start(path=temp_project, port=8450) is False
        err = capsys.readouterr().err
        assert '已被占用' in err
        assert 'hs kill 8450' in err
        assert mgr.registry.find(path=_abs(temp_project)) is None

    def test_port_in_use_reports_registry_occupant(self, monkeypatch, temp_project, capsys):
        mgr = ServerManager()
        mgr.registry.add(port=8451, path='/tmp/other-cl003', pid=4242, domain='localhost')
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p == 8451)
        assert mgr.start(path=temp_project, port=8451) is False
        err = capsys.readouterr().err
        assert 'PID 4242' in err and 'other-cl003' in err

    def test_reserved_port_occupied_dual_state(self, monkeypatch, temp_project, capsys):
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p == 8180)
        assert ServerManager().start(path=temp_project, port=8180) is False
        err = capsys.readouterr().err
        assert '保留端口' in err
        assert '正在使用' in err

    def test_reserved_port_free_dual_state(self, temp_project, capsys):
        assert ServerManager().start(path=temp_project, port=8181) is False
        err = capsys.readouterr().err
        assert '保留端口' in err
        assert 'hs dashboard -p 8181' in err

    def test_range_violations_raise_usage_error(self, temp_project):
        mgr = ServerManager()
        for bad in (99, 0, 70000):
            with pytest.raises(UsageError):
                mgr.start(path=temp_project, port=bad)

    def test_range_violation_json_envelope(self, temp_project, capsys):
        with pytest.raises(UsageError):
            ServerManager().start(path=temp_project, port=99, json=True)
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is False
        assert '1024-65535' in payload['error']

    def test_json_mode_fail_closed_envelope(self, monkeypatch, temp_project, capsys):
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p == 8452)
        assert ServerManager().start(path=temp_project, port=8452, json=True) is False
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is False and '已被占用' in payload['error']


# ── 执行顺序链（评审 F-1 的两个反例）────────────────────

class TestOrderChain:

    def _running_on_8099(self, mgr, temp_project):
        mgr.registry.add(port=8099, path=_abs(temp_project), pid=99999, domain='localhost')

    def test_idempotent_precedes_occupancy_check(self, monkeypatch, temp_project, capsys):
        mgr = ServerManager()
        self._running_on_8099(mgr, temp_project)
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p == 8099)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: p == 8099)
        assert mgr.start(path=temp_project, port=8099, url_only=True) is True
        captured = capsys.readouterr()
        assert '已被占用' not in captured.err
        assert 'http://localhost:8099' in captured.out

    def test_idempotent_precedes_reserved_check(self, monkeypatch, temp_project, capsys):
        mgr = ServerManager()
        self._running_on_8099(mgr, temp_project)
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p == 8099)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: p == 8099)
        assert mgr.start(path=temp_project, port=8180, url_only=True) is True
        captured = capsys.readouterr()
        assert '保留端口' not in captured.err
        assert '已运行在 8099' in captured.err
        assert 'http://localhost:8099' in captured.out


# ── kill 返回值契约（D14 / R-1）────────────────────────

class TestKillReturnContract:

    def test_not_registered_port_returns_false(self, capsys):
        assert ServerManager().kill('59999') is False
        assert 'not registered' in capsys.readouterr().out

    def test_empty_arg_returns_false(self, capsys):
        assert ServerManager().kill('') is False

    def test_registered_service_returns_true(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        capsys.readouterr()
        assert mgr.kill('8080') is True


# ── 未识别参数告警 helper（D6）──────────────────────────

class TestUnknownArgsWarning:

    def test_warns_on_unknown_flag_with_hint(self, capsys):
        rest = cli._warn_unknown_args(['--prot', '8080'])
        assert rest == ['--prot', '8080']
        err = capsys.readouterr().err
        assert '未识别参数' in err
        assert '--prot' in err
        assert 'hs . -p <port>' in err

    def test_html_tokens_whitelisted(self, capsys):
        assert cli._warn_unknown_args(['a.html', 'B.HTM'], allow_html=True) == []
        assert capsys.readouterr().err == ''

    def test_positional_whitelisted(self, capsys):
        assert cli._warn_unknown_args(['some-keyword'], allow_positional=True) == []
        assert capsys.readouterr().err == ''

    def test_allow_list(self, capsys):
        assert cli._warn_unknown_args(['--json'], allow=('--json',)) == []
        assert capsys.readouterr().err == ''

    def test_empty_is_silent(self, capsys):
        assert cli._warn_unknown_args([]) == []
        assert capsys.readouterr().err == ''


# ── 顶层兜底重组（D8）──────────────────────────────────

class TestTopLevelReorg:

    @pytest.fixture
    def _start_capture(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(cli, 'ensure_storage', lambda: None)
        monkeypatch.setattr(cli, 'ServerManager', lambda: 'MGR')
        monkeypatch.setitem(cli._COMMANDS, 'start',
                            lambda mgr, args: captured.update(mgr=mgr, args=args))
        return captured

    def test_leaked_port_value_reaches_start(self, monkeypatch, _start_capture):
        monkeypatch.setattr(sys, 'argv', ['hs', '-p', '8099'])
        cli.main()
        assert _start_capture['args'] == ['-p', '8099']

    def test_leaked_index_value_reaches_start(self, monkeypatch, _start_capture):
        monkeypatch.setattr(sys, 'argv', ['hs', '-i', 'no-such-cl003.html', '-p', '8099'])
        cli.main()
        assert _start_capture['args'] == ['-i', 'no-such-cl003.html', '-p', '8099']

    def test_bare_number_still_unknown_command(self, monkeypatch, _start_capture, capsys):
        monkeypatch.setattr(sys, 'argv', ['hs', '8089'])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1
        assert _start_capture == {}


# ── 退出码（D9e / D14）────────────────────────────────

class _StubManager:
    def start(self, **kw):
        return False

    def kill(self, *a, **kw):
        return False


class TestExitCodes:

    def test_invalid_port_value_exits_2(self):
        with pytest.raises(SystemExit) as exc:
            cli._COMMANDS['start'](_StubManager(), ['-p', 'abc'])
        assert exc.value.code == 2

    def test_out_of_range_port_exits_2(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            cli._COMMANDS['start'](ServerManager(), [str(tmp_path), '-p', '70000'])
        assert exc.value.code == 2

    def test_missing_path_exits_1(self):
        with pytest.raises(SystemExit) as exc:
            cli._COMMANDS['start'](_StubManager(), ['/nonexistent-cl003-xyz'])
        assert exc.value.code == 1

    def test_kill_not_registered_exits_1(self):
        with pytest.raises(SystemExit) as exc:
            cli._COMMANDS['kill'](_StubManager(), ['59999'])
        assert exc.value.code == 1


# ── dashboard restart --port（D9a）─────────────────────

class TestDashboardRestartPort:

    def test_cmd_dashboard_passes_port(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(cli, '_manage_dashboard',
                            lambda subcmd, json_mode=False, port=None: captured.update(
                                sub=subcmd, port=port))
        cli._COMMANDS['dashboard'](None, ['restart', '--port', '8290'])
        assert captured == {'sub': 'restart', 'port': 8290}

    def test_cmd_dashboard_restart_defaults_to_none(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(cli, '_manage_dashboard',
                            lambda subcmd, json_mode=False, port=None: captured.update(
                                sub=subcmd, port=port))
        cli._COMMANDS['dashboard'](None, ['restart'])
        assert captured['port'] is None

    def test_cmd_dashboard_rejects_out_of_range(self):
        with pytest.raises(SystemExit) as exc:
            cli._COMMANDS['dashboard'](None, ['restart', '--port', '99'])
        assert exc.value.code == 2

    def _patch_managed(self, monkeypatch, entry):
        class _MReg:
            def find(self, name=None):
                return entry

            def remove(self, name=None):
                pass

        monkeypatch.setattr('http_server_cli.registry_managed.ManagedRegistry', _MReg)
        monkeypatch.setattr('http_server_cli.utils.is_process_alive', lambda pid: False)
        monkeypatch.setattr('http_server_cli.utils.is_port_in_use', lambda p: False)
        import http_server_cli.dashboard as dash
        calls = {}
        monkeypatch.setattr(dash, 'serve', lambda **kw: calls.update(kw))
        return calls

    def test_restart_reuses_entry_port(self, monkeypatch):
        calls = self._patch_managed(
            monkeypatch, {'name': 'dashboard', 'port': 8280, 'pid': 99999, 'started_at': ''})
        cli._manage_dashboard('restart', json_mode=False)
        assert calls['port'] == 8280

    def test_restart_uses_requested_port(self, monkeypatch):
        calls = self._patch_managed(
            monkeypatch, {'name': 'dashboard', 'port': 8280, 'pid': 99999, 'started_at': ''})
        cli._manage_dashboard('restart', json_mode=False, port=8290)
        assert calls['port'] == 8290

    def test_restart_rejects_mcp_reserved_port(self, monkeypatch):
        self._patch_managed(
            monkeypatch, {'name': 'dashboard', 'port': 8280, 'pid': 99999, 'started_at': ''})
        with pytest.raises(SystemExit) as exc:
            cli._manage_dashboard('restart', json_mode=False, port=8181)
        assert exc.value.code == 1

    def test_not_running_does_not_start(self, monkeypatch, capsys):
        calls = self._patch_managed(monkeypatch, None)
        cli._manage_dashboard('restart', json_mode=False)
        assert calls == {}
        assert 'not running' in capsys.readouterr().out


# ── hs web --port / --no-port（D9b）────────────────────

class TestWebPortFlag:

    def test_add_with_port(self, capsys):
        cli._COMMANDS['web'](None, ['add', 'cl003p', '--cmd', 'echo hi', '--port', '9001'])
        svc = ServiceStore().get('cl003p')
        assert svc['use_port'] is True and svc['port'] == 9001
        assert 'Port: on' in capsys.readouterr().out

    def test_add_no_port(self):
        cli._COMMANDS['web'](None, ['add', 'cl003q', '--cmd', 'echo hi', '--no-port'])
        svc = ServiceStore().get('cl003q')
        assert svc['use_port'] is False and svc['port'] is None

    def test_add_rejects_out_of_range(self, capsys):
        cli._COMMANDS['web'](None, ['add', 'cl003bad', '--cmd', 'echo hi', '--port', '99'])
        assert ServiceStore().get('cl003bad') is None
        assert '1024-65535' in capsys.readouterr().err

    def test_add_rejects_mutually_exclusive(self, capsys):
        cli._COMMANDS['web'](None, ['add', 'cl003mx', '--cmd', 'echo hi',
                                    '--port', '9001', '--no-port'])
        assert ServiceStore().get('cl003mx') is None
        assert 'mutually exclusive' in capsys.readouterr().err

    def test_update_sets_then_clears_both_fields(self):
        cli._COMMANDS['web'](None, ['add', 'cl003u', '--cmd', 'echo hi'])
        cli._COMMANDS['web'](None, ['update', 'cl003u', '--port', '9002'])
        svc = ServiceStore().get('cl003u')
        assert (svc['use_port'], svc['port']) == (True, 9002)
        cli._COMMANDS['web'](None, ['update', 'cl003u', '--no-port'])
        svc = ServiceStore().get('cl003u')
        assert (svc['use_port'], svc['port']) == (False, None)

    def test_update_nothing_to_update_message(self, capsys):
        cli._COMMANDS['web'](None, ['add', 'cl003v', '--cmd', 'echo hi'])
        cli._COMMANDS['web'](None, ['update', 'cl003v'])
        assert '--no-port' in capsys.readouterr().err

    def test_run_injects_domain_then_port(self, monkeypatch):
        ServiceStore().add('cl003r', cmd='echo hi', use_domain=True, use_port=True, port=9001)
        calls = []

        def _fake_run(cmd, **kw):
            calls.append(cmd)
            return types.SimpleNamespace(returncode=0)

        monkeypatch.setattr('http_server_cli.cli.subprocess.run', _fake_run)
        cli._COMMANDS['web'](None, ['cl003r', '--no-probe'])
        assert calls == ['echo hi --domain "localhost" --port 9001']

    def test_legacy_entry_without_port_fields_still_works(self):
        store = ServiceStore()
        store.add('cl003legacy', cmd='echo hi')
        data = store._read_all()
        for s in data:
            if s['name'] == 'cl003legacy':
                s.pop('use_port', None)
                s.pop('port', None)
        store._write_all(data)
        svc = store.get('cl003legacy')
        assert svc.get('use_port') is None and svc.get('port') is None
        cli._COMMANDS['web'](None, ['update', 'cl003legacy', '--port', '9003'])
        assert ServiceStore().get('cl003legacy')['port'] == 9003
