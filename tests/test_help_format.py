# -*- coding: utf-8 -*-
"""
Help 打印规范（hm-style grouped help）契约测试。

治理规范: hermes-manager/skills-governance/cli-architecture-patterns.md §8
参考实例: `hm help` / `dk help`

断言结构（每个 help 入口）:
- `=`-rule + `📖` 标题行 + `=`-rule
- 【功能概述】
- `── 分组 ──` 分组条目
- 尾部可选 📋 示例 block
"""

import pytest

import http_server_cli.cli as cli


def _check_grouped_help(text, title_fragment):
    """通用结构断言（hm-style grouped help）。"""
    assert text.startswith('=' * 60), 'help 须以 = 规则线开头'
    assert '📖' in text.splitlines()[1], '第 2 行须为 📖 标题'
    assert title_fragment in text.splitlines()[1]
    assert '【功能概述】' in text, '须含【功能概述】'
    assert '── ' in text, '须含 ── 分组 ── 标题'


class TestMainHelp:

    def test_hs_help_structure(self, capsys):
        cli._cmd_help(None, [])
        out = capsys.readouterr().out
        _check_grouped_help(out, 'http-server')
        assert '· 别名 hs' in out
        assert '📋 示例:' in out
        assert '数据目录: ~/.http-server.cli/' in out

    def test_hs_help_version_line(self, capsys):
        cli._cmd_help(None, [])
        out = capsys.readouterr().out
        from http_server_cli import __version__, __release_date__
        compact = __release_date__.replace('-', '')
        assert f'{__version__}({compact})' in out, '版本行须含 版本号(发布日)'

    def test_hs_help_has_danger_markers(self, capsys):
        """B1: 危险命令（kill / kill-all / prune）须 ⚠️ 标记。"""
        cli._cmd_help(None, [])
        out = capsys.readouterr().out
        assert '⚠️ kill ' in out
        assert '⚠️ kill-all' in out
        assert '⚠️ prune' in out

    def test_bare_hs_still_exit2(self, monkeypatch, capsys):
        """空参数 fail-closed 契约不变（CL007 A2）: 打印帮助 + exit 2。"""
        import sys
        monkeypatch.setattr(cli, 'ensure_storage', lambda: None)
        monkeypatch.setattr(cli, 'ServerManager', lambda: 'MGR')
        monkeypatch.setattr(sys, 'argv', ['hs'])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 2
        _check_grouped_help(capsys.readouterr().out, 'http-server')


class TestSubcommandHelp:

    @pytest.mark.parametrize('fn,fragment', [
        (cli._web_help, 'web 服务注册'),
    ])
    def test_web_help_structure(self, capsys, fn, fragment):
        fn()
        out = capsys.readouterr().out
        _check_grouped_help(out, fragment)
        assert '📋 示例:' in out

    def test_web_help_domain_boundary(self, capsys):
        """A4: --domain 语义边界须在 web help 里。"""
        cli._web_help()
        out = capsys.readouterr().out
        assert '仅 cmd 自身支持 --domain' in out
        assert '--force-domain' in out

    def test_dashboard_help_structure(self, monkeypatch, capsys):
        cli._cmd_dashboard(None, ['help'])
        _check_grouped_help(capsys.readouterr().out, 'dashboard 服务')

    def test_mcp_help_structure(self, monkeypatch, capsys):
        cli._cmd_mcp(None, ['help'])
        _check_grouped_help(capsys.readouterr().out, 'MCP 服务')

    def test_bookmark_help_structure(self, capsys):
        cli._bookmark_help()
        out = capsys.readouterr().out
        _check_grouped_help(out, '书签管理')
        assert '📋 示例:' in out


class TestVersionUnchanged:
    """E1: hs version 保持机器可读格式，不受 help 改造影响。"""

    def test_version_plain(self, capsys):
        from http_server_cli import __version__
        cli._cmd_version(None, [])
        out = capsys.readouterr().out.strip()
        assert out == f'http-server v{__version__}'