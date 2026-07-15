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

    def test_relative_path_without_prefix_routes_to_start(self, monkeypatch, tmp_path):
        """hs relative/path.html（无 ./ 前缀）应路由到 start"""
        test_file = tmp_path / 'my-project-v1.html'
        test_file.write_text('<html></html>')

        captured = {'args': None}
        def fake_start(mgr, args):
            captured['args'] = args

        cmds = dict(_COMMANDS)
        cmds['start'] = fake_start
        monkeypatch.setattr('http_server_cli.cli._COMMANDS', cmds)
        monkeypatch.setattr('http_server_cli.cli.ServerManager', lambda: None)
        monkeypatch.setattr('http_server_cli.cli.ensure_storage', lambda: None)

        import sys, os
        old_argv, old_cwd = sys.argv, os.getcwd()
        sys.argv = ['hs', str(test_file), '--json']
        os.chdir(str(tmp_path))
        try:
            from http_server_cli.cli import main
            main()
        except SystemExit:
            pass
        sys.argv = old_argv
        os.chdir(old_cwd)

        assert captured['args'] is not None
        assert 'my-project-v1' in captured['args'][0]  # 原始连字符保留
        assert '--json' in captured['args']

    def test_nonexistent_path_still_unknown(self, monkeypatch):
        """不存在的路径应保持 Unknown command"""
        captured = {'called_start': False}
        def fake_start(mgr, args):
            captured['called_start'] = True

        cmds = dict(_COMMANDS)
        cmds['start'] = fake_start
        monkeypatch.setattr('http_server_cli.cli._COMMANDS', cmds)
        monkeypatch.setattr('http_server_cli.cli.ServerManager', lambda: None)
        monkeypatch.setattr('http_server_cli.cli.ensure_storage', lambda: None)

        import sys
        old_argv = sys.argv
        sys.argv = ['hs', 'this-file-does-not-exist.foobar']
        try:
            from http_server_cli.cli import main
            main()
        except SystemExit:
            pass
        sys.argv = old_argv

        assert not captured['called_start']


class TestListOptions:
    """hs list --port/--path/--short 选项测试"""

    @pytest.fixture
    def mock_manager(self):
        """创建一个包含 2 条测试数据的 mock manager"""
        mgr = MagicMock()
        from http_server_cli.config import Config
        mgr.config = Config()
        mgr.registry.active_servers.return_value = [
            {'port': 8081, 'path': '/tmp/project-alpha', 'pid': 10001,
             'domain': 'localhost', '_alive': True, 'daemon': False,
             'foreground': False, 'started_at': '2026-06-20T00:00:00'},
            {'port': 8082, 'path': '/tmp/project-beta', 'pid': 10002,
             'domain': 'localhost', '_alive': True, 'daemon': True,
             'foreground': False, 'started_at': '2026-06-20T00:05:00'},
        ]
        return mgr

    def test_list_port_only(self, mock_manager, capsys):
        from http_server_cli.cli import _list_servers
        _list_servers(mock_manager, port_only=True)
        captured = capsys.readouterr()
        lines = captured.out.strip().split('\n')
        assert lines == ['8081', '8082']

    def test_list_path_only(self, mock_manager, capsys):
        from http_server_cli.cli import _list_servers
        _list_servers(mock_manager, path_only=True)
        captured = capsys.readouterr()
        lines = captured.out.strip().split('\n')
        assert len(lines) == 2
        assert 'project-alpha' in lines[0]
        assert 'project-beta' in lines[1]

    def test_list_short(self, mock_manager, capsys):
        from http_server_cli.cli import _list_servers
        _list_servers(mock_manager, short=True)
        captured = capsys.readouterr()
        lines = captured.out.strip().split('\n')
        assert len(lines) == 2
        assert lines[0].startswith('8081:')
        assert lines[1].startswith('8082:')

    def test_list_port_highest_priority(self, mock_manager, capsys):
        """三者同给时 --port 优先级最高"""
        from http_server_cli.cli import _list_servers
        _list_servers(mock_manager, port_only=True, path_only=True, short=True)
        captured = capsys.readouterr()
        lines = captured.out.strip().split('\n')
        assert lines == ['8081', '8082']

    def test_list_path_over_short(self, mock_manager, capsys):
        """--path 优先级高于 --short"""
        from http_server_cli.cli import _list_servers
        _list_servers(mock_manager, path_only=True, short=True)
        captured = capsys.readouterr()
        lines = captured.out.strip().split('\n')
        assert 'project-alpha' in lines[0]
        assert ':' not in lines[0]  # not short format


