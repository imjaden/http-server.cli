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

    def test_bookmark_add_subdirectory_index(self, tmp_path, capsys):
        """-i 'subdir/page.html' 子目录路径应合法"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path), '-i', 'subdir/page.html'])
        captured = capsys.readouterr()
        assert '✅' in captured.out

    def test_bookmark_add_glob_index(self, tmp_path, capsys):
        """-i 'snapshots/*.html' 通配符应原样存储，不展开"""
        import os
        snapshots = tmp_path / 'snapshots'
        snapshots.mkdir()
        (snapshots / 'snapshot-20260704.html').write_text('<old>')

        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path), '-i', 'snapshots/snapshot-*.html'])
        captured = capsys.readouterr()
        assert '✅' in captured.out
        # 应存储原始通配符模式，而非展开后的文件名
        assert 'snapshots/snapshot-*.html' in captured.out
        assert '20260704' not in captured.out  # 不应出现具体文件名

        # 验证书签存储的是通配符模式
        from http_server_cli.bookmark import BookmarkStore
        bm = BookmarkStore().get('myapp')
        assert bm['index_page'] == 'snapshots/snapshot-*.html'

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

    def test_bookmark_implicit_start_glob_resolve(self, tmp_path, capsys, monkeypatch):
        """bookmark 含通配符 * 时，运行时解析为最近修改的文件"""
        import os, time
        snapshots = tmp_path / 'snapshots'
        snapshots.mkdir()
        (snapshots / 'snap-20260704.html').write_text('<old>')
        time.sleep(0.01)
        (snapshots / 'snap-20260715.html').write_text('<new>')

        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path), '-i', 'snapshots/snap-*.html'])
        capsys.readouterr()

        captured = {}
        def fake_start(mgr, args):
            captured['args'] = args

        monkeypatch.setattr('http_server_cli.cli._COMMANDS',
                            {'start': fake_start, 'bookmark': lambda m, a: None})
        monkeypatch.setattr('http_server_cli.cli.ensure_storage', lambda: None)

        import sys
        old_argv = sys.argv
        sys.argv = ['hs', 'myapp']
        try:
            from http_server_cli.cli import main
            main()
        except SystemExit:
            pass
        sys.argv = old_argv

        # 应解析为最近修改的文件
        args_str = ' '.join(captured['args'])
        assert 'snap-20260715.html' in args_str
        assert 'snap-20260704.html' not in args_str

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

    def test_bookmark_update_index(self, tmp_path, capsys):
        """hs bookmark update myapp -i new.html"""
        from http_server_cli.cli import _bookmark_add, _bookmark_update, _bookmark_show
        _bookmark_add(['myapp', str(tmp_path), '-i', 'old.html'])
        capsys.readouterr()

        _bookmark_update(['myapp', '-i', 'new.html'])
        captured = capsys.readouterr()
        assert '✅' in captured.out
        assert 'new.html' in captured.out

    def test_bookmark_update_path(self, tmp_path, capsys):
        """hs bookmark update myapp /new/path"""
        from http_server_cli.cli import _bookmark_add, _bookmark_update, _bookmark_show
        _bookmark_add(['myapp', str(tmp_path)])
        capsys.readouterr()

        # update to same path (tmp_path is still valid)
        _bookmark_update(['myapp', str(tmp_path)])
        captured = capsys.readouterr()
        assert '✅' in captured.out


class TestBookmarkMultiPageCLI:
    """bookmark 同项目多页面（组合键）+ --force 集成测试"""

    def test_bookmark_add_same_path_different_index(self, tmp_path, capsys):
        """同 path 不同 index 两个书签均成功（TC-01）"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['a', str(tmp_path), '-i', 'a.html'])
        capsys.readouterr()
        _bookmark_add(['b', str(tmp_path), '-i', 'b.html'])
        captured = capsys.readouterr()
        assert '✅' in captured.out

        from http_server_cli.bookmark import BookmarkStore
        store = BookmarkStore()
        assert store.get('a') is not None
        assert store.get('b') is not None

    def test_bookmark_add_conflict_without_force(self, tmp_path, capsys):
        """同 path 同 index 无 --force → 报错（TC-02）"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['a', str(tmp_path), '-i', 'a.html'])
        capsys.readouterr()
        _bookmark_add(['b', str(tmp_path), '-i', 'a.html'])
        captured = capsys.readouterr()
        assert 'path+index already bookmarked' in captured.err

    def test_bookmark_add_force_overrides(self, tmp_path, capsys):
        """同 path 同 index + --force → 旧条目被替换（TC-03）"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['a', str(tmp_path), '-i', 'a.html'])
        capsys.readouterr()
        _bookmark_add(['b', str(tmp_path), '-i', 'a.html', '--force'])
        captured = capsys.readouterr()
        assert '✅' in captured.out

        from http_server_cli.bookmark import BookmarkStore
        store = BookmarkStore()
        assert store.get('a') is None
        assert store.get('b') is not None

    def test_bookmark_add_force_name_conflict_still_fails(self, tmp_path, capsys):
        """--force 不覆盖 name 冲突"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path)])
        capsys.readouterr()
        _bookmark_add(['myapp', str(tmp_path), '--force'])
        captured = capsys.readouterr()
        assert 'already exists' in captured.err

    def test_list_multi_label(self, tmp_path, capsys):
        """hs list 文本模式多标签 [a,b]（TC-06）"""
        from http_server_cli.cli import _bookmark_add, _list_servers
        from unittest.mock import MagicMock
        from http_server_cli.config import Config
        _bookmark_add(['a', str(tmp_path), '-i', 'a.html'])
        capsys.readouterr()
        _bookmark_add(['b', str(tmp_path), '-i', 'b.html'])
        capsys.readouterr()

        mgr = MagicMock()
        mgr.config = Config()
        mgr.registry.active_servers.return_value = [
            {'port': 8081, 'path': str(tmp_path), 'pid': 10001,
             'domain': 'localhost', '_alive': True, 'daemon': False,
             'foreground': False, 'started_at': '2026-06-20T00:00:00'},
        ]
        _list_servers(mgr)
        captured = capsys.readouterr()
        assert '[a,b]' in captured.out

    def test_list_json_bookmark_is_list(self, tmp_path, capsys):
        """hs list JSON bookmark 为名称列表（TC-06/07）"""
        from http_server_cli.cli import _bookmark_add, _list_servers
        from unittest.mock import MagicMock
        from http_server_cli.config import Config
        _bookmark_add(['a', str(tmp_path), '-i', 'a.html'])
        capsys.readouterr()
        _bookmark_add(['b', str(tmp_path), '-i', 'b.html'])
        capsys.readouterr()

        mgr = MagicMock()
        mgr.config = Config()
        mgr.registry.active_servers.return_value = [
            {'port': 8081, 'path': str(tmp_path), 'pid': 10001,
             'domain': 'localhost', '_alive': True, 'daemon': False,
             'foreground': False, 'started_at': '2026-06-20T00:00:00'},
            {'port': 8082, 'path': '/tmp/no-bookmark', 'pid': 10002,
             'domain': 'localhost', '_alive': True, 'daemon': False,
             'foreground': False, 'started_at': '2026-06-20T00:05:00'},
        ]
        _list_servers(mgr, json=True)
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        servers = result['data']['servers']
        by_path = {s['path']: s['bookmark'] for s in servers}
        assert by_path[str(tmp_path)] == ['a', 'b']
        assert by_path['/tmp/no-bookmark'] == []  # no-match 为 []（非 null）


class TestBookmarkCLIJson:
    """bookmark 子命令 --json 输出（功能二）"""

    def _add(self, name, path, index=None):
        from http_server_cli.cli import _bookmark_add
        args = [name, str(path)]
        if index:
            args += ['-i', index]
        _bookmark_add(args)

    def test_bookmark_list_json(self, tmp_path, capsys):
        """hs bookmark list --json 合法 JSON 含 count+bookmarks 无 emoji（TC-01）"""
        self._add('myapp', tmp_path, 'app.html')
        capsys.readouterr()
        from http_server_cli.cli import _bookmark_list
        _bookmark_list(['--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'bookmark-list'
        assert result['data']['count'] == 1
        assert result['data']['bookmarks'][0]['name'] == 'myapp'
        # 无 emoji
        assert '📌' not in captured.out
        assert '📊' not in captured.out

    def test_bookmark_show_json(self, tmp_path, capsys):
        """hs bookmark show <name> --json 返回详情（TC-02）"""
        self._add('myapp', tmp_path, 'app.html')
        capsys.readouterr()
        from http_server_cli.cli import _bookmark_show
        _bookmark_show(['myapp', '--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'bookmark-show'
        assert result['data']['name'] == 'myapp'
        assert result['data']['index_page'] == 'app.html'

    def test_bookmark_show_json_not_found(self, capsys):
        """hs bookmark show <缺失> --json 错误走信封（TC-03）"""
        from http_server_cli.cli import _bookmark_show
        _bookmark_show(['nope', '--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is False
        assert result['error'] is not None
        assert 'not found' in result['error']

    def test_bookmark_add_json(self, tmp_path, capsys):
        """hs bookmark add --json 返回 data 含 name/path/index_page（TC-04）"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['myapp', str(tmp_path), '-i', 'app.html', '--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'bookmark-add'
        assert result['data']['name'] == 'myapp'
        assert result['data']['index_page'] == 'app.html'
        assert 'created_at' in result['data']

    def test_bookmark_add_json_conflict(self, tmp_path, capsys):
        """hs bookmark add --json 冲突错误走信封（TC-05）"""
        from http_server_cli.cli import _bookmark_add
        _bookmark_add(['a', str(tmp_path), '-i', 'a.html'])
        capsys.readouterr()
        _bookmark_add(['b', str(tmp_path), '-i', 'a.html', '--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is False
        assert 'path+index already bookmarked' in result['error']

    def test_bookmark_remove_json(self, tmp_path, capsys):
        """hs bookmark remove --json 成功走信封（TC-06）"""
        self._add('myapp', tmp_path)
        capsys.readouterr()
        from http_server_cli.cli import _bookmark_remove
        _bookmark_remove(['myapp', '--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'bookmark-remove'
        assert result['data']['name'] == 'myapp'

    def test_bookmark_remove_json_not_found(self, capsys):
        """hs bookmark remove <缺失> --json 未找到走信封（TC-06）"""
        from http_server_cli.cli import _bookmark_remove
        _bookmark_remove(['nope', '--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is False
        assert 'not found' in result['error']

    def test_bookmark_update_json(self, tmp_path, capsys):
        """hs bookmark update --json 成功走信封（TC-07）"""
        self._add('myapp', tmp_path, 'old.html')
        capsys.readouterr()
        from http_server_cli.cli import _bookmark_update
        _bookmark_update(['myapp', '-i', 'new.html', '--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'bookmark-update'
        assert result['data']['index_page'] == 'new.html'

    def test_bookmark_update_json_not_found(self, capsys):
        """hs bookmark update <缺失> --json 未找到走信封（TC-07）"""
        from http_server_cli.cli import _bookmark_update
        _bookmark_update(['nope', '--json'])
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is False
        assert 'not found' in result['error']

    def test_bookmark_json_error_no_stdout_pollution(self, capsys):
        """json 模式错误不污染 stdout（TC-12）"""
        from http_server_cli.cli import _bookmark_show
        _bookmark_show(['nope', '--json'])
        captured = capsys.readouterr()
        # stdout 必须是单行合法 JSON，无 emoji
        import json
        result = json.loads(captured.out.strip())
        assert result['success'] is False
        assert '📌' not in captured.out
        assert '❌' not in captured.out

    def test_bookmark_json_corrupted_file(self, tmp_path, capsys):
        """bookmarks.json 损坏时各子命令走信封无 traceback（TC-13）"""
        import http_server_cli.bookmark as bm_mod
        bad_path = tmp_path / 'bookmarks.json'
        bad_path.write_text('{this is not json')

        original = bm_mod.BOOKMARKS_PATH
        bm_mod.BOOKMARKS_PATH = str(bad_path)
        try:
            from http_server_cli.cli import _bookmark_list, _bookmark_show, _bookmark_remove
            for fn, args in ((_bookmark_list, ['--json']),
                             (_bookmark_show, ['myapp', '--json']),
                             (_bookmark_remove, ['myapp', '--json'])):
                fn(args)
                captured = capsys.readouterr()
                import json as _json
                result = _json.loads(captured.out)
                assert result['success'] is False
                assert result['error'] == 'bookmarks file corrupted'
                # 无 traceback 冒泡到 stderr
                assert 'Traceback' not in captured.err
        finally:
            bm_mod.BOOKMARKS_PATH = original


class TestManageJson:
    """mcp / dashboard 管理子命令 --json 输出"""

    def _make_mgr(self, monkeypatch, name, entry):
        from unittest.mock import MagicMock
        mreg = MagicMock()
        mreg.find.return_value = entry
        # _manage_mcp/_manage_dashboard 内部 `from registry_managed import ManagedRegistry`，
        # 需 patch 源模块
        monkeypatch.setattr(
            'http_server_cli.registry_managed.ManagedRegistry', lambda: mreg)
        return mreg

    def _patch_alive(self, monkeypatch, alive):
        # is_process_alive / is_port_in_use 是函数内局部导入，patch 源模块 utils
        monkeypatch.setattr('http_server_cli.utils.is_process_alive',
                            lambda pid: alive)
        monkeypatch.setattr('http_server_cli.utils.is_port_in_use',
                            lambda port: alive)

    def test_mcp_status_json_not_running(self, monkeypatch, capsys):
        """hs mcp status --json 未运行 → error 信封（TC-08）"""
        self._make_mgr(monkeypatch, 'mcp', None)
        from http_server_cli.cli import _manage_mcp
        _manage_mcp('status', json_mode=True)
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is False
        assert result['command'] == 'mcp-status'
        assert result['error'] == 'MCP not running'

    def test_mcp_status_json_running(self, monkeypatch, capsys):
        """hs mcp status --json 运行 → 成功信封（TC-08）"""
        entry = {'name': 'mcp', 'port': 8181, 'pid': 12345,
                 'started_at': '2026-06-20T00:00:00', 'transport': 'sse'}
        self._make_mgr(monkeypatch, 'mcp', entry)
        self._patch_alive(monkeypatch, True)
        from http_server_cli.cli import _manage_mcp
        _manage_mcp('status', json_mode=True)
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'mcp-status'
        assert result['data']['name'] == 'mcp'
        assert result['data']['alive'] is True

    def test_mcp_stop_json(self, monkeypatch, capsys):
        """hs mcp stop --json → 成功信封（TC-09）"""
        entry = {'name': 'mcp', 'port': 8181, 'pid': 12345,
                 'started_at': '2026-06-20T00:00:00', 'transport': 'sse'}
        self._make_mgr(monkeypatch, 'mcp', entry)
        self._patch_alive(monkeypatch, False)
        from http_server_cli.cli import _manage_mcp
        _manage_mcp('stop', json_mode=True)
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'mcp-stop'
        assert result['data']['stopped'] is True

    def test_dashboard_status_json_not_running(self, monkeypatch, capsys):
        """hs dashboard status --json 未运行 → error 信封（TC-10）"""
        self._make_mgr(monkeypatch, 'dashboard', None)
        from http_server_cli.cli import _manage_dashboard
        _manage_dashboard('status', json_mode=True)
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is False
        assert result['command'] == 'dashboard-status'
        assert result['error'] == 'dashboard not running'

    def test_dashboard_status_json_running(self, monkeypatch, capsys):
        """hs dashboard status --json 运行 → 成功信封（TC-10）"""
        entry = {'name': 'dashboard', 'port': 8180, 'pid': 12345,
                 'started_at': '2026-06-20T00:00:00'}
        self._make_mgr(monkeypatch, 'dashboard', entry)
        self._patch_alive(monkeypatch, True)
        from http_server_cli.cli import _manage_dashboard
        _manage_dashboard('status', json_mode=True)
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'dashboard-status'
        assert result['data']['name'] == 'dashboard'
        assert result['data']['alive'] is True

    def test_dashboard_stop_json(self, monkeypatch, capsys):
        """hs dashboard stop --json → 成功信封（TC-11）"""
        entry = {'name': 'dashboard', 'port': 8180, 'pid': 12345,
                 'started_at': '2026-06-20T00:00:00'}
        self._make_mgr(monkeypatch, 'dashboard', entry)
        self._patch_alive(monkeypatch, False)
        from http_server_cli.cli import _manage_dashboard
        _manage_dashboard('stop', json_mode=True)
        captured = capsys.readouterr()
        import json
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'dashboard-stop'
        assert result['data']['stopped'] is True
