# -*- coding: utf-8 -*-
"""
HTTP-SERVER-CL008：web --domain 源头防呆 + 启动横幅修正。

AC（设计件 A1-A3）：
- A1 cmd_failed 时 stderr 输出 `❌ Service '<name>' failed (exit N)`，不打印 ✅ 成功横幅
- A2 `hs web add/update` 在 use_domain=true + hs 型 cmd 时 fail-closed（exit 2）；--force-domain 逃生
- A3 `hs web list/show` 对 hs 型 + use_domain=true 条目打风险标记；JSON 信封新增 domain_risk

全部用例在 `_isolate_data_dir`（conftest autouse）沙箱内运行，绝不触碰真实服务。
"""

import json

import pytest

import http_server_cli.cli as cli
from http_server_cli.services import ServiceStore

HS_CMD = 'hs /Users/jadenli/CodeSpace/daily-tracker -i index.html -o'
NON_HS_CMD = 'dk server start --daemon --open'


# ── _is_hs_cmd 纯函数 ─────────────────────────────────

class TestIsHsCmd:
    def test_hs_literal(self):
        assert cli._is_hs_cmd('hs /path/to/site -o') is True

    def test_non_hs_cmd(self):
        assert cli._is_hs_cmd('dk server start --daemon --open') is False

    def test_empty_cmd(self):
        assert cli._is_hs_cmd('') is False

    def test_hs_as_arg_not_flagged(self):
        """hs 作为参数值不触发（非首 token）"""
        assert cli._is_hs_cmd('echo hs') is False

    # ── SEC-001（round-2）：绕过面收口 ──

    def test_tilde_path(self):
        """`~/bin/hs` —— 旧实现 shlex 不展开 ~ 且非绝对路径 → fail-open"""
        assert cli._is_hs_cmd('~/bin/hs /tmp/site -o') is True

    def test_relative_path(self):
        """`./hs` —— 旧实现相对路径非绝对 → fail-open"""
        assert cli._is_hs_cmd('./hs /tmp/site -o') is True

    def test_absolute_path_any(self):
        """任意绝对路径 basename=hs（旧实现需与 PATH 中 hs 同 inode）"""
        assert cli._is_hs_cmd('/opt/other/bin/hs /tmp/site -o') is True

    def test_uppercase(self):
        """`HS` —— 大小写不敏感"""
        assert cli._is_hs_cmd('HS /tmp/site -o') is True

    def test_exe_suffix(self):
        assert cli._is_hs_cmd('hs.exe /tmp/site -o') is True

    def test_env_wrapper_not_recognized(self):
        """明确边界：`env hs` 不识别（文档已收窄表述）"""
        assert cli._is_hs_cmd('env hs /tmp/site -o') is False

    def test_sh_c_wrapper_not_recognized(self):
        """明确边界：`sh -c 'hs …'` 不识别"""
        assert cli._is_hs_cmd("sh -c 'hs /tmp/site -o'") is False

    def test_unrelated_basename(self):
        assert cli._is_hs_cmd('/usr/bin/hsync /tmp/site') is False


# ── A2：add 防呆 ─────────────────────────────────────

class TestA2AddGuard:

    def test_add_hs_cmd_with_domain_blocked(self, capsys):
        """`hs web add x --cmd 'hs ...' --domain` → exit 2，无副作用"""
        with pytest.raises(SystemExit) as exc:
            cli._web_add(['x', '--cmd', HS_CMD, '--domain'])
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert 'hs 型 cmd 不支持 --domain' in err
        store = ServiceStore()
        assert store.get('x') is None  # 零副作用

    def test_add_hs_cmd_with_domain_force_domain_allowed(self, capsys):
        """--force-domain 逃生开关绕过防呆"""
        cli._web_add(['x', '--cmd', HS_CMD, '--domain', '--force-domain'])
        out = capsys.readouterr().out
        assert '✅' in out
        store = ServiceStore()
        svc = store.get('x')
        assert svc is not None
        assert svc['use_domain'] is True

    def test_add_hs_cmd_no_domain_allowed(self, capsys):
        """不带 --domain 时不触发防呆"""
        cli._web_add(['x', '--cmd', HS_CMD])
        out = capsys.readouterr().out
        assert '✅' in out

    def test_add_non_hs_cmd_with_domain_allowed(self, capsys):
        """非 hs 型 cmd + --domain 正常注册"""
        cli._web_add(['x', '--cmd', NON_HS_CMD, '--domain'])
        out = capsys.readouterr().out
        assert '✅' in out
        store = ServiceStore()
        assert store.get('x')['use_domain'] is True

    def test_add_tilde_hs_cmd_with_domain_blocked(self, capsys):
        """SEC-001：`~/bin/hs` 形态也须拦截（旧实现 fail-open 静默放行）"""
        with pytest.raises(SystemExit) as exc:
            cli._web_add(['x', '--cmd', '~/bin/hs /tmp/site -o', '--domain'])
        assert exc.value.code == 2
        assert ServiceStore().get('x') is None

    def test_add_dot_slash_hs_cmd_with_domain_blocked(self, capsys):
        """SEC-001：`./hs` 形态也须拦截"""
        with pytest.raises(SystemExit) as exc:
            cli._web_add(['x', '--cmd', './hs /tmp/site -o', '--domain'])
        assert exc.value.code == 2
        assert ServiceStore().get('x') is None


# ── A2：update 防呆 ──────────────────────────────────

class TestA2UpdateGuard:

    def test_update_hs_cmd_with_domain_blocked(self, capsys):
        """先注册非 domain 条目，update 加 --domain + hs cmd → exit 2"""
        store = ServiceStore()
        store.add('y', cmd=HS_CMD, use_domain=False)

        with pytest.raises(SystemExit) as exc:
            cli._web_update(['y', '--domain'])
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert 'hs 型 cmd 不支持 --domain' in err
        # 零副作用：use_domain 保持 False
        assert store.get('y')['use_domain'] is False

    def test_update_hs_cmd_with_domain_force_domain_allowed(self, capsys):
        """--force-domain 逃生开关绕过防呆"""
        store = ServiceStore()
        store.add('y', cmd=HS_CMD, use_domain=False)

        cli._web_update(['y', '--domain', '--force-domain'])
        out = capsys.readouterr().out
        assert '✅' in out
        assert store.get('y')['use_domain'] is True

    def test_update_non_hs_cmd_with_domain_allowed(self, capsys):
        store = ServiceStore()
        store.add('y', cmd=NON_HS_CMD, use_domain=False)

        cli._web_update(['y', '--domain'])
        out = capsys.readouterr().out
        assert '✅' in out
        assert store.get('y')['use_domain'] is True

    # ── SEC-002（round-2）：按「更新后的有效状态」判定 ──

    def test_update_to_hs_cmd_without_domain_flag_blocked(self, capsys):
        """既有 use_domain=true + update --cmd '<hs …>'（未传 --domain）→ exit 2

        旧实现只判「本次是否传 --domain」→ rc=0 静默重建 R4 风险态。
        """
        store = ServiceStore()
        store.add('y', cmd=NON_HS_CMD, use_domain=True)

        with pytest.raises(SystemExit) as exc:
            cli._web_update(['y', '--cmd', HS_CMD])
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert 'hs 型 cmd 不支持 --domain' in err
        # 零副作用：cmd 未改写
        assert store.get('y')['cmd'] == NON_HS_CMD

    def test_update_no_domain_wins_over_domain(self, capsys):
        """OBS-002 收敛：--no-domain 与 --domain 同给 → 清除语义赢（有效态 False，不拦）"""
        store = ServiceStore()
        store.add('y', cmd=HS_CMD, use_domain=True)

        cli._web_update(['y', '--no-domain', '--domain'])
        out = capsys.readouterr().out
        assert '✅' in out
        assert store.get('y')['use_domain'] is False

    def test_update_hs_cmd_existing_domain_same_cmd_blocked(self, capsys):
        """风险态条目上任何改动（如 --open）也被拦（有效态仍为 true + hs 型）"""
        store = ServiceStore()
        store.add('y', cmd=HS_CMD, use_domain=True)

        with pytest.raises(SystemExit) as exc:
            cli._web_update(['y', '--open', 'none'])
        assert exc.value.code == 2