class TestHistoryCommand:
    """hs history 指令测试"""

    def test_history_empty(self, capsys):
        """无历史记录时应提示"""
        from http_server_cli.history import HistoryStore
        store = HistoryStore()
        store.clear()
        from http_server_cli.cli import _cmd_history
        _cmd_history(None, [])
        captured = capsys.readouterr()
        assert 'No history records' in captured.out

    def test_history_json_empty(self, capsys):
        """空历史 --json 应返回合法 JSON"""
        from http_server_cli.history import HistoryStore
        store = HistoryStore()
        store.clear()
        from http_server_cli.cli import _cmd_history
        _cmd_history(None, ['--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data']['count'] == 0

    def test_history_with_records(self, capsys):
        """有历史记录时应显示"""
        from http_server_cli.history import HistoryStore
        store = HistoryStore()
        store.clear()
        store.add(port=8080, path='/Users/test/project', started_at='2026-06-20T10:00:00')
        store.close(port=8080, path='/Users/test/project')
        from http_server_cli.cli import _cmd_history
        _cmd_history(None, [])
        captured = capsys.readouterr()
        assert '8080' in captured.out
        assert '/Users/test/project' in captured.out

    def test_history_json_with_records(self, capsys):
        """历史记录 --json 应输出合法 JSON"""
        from http_server_cli.history import HistoryStore
        store = HistoryStore()
        store.clear()
        store.add(port=8080, path='/Users/test/project', started_at='2026-06-20T10:00:00')
        store.close(port=8080, path='/Users/test/project')
        from http_server_cli.cli import _cmd_history
        _cmd_history(None, ['--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data']['count'] == 1
        assert result['data']['records'][0]['port'] == 8080


class TestSearchCommand:
    """hs search 指令测试"""

    @pytest.fixture
    def search_manager(self):
        """创建包含可搜索数据的 mock manager"""
        mgr = MagicMock()
        from http_server_cli.config import Config
        mgr.config = Config()
        mgr.registry.active_servers.return_value = [
            {'port': 8080, 'path': '/tmp/my-project', 'pid': 10001,
             'domain': 'localhost', '_alive': True, 'daemon': False,
             'foreground': False, 'started_at': '2026-06-20T00:00:00'},
            {'port': 8081, 'path': '/tmp/alpha', 'pid': 10002,
             'domain': 'localhost', '_alive': True, 'daemon': False,
             'foreground': False, 'started_at': '2026-06-20T00:05:00'},
        ]
        return mgr

    def test_search_no_keyword(self, capsys):
        """无关键字时应提示用法"""
        from http_server_cli.cli import _cmd_search
        _cmd_search(None, [])
        captured = capsys.readouterr()
        assert 'Usage' in captured.out

    def test_search_by_port(self, search_manager, capsys):
        """按端口搜索应匹配"""
        from http_server_cli.cli import _cmd_search
        _cmd_search(search_manager, ['8080'])
        captured = capsys.readouterr()
        assert '8080' in captured.out
        assert 'my-project' in captured.out

    def test_search_by_path(self, search_manager, capsys):
        """按路径模糊匹配应生效"""
        from http_server_cli.cli import _cmd_search
        _cmd_search(search_manager, ['alpha'])
        captured = capsys.readouterr()
        assert '8081' in captured.out

    def test_search_case_insensitive(self, search_manager, capsys):
        """忽略大小写"""
        from http_server_cli.cli import _cmd_search
        _cmd_search(search_manager, ['MY-PROJECT'])
        captured = capsys.readouterr()
        assert '8080' in captured.out

    def test_search_no_match(self, search_manager, capsys):
        """无匹配时应提示"""
        from http_server_cli.cli import _cmd_search
        _cmd_search(search_manager, ['nonexistent'])
        captured = capsys.readouterr()
        assert 'No services matching' in captured.out

    def test_search_json(self, search_manager, capsys):
        """--json 应输出合法 JSON"""
        from http_server_cli.cli import _cmd_search
        _cmd_search(search_manager, ['8080', '--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data']['count'] >= 1


class TestUrlFlag:
    """hs start --url 标志测试"""

    def test_url_json_mutual_exclusion(self, capsys):
        """--url --json 同时给出应 exit 2，错误信息走 stderr"""
        import sys
        from unittest.mock import MagicMock

        mgr = MagicMock()
        mgr.config.port = 8080
        mgr.config.domain = 'localhost'

        with pytest.raises(SystemExit) as exc_info:
            _COMMANDS['start'](mgr, ['.', '--url', '--json'])
        assert exc_info.value.code == 2

    def test_url_flag_passed_to_manager(self, monkeypatch):
        """验证 url_only=True 正确传入 manager.start()"""
        captured = {}

        def fake_start(self, **kwargs):
            captured['url_only'] = kwargs.get('url_only', False)
            captured['json'] = kwargs.get('json', False)

        monkeypatch.setattr('http_server_cli.server.ServerManager.start', fake_start)
        monkeypatch.setattr('http_server_cli.cli.ensure_storage', lambda: None)

        import sys
        old_argv = sys.argv
        sys.argv = ['hs', '.', '--url']
        try:
            from http_server_cli.cli import main
            main()
        except SystemExit:
            pass
        sys.argv = old_argv

        assert captured.get('url_only') is True
        assert captured.get('json') is False


class TestBookmarkCLI:
    """hs bookmark 集成测试"""

    def test_bookmark_add_default_cwd(self, tmp_path, capsys):
        """hs bookmark add myapp 默认取 CWD"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path)])
        captured = capsys.readouterr()
        assert '✅' in captured.out
        assert 'myapp' in captured.out

    def test_bookmark_add_with_index(self, tmp_path, capsys):
        """hs bookmark add myapp path -i app.html"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path), '-i', 'app.html'])
        captured = capsys.readouterr()
        assert '✅' in captured.out
        assert 'app.html' in captured.out

    def test_bookmark_add_invalid_index(self, tmp_path, capsys):
        """-i '../../etc/passwd' 应被拒绝"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path), '-i', '../../etc/passwd'])
        captured = capsys.readouterr()
        assert '❌' in captured.err or 'invalid' in captured.err

    def test_bookmark_add_duplicate_name(self, tmp_path, capsys):
        """同名书签 → 报错"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path)])
        capsys.readouterr()
        _bookmark_add(['myapp', str(tmp_path)])
        captured = capsys.readouterr()
        assert 'already exists' in captured.err

    def test_bookmark_show(self, tmp_path, capsys):
        """hs bookmark show 显示详情"""
        from http_server_cli.cli import _bookmark_add, _bookmark_show
        _bookmark_add(['myapp', str(tmp_path)])
        capsys.readouterr()
        _bookmark_show(['myapp'])
        captured = capsys.readouterr()
        assert 'myapp' in captured.out

    def test_bookmark_show_not_found(self, capsys):
        """查询不存在的书签 → 错误"""
        from http_server_cli.cli import _bookmark_show
        _bookmark_show(['nope'])
        captured = capsys.readouterr()
        assert 'not found' in captured.err

    def test_bookmark_implicit_start(self, tmp_path, capsys, monkeypatch):
        """hs myapp 隐式启动 → _cmd_start 被调用并收到正确 path"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path), '-i', 'app.html'])
        capsys.readouterr()

        captured = {}
        def fake_start(mgr, args):
            captured['args'] = args

        monkeypatch.setattr('http_server_cli.cli._COMMANDS',
                            {'start': fake_start, 'bookmark': lambda m, a: None})
        monkeypatch.setattr('http_server_cli.cli.ensure_storage', lambda: None)

        import sys
        old_argv = sys.argv
        sys.argv = ['hs', 'myapp', '-o']
        try:
            from http_server_cli.cli import main
            main()
        except SystemExit:
            pass
        sys.argv = old_argv

        assert 'args' in captured
        # bookmark path 应作为第一个 arg 传入
        assert str(tmp_path) in captured['args']
        # bookmark 的 index_page 应通过 -i 传入
        assert '-i' in captured['args']
        assert 'app.html' in captured['args']
        # 用户显式 flag 保留
        assert '-o' in captured['args']

    def test_bookmark_implicit_start_override(self, tmp_path, capsys, monkeypatch):
        """hs myapp -i other.html 运行时覆盖 bookmark 默认 index"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path), '-i', 'app.html'])
        capsys.readouterr()

        captured = {}
        def fake_start(mgr, args):
            captured['args'] = args

        monkeypatch.setattr('http_server_cli.cli._COMMANDS',
                            {'start': fake_start, 'bookmark': lambda m, a: None})
        monkeypatch.setattr('http_server_cli.cli.ensure_storage', lambda: None)

        import sys
        old_argv = sys.argv
        sys.argv = ['hs', 'myapp', '-i', 'other.html']
        try:
            from http_server_cli.cli import main
            main()
        except SystemExit:
            pass
        sys.argv = old_argv

        # 用户覆盖的 -i other.html 应该在 bookmark 的 -i app.html 之后
        # argparse 后面的值会覆盖前面的
        args_str = ' '.join(captured['args'])
        assert 'other.html' in args_str

    def test_bookmark_kill_by_name(self, tmp_path, capsys):
        """hs kill myapp 按书签名转换为路径"""
        from http_server_cli.cli import _bookmark_add, _cmd_kill
        from unittest.mock import MagicMock
        _bookmark_add(['myapp', str(tmp_path)])
        capsys.readouterr()

        mgr = MagicMock()
        _cmd_kill(mgr, ['myapp'])
        # 验证 manager.kill 被调用时 arg 已转换为路径
        mgr.kill.assert_called_once()
        call_arg = mgr.kill.call_args[0][0]
        assert call_arg == str(tmp_path)

    def test_bookmark_status_by_name(self, tmp_path, capsys):
        """hs status myapp 按书签名转换为路径"""
        from http_server_cli.cli import _bookmark_add, _cmd_status
        from unittest.mock import MagicMock
        _bookmark_add(['myapp', str(tmp_path)])
        capsys.readouterr()

        mgr = MagicMock()
        _cmd_status(mgr, ['myapp'])
        mgr.status.assert_called_once()
        call_arg = mgr.status.call_args[1]['arg']
        assert call_arg == str(tmp_path)
