# -*- coding: utf-8 -*-
"""HTTP-SERVER-CL005：输出通道契约 / `hs web` 退出码 / 目录级启动锁 / 派发件模板。

对应设计 §6 测试清单（`documents/http-server-cl005-hardening-design-v1.2-20260923.md`）：
T1–T27。锁相关用例直接操作 `utils.lock_dir()`（派生自 DATA_DIR ⇒ conftest autouse 隔离）。
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import http_server_cli.cli as cli
from http_server_cli import utils as hs_utils
from http_server_cli.server import ServerManager
from http_server_cli.services import ServiceStore

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

pytestmark = pytest.mark.spec("cl005-hardening")


# ── 工具 ────────────────────────────────────────────────

def _abs(path):
    return os.path.realpath(path)


def _write_lock(target_dir, payload, age_s=0.0):
    """直接写锁文件（模拟他人持有）；age_s > 0 时把 mtime 回拨。"""
    lf = hs_utils.lock_path(_abs(target_dir))
    os.makedirs(os.path.dirname(lf), exist_ok=True)
    with open(lf, 'w', encoding='utf-8') as f:
        f.write(payload if isinstance(payload, str) else json.dumps(payload))
    if age_s:
        old = time.time() - age_s
        os.utime(lf, (old, old))
    return lf


def _spawn_cli_like_holder(seconds=15):
    """起一个命令行含 `http_server_cli` 的活进程，用作「有效锁 holder」。"""
    code = f'import http_server_cli, time; time.sleep({seconds})'
    env = dict(os.environ, PYTHONPATH=str(REPO / 'src'))
    proc = subprocess.Popen([PY, '-c', code], env=env)
    return proc


def _mocked_start_env(monkeypatch, listening=None):
    """mock 掉启动副作用。

    要点：只替换 `http_server_cli.server`/`cli` 模块里的 `subprocess`/`webbrowser` 绑定，
    不污染 stdlib 全局（否则 `utils.get_process_info` 等会拿到 None 而崩）。
    `listening` 为可变集合，模拟「已监听端口」——启动成功后端口即被视为占用。
    """
    import types
    listening = listening if listening is not None else set()
    popen_calls = []
    chosen = {'port': None}

    def _popen(*a, **kw):
        popen_calls.append(a)
        if chosen['port'] is not None:
            listening.add(chosen['port'])        # 启动后该端口进入监听
        m = MagicMock()
        m.pid = 90000 + len(popen_calls)
        m.poll.return_value = None
        return m

    def _find_available(start):
        chosen['port'] = start
        return start

    fake_subprocess = types.SimpleNamespace(Popen=_popen, run=lambda *a, **kw: None,
                                            DEVNULL=-3, PIPE=-1, STDOUT=-2)
    monkeypatch.setattr('http_server_cli.server.subprocess', fake_subprocess)
    monkeypatch.setattr('http_server_cli.server.webbrowser',
                        types.SimpleNamespace(open=lambda url: True))
    monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p in listening)
    monkeypatch.setattr('http_server_cli.server.is_process_alive', lambda pid: True)
    monkeypatch.setattr('http_server_cli.server.get_pid_by_lsof', lambda p, listen_only=False: [])
    monkeypatch.setattr('http_server_cli.server.find_available_port', _find_available)
    monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: p in listening)
    monkeypatch.setattr('http_server_cli.registry.is_process_alive', lambda pid: True)
    # 锁协议用的进程判据（utils 侧）：本进程视为「本 CLI」，命令行 token 命中
    monkeypatch.setattr('http_server_cli.utils.is_process_alive', lambda pid: True)
    monkeypatch.setattr('http_server_cli.utils.get_process_info',
                        lambda pid: {'user': 'me', 'command': '/x/python -m http_server_cli start'})
    return popen_calls, listening


# ── T1–T5：输出通道 ─────────────────────────────────────

class TestOutputChannels:

    def test_t1_eprint_goes_to_stderr(self, capsys):
        hs_utils.eprint('boom', '❌')
        captured = capsys.readouterr()
        assert captured.out == ''
        assert 'boom' in captured.err

    def test_t2_print_msg_goes_to_stdout(self, capsys):
        hs_utils.print_msg('hello', '📊')
        captured = capsys.readouterr()
        assert 'hello' in captured.out
        assert captured.err == ''

    def test_t3_config_output_is_stdout(self, capsys):
        from http_server_cli.config import Config
        Config().show()
        captured = capsys.readouterr()
        assert 'port' in captured.out
        assert captured.err == ''

    def test_t4_set_error_is_stderr_only(self, capsys):
        """错误文案只走 stderr 且 rc=2（O7：用法错误统一 exit 2）"""
        from http_server_cli.config import Config
        with pytest.raises(SystemExit) as exc:
            cli._handle_set(['port', 'abc'])
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ''
        assert 'Invalid port number' in captured.err or 'must match' in captured.err

    def test_t5_start_json_envelope_is_parseable(self, temp_project, capsys, monkeypatch):
        _mocked_start_env(monkeypatch)
        monkeypatch.setattr('http_server_cli.server.time.sleep', lambda s: None)
        mgr = ServerManager()
        assert mgr.start(path=temp_project, json=True) is True
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is True and payload['command'] == 'start'


# ── T6–T15：`hs web` 退出码（web 单测已同步至 tests/test_web.py）──

class TestWebExitCodes:

    def _run_web(self, argv):
        try:
            cli._COMMANDS['web'](None, argv)
        except SystemExit as e:
            return e.code
        return 0

    def test_t6_add_missing_cmd_is_usage_error(self, capsys):
        assert self._run_web(['add', 'a']) == 2
        capsys.readouterr()

    def test_t7_add_conflict_is_usage_error(self, capsys):
        assert self._run_web(['add', 'list', '--cmd', 'echo a']) == 2
        capsys.readouterr()

    def test_t8_add_duplicate_is_usage_error(self, capsys):
        assert self._run_web(['add', 'a', '--cmd', 'echo a']) == 0
        assert self._run_web(['add', 'a', '--cmd', 'echo b']) == 2   # F-3：ValueError → 2
        capsys.readouterr()

    def test_t9_update_empty_cmd_is_usage_error(self, capsys):
        assert self._run_web(['add', 'a', '--cmd', 'echo a']) == 0
        assert self._run_web(['update', 'a', '--cmd', '']) == 2      # F-3：ValueError → 2
        capsys.readouterr()

    def test_t10_show_not_found_is_runtime_error(self, capsys):
        assert self._run_web(['show', 'nope']) == 1
        capsys.readouterr()

    def test_t11_remove_not_found_is_runtime_error(self, capsys):
        assert self._run_web(['remove', 'nope']) == 1
        capsys.readouterr()

    def test_t12_list_corrupted_services_is_runtime_error(self, capsys, monkeypatch):
        from http_server_cli.services import DataCorruptionError
        monkeypatch.setattr('http_server_cli.services.ServiceStore.list_all',
                            lambda self: (_ for _ in ()).throw(DataCorruptionError()))
        assert self._run_web(['list']) == 1
        capsys.readouterr()

    def test_t13_run_cmd_failure_is_runtime_error(self, capsys, monkeypatch):
        import types
        ServiceStore().add('a', cmd='false')
        mock = MagicMock()
        mock.returncode = 3
        monkeypatch.setattr('http_server_cli.cli.subprocess',
                            types.SimpleNamespace(run=lambda *a, **kw: mock))
        assert self._run_web(['a', '--no-probe']) == 1              # F-3：cmd 失败 → 1
        captured = capsys.readouterr()
        assert 'exited with code 3' in captured.err

    def test_t13b_run_cmd_failure_json_envelope(self, capsys, monkeypatch):
        import types
        ServiceStore().add('a', cmd='false')
        mock = MagicMock()
        mock.returncode = 3
        monkeypatch.setattr('http_server_cli.cli.subprocess',
                            types.SimpleNamespace(run=lambda *a, **kw: mock))
        assert self._run_web(['a', '--no-probe', '--json']) == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is False
        assert payload['data']['status'] == 'cmd_failed'
        assert payload['data']['exit_code'] == 3

    def test_t14_run_corrupted_services_is_runtime_error(self, capsys, monkeypatch):
        from http_server_cli.services import DataCorruptionError
        monkeypatch.setattr('http_server_cli.services.ServiceStore.get',
                            lambda self, n: (_ for _ in ()).throw(DataCorruptionError()))
        assert self._run_web(['a']) == 1
        capsys.readouterr()

    def test_t15_web_without_subcommand_is_help(self, capsys):
        assert self._run_web([]) == 0
        assert 'hs web' in capsys.readouterr().out


# ── T16：并发启动互斥（单元级：Popen/端口 mock，断言锁 + 幂等协作）──

class TestStartLockConcurrency:

    def test_t16_five_concurrent_starts_single_winner(self, temp_project, monkeypatch, capsys):
        popen_calls, listening = _mocked_start_env(monkeypatch)
        monkeypatch.setattr('http_server_cli.server.time.sleep', lambda s: None)
        monkeypatch.setattr('http_server_cli.utils.time.sleep', lambda s: None)
        results = []

        def _go():
            results.append(ServerManager().start(path=temp_project, url_only=True))

        threads = [threading.Thread(target=_go) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        capsys.readouterr()
        entries = [e for e in ServerManager().registry.all()
                   if e.get('path') == _abs(temp_project)]
        assert len(entries) == 1, entries            # 同目录仅 1 条登记
        assert len(popen_calls) == 1, popen_calls    # 仅 1 次真实启动
        assert all(r is True for r in results)       # 其余走幂等/等待后命中

    def test_t20_html_shortcut_shares_lock_with_dir(self, temp_project):
        """F-1①：`hs index.html` 与 `hs <dir>` 必须落到同一把锁。"""
        page = Path(temp_project) / 'page.html'
        page.write_text('<html><body>hi</body></html>', encoding='utf-8')
        mgr = ServerManager()
        abs_dir, idx, ok = mgr._prepare_start_target(str(page), None, False, True)
        assert ok is True and idx == 'page.html'
        assert abs_dir == _abs(temp_project)          # html 入口提取父目录
        assert hs_utils.lock_path(abs_dir) == hs_utils.lock_path(_abs(temp_project))


# ── T17/T18/T21/T27：锁协议（真实 pid 判据，不用全局 mock）──

class TestStartLockProtocol:

    def _fast(self, monkeypatch):
        monkeypatch.setattr('http_server_cli.server.LOCK_WAIT', 0.5)
        monkeypatch.setattr('http_server_cli.server.LOCK_POLL', 0.05)

    def test_t17_valid_holder_is_fail_closed(self, temp_project, capsys, monkeypatch):
        self._fast(monkeypatch)
        holder = _spawn_cli_like_holder()
        try:
            _write_lock(temp_project, {'path': _abs(temp_project), 'pid': holder.pid,
                                       'started_mono': hs_utils.mono_now(),
                                       'started_at': '2026-09-23 00:00:00'})
            assert ServerManager().start(path=temp_project) is False
            captured = capsys.readouterr()
            assert '另一实例正在启动' in captured.err
            assert os.path.exists(hs_utils.lock_path(_abs(temp_project)))   # 他人锁未被删
        finally:
            holder.kill()
            holder.wait()

    def test_t27_negative_age_does_not_delete_lock(self, temp_project, capsys, monkeypatch):
        """F-2a：负龄（跨重启/时钟异常）不判 stale ⇒ 不删锁、fail-closed。"""
        self._fast(monkeypatch)
        holder = _spawn_cli_like_holder()
        try:
            _write_lock(temp_project, {'path': _abs(temp_project), 'pid': holder.pid,
                                       'started_mono': hs_utils.mono_now() + 1e6,
                                       'started_at': '2026-09-23 00:00:00'})
            assert ServerManager().start(path=temp_project) is False
            capsys.readouterr()
            assert os.path.exists(hs_utils.lock_path(_abs(temp_project)))   # 负龄锁被保留
        finally:
            holder.kill()
            holder.wait()

    def test_t18a_stale_lock_dead_pid_is_cleared(self, temp_project, monkeypatch):
        _write_lock(temp_project, {'path': _abs(temp_project), 'pid': 999999,
                                   'started_mono': hs_utils.mono_now(), 'started_at': ''})
        state, holder, lockfile = hs_utils.acquire_start_lock(_abs(temp_project))
        assert state == 'hit'                                  # 清掉死 pid 锁后取得
        hs_utils.release_start_lock(lockfile)

    def test_t18b_stale_lock_expired_ttl_is_cleared(self, temp_project, monkeypatch, capsys):
        _mocked_start_env(monkeypatch)
        monkeypatch.setattr('http_server_cli.server.time.sleep', lambda s: None)
        holder = _spawn_cli_like_holder()
        try:
            monkeypatch.setattr(hs_utils, 'LOCK_TTL', 0.01)
            _write_lock(temp_project, {'path': _abs(temp_project), 'pid': holder.pid,
                                       'started_mono': hs_utils.mono_now() - 5.0, 'started_at': ''})
            assert ServerManager().start(path=temp_project, url_only=True) is True
            capsys.readouterr()
        finally:
            holder.kill()
            holder.wait()

    def test_t18c_unparsable_old_lock_is_cleared(self, temp_project):
        _write_lock(temp_project, 'not-json', age_s=5.0)
        state, holder, lockfile = hs_utils.acquire_start_lock(_abs(temp_project))
        assert state == 'hit'
        hs_utils.release_start_lock(lockfile)

    def test_t21_midwrite_fresh_lock_is_waited_not_deleted(self, temp_project):
        """F-1②：空锁文件 + mtime 新鲜 ⇒ 视为 holder 正在写，绝不删。"""
        lf = _write_lock(temp_project, '', age_s=0.0)
        state, holder, lockfile = hs_utils.acquire_start_lock(_abs(temp_project))
        assert state == 'busy' and holder is None
        assert os.path.exists(lf)

    def test_t19_release_respects_ownership(self, temp_project, capsys):
        holder = _spawn_cli_like_holder()
        try:
            lf = _write_lock(temp_project, {'path': _abs(temp_project), 'pid': holder.pid,
                                            'started_mono': hs_utils.mono_now(), 'started_at': ''})
            hs_utils.release_start_lock(lf)                    # 非本进程锁 ⇒ 不删
            assert os.path.exists(lf)
            capsys.readouterr()
        finally:
            holder.kill()
            holder.wait()

    def test_t24_lock_released_after_start(self, temp_project, monkeypatch, capsys):
        _mocked_start_env(monkeypatch)
        monkeypatch.setattr('http_server_cli.server.time.sleep', lambda s: None)
        assert ServerManager().start(path=temp_project, url_only=True) is True
        capsys.readouterr()
        assert not os.path.exists(hs_utils.lock_path(_abs(temp_project)))

    def test_t26_clock_gettime_monotonic_is_cross_process_comparable(self):
        """F-2a：mono_now 必须用 CLOCK_MONOTONIC（跨进程可比），不得回退 time.monotonic。"""
        code = ('import sys; sys.path.insert(0, %r); from http_server_cli.utils import mono_now;'
                ' print(repr(mono_now()))' % str(REPO / 'src'))
        outs = []
        for interp in [PY] + ([p for p in ['/usr/bin/python3'] if os.path.exists(p)]):
            vals = []
            for _ in range(2):
                r = subprocess.run([interp, '-c', code], capture_output=True, text=True)
                assert r.returncode == 0, r.stderr
                vals.append(float(r.stdout.strip()))
            assert all(v > 1e4 for v in vals), (interp, vals)      # uptime 量级，非近零
            assert abs(vals[0] - vals[1]) < 60, (interp, vals)     # 跨进程一致（同机同钟）
            outs.append((interp, vals))
        assert len(outs) >= 1

    def test_src_does_not_use_time_monotonic(self):
        """AST 级检查：代码里不得出现 time.monotonic（docstring 中的反例说明不算）。"""
        import ast
        src = (REPO / 'src' / 'http_server_cli' / 'utils.py').read_text(encoding='utf-8')
        bad = [n for n in ast.walk(ast.parse(src))
               if isinstance(n, ast.Attribute) and n.attr == 'monotonic']
        assert bad == []
        assert 'time.clock_gettime(time.CLOCK_MONOTONIC)' in src


# ── T28：注册失败回滚（SEC-1 / 设计 D3.5）───────────────

class TestRegistryRollback:

    def test_t28_registry_add_failure_terminates_runner(self, temp_project, capsys, monkeypatch):
        """D3.5：registry.add 抛异常 ⇒ 先终止本次 runner（不产生孤儿）并报运行期失败。"""
        popen_calls, _ = _mocked_start_env(monkeypatch)
        monkeypatch.setattr('http_server_cli.server.time.sleep', lambda s: None)
        killed = []
        monkeypatch.setattr('http_server_cli.server._terminate_runner',
                            lambda pid: (killed.append(pid), True)[1])
        from http_server_cli.registry import Registry

        def boom(self, **kw):
            raise OSError('disk full')

        monkeypatch.setattr(Registry, 'add', boom)
        assert ServerManager().start(path=temp_project, url_only=True) is False
        captured = capsys.readouterr()
        assert killed == [90001]                                   # 本次 runner 被终止
        assert 'Registry write failed' in captured.err
        assert not os.path.exists(hs_utils.lock_path(_abs(temp_project)))   # 锁已释放（finally）

    def test_t28b_history_add_failure_json_envelope(self, temp_project, capsys, monkeypatch):
        """history.add 失败同样回滚；`--json` 走信封（stdout 可解析、success=false）。"""
        _mocked_start_env(monkeypatch)
        monkeypatch.setattr('http_server_cli.server.time.sleep', lambda s: None)
        killed = []
        monkeypatch.setattr('http_server_cli.server._terminate_runner',
                            lambda pid: (killed.append(pid), True)[1])
        from http_server_cli.history import HistoryStore

        def boom(self, **kw):
            raise OSError('read-only fs')

        monkeypatch.setattr(HistoryStore, 'add', boom)
        assert ServerManager().start(path=temp_project, json=True) is False
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is False and 'Registry write failed' in payload['error']
        assert killed == [90001]
        assert not os.path.exists(hs_utils.lock_path(_abs(temp_project)))


# ── T25：派发件模板 ─────────────────────────────────────

class TestReviewDispatchTemplate:

    def _run(self, *args):
        script = REPO / 'scripts' / 'review-dispatch.sh'
        return subprocess.run(['bash', str(script)] + list(args),
                              capture_output=True, text=True)

    def test_t25_dry_run_derives_both_paths(self):
        r = self._run('--target', str(REPO), '--code', 'HTTP-SERVER-CL005',
                      '--project', 'http-server.cli', '--step', 'design-rereview2',
                      '--date', '20260923', '--prompt', 'cache/review-prep/x.md', '--dry-run')
        assert r.returncode == 0, r.stderr
        assert 'HTTP-SERVER-CL005-design-rereview2-dispatch.log' in r.stdout
        assert '20260923-http-server.cli-HTTP-SERVER-CL005-design-rereview2.json' in r.stdout

    def test_t25b_missing_args_fail(self):
        r = self._run('--dry-run')
        assert r.returncode != 0

    def test_t25d_generates_shell_with_three_paths(self, tmp_path):
        """生成物：壳内 LOG/PROMPT/USAGE 三行由推导值填充，且过 bash -n。"""
        target = tmp_path / 'fake-repo'
        (target / 'cache' / 'review-prep').mkdir(parents=True)
        (target / 'cache' / 'closed-loop').mkdir(parents=True)
        prompt = target / 'cache' / 'review-prep' / 'prompt-x.md'
        prompt.write_text('审计提示词', encoding='utf-8')
        r = self._run('--target', str(target), '--code', 'HTTP-SERVER-CL005',
                      '--project', 'http-server.cli', '--step', 'audit',
                      '--date', '20260923', '--prompt', 'cache/review-prep/prompt-x.md',
                      '--no-run')
        assert r.returncode == 0, r.stderr
        shell = target / 'cache' / 'review-prep' / 'dispatch-http-server.cli-http-server-cl005-audit-20260923.sh'
        assert shell.exists()
        body = shell.read_text(encoding='utf-8')
        assert 'LOG="%s/cache/closed-loop/HTTP-SERVER-CL005-audit-dispatch.log"' % target in body
        assert 'USAGE="%s/cache/closed-loop/20260923-http-server.cli-HTTP-SERVER-CL005-audit.json"' % target in body
        assert 'PROMPT="%s"' % prompt in body
        assert '[ ! -s "$USAGE" ]' in body          # ② usage 非空自校验
        assert subprocess.run(['bash', '-n', str(shell)]).returncode == 0

    def test_t25e_empty_prompt_is_usage_error(self, tmp_path):
        target = tmp_path / 'empty-repo'
        (target / 'cache').mkdir(parents=True)
        (target / 'p.md').write_text('', encoding='utf-8')
        r = self._run('--target', str(target), '--code', 'X-CL001', '--project', 'p',
                      '--step', 'audit', '--date', '20260923', '--prompt', 'p.md', '--no-run')
        assert r.returncode == 2 and '提示词文件缺失或为空' in r.stderr

    def test_t25c_case_normalisation(self):
        r = self._run('--target', str(REPO), '--code', 'http-server-cl005',
                      '--project', 'http-server.cli', '--step', 'audit',
                      '--date', '20260923', '--prompt', 'p.md', '--dry-run')
        assert r.returncode == 0, r.stderr
        assert 'HTTP-SERVER-CL005-audit-dispatch.log' in r.stdout
        assert '20260923-http-server.cli-HTTP-SERVER-CL005-audit.json' in r.stdout


# ── O7/O8 收口：用法/运行期退出码三态扩展 ───────────────

def _patch_managed(monkeypatch, entry):
    """把 ManagedRegistry 与进程/端口判据打桩（照 test_port_flag 口径）"""
    class _MReg:
        def find(self, name=None):
            return entry

        def remove(self, name=None):
            pass

    monkeypatch.setattr('http_server_cli.registry_managed.ManagedRegistry', _MReg)
    monkeypatch.setattr('http_server_cli.utils.is_process_alive', lambda pid: False)
    monkeypatch.setattr('http_server_cli.utils.is_port_in_use', lambda p: False)


class TestOSeriesExitCodes:
    """O7：`set`/`search` 用法错误 ⇒ rc=2；O8：`dashboard`/`mcp` stop·restart 未运行 ⇒ rc=1（status 保持 0）"""

    def test_o7_set_usage_exit2_matrix(self):
        for args in ([], ['port'], ['port', 'abc'], ['port', '70000'],
                     ['domain', 'a;b'], ['unknown', 'x']):
            with pytest.raises(SystemExit) as exc:
                cli._handle_set(list(args))
            assert exc.value.code == 2, args

    def test_o7_set_json_envelope_exit2(self, capsys):
        with pytest.raises(SystemExit) as exc:
            cli._handle_set(['port', 'abc', '--json'])
        assert exc.value.code == 2
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is False and 'Invalid port number' in payload['error']

    def test_o7_search_usage_exit2(self, capsys):
        with pytest.raises(SystemExit) as exc:
            cli._cmd_search(None, [])
        assert exc.value.code == 2
        assert capsys.readouterr().out == ''          # 非 json：stdout 零污染（用法提示走 stderr）

    def test_o7_search_json_usage_envelope(self, capsys):
        with pytest.raises(SystemExit) as exc:
            cli._cmd_search(None, ['--json'])
        assert exc.value.code == 2
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is False and 'Usage' in payload['error']

    def test_o8_dashboard_stop_not_running_exit1(self, monkeypatch, capsys):
        _patch_managed(monkeypatch, None)
        with pytest.raises(SystemExit) as exc:
            cli._manage_dashboard('stop', json_mode=False)
        assert exc.value.code == 1
        assert 'not running' in capsys.readouterr().err

    def test_o8_dashboard_status_not_running_rc0(self, monkeypatch, capsys):
        _patch_managed(monkeypatch, None)
        cli._manage_dashboard('status', json_mode=False)     # 查询：不抛 SystemExit
        assert 'not running' in capsys.readouterr().out

    def test_o8_dashboard_stop_json_envelope_exit1(self, monkeypatch, capsys):
        _patch_managed(monkeypatch, None)
        with pytest.raises(SystemExit) as exc:
            cli._manage_dashboard('stop', json_mode=True)
        assert exc.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload['success'] is False and payload['error'] == 'dashboard not running'

    def test_o8_mcp_stop_not_running_exit1(self, monkeypatch, capsys):
        _patch_managed(monkeypatch, None)
        with pytest.raises(SystemExit) as exc:
            cli._manage_mcp('stop', json_mode=False)
        assert exc.value.code == 1
        assert 'not running' in capsys.readouterr().err

    def test_o8_mcp_status_not_running_rc0(self, monkeypatch, capsys):
        _patch_managed(monkeypatch, None)
        cli._manage_mcp('status', json_mode=False)
        assert 'not running' in capsys.readouterr().out


class TestMachineModeStdoutPurity:
    """O9：机器模式（--json）stdout 只允许可解析信封；附带文案一律走 stderr"""

    def _run(self, fn, capsys):
        try:
            fn()
        except SystemExit:
            pass
        return capsys.readouterr()

    def test_o9_json_commands_stdout_parseable(self, capsys):
        mgr = ServerManager()
        cases = {
            'list': lambda: cli._COMMANDS['list'](mgr, ['--json']),
            'history': lambda: cli._COMMANDS['history'](mgr, ['--json']),
            'status': lambda: cli._COMMANDS['status'](mgr, ['9999', '--json']),
            'kill': lambda: cli._COMMANDS['kill'](mgr, ['9999', '--json']),
            'search': lambda: cli._COMMANDS['search'](mgr, ['nonexistent', '--json']),
            'set': lambda: cli._COMMANDS['set'](mgr, ['port', 'abc', '--json']),
            'web-list': lambda: cli._COMMANDS['web'](None, ['list', '--json']),
        }
        bad = []
        for name, fn in cases.items():
            cap = self._run(fn, capsys)
            try:
                payload = json.loads(cap.out)
            except Exception as e:                     # noqa: BLE001
                bad.append((name, 'stdout 不可解析: %r' % cap.out[:120], str(e)))
                continue
            if 'success' not in payload:
                bad.append((name, '信封缺 success 键', cap.out[:80]))
        assert not bad, bad


class TestOLockEnvOverride:
    """O10：锁常量支持环境变量覆盖（重负载/慢盘调参），非法值退回默认；O11：HS_DATA_DIR 覆盖数据目录"""

    def test_o11_data_dir_env_override(self, tmp_path):
        """子进程级：HS_DATA_DIR → DATA_DIR 与派生路径（真实接线，非 mock）"""
        env = dict(os.environ)
        env.update({'HS_DATA_DIR': str(tmp_path), 'PYTHONPATH': str(REPO / 'src')})
        r = subprocess.run(
            [sys.executable, '-c',
             'import http_server_cli.utils as u;'
             'print(u.DATA_DIR);print(u.REGISTRY_PATH);print(u.LOG_DIR)'],
            capture_output=True, text=True, timeout=60, env=env)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        assert lines and all(l.startswith(str(tmp_path)) for l in lines), r.stdout + r.stderr

    def test_o10_helper_semantics(self, monkeypatch):
        from http_server_cli.utils import _lock_env
        monkeypatch.setenv('HS_X', '2.5')
        assert _lock_env('HS_X', 1.0) == 2.5
        for bad in ('abc', '', '-1', '0'):
            monkeypatch.setenv('HS_X', bad)
            assert _lock_env('HS_X', 1.0) == 1.0, bad
        monkeypatch.delenv('HS_X', raising=False)
        assert _lock_env('HS_X', 1.0) == 1.0

    def test_o10_env_applied_at_import(self):
        """子进程级：env → 模块常量（真实接线，非 mock）"""
        env = dict(os.environ)
        env.update({'HS_LOCK_WRITE_GRACE': '2.5', 'HS_LOCK_TTL': '45',
                    'HS_LOCK_WAIT': '5', 'HS_LOCK_POLL': '0.5',
                    'PYTHONPATH': str(REPO / 'src')})
        r = subprocess.run(
            [sys.executable, '-c',
             'import http_server_cli.utils as u;'
             'print(u.LOCK_WRITE_GRACE, u.LOCK_TTL, u.LOCK_WAIT, u.LOCK_POLL)'],
            capture_output=True, text=True, timeout=60, env=env)
        assert r.stdout.split() == ['2.5', '45.0', '5.0', '0.5'], r.stdout + r.stderr