# ── A1：cmd_failed 横幅 ─────────────────────────────

class TestA1FailureBanner:

    def test_cmd_failed_no_success_banner(self, monkeypatch, capsys):
        """cmd 退出码非 0 → stderr ❌，stdout 无 ✅"""
        store = ServiceStore()
        store.add('z', cmd='false-cmd', use_domain=False)

        class FakeResult:
            returncode = 2

        monkeypatch.setattr('http_server_cli.cli.subprocess.run',
                            lambda *a, **k: FakeResult())

        with pytest.raises(SystemExit) as exc:
            cli._web_run(['z', '--no-probe'])
        assert exc.value.code == 1  # CL005 D2：cmd_failed → rc=1

        captured = capsys.readouterr()
        assert '✅' not in captured.out  # 不得有成功横幅
        assert '❌' in captured.err and 'failed (exit 2)' in captured.err

    def test_cmd_success_has_success_banner(self, monkeypatch, capsys):
        """cmd 退出码 0 → ✅ 成功横幅"""
        store = ServiceStore()
        store.add('z', cmd='ok-cmd', use_domain=False)

        class FakeResult:
            returncode = 0

        monkeypatch.setattr('http_server_cli.cli.subprocess.run',
                            lambda *a, **k: FakeResult())

        cli._web_run(['z', '--no-probe'])
        captured = capsys.readouterr()
        assert '✅' in captured.out
        assert 'failed' not in captured.err

    def test_cmd_failed_json_envelope_unchanged(self, monkeypatch, capsys):
        """JSON 信封字段零变更：success=false / status=cmd_failed / exit_code"""
        store = ServiceStore()
        store.add('z', cmd='false-cmd', use_domain=False)

        class FakeResult:
            returncode = 3

        monkeypatch.setattr('http_server_cli.cli.subprocess.run',
                            lambda *a, **k: FakeResult())

        with pytest.raises(SystemExit):
            cli._web_run(['z', '--no-probe', '--json'])

        out = capsys.readouterr().out
        envelope = json.loads(out)
        assert envelope['success'] is False
        assert envelope['data']['status'] == 'cmd_failed'
        assert envelope['data']['exit_code'] == 3


# ── A3：风险标记 ─────────────────────────────────────

class TestA3RiskMarkers:

    def test_list_json_domain_risk_true(self, capsys):
        store = ServiceStore()
        store.add('risk', cmd=HS_CMD, use_domain=True)

        cli._web_list(['--json'])
        out = capsys.readouterr().out
        envelope = json.loads(out)
        services = envelope['data']['services']
        svc = next(s for s in services if s['name'] == 'risk')
        assert svc['domain_risk'] is True

    def test_list_json_domain_risk_false_non_hs(self, capsys):
        store = ServiceStore()
        store.add('safe', cmd=NON_HS_CMD, use_domain=True)

        cli._web_list(['--json'])
        out = capsys.readouterr().out
        envelope = json.loads(out)
        services = envelope['data']['services']
        svc = next(s for s in services if s['name'] == 'safe')
        assert svc['domain_risk'] is False

    def test_show_human_risk_marker(self, capsys):
        store = ServiceStore()
        store.add('risk', cmd=HS_CMD, use_domain=True)

        cli._web_show(['risk'])
        out = capsys.readouterr().out
        assert '⚠️' in out and 'hs cmd 不支持 --domain' in out

    def test_show_json_domain_risk(self, capsys):
        store = ServiceStore()
        store.add('risk', cmd=HS_CMD, use_domain=True)

        cli._web_show(['risk', '--json'])
        out = capsys.readouterr().out
        envelope = json.loads(out)
        assert envelope['data']['domain_risk'] is True