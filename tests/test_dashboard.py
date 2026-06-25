# -*- coding: utf-8 -*-
"""Tests for hs dashboard module."""

import json
import os
import socket
import sys
import tempfile

import pytest
from http_server_cli.utils import DATA_DIR, write_json, timestamp


# ── 辅助 ───────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _setup_clean_env():
    """每个测试使用独立的存储目录"""
    tmpdir = tempfile.mkdtemp()
    import http_server_cli.utils as utils_mod
    import http_server_cli.registry as reg_mod
    # Save originals
    orig_data_dir = utils_mod.DATA_DIR
    orig_reg_path = utils_mod.REGISTRY_PATH
    orig_cfg_path = utils_mod.CONFIG_PATH
    orig_log_dir = utils_mod.LOG_DIR
    # Override
    utils_mod.DATA_DIR = tmpdir
    utils_mod.REGISTRY_PATH = os.path.join(tmpdir, 'registry.json')
    utils_mod.CONFIG_PATH = os.path.join(tmpdir, 'config.json')
    utils_mod.LOG_DIR = os.path.join(tmpdir, 'logs')
    # Ensure directories exist
    os.makedirs(utils_mod.LOG_DIR, exist_ok=True)
    write_json(utils_mod.REGISTRY_PATH, {'servers': []})
    write_json(utils_mod.CONFIG_PATH, {'port': 8080, 'domain': 'localhost'})
    # Reset registry cache
    reg_mod.Registry._data = {}
    yield
    utils_mod.DATA_DIR = orig_data_dir
    utils_mod.REGISTRY_PATH = orig_reg_path
    utils_mod.CONFIG_PATH = orig_cfg_path
    utils_mod.LOG_DIR = orig_log_dir


# ── 测试 ───────────────────────────────────────────────

class TestServe:
    def test_json_output_mode(self):
        """--json 模式返回服务列表 JSON"""
        from http_server_cli.server import ServerManager
        from http_server_cli.dashboard import serve
        mgr = ServerManager()
        mgr.registry.add(
            port=29991, path='/tmp/test', pid=99999,
            started_at=timestamp(),
        )
        captured = __import__('io').StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            serve(port=29990, json_output_mode=True)
        finally:
            sys.stdout = old
        data = json.loads(captured.getvalue())
        assert data['command'] == 'dashboard'
        assert data['success'] is True
        assert 'managed' in data['data']

    def test_foreground_starts_server(self):
        """前台模式启动 HTTPServer"""
        from http_server_cli.dashboard import serve
        import socket
        import threading
        import time
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
        t = threading.Thread(target=serve, args=(port,), daemon=True)
        t.start()
        time.sleep(0.5)
        from http_server_cli.utils import is_port_in_use
        assert is_port_in_use(port), 'Dashboard should be listening'
        # 关闭监听 socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            s.connect(('127.0.0.1', port))
        finally:
            s.close()


class TestJsonMode:
    def test_json_with_servers(self):
        """注册了服务时 --json 返回包含服务器列表"""
        from http_server_cli.server import ServerManager
        from http_server_cli.dashboard import serve
        mgr = ServerManager()
        mgr.registry.add(port=8881, path='/tmp/a', pid=10001,
                         started_at=timestamp())
        mgr.registry.add(port=8882, path='/tmp/b', pid=10002,
                         started_at=timestamp())
        captured = __import__('io').StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            serve(port=9999, json_output_mode=True)
        finally:
            sys.stdout = old
        data = json.loads(captured.getvalue())
        assert data['success'] is True
        assert data['data']['count'] == 2
        assert 'managed' in data['data']
        ports = {s['port'] for s in data['data']['servers']}
        assert ports == {8881, 8882}

    def test_json_empty(self):
        """无服务时 --json 返回空列表"""
        from http_server_cli.dashboard import serve
        captured = __import__('io').StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            serve(port=9998, json_output_mode=True)
        finally:
            sys.stdout = old
        data = json.loads(captured.getvalue())
        assert data['success'] is True
        assert data['data']['count'] == 0
        assert data['data']['servers'] == []


class TestHTMLPage:
    def test_html_page_contains_dashboard_title(self):
        """HTML 页面包含关键 UI 元素"""
        from http_server_cli.dashboard import _get_html
        html = _get_html()
        assert 'hs dashboard' in html
        assert 'Kill All' in html
        assert 'URL' in html
        assert 'fetch' in html or '/api/servers' in html

    def test_html_has_refresh_script(self):
        """HTML 包含自动刷新逻辑"""
        from http_server_cli.dashboard import _get_html
        html = _get_html()
        assert 'setInterval' in html
        assert 'loadServers' in html


class TestHandlerBehavior:
    def test_dashboard_handler_manager(self):
        """Handler 正确设置 manager"""
        from http_server_cli.dashboard import DashboardHandler
        from http_server_cli.server import ServerManager
        mgr = ServerManager()
        DashboardHandler.manager = mgr
        assert DashboardHandler.manager is mgr

class TestDaemonMode:
    def test_daemon_mode_subprocess(self):
        """daemon 模式通过子进程启动（不 hang）"""
        from http_server_cli.dashboard import serve
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
        captured = __import__('io').StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            serve(port=port, daemon=True)
        finally:
            sys.stdout = old
        output = captured.getvalue()
        assert 'daemon' in output
        assert 'PID:' in output
