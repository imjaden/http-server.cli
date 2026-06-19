# -*- coding: utf-8 -*-
"""
ServerManager 模块测试 — OpenSpec: lifecycle-01 ~ lifecycle-04, port-01 ~ port-03

大部分测试通过 mock 系统调用（lsof / subprocess / os.kill）来验证业务逻辑。

注意 import-by-value 陷阱：server.py 和 registry.py 都从 utils.py 按值导入了
is_port_in_use / is_process_alive 等函数。monkeypatch 必须打在 **消费者模块的
命名空间** 上，不能只打 utils。
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from http_server_cli.server import ServerManager

pytestmark = pytest.mark.spec("service-lifecycle")

# ── 夹具：mock 掉系统依赖 ───────────────────────────────

@pytest.fixture(autouse=True)
def _mock_system_calls(monkeypatch):
    """默认 mock 掉所有有副作用的系统调用，个别测试可 override。

    server.py 从 utils.py 按值导入了 is_port_in_use / is_process_alive 等。
    registry.py 也按值导入了同样的函数（registry.active_servers 会用到）。
    因此必须同时打 server 和 registry 两个模块的补丁。
    """
    # server 模块 namespace
    monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: False)
    monkeypatch.setattr('http_server_cli.server.is_process_alive', lambda pid: True)
    monkeypatch.setattr('http_server_cli.server.find_available_port', lambda sp: sp + 1)

    # registry 模块 namespace（registry.active_servers 会调用）
    monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: False)
    monkeypatch.setattr('http_server_cli.registry.is_process_alive', lambda pid: True)

    # subprocess & side effects
    mock_proc = MagicMock()
    mock_proc.pid = 99999
    monkeypatch.setattr('http_server_cli.server.subprocess.Popen', lambda *a, **kw: mock_proc)
    monkeypatch.setattr('http_server_cli.server.subprocess.run', lambda cmd, **kw: None)
    monkeypatch.setattr('http_server_cli.server.webbrowser.open', lambda url: True)
    monkeypatch.setattr('http_server_cli.server.os.killpg', lambda pid, sig: None)
    monkeypatch.setattr('http_server_cli.server.os.getpgid', lambda pid: pid)
    monkeypatch.setattr('http_server_cli.server.time.sleep', lambda s: None)
    # get_pid_by_lsof 是 server.status() 内惰性导入（from utils import），
    # 挂 utils 源即可生效
    monkeypatch.setattr('http_server_cli.utils.get_pid_by_lsof', lambda p: [])

# ── start ──────────────────────────────────────────────

class TestStart:
    """lifecycle-01 / port-01~03: 启动服务 + 端口分配"""

    def test_start_uses_default_port_when_free(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()
        assert '服务已启动' in captured.out
        assert '8080' in captured.out

    def test_start_auto_ports_when_default_busy(self, monkeypatch, temp_project, capsys):
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p == 8080)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: p == 8080)
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()
        assert '自动分配端口' in captured.out

    def test_start_no_port_available(self, monkeypatch, temp_project, capsys):
        """所有端口被占时应报错"""
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        # find_available_port 也应返回 None（模拟无可用端口）
        monkeypatch.setattr('http_server_cli.server.find_available_port', lambda sp: None)
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()
        assert '已全部被占用' in captured.out

    def test_start_registers_in_registry(self, temp_project):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        assert mgr.registry.count() == 1
        entry = mgr.registry.find(path=os.path.realpath(temp_project))
        assert entry is not None
        assert entry['port'] == 8080

    def test_start_detects_already_running(self, monkeypatch, temp_project, capsys):
        """重复启动同一项目应提示已在运行"""
        # 端口全部空闲，首次启动使用 8080
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()  # 清掉首次输出

        # 标记端口全部占用 + 进程存活 → 模拟"服务已在运行"
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)

        mgr.start(path=temp_project)
        captured = capsys.readouterr()
        assert '已在运行' in captured.out

    def test_start_cleans_stale_entry(self, monkeypatch, temp_project, capsys):
        """进程已死的残留记录应自动清理"""
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()  # 清掉首次输出

        # mock 为进程已死且端口空闲
        monkeypatch.setattr('http_server_cli.server.is_process_alive', lambda pid: False)
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: False)
        monkeypatch.setattr('http_server_cli.registry.is_process_alive', lambda pid: False)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: False)

        mgr.start(path=temp_project)
        captured = capsys.readouterr()
        assert '清理后重新启动' in captured.out

    def test_start_invalid_path(self, capsys):
        mgr = ServerManager()
        mgr.start(path='/nonexistent/path')
        captured = capsys.readouterr()
        assert '路径不存在' in captured.out
        assert mgr.registry.count() == 0

    def test_start_with_open_browser(self, monkeypatch, temp_project):
        opened = []
        monkeypatch.setattr('http_server_cli.server.webbrowser.open', lambda url: opened.append(url))
        mgr = ServerManager()
        mgr.start(path=temp_project, open_browser=True)
        assert len(opened) == 1
        assert 'localhost:8080' in opened[0]

    def test_start_defaults_to_cwd(self, monkeypatch, capsys):
        """path 默认为当前目录"""
        mgr = ServerManager()
        cwd = os.getcwd()
        mgr.start(open_browser=True)
        captured = capsys.readouterr()
        # 输出使用 format_path 格式化了（~ 简写），取当前目录名做近似匹配
        cwd_basename = os.path.basename(os.getcwd())
        assert cwd_basename in captured.out

# ── list ────────────────────────────────────────────────

class TestList:
    """lifecycle-02: 列出服务"""
    def test_list_empty(self, capsys):
        mgr = ServerManager()
        mgr.list()
        captured = capsys.readouterr()
        assert '没有正在运行' in captured.out

    def test_list_with_servers(self, capsys):
        mgr = ServerManager()
        mgr.start(path='/tmp')
        mgr.list()
        captured = capsys.readouterr()
        assert 'localhost:8080' in captured.out

# ── status ─────────────────────────────────────────────

class TestStatus:
    """lifecycle-03: 查询状态"""
    def test_status_no_arg_calls_list(self, monkeypatch, capsys):
        """无参数时等同于 list"""
        called = []
        monkeypatch.setattr('http_server_cli.server.ServerManager.list', lambda self, **kw: called.append(kw))
        mgr = ServerManager()
        mgr.status()
        assert len(called) == 1
        assert 'json' in called[0]

    def test_status_by_port(self, monkeypatch, capsys):
        """按端口查询"""
        mgr = ServerManager()
        mgr.start(path='/tmp')
        captured = capsys.readouterr()  # clear

        # status 需要端口被占用才显示"运行中"
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        mgr.status('8080')
        captured = capsys.readouterr()
        assert '运行中' in captured.out

    def test_status_unregistered_port(self, monkeypatch, capsys):
        """未注册端口应提示"""
        mgr = ServerManager()
        mgr.status('9999')
        captured = capsys.readouterr()
        assert '未注册' in captured.out

    def test_status_port_occupied_by_other(self, monkeypatch, capsys):
        """端口被非本工具进程占用时给出提示"""
        monkeypatch.setattr('http_server_cli.utils.get_pid_by_lsof', lambda p: [7777])
        mgr = ServerManager()
        mgr.status('8080')
        captured = capsys.readouterr()
        assert '但非本工具管理' in captured.out

class TestDaemon:
    """daemon 模式专用测试"""

    def test_daemon_starts_tail(self, monkeypatch, temp_project, capsys):
        """daemon=True 时应进入 tail -f 日志查看"""
        tail_called = []
        monkeypatch.setattr('http_server_cli.server.subprocess.run',
                            lambda cmd, **kw: tail_called.append(cmd))
        mgr = ServerManager()
        mgr.start(path=temp_project, daemon=True)
        assert any('tail' in str(c) for c in tail_called)

    def test_daemon_catches_keyboard_interrupt(self, monkeypatch, temp_project, capsys):
        """Ctrl+C 时应提示服务仍在运行"""
        def _tail_that_raises(*a, **kw):
            raise KeyboardInterrupt()
        monkeypatch.setattr('http_server_cli.server.subprocess.run', _tail_that_raises)
        mgr = ServerManager()
        mgr.start(path=temp_project, daemon=True)
        captured = capsys.readouterr()
        assert '仍在后台运行' in captured.out

    def test_daemon_registers_flag(self, temp_project):
        """daemon 模式条目应标记 daemon=True"""
        mgr = ServerManager()
        mgr.start(path=temp_project, daemon=True)
        entry = mgr.registry.find(path=os.path.realpath(temp_project))
        assert entry is not None
        assert entry['daemon'] is True

    def test_non_daemon_has_false_flag(self, temp_project):
        """普通模式条目 daemon 应为 False"""
        mgr = ServerManager()
        mgr.start(path=temp_project)
        entry = mgr.registry.find(path=os.path.realpath(temp_project))
        assert entry is not None
        assert entry['daemon'] is False

    def test_list_shows_daemon_tag(self, monkeypatch, temp_project, capsys):
        """list 输出应包含 daemon 标记 🖥"""
        mgr = ServerManager()
        mgr.start(path=temp_project, daemon=True)
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        mgr.list()
        captured = capsys.readouterr()
        assert '🖥' in captured.out

    def test_status_shows_daemon_mode(self, monkeypatch, temp_project, capsys):
        """status 输出应显示 daemon 模式"""
        mgr = ServerManager()
        mgr.start(path=temp_project, daemon=True)
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        mgr.status('8080')
        captured = capsys.readouterr()
        assert 'daemon' in captured.out

# ── kill ────────────────────────────────────────────────

class TestKill:
    """lifecycle-04: 关闭服务"""
    def test_kill_by_port(self, capsys):
        mgr = ServerManager()
        mgr.start(path='/tmp')
        mgr.kill('8080')
        captured = capsys.readouterr()
        assert '服务已关闭' in captured.out
        assert mgr.registry.count() == 0

    def test_kill_by_path(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        mgr.kill(temp_project)
        captured = capsys.readouterr()
        assert '服务已关闭' in captured.out

    def test_kill_unregistered_port(self, capsys):
        mgr = ServerManager()
        mgr.kill('9999')
        captured = capsys.readouterr()
        assert '未注册' in captured.out

    def test_kill_unregistered_path(self, capsys):
        mgr = ServerManager()
        mgr.kill('/nonexistent')
        captured = capsys.readouterr()
        assert '未注册' in captured.out

    def test_kill_no_arg(self, capsys):
        mgr = ServerManager()
        mgr.kill('')
        captured = capsys.readouterr()
        assert '请指定' in captured.out

# ── kill_all ────────────────────────────────────────────

class TestKillAll:
    """lifecycle-04: 关闭所有服务"""
    def test_kill_all_empty(self, capsys):
        mgr = ServerManager()
        mgr.kill_all()
        captured = capsys.readouterr()
        assert '没有正在运行' in captured.out

    def test_kill_all_clears_all(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        mgr.kill_all()
        captured = capsys.readouterr()
        assert '已关闭' in captured.out
        assert mgr.registry.count() == 0
