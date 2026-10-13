# -*- coding: utf-8 -*-
"""HTTP-SERVER-CL007：参数面加固（未知 flag fail-closed + 裸调用不静默起服务）。

AC（转交单 A1–A4）：
- A1 写/破坏性命令遇未知 flag → 不执行副作用（exit 2）；-h/--help 走帮助（exit 0）
- A2 裸 `hs` → 打印用法 + exit 2，不起服务；`hs .` 仍正常启动
- A3 `hs prune` 输出 已删 / 保留 汇总；`-n` 仅预览
- A4 读命令（list/status/history/config/search）未知 flag 仍告警放行；--json 既有字段不变

全部用例在 `_isolate_data_dir`（conftest autouse）沙箱内运行，绝不触碰真实服务。
"""

import argparse
import json
import sys

import pytest

import http_server_cli.cli as cli
from http_server_cli.server import ServerManager

LIVE_PID = 500001
STALE_PID = 1289


# ── 纯函数：_filter_unknown ────────────────────────────────

class TestFilterUnknown:

    def test_empty(self):
        assert cli._filter_unknown([]) == []

    def test_all_unknown(self):
        assert cli._filter_unknown(['--prt', '8080']) == ['--prt', '8080']

    def test_allow_html(self):
        assert cli._filter_unknown(['a.html', 'B.HTM'], allow_html=True) == []

    def test_allow_positional(self):
        assert cli._filter_unknown(['keyword', '--prt'],
                                   allow_positional=True) == ['--prt']

    def test_allow_token(self):
        assert cli._filter_unknown(['--json'], allow=('--json',)) == []


# ── A1：写 / 破坏性命令 fail-closed ───────────────────────

def _seed_stale(mgr):
    """写一条 pid 必死的沉积记录。"""
    mgr.registry.add(port=8090, path='/tmp/hs-cl007-stale', pid=STALE_PID,
                     domain='localhost')


class TestA1FailClosed:

    def test_prune_unknown_flag_no_side_effect(self, capsys):
        """`hs prune --bogus` 不得删任何记录（原实现会照删）。"""
        mgr = ServerManager()
        _seed_stale(mgr)
        before = mgr.registry.count()

        with pytest.raises(SystemExit) as exc:
            cli._cmd_prune(mgr, ['--bogus'])
        assert exc.value.code == 2
        assert mgr.registry.count() == before          # 未动手删
        err = capsys.readouterr().err
        assert '未识别参数' in err and '--bogus' in err

    def test_prune_help_no_side_effect(self, capsys):
        """转交单 A1 原始触发：`hs prune --help` 现在只打印帮助，rc=0，不删。"""
        mgr = ServerManager()
        _seed_stale(mgr)
        before = mgr.registry.count()

        with pytest.raises(SystemExit) as exc:
            cli._cmd_prune(mgr, ['--help'])
        assert exc.value.code == 0
        assert mgr.registry.count() == before
        assert '用法:' in capsys.readouterr().out

    def test_kill_unknown_flag_no_kill(self, monkeypatch, capsys):
        """`hs kill 8090 --bogus` 不得 kill。"""
        mgr = ServerManager()
        _seed_stale(mgr)
        killed = []
        monkeypatch.setattr(mgr, 'kill', lambda *a, **k: killed.append(a))

        with pytest.raises(SystemExit) as exc:
            cli._cmd_kill(mgr, ['8090', '--bogus'])
        assert exc.value.code == 2
        assert killed == []
        assert '未识别参数' in capsys.readouterr().err

    def test_start_unknown_flag_no_start(self, monkeypatch, capsys):
        """`hs <dir> --prt 8080`（近形 typo）不得启动服务。"""
        mgr = ServerManager()
        started = []
        monkeypatch.setattr(mgr, 'start', lambda **k: started.append(k))

        with pytest.raises(SystemExit) as exc:
            cli._cmd_start(mgr, ['.', '--prt', '8080'])
        assert exc.value.code == 2
        assert started == []
        err = capsys.readouterr().err
        assert '未识别参数' in err and 'hs . -p <port>' in err   # 近形引导保留

    def test_killall_unknown_flag_no_kill(self, monkeypatch, capsys):
        mgr = ServerManager()
        called = []
        monkeypatch.setattr(mgr, 'kill_all', lambda **k: called.append(True))
        with pytest.raises(SystemExit) as exc:
            cli._cmd_killall(mgr, ['--bogus'])
        assert exc.value.code == 2 and called == []


# ── A2：裸 `hs` 不静默起服务 ──────────────────────────────

class TestA2BareInvocation:

    @pytest.fixture
    def _capture(self, monkeypatch):
        cap = {}
        monkeypatch.setattr(cli, 'ensure_storage', lambda: None)
        monkeypatch.setattr(cli, 'ServerManager', lambda: 'MGR')
        monkeypatch.setitem(cli._COMMANDS, 'start',
                            lambda mgr, args: cap.update(started=args))
        return cap

    def test_bare_hs_prints_usage_exit2(self, monkeypatch, _capture, capsys):
        monkeypatch.setattr(sys, 'argv', ['hs'])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 2
        assert 'started' not in _capture                    # 未启动
        assert '用法:' in capsys.readouterr().out

    def test_hs_dot_still_starts(self, monkeypatch, _capture):
        """显式给路径仍正常进 start（不破坏既有接口）。"""
        monkeypatch.setattr(sys, 'argv', ['hs', '.'])
        cli.main()
        assert _capture['started'] == ['.']

    def test_hs_bool_flag_still_starts(self, monkeypatch, _capture):
        """`hs -o`（带明确意图）仍进 start。"""
        monkeypatch.setattr(sys, 'argv', ['hs', '-o'])
        cli.main()
        assert _capture['started'] == ['-o']


# ── A3：prune 汇总 + -n 预览差异 ──────────────────────────

class TestA3PruneSummary:

    def test_prune_reports_removed_and_kept(self, capsys):
        mgr = ServerManager()
        _seed_stale(mgr)
        cli._cmd_prune(mgr, [])
        out = capsys.readouterr().out
        assert 'Removed 1 stale registry record' in out
        assert 'Kept 0 registry record(s)' in out

    def test_prune_dry_run_differs_from_apply(self, capsys):
        mgr = ServerManager()
        _seed_stale(mgr)

        cli._cmd_prune(mgr, ['-n'])
        out_dry = capsys.readouterr().out
        assert 'Would remove 1 stale registry record' in out_dry
        assert 'Kept 1 registry record(s)' in out_dry
        assert mgr.registry.count() == 1                     # 未删

        cli._cmd_prune(mgr, [])
        out_apply = capsys.readouterr().out
        assert 'Removed 1 stale registry record' in out_apply
        assert mgr.registry.count() == 0                     # 已删

    def test_prune_json_adds_kept_field(self, capsys):
        mgr = ServerManager()
        _seed_stale(mgr)
        cli._cmd_prune(mgr, ['--json'])
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is True and payload['command'] == 'prune'
        assert payload['data']['removed'] == 1
        assert payload['data']['kept'] == 0                   # additive 新字段


# ── A4：读命令告警放行 + JSON 错误信封 ────────────────────

class TestA4ReadOnlyAndJson:

    def test_list_unknown_flag_still_warns_and_passes(self, capsys):
        """`hs list --prot` 保持 D6 口径：告警到 stderr，不抛异常（rc 0）。"""
        mgr = ServerManager()
        cli._cmd_list(mgr, ['--prot'])                        # 不 raise
        err = capsys.readouterr().err
        assert '未识别参数' in err and '--prot' in err

    def test_status_unknown_flag_passes(self, capsys):
        mgr = ServerManager()
        cli._cmd_status(mgr, ['--prot'])                      # 不 raise
        assert '未识别参数' in capsys.readouterr().err

    def test_prune_json_error_envelope_on_unknown(self, capsys):
        """写命令 + --json + 未知 flag：stdout 出 JSON 错误信封，rc 2。"""
        mgr = ServerManager()
        with pytest.raises(SystemExit) as exc:
            cli._cmd_prune(mgr, ['--bogus', '--json'])
        assert exc.value.code == 2
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is False
        assert payload['command'] == 'prune'
        assert '--bogus' in payload['error']

    def test_list_json_contract_unchanged(self, capsys):
        """无未知参数时，list --json 既有字段不变。"""
        mgr = ServerManager()
        cli._list_servers(mgr, json=True)
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is True and payload['command'] == 'list'
        for key in ('count', 'stale_count', 'servers', 'managed'):
            assert key in payload['data']
