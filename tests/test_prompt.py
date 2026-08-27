# -*- coding: utf-8 -*-
"""
hs prompt 子命令测试 — AI 对接（skills/ 供给站，参考 html-gen prompt）

覆盖: skills/ 5 篇存在与 frontmatter / 无参列表 / 详情全文 / --brief /
--json 信封（正常 + 错误路径）/ 不存在 skill 报错 + 可用列表 + exit 1。
"""

import json
from pathlib import Path

import pytest

from http_server_cli.cli import _COMMANDS

pytestmark = pytest.mark.spec("cli-interface")

SKILLS_DIR = Path(__file__).resolve().parent.parent / 'skills'
EXPECTED_SKILLS = {'hs-cli', 'hs-bookmark', 'hs-mcp', 'hs-dashboard',
                   'ai-interchange', 'hs-web'}


class TestSkillsDir:
    """skills/ 目录与 frontmatter 合法性"""

    def test_five_skills_exist(self):
        """5 篇 SKILL.md 齐全"""
        found = {d.name for d in SKILLS_DIR.iterdir() if (d / 'SKILL.md').exists()}
        assert EXPECTED_SKILLS == found

    def test_frontmatter_description_present(self):
        """每篇有 YAML frontmatter name + description"""
        for name in EXPECTED_SKILLS:
            text = (SKILLS_DIR / name / 'SKILL.md').read_text(encoding='utf-8')
            assert text.startswith('---\n'), f'{name} 缺 frontmatter 起始'
            assert f'name: {name}' in text
            assert 'description:' in text


class TestPromptCommand:
    """hs prompt 子命令行为"""

    def test_list_no_args(self, capsys):
        """无参列出全部 skill 名与用法行"""
        _COMMANDS['prompt'](None, [])
        out = capsys.readouterr().out
        for name in EXPECTED_SKILLS:
            assert name in out
            assert f'hs prompt {name}' in out

    def test_list_json(self, capsys):
        """--json 信封: status ok + 5 项 + description 非空"""
        _COMMANDS['prompt'](None, ['--json'])
        d = json.loads(capsys.readouterr().out)
        assert d['status'] == 'ok'
        names = {item['name'] for item in d['data']}
        assert names == EXPECTED_SKILLS
        assert all(item['description'] for item in d['data'])

    def test_detail_full_text(self, capsys):
        """详情输出 SKILL.md 全文"""
        _COMMANDS['prompt'](None, ['hs-cli'])
        out = capsys.readouterr().out
        assert '# hs-cli' in out
        assert '安装' in out
        assert 'pip install http-server-cli' in out

    def test_detail_json(self, capsys):
        """详情 --json: data.content 含正文"""
        _COMMANDS['prompt'](None, ['hs-bookmark', '--json'])
        d = json.loads(capsys.readouterr().out)
        assert d['status'] == 'ok'
        assert d['data']['name'] == 'hs-bookmark'
        assert '组合键' in d['data']['content']

    def test_brief(self, capsys):
        """--brief: description + 章节标题"""
        _COMMANDS['prompt'](None, ['hs-mcp', '--brief'])
        out = capsys.readouterr().out
        assert 'MCP 服务对接' in out
        assert '章节:' in out
        assert '工具清单' in out

    def test_not_found_exit(self, capsys):
        """不存在 skill: stderr 报错 + 可用列表 + exit 1"""
        with pytest.raises(SystemExit) as exc:
            _COMMANDS['prompt'](None, ['nope'])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "skill 'nope' 不存在" in captured.err
        assert 'hs-bookmark' in captured.out
        assert 'ai-interchange' in captured.out

    def test_not_found_json(self, capsys):
        """不存在 skill --json: status error 信封 + exit 1"""
        with pytest.raises(SystemExit) as exc:
            _COMMANDS['prompt'](None, ['nope', '--json'])
        assert exc.value.code == 1
        d = json.loads(capsys.readouterr().out)
        assert d['status'] == 'error'
        assert d['data'] is None
        assert '不存在' in d['error']
