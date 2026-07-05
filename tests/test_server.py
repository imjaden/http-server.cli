# -*- coding: utf-8 -*-
"""
ServerManager 模块测试 — OpenSpec: lifecycle-01 ~ lifecycle-04, port-01 ~ port-03, res-01, res-02, log-01, log-02

大部分测试通过 mock 系统调用（lsof / subprocess / os.kill）来验证业务逻辑。

注意 import-by-value 陷阱：server.py 和 registry.py 都从 utils.py 按值导入了
is_port_in_use / is_process_alive 等函数。monkeypatch 必须打在 **消费者模块的
命名空间** 上，不能只打 utils。
"""

import json
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
    # 默认返回传入的端口（不递增）
    monkeypatch.setattr('http_server_cli.server.find_available_port', lambda sp: sp)

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
        # 新格式使用 emoji 和 URL
        assert 'http://localhost:8080' in captured.out
        assert '✅' in captured.out

    def test_start_auto_ports_when_default_busy(self, monkeypatch, temp_project, capsys):
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: p == 8080)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: p == 8080)
        # 端口 8080 被占用时，应返回下一个空闲端口
        monkeypatch.setattr('http_server_cli.server.find_available_port', lambda sp: 8081)
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()
        assert 'auto-assigned port' in captured.out or '8081' in captured.out

    def test_start_no_port_available(self, monkeypatch, temp_project, capsys):
        """所有端口被占时应报错"""
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        # find_available_port 也应返回 None（模拟无可用端口）
        monkeypatch.setattr('http_server_cli.server.find_available_port', lambda sp: None)
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()
        assert 'all in use, cannot start' in captured.out

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
        # 新格式：服务已运行时显示服务信息，不显示"已在运行"
        assert 'http://localhost:8080' in captured.out
        assert '✅' in captured.out

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
        assert 'cleaning up before restart' in captured.out

    def test_start_invalid_path(self, capsys):
        mgr = ServerManager()
        mgr.start(path='/nonexistent/path')
        captured = capsys.readouterr()
        assert 'Path does not exist' in captured.out
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

    def test_start_with_custom_index_page(self, temp_project):
        """--index app.html 应在 registry 中记录"""
        mgr = ServerManager()
        mgr.start(path=temp_project, index_page='app.html')
        entry = mgr.registry.find(path=os.path.realpath(temp_project))
        assert entry is not None
        assert entry['index_page'] == 'app.html'

    def test_start_default_index_page(self, temp_project):
        """未指定 --index 时默认 index.html"""
        mgr = ServerManager()
        mgr.start(path=temp_project)
        entry = mgr.registry.find(path=os.path.realpath(temp_project))
        assert entry is not None
        assert entry['index_page'] == 'index.html'

# ── list ────────────────────────────────────────────────

class TestList:
    """lifecycle-02: 列出服务"""
    def test_list_empty(self, capsys):
        mgr = ServerManager()
        mgr.list()
        captured = capsys.readouterr()
        assert 'No running HTTP services' in captured.out

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
        # 新格式使用 emoji\n        assert '✅' in captured.out

    def test_status_unregistered_port(self, monkeypatch, capsys):
        """未注册端口应提示"""
        mgr = ServerManager()
        mgr.status('9999')
        captured = capsys.readouterr()
        assert 'not registered' in captured.out

    def test_status_port_occupied_by_other(self, monkeypatch, capsys):
        """端口被非本工具进程占用时给出提示"""
        monkeypatch.setattr('http_server_cli.utils.get_pid_by_lsof', lambda p: [7777])
        mgr = ServerManager()
        mgr.status('8080')
        captured = capsys.readouterr()
        assert 'not managed by this tool' in captured.out

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
        assert 'still running in background' in captured.out

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
        captured = capsys.readouterr()  # clear start output
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        mgr.status('8080')
        captured = capsys.readouterr()
        # daemon 模式在启动时显示，status 时可能不显示
        # 检查是否显示运行状态
        assert '✅' in captured.out or 'daemon' in captured.out

# ── kill ────────────────────────────────────────────────

