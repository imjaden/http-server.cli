# -*- coding: utf-8 -*-
"""HTTP-SERVER-CL004：端口探测残留态「假占用」+ 顶层取值型 flag 归位 + stale 三态/宽限/归属校验 + web 退出码。

对应设计 §7 测试清单 T1–T13（`documents/http-server-port-residual-design-v1.4-20260922.md`）。
"""

import json
import os
import socket
import sys
import threading
import time
import types

import pytest

import http_server_cli.cli as cli
import http_server_cli.registry as registry_mod
import http_server_cli.server as server_mod
from http_server_cli.server import ServerManager
from http_server_cli.utils import find_available_port, get_pid_by_lsof, is_port_in_use

pytestmark = pytest.mark.spec("port-allocation")


# ── socket 工具（T1–T3/T13 用真实 socket，不打桩） ──────

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def _free_port_low() -> int:
    """取一个 ≤ MAX_PORT(10000) 的空闲端口（find_available_port 有 MAX_PORT 上限）。"""
    for port in range(9000, 9900):
        if not is_port_in_use(port):
            return port
    raise RuntimeError('no free low port')


def _residual_port(port: int) -> int:
    """构造残留态端口：服务端**先** close（先发 FIN）⇒ 该端口进入 TIME_WAIT（R-3）。

    客户端先关只会在客户端临时端口留残留，服务端口不受影响，故方向不可反。
    """
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('', port))
    srv.listen(1)
    holder = {}

    def _accept():
        conn, _ = srv.accept()
        holder['conn'] = conn

    t = threading.Thread(target=_accept)
    t.start()
    client = socket.socket()
    client.connect(('127.0.0.1', port))
    time.sleep(0.3)
    holder['conn'].close()
    time.sleep(0.2)
    client.close()
    srv.close()
    t.join(timeout=2)
    return port


def _abs(path):
    return os.path.realpath(path)


# ── T1–T3：探测语义（D1） ───────────────────────────────

class TestPortProbe:

    def test_t1_real_listener_still_in_use(self):
        """T1：真实 LISTEN 端口仍判占用（真占用不放宽）。"""
        port = _free_port()
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('', port))
        srv.listen(1)
        try:
            assert is_port_in_use(port) is True
        finally:
            srv.close()

    def test_t1b_loopback_listener_detected(self):
        """T1b（实施偏差 D1'）：仅监听 127.0.0.1 的服务也须判占用。

        纯 socket + SO_REUSEADDR 口径在 BSD 语义下会漏判（wildcard 探测可绑成功），
        故 darwin 主路径改 lsof LISTEN（见设计 §13 偏差表）。
        """
        port = _free_port()
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('127.0.0.1', port))
        srv.listen(1)
        try:
            assert is_port_in_use(port) is True
        finally:
            srv.close()

    def test_t1c_lan_bound_listener_detected(self):
        """T1c：绑定到非 wildcard/非 loopback 地址的监听者也须判占用（lsof 口径）。"""
        import subprocess
        try:
            lan = subprocess.run(['ipconfig', 'getifaddr', 'en0'], capture_output=True,
                                 text=True).stdout.strip()
        except OSError:
            lan = ''
        if not lan:
            pytest.skip('no LAN address available')
        port = _free_port()
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind((lan, port))
        except OSError:
            pytest.skip('cannot bind LAN address')
        srv.listen(1)
        try:
            assert is_port_in_use(port) is True
        finally:
            srv.close()

    def test_t14_fallback_probe_when_lsof_unavailable(self, monkeypatch):
        """T14：lsof 不可用时回退 socket 探测（SO_REUSEADDR 仍不误判残留态）。"""
        import http_server_cli.utils as utils
        monkeypatch.setattr(utils, '_listening_ports', lambda: None)
        port = _free_port()
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('', port))
        srv.listen(1)
        try:
            assert is_port_in_use(port) is True          # 同地址同 wildcard 监听 → 仍可检出
        finally:
            srv.close()
        assert is_port_in_use(_residual_port(_free_port())) is False

    def test_t2_residual_port_not_in_use(self):
        """T2：TIME_WAIT 残留端口不再判占用（修复点；修前为 True）。"""
        port = _residual_port(_free_port())
        assert is_port_in_use(port) is False

    def test_t3_find_available_port_keeps_residual_port(self):
        """T3：find_available_port 对残留态端口返回该端口本身（不再漂移）。"""
        port = _residual_port(_free_port_low())
        assert find_available_port(port) == port


