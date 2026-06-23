# -*- coding: utf-8 -*-
"""
CLI 入口测试 — OpenSpec: cli-01 ~ cli-03

测试命令分派、help/version 输出、未知命令处理、killall 别名。
不测试 main() 完整流程（argparse + sys.exit），而是直接测试 _cmd_* 分派函数
和 _COMMANDS 注册表。
"""

import json
import sys
from unittest.mock import MagicMock

import pytest

from http_server_cli import __version__
from http_server_cli.cli import _COMMANDS

pytestmark = pytest.mark.spec("cli-interface")

class TestCommandRegistry:
    """所有命令是否已注册"""

    def test_all_commands_registered(self):
        """期望的全部命令列表"""
        expected = {
            'start', 'list', 'status', 'kill', 'kill_all', 'killall',
            'config', 'set', 'help', 'version',
        }
        assert expected.issubset(_COMMANDS.keys())

    def test_killall_is_alias(self):
        """killall 和 kill_all 应是不同入口但指向不同处理函数"""
        assert 'killall' in _COMMANDS
        assert 'kill_all' in _COMMANDS

class TestVersionCommand:
    """version 命令输出"""

    def test_version_output(self, capsys):
        _COMMANDS['version'](None, [])
        captured = capsys.readouterr()
        assert f'http-server-cli v{__version__}' in captured.out

    def test_version_json_output(self, capsys):
        _COMMANDS['version'](None, ['--json'])
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'version'
        assert result['data']['version'] == __version__
        assert result['data']['name'] == 'http-server-cli'
        assert result['error'] is None

class TestHelpCommand:
    """help 命令输出"""

    def test_help_contains_start(self, capsys):
        _COMMANDS['help'](None, [])
        captured = capsys.readouterr()
        assert 'start' in captured.out
        assert 'list' in captured.out
        assert 'kill' in captured.out
        assert 'config' in captured.out

    def test_help_contains_daemon_flag(self, capsys):
        _COMMANDS['help'](None, [])
        captured = capsys.readouterr()
        assert '-d' in captured.out

class TestKillAllAlias:
    """killall 别名应调用 kill_all 相同逻辑"""

    def test_killall_dispatches_to_kill_all(self, monkeypatch):
        called = []
        mock_mgr = MagicMock()
        monkeypatch.setattr(mock_mgr, 'kill_all', lambda **kw: called.append(True))

        _COMMANDS['killall'](mock_mgr, [])
        _COMMANDS['kill_all'](mock_mgr, [])

        assert len(called) == 2

class TestPathShortcut:
    """路径快捷方式（hs /path/to/dir）应保留原始路径"""

    def test_shorthand_path_preserves_hyphens(self, monkeypatch):
        """hs /path/with-hyphens --json 应保留连字符，不转为下划线"""
        captured = {}
        def fake_start(mgr, args):
            captured['args'] = args

        monkeypatch.setattr('http_server_cli.cli._COMMANDS', {'start': fake_start})
        monkeypatch.setattr('http_server_cli.cli.ServerManager', lambda: None)
        monkeypatch.setattr('http_server_cli.cli.ensure_storage', lambda: None)

        import sys
        old_argv = sys.argv
        sys.argv = ['hs', '/Users/test/my-project-foo', '--json']
        try:
            from http_server_cli.cli import main
            main()
        except SystemExit:
            pass
        sys.argv = old_argv

        assert 'args' in captured
        # 路径中的连字符应被保留
        assert '/Users/test/my-project-foo' in captured['args']
        assert '--json' in captured['args']

    def test_shorthand_relative_path_with_hyphens(self, monkeypatch):
        """hs ./my-project --json 相对路径中的连字符应保留"""
        captured = {}
        def fake_start(mgr, args):
            captured['args'] = args

        monkeypatch.setattr('http_server_cli.cli._COMMANDS', {'start': fake_start})
        monkeypatch.setattr('http_server_cli.cli.ServerManager', lambda: None)
        monkeypatch.setattr('http_server_cli.cli.ensure_storage', lambda: None)

        import sys
        old_argv = sys.argv
        sys.argv = ['hs', './my-project', '--json']
        try:
            from http_server_cli.cli import main
            main()
        except SystemExit:
            pass
        sys.argv = old_argv

        assert 'args' in captured
        assert './my-project' in captured['args']

    def test_command_name_still_normalized(self, monkeypatch):
        """hs kill-all 的命令名连字符仍应转下划线"""
        captured = []
        def tracker(mgr, args):
            captured.append(True)

        cmds = dict(_COMMANDS)
        cmds['kill_all'] = tracker
        monkeypatch.setattr('http_server_cli.cli._COMMANDS', cmds)
        monkeypatch.setattr('http_server_cli.cli.ServerManager', lambda: None)
        monkeypatch.setattr('http_server_cli.cli.ensure_storage', lambda: None)

        import sys
        old_argv = sys.argv
        sys.argv = ['hs', 'kill-all']
        try:
            from http_server_cli.cli import main
            main()
        except SystemExit:
            pass
        sys.argv = old_argv

        assert len(captured) == 1


class TestUnknownCommand:
    """未知命令应在 main() 中处理。此处验证 _COMMANDS 不包含它。"""

    def test_unknown_not_in_registry(self):
        assert 'unknown-command' not in _COMMANDS
        assert 'foobar' not in _COMMANDS