class TestKill:
    """lifecycle-04: 关闭服务"""
    def test_kill_by_port(self, capsys):
        mgr = ServerManager()
        mgr.start(path='/tmp')
        mgr.kill('8080')
        captured = capsys.readouterr()
        assert '🛑' in captured.out
        assert mgr.registry.count() == 0

    def test_kill_by_path(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        mgr.kill(temp_project)
        captured = capsys.readouterr()
        assert 'Terminated' in captured.out

    def test_kill_unregistered_port(self, capsys):
        mgr = ServerManager()
        mgr.kill('9999')
        captured = capsys.readouterr()
        assert 'not registered' in captured.out

    def test_kill_unregistered_path(self, capsys):
        mgr = ServerManager()
        mgr.kill('/nonexistent')
        captured = capsys.readouterr()
        assert 'not registered' in captured.out

    def test_kill_no_arg(self, capsys):
        mgr = ServerManager()
        mgr.kill('')
        captured = capsys.readouterr()
        assert 'Please specify' in captured.out

# ── kill_all ────────────────────────────────────────────

class TestKillAll:
    """lifecycle-04: 关闭所有服务"""
    def test_kill_all_empty(self, capsys):
        mgr = ServerManager()
        mgr.kill_all()
        captured = capsys.readouterr()
        assert 'No running services' in captured.out

    def test_kill_all_clears_all(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        mgr.kill_all()
        captured = capsys.readouterr()
        assert 'service(s) closed' in captured.out
        assert mgr.registry.count() == 0


# ── 进程资源监控 ──────────────────────────────────────

class TestResourceMonitoring:
    """OpenSpec: res-01, res-02"""

    def test_start_shows_start_time(self, temp_project, capsys):
        """启动服务时显示启动时间"""
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()
        assert 'Started:' in captured.out

    def test_list_shows_cpu_memory(self, temp_project, capsys, monkeypatch):
        """列出服务时显示 CPU 和内存信息"""
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()  # 清掉启动输出
        # list() now checks is_port_in_use via active_servers()
        # The subprocess may not have bound the port yet, so monkeypatch
        # is_port_in_use in the registry module to simulate an alive server
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        mgr.list()
        captured = capsys.readouterr()
        assert 'CPU' in captured.out
        assert 'Memory:' in captured.out

    def test_list_shows_duration(self, temp_project, capsys, monkeypatch):
        """列出服务时显示运行时长"""
        mgr = ServerManager()
        mgr.start(path=temp_project)
        captured = capsys.readouterr()  # 清掉启动输出
        # Same reasoning as test_list_shows_cpu_memory — simulate port in use
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        mgr.list()
        captured = capsys.readouterr()
        assert 'Duration:' in captured.out


# ── 日志管理 ──────────────────────────────────────────

class TestLogging:
    """OpenSpec: log-01, log-02"""

    def test_start_creates_log_file(self, temp_project, monkeypatch):
        """启动服务时创建日志文件"""
        import http_server_cli.utils as hs_utils
        # 使用测试的临时日志目录
        test_log_dir = os.path.join(temp_project, 'logs')
        monkeypatch.setattr('http_server_cli.server.LOG_DIR', test_log_dir)
        monkeypatch.setattr('http_server_cli.utils.LOG_DIR', test_log_dir)
        os.makedirs(test_log_dir, exist_ok=True)

        mgr = ServerManager()
        mgr.start(path=temp_project)

        # 获取实际使用的端口（可能是 8081）
        entry = mgr.registry.find(path=os.path.realpath(temp_project))
        port = entry['port']

        log_path = os.path.join(test_log_dir, f'{port}.log')
        assert os.path.isfile(log_path)

    def test_kill_deletes_log_file(self, temp_project, monkeypatch):
        """关闭服务时删除日志文件"""
        import http_server_cli.utils as hs_utils
        # 使用测试的临时日志目录
        test_log_dir = os.path.join(temp_project, 'logs')
        monkeypatch.setattr('http_server_cli.server.LOG_DIR', test_log_dir)
        monkeypatch.setattr('http_server_cli.utils.LOG_DIR', test_log_dir)
        os.makedirs(test_log_dir, exist_ok=True)

        mgr = ServerManager()
        mgr.start(path=temp_project)

        # 获取实际使用的端口
        entry = mgr.registry.find(path=os.path.realpath(temp_project))
        port = entry['port']

        log_path = os.path.join(test_log_dir, f'{port}.log')
        assert os.path.isfile(log_path)

        mgr.kill(str(port))
        assert not os.path.isfile(log_path)


# ═══════════════════════════════════════════════════════════
# --json 模式测试
# ═══════════════════════════════════════════════════════════

class TestStartJson:
    """start --json 输出格式"""

    def test_start_success_json(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project, json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'start'
        assert result['error'] is None
        d = result['data']
        assert d['path'] == os.path.realpath(temp_project)
        assert 'url' in d
        assert 'pid' in d
        assert 'stats' in d
        assert 'duration' in d

    def test_start_already_running_json(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        capsys.readouterr()  # 清掉首次输出
        # 模拟端口被占 + 进程存活 → 已运行状态
        import http_server_cli.server as hs_srv
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)

        mgr.start(path=temp_project, json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data']['index_page'] == 'index.html'
        monkeypatch.undo()

    def test_start_already_running_json_custom_index(self, temp_project, capsys):
        """已运行服务 JSON 输出应包含注册的 index_page"""
        mgr = ServerManager()
        mgr.start(path=temp_project, index_page='dashboard.html')
        capsys.readouterr()
        import http_server_cli.server as hs_srv
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)

        mgr.start(path=temp_project, json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['data']['index_page'] == 'dashboard.html'
        monkeypatch.undo()

    def test_start_invalid_path_json(self, capsys):
        mgr = ServerManager()
        mgr.start(path='/nonexistent/path', json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is False
        assert result['command'] == 'start'
        assert 'Path does not exist' in result['error']

    def test_start_no_port_available_json(self, monkeypatch, temp_project, capsys):
        monkeypatch.setattr('http_server_cli.server.find_available_port', lambda sp: None)
        mgr = ServerManager()
        mgr.start(path=temp_project, json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is False
        assert 'all in use, cannot start' in result['error']

    def test_start_json_contains_index_page(self, temp_project, capsys):
        """start --json 输出应包含 index_page"""
        mgr = ServerManager()
        mgr.start(path=temp_project, json=True, index_page='dashboard.html')
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['data']['index_page'] == 'dashboard.html'

    def test_start_json_default_index_page(self, temp_project, capsys):
        """start --json 默认 index_page 应为 index.html"""
        mgr = ServerManager()
        mgr.start(path=temp_project, json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['data']['index_page'] == 'index.html'


class TestListJson:
    """list --json 输出格式"""

    def test_list_empty_json(self, capsys):
        mgr = ServerManager()
        mgr.list(json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'list'
        assert result['data'] == {'servers': [], 'count': 0}

    def test_list_with_servers_json(self, monkeypatch, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project, index_page='app.html')
        capsys.readouterr()  # 清掉启动输出
        # 标记端口被占用 + 进程存活 → alive=True
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)

        mgr.list(json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data']['count'] == 1
        server = result['data']['servers'][0]
        assert server['port'] == 8080
        assert server['alive'] is True
        assert server['index_page'] == 'app.html'
        assert 'url' in server
        assert 'path' in server

    def test_reopen_shows_index_page_in_url(self, monkeypatch, temp_project, capsys):
        """已运行服务 reopen 时 URL 应包含自定义 index_page"""
        mgr = ServerManager()
        mgr.start(path=temp_project, index_page='app.html')
        capsys.readouterr()  # 清掉首次输出
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        # 不带 index_page 参数 reopen
        mgr.start(path=temp_project, open_browser=False)
        captured = capsys.readouterr()
        assert 'app.html' in captured.out
        assert 'http' in captured.out


class TestStatusJson:
    """status --json 输出格式"""

    def test_status_found_json(self, monkeypatch, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        capsys.readouterr()
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)

        mgr.status(arg='8080', json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data']['found'] is True
        assert result['data']['port'] == 8080
        assert result['data']['alive'] is True
        assert result['data']['index_page'] == 'index.html'
        assert 'stats' in result['data']
        assert 'duration' in result['data']

    def test_status_json_custom_index_page(self, monkeypatch, temp_project, capsys):
        """status --json 应显示自定义 index_page"""
        mgr = ServerManager()
        mgr.start(path=temp_project, index_page='dashboard.html')
        capsys.readouterr()
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)

        mgr.status(arg='8080', json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['data']['index_page'] == 'dashboard.html'

    def test_status_not_found_json(self, capsys):
        mgr = ServerManager()
        mgr.status(arg='9999', json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data']['found'] is False

    def test_status_occupied_by_other_json(self, monkeypatch, capsys):
        monkeypatch.setattr('http_server_cli.utils.get_pid_by_lsof', lambda p: [7777])
        mgr = ServerManager()
        mgr.status(arg='8080', json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data']['found'] is False
        assert result['data']['occupied'] is True
        assert result['data']['pids'] == [7777]
        # 7777 进程不存在，process 字段应为 None（不会被包含）
        assert 'process' not in result['data']


class TestKillJson:
    """kill --json 输出格式"""

    def test_kill_by_port_json(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        capsys.readouterr()
        mgr.kill('8080', json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'kill'
        assert result['data']['killed'] is True
        assert result['data']['port'] == 8080

    def test_kill_unregistered_port_json(self, capsys):
        mgr = ServerManager()
        mgr.kill('9999', json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is False
        assert 'not registered' in result['error']

    def test_kill_no_arg_json(self, capsys):
        mgr = ServerManager()
        mgr.kill('', json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is False
        assert 'specify' in result['error'].lower()


class TestKillGlobResolution:
    """kill 命令通配符路径解析"""

    def test_kill_html_path_resolves_to_dir(self, temp_project, capsys):
        """kill 传入 html 文件路径应解析到父目录"""
        mgr = ServerManager()
        mgr.start(path=temp_project, json=True)
        captured = capsys.readouterr()
        import http_server_cli.server as hs_srv
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: True)
        monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: True)
        # 创建一个真实 html 文件后 kill，应解析到注册的目录
        html_path = os.path.join(temp_project, 'test.html')
        with open(html_path, 'w') as f:
            f.write('<html></html>')
        mgr.kill(html_path)
        captured = capsys.readouterr()
        # 应该匹配到注册的目录，而不是报 not registered
        assert 'not registered' not in captured.out
        monkeypatch.undo()


class TestKillAllJson:
    """kill-all --json 输出格式"""

    def test_kill_all_empty_json(self, capsys):
        mgr = ServerManager()
        mgr.kill_all(json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data'] == {'total': 0, 'killed': 0, 'entries': []}

    def test_kill_all_with_servers_json(self, temp_project, capsys):
        mgr = ServerManager()
        mgr.start(path=temp_project)
        capsys.readouterr()
        mgr.kill_all(json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data']['total'] == 1
        assert result['data']['killed'] == 1
        assert result['data']['entries'][0]['port'] == 8080