# ── T13：lsof 口径（D11 / R-9） ─────────────────────────

class TestLsofListenOnly:

    def test_t13_listen_only_filters_established(self):
        """T13：默认口径含 ESTABLISHED，listen_only=True 仅 LISTEN（既有调用点行为不变）。"""
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('127.0.0.1', 0))
        srv.listen(1)
        sport = srv.getsockname()[1]
        client = socket.socket()
        client.connect(('127.0.0.1', sport))
        lport = client.getsockname()[1]
        try:
            time.sleep(0.3)
            assert os.getpid() in get_pid_by_lsof(sport)
            assert os.getpid() in get_pid_by_lsof(sport, listen_only=True)
            # 客户端临时端口只有 ESTABLISHED：默认非空、listen_only 为空
            assert get_pid_by_lsof(lport)
            assert get_pid_by_lsof(lport, listen_only=True) == []
        finally:
            client.close()
            srv.close()


# ── T4/T5：顶层取值型 flag 归位（D2） ───────────────────

class TestTopLevelReorgOrder:

    @pytest.fixture
    def _start_capture(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(cli, 'ensure_storage', lambda: None)
        monkeypatch.setattr(cli, 'ServerManager', lambda: 'MGR')
        monkeypatch.setitem(cli._COMMANDS, 'start',
                            lambda mgr, args: captured.update(mgr=mgr, args=args))
        return captured

    def test_t4_leaked_port_value(self, monkeypatch, _start_capture):
        monkeypatch.setattr(sys, 'argv', ['hs', '-p', '8099'])
        cli.main()
        assert _start_capture['args'] == ['-p', '8099']

    def test_t5_existing_cwd_file_with_flags_goes_to_reorg(self, monkeypatch, tmp_path,
                                                           _start_capture):
        """T5（修复点）：-i 的值在 CWD 存在时**不再**走路径快捷方式，-i 与目录都保留。"""
        cwd = tmp_path / 'cwd'
        cwd.mkdir()
        (cwd / 'index.html').write_text('<h1>x</h1>', encoding='utf-8')
        target = tmp_path / 'target'
        target.mkdir()
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(sys, 'argv',
                            ['hs', '-i', 'index.html', '-p', '8095', str(target)])
        cli.main()
        assert _start_capture['args'] == ['-i', 'index.html', '-p', '8095', str(target)]

    def test_t4_index_value_without_path_still_reorg(self, monkeypatch, tmp_path,
                                                     _start_capture):
        cwd = tmp_path / 'cwd2'
        cwd.mkdir()
        (cwd / 'index.html').write_text('<h1>x</h1>', encoding='utf-8')
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(sys, 'argv', ['hs', '-i', 'index.html'])
        cli.main()
        assert _start_capture['args'] == ['-i', 'index.html']

    def test_t4_bare_path_shortcut_kept(self, monkeypatch, tmp_path, _start_capture):
        """无取值型 flag 时路径快捷方式仍生效。"""
        cwd = tmp_path / 'cwd3'
        cwd.mkdir()
        (cwd / 'index.html').write_text('<h1>x</h1>', encoding='utf-8')
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(sys, 'argv', ['hs', 'index.html'])
        cli.main()
        assert _start_capture['args'] == ['index.html']

    def test_t4_bool_flag_before_path_still_shortcut(self, monkeypatch, tmp_path,
                                                     _start_capture):
        """-o（布尔 flag，不在触发位）仍走路径快捷方式。"""
        cwd = tmp_path / 'cwd4'
        cwd.mkdir()
        (cwd / 'index.html').write_text('<h1>x</h1>', encoding='utf-8')
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(sys, 'argv', ['hs', '-o', 'index.html'])
        cli.main()
        assert _start_capture['args'] == ['index.html']


# ── T6/T7：web 用法错误退出码（D3） ─────────────────────

class TestWebPortExitCodes:

    def test_t6_add_invalid_port_exits_2(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            cli._COMMANDS['web'](None, ['add', 'cl004t6', '--cmd', 'echo hi',
                                        '--port', '99'])
        assert exc.value.code == 2

    def test_t6b_add_mutually_exclusive_exits_2(self):
        with pytest.raises(SystemExit) as exc:
            cli._COMMANDS['web'](None, ['add', 'cl004t6b', '--cmd', 'echo hi',
                                        '--port', '9001', '--no-port'])
        assert exc.value.code == 2

    def test_t7_update_invalid_port_exits_2(self):
        cli._COMMANDS['web'](None, ['add', 'cl004t7', '--cmd', 'echo hi'])
        with pytest.raises(SystemExit) as exc:
            cli._COMMANDS['web'](None, ['update', 'cl004t7', '--port', '99'])
        assert exc.value.code == 2

    def test_t7b_update_both_flags_exits_2(self):
        cli._COMMANDS['web'](None, ['add', 'cl004t7b', '--cmd', 'echo hi'])
        with pytest.raises(SystemExit) as exc:
            cli._COMMANDS['web'](None, ['update', 'cl004t7b', '--port', '9001',
                                        '--no-port'])
        assert exc.value.code == 2


# ── T8–T10/T12：stale 三态与宽限（D4/D5/R-5/R-6/R-7） ───

class TestStaleThreeState:

    PID = 999999

    def _seed(self, mgr, path, port=8091):
        mgr.registry.add(port=port, path=_abs(path), pid=self.PID,
                         index_page='index.html')

    def _patch_common(self, monkeypatch, alive=True, listening=False, listeners=(),
                      command=None):
        monkeypatch.setattr(server_mod, 'START_GRACE_INTERVAL', 0)
        monkeypatch.setattr(server_mod, 'START_GRACE_ATTEMPTS', 2)
        monkeypatch.setattr(server_mod, 'is_process_alive', lambda pid: alive)
        monkeypatch.setattr(server_mod, 'is_port_in_use', lambda p: listening)
        monkeypatch.setattr(server_mod, 'get_pid_by_lsof',
                            lambda p, listen_only=False: list(listeners))
        monkeypatch.setattr(server_mod, 'get_process_info',
                            lambda pid: {'user': 'me', 'command': command or ''})
        monkeypatch.setattr(registry_mod, 'is_process_alive', lambda pid: alive)
        monkeypatch.setattr(registry_mod, 'is_port_in_use', lambda p: listening)
        monkeypatch.setattr(server_mod, 'find_available_port', lambda sp: sp)
        proc = types.SimpleNamespace(pid=88888)
        monkeypatch.setattr(server_mod.subprocess, 'Popen', lambda *a, **kw: proc)
        monkeypatch.setattr(server_mod.subprocess, 'run',
                            lambda *a, **kw: types.SimpleNamespace(returncode=1,
                                                                   stdout='', stderr=''))
        monkeypatch.setattr(server_mod.webbrowser, 'open', lambda url: True)
        recorder = {'killed': [], 'removed': []}
        monkeypatch.setattr(server_mod, '_terminate_runner',
                            lambda pid: recorder['killed'].append(pid) or True)
        return recorder

    def _spy_remove(self, monkeypatch, mgr):
        calls = []
        real_remove = mgr.registry.remove

        def _remove(*a, **kw):
            calls.append(kw or (a[0] if a else None))
            return real_remove(*a, **kw)

        monkeypatch.setattr(mgr.registry, 'remove', _remove)
        return calls

    def test_t8_grace_turns_ready(self, monkeypatch, temp_project, capsys):
        """T8：pid 活 + 端口首检未监听，宽限内出现监听 ⇒ 幂等命中，不删登记、不 kill。"""
        mgr = ServerManager()
        self._seed(mgr, temp_project)
        state = {'n': 0}

        def _listen(p):
            state['n'] += 1
            return state['n'] > 2          # ①未监听 → 宽限第 1 次起监听到

        rec = self._patch_common(monkeypatch, alive=True, listening=False)
        monkeypatch.setattr(server_mod, 'is_port_in_use', _listen)
        monkeypatch.setattr(server_mod, 'get_pid_by_lsof',
                            lambda p, listen_only=False: [self.PID])
        removed = self._spy_remove(monkeypatch, mgr)
        out = capsys.readouterr()
        assert mgr.start(path=temp_project, url_only=True) is True
        assert removed == [] and rec['killed'] == []
        assert '8091' in capsys.readouterr().out

    def test_t9_stale_alive_runner_is_terminated(self, monkeypatch, temp_project, capsys):
        """T9：宽限后仍未监听 + 归属校验通过 ⇒ 先终止进程组再删登记（反孤儿）。"""
        mgr = ServerManager()
        self._seed(mgr, temp_project)
        cmd = f'/usr/bin/python3 /opt/hs/runner.py 8091 {_abs(temp_project)} --bind x'
        rec = self._patch_common(monkeypatch, alive=True, listening=False, command=cmd)
        removed = self._spy_remove(monkeypatch, mgr)
        assert mgr.start(path=temp_project, url_only=True) is True
        assert rec['killed'] == [self.PID]
        assert removed == [{'path': _abs(temp_project)}]
        assert 'Found stale registry entry' in capsys.readouterr().err

    def test_t10_stale_dead_pid_only_cleans(self, monkeypatch, temp_project, capsys):
        """T10：pid 已死 ⇒ 只删登记，不调用 kill。"""
        mgr = ServerManager()
        self._seed(mgr, temp_project)
        rec = self._patch_common(monkeypatch, alive=False, listening=False)
        removed = self._spy_remove(monkeypatch, mgr)
        assert mgr.start(path=temp_project, url_only=True) is True
        assert rec['killed'] == []
        assert removed == [{'path': _abs(temp_project)}]

    def test_t12a_non_runner_pid_not_killed(self, monkeypatch, temp_project, capsys):
        """T12①：命令行不含 runner.py ⇒ 不 kill，仅清理登记。"""
        mgr = ServerManager()
        self._seed(mgr, temp_project)
        rec = self._patch_common(monkeypatch, alive=True, listening=False,
                                 command='/usr/bin/nginx -g daemon off;')
        removed = self._spy_remove(monkeypatch, mgr)
        assert mgr.start(path=temp_project, url_only=True) is True
        assert rec['killed'] == [] and len(removed) == 1
        assert '非本工具服务' in capsys.readouterr().err

    def test_t12b_other_process_owns_port(self, monkeypatch, temp_project, capsys):
        """T12②（R-7）：宽限内端口被他人占用 ⇒ 判「端口被他人占用」，不 kill 他人。

        注：① 判定为「pid 活 ∧ 端口在监听」，故本场景只能发生在「① 时端口空闲 →
        宽限窗口内被其他进程抢占」的窄窗口，用计数器构造该时序。
        """
        mgr = ServerManager()
        self._seed(mgr, temp_project)
        rec = self._patch_common(monkeypatch, alive=True, listening=False,
                                 listeners=[4321],
                                 command=f'/usr/bin/python3 /opt/hs/runner.py 8091 {_abs(temp_project)}')
        state = {'n': 0}

        def _listen(p):
            state['n'] += 1
            return state['n'] > 2          # ① 空闲 → 宽限第 2 次起「他人已监听」

        monkeypatch.setattr(server_mod, 'is_port_in_use', _listen)
        removed = self._spy_remove(monkeypatch, mgr)
        assert mgr.start(path=temp_project, url_only=True) is True
        assert rec['killed'] == []
        assert len(removed) == 1
        assert '端口已被其他进程占用' in capsys.readouterr().err

    def test_t11_stale_message_never_pollutes_json_stdout(self, monkeypatch, temp_project,
                                                          capsys):
        """T11（F-1）：--json 触发 stale ⇒ stdout 首字符 `{` 且可解析，stale 文案在 stderr。"""
        mgr = ServerManager()
        self._seed(mgr, temp_project)
        self._patch_common(monkeypatch, alive=False, listening=False)
        assert mgr.start(path=temp_project, json=True) is True
        out, err = capsys.readouterr()
        assert out.lstrip().startswith('{')
        payload = json.loads(out)              # 不抛 JSONDecodeError
        assert payload['success'] is True
        assert 'Found stale registry entry' in err
