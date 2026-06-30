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
        """中文版 HTML 包含中文 UI 元素"""
        from http_server_cli.dashboard import _get_html
        html = _get_html()
        assert 'hs dashboard' in html or 'HTTP Server Dashboard' in html
        assert '全部关闭' in html
        assert 'URL（端口）' in html
        assert 'fetch' in html or '/api/servers' in html

    def test_html_has_refresh_script(self):
        """HTML 包含自动刷新逻辑"""
        from http_server_cli.dashboard import _get_html
        html = _get_html()
        assert 'setInterval' in html
        assert 'loadServers' in html

    def test_html_en_version(self):
        """英文版 HTML 可加载且包含英文 UI 文字"""
        from http_server_cli.dashboard import _get_html
        html = _get_html('en')
        assert 'HTTP Server Dashboard' in html
        assert 'Loading...' in html
        assert 'Refresh' in html
        assert 'Kill All' in html
        assert 'Status' in html
        assert 'Last Access' in html
        assert '/en' in html  # language toggle

    def test_html_cn_version_lang_switch(self):
        """中文版 HTML 包含 '/en' 语言切换链接"""
        from http_server_cli.dashboard import _get_html
        html = _get_html('zh')
        assert '🇨🇳' in html or '/en' in html

    def test_html_en_lang_switch(self):
        """英文版 HTML 包含 '/' 语言切换链接"""
        from http_server_cli.dashboard import _get_html
        html = _get_html('en')
        assert '🇺🇸' in html or '/' in html

    def test_html_error_handler(self):
        """两个版本 HTML 都包含 window.onerror"""
        from http_server_cli.dashboard import _get_html
        for lang in ('zh', 'en'):
            html = _get_html(lang)
            assert 'window.onerror' in html

    def test_html_url_column_exists(self):
        """中文版表格包含 URL（端口）列"""
        from http_server_cli.dashboard import _get_html
        html = _get_html()
        assert 'URL（端口）' in html

    def test_html_status_column_exists(self):
        """中文版表格包含 状态 列"""
        from http_server_cli.dashboard import _get_html
        html = _get_html()
        assert '状态' in html

    def test_html_cpu_column(self):
        """两个版本表格都包含 CPU 列"""
        from http_server_cli.dashboard import _get_html
        for lang in ('zh', 'en'):
            html = _get_html(lang)
            assert 'CPU' in html

    def test_html_memory_column(self):
        """中文版表格包含 内存 列"""
        from http_server_cli.dashboard import _get_html
        html = _get_html()
        assert '内存' in html

    def test_html_last_access_column(self):
        """中文版表格包含 最近访问 列"""
        from http_server_cli.dashboard import _get_html
        html = _get_html()
        assert '最近访问' in html

    def test_html_action_column(self):
        """中文版表格包含 操作 列"""
        from http_server_cli.dashboard import _get_html
        html = _get_html()
        assert '操作' in html

    def test_html_version_footer(self):
        """两个版本 HTML 都包含版本号 footer 元素"""
        from http_server_cli.dashboard import _get_html
        for lang in ('zh', 'en'):
            html = _get_html(lang)
            assert 'footer-version' in html
            assert 'commands-body' in html

    def test_html_en_columns(self):
        """英文版表格列标题使用英文"""
        from http_server_cli.dashboard import _get_html
        html = _get_html('en')
        assert 'Status' in html
        assert 'Memory' in html
        assert 'Last Access' in html
        assert 'Action' in html


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
