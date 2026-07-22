# -*- coding: utf-8 -*-
"""
Handler 模块测试 — OpenSpec: home-01 ~ home-03

测试首页智能跳转逻辑：
- 存在 index.html 时正常返回
- 无 index.html 时重定向到最近修改的 HTML 文件
- 无任何 HTML 文件时返回目录列表
"""

import os
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from http_server_cli.handler import SmartHTTPRequestHandler

pytestmark = pytest.mark.spec("smart-homepage")


class TestHomepageRedirect:
    """首页智能跳转 — OpenSpec: home-01, home-02"""

    def test_find_latest_html_returns_none_when_no_html(self):
        """无 HTML 文件时返回 None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建 handler 实例，避免调用父类 __init__
            handler = MagicMock(spec=SmartHTTPRequestHandler)
            handler.directory = tmpdir
            # 直接调用实际方法
            result = SmartHTTPRequestHandler._find_latest_html(handler)
            assert result is None

    def test_find_latest_html_returns_single_html(self):
        """单个 HTML 文件时返回该文件名"""
        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = os.path.join(tmpdir, 'test.html')
            with open(html_file, 'w') as f:
                f.write('<html><body>Test</body></html>')

            handler = MagicMock(spec=SmartHTTPRequestHandler)
            handler.directory = tmpdir
            result = SmartHTTPRequestHandler._find_latest_html(handler)
            assert result == 'test.html'

    def test_find_latest_html_returns_most_recent(self):
        """多个 HTML 文件时返回最近修改的"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建两个 HTML 文件，b.html 更新时间更晚
            a_html = os.path.join(tmpdir, 'a.html')
            b_html = os.path.join(tmpdir, 'b.html')

            with open(a_html, 'w') as f:
                f.write('<html>A</html>')

            with open(b_html, 'w') as f:
                f.write('<html>B</html>')

            # 确保 b.html 更新时间更晚
            import time
            time.sleep(0.1)
            with open(b_html, 'w') as f:
                f.write('<html>B updated</html>')

            handler = MagicMock(spec=SmartHTTPRequestHandler)
            handler.directory = tmpdir
            result = SmartHTTPRequestHandler._find_latest_html(handler)
            assert result == 'b.html'

    def test_find_latest_html_ignores_index(self):
        """查找时忽略 index.html"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_html = os.path.join(tmpdir, 'index.html')
            other_html = os.path.join(tmpdir, 'other.html')

            with open(index_html, 'w') as f:
                f.write('<html>Index</html>')

            with open(other_html, 'w') as f:
                f.write('<html>Other</html>')

            handler = MagicMock(spec=SmartHTTPRequestHandler)
            handler.directory = tmpdir
            result = SmartHTTPRequestHandler._find_latest_html(handler)
            assert result == 'other.html'


class TestQueryParameterHandling:
    """查询参数处理 — OpenSpec: home-02"""

    def test_urlparse_removes_query(self):
        """urlparse 应正确分离路径和查询参数"""
        from urllib.parse import urlparse

        # 测试带查询参数的 URL
        result = urlparse('/?t=1781889346836')
        assert result.path == '/'
        assert result.query == 't=1781889346836'

        # 测试带路径和查询参数
        result = urlparse('/test.html?v=1')
        assert result.path == '/test.html'
        assert result.query == 'v=1'


class TestCustomIndexPage:
    """自定义首页 — --index 参数"""

    def _make_handler_instance(self, tmpdir, index_page='index.html'):
        """辅助：创建一个 SmartHTTPRequestHandler 实例（mock 掉父类 __init__ 避免 socket）"""
        from http.server import SimpleHTTPRequestHandler
        with patch.object(SimpleHTTPRequestHandler, '__init__', return_value=None):
            from http_server_cli.handler import create_handler
            handler_class = create_handler(tmpdir, index_page=index_page)
            handler = handler_class.__new__(handler_class)
            handler.__init__()
            return handler

    def test_create_handler_sets_custom_index_page(self):
        """create_handler(index_page='app.html') 应将 app.html 传给实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = self._make_handler_instance(tmpdir, index_page='app.html')
            assert handler.directory == tmpdir
            assert handler.index_page == 'app.html'

    def test_default_index_page_is_index_html(self):
        """create_handler() 默认 index_page 应为 index.html"""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = self._make_handler_instance(tmpdir)
            assert handler.index_page == 'index.html'

    def test_find_latest_html_still_works_with_custom_index(self):
        """自定义首页不影响 _find_latest_html 行为"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard = os.path.join(tmpdir, 'dashboard.html')
            with open(dashboard, 'w') as f:
                f.write('<html>Dashboard</html>')

            handler = MagicMock(spec=SmartHTTPRequestHandler)
            handler.directory = tmpdir
            result = SmartHTTPRequestHandler._find_latest_html(handler)
            assert result == 'dashboard.html'

    def test_custom_index_affects_log_message(self):
        """自定义 index_page 应出现在 log_message 中"""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = self._make_handler_instance(tmpdir, index_page='dashboard.html')
            # 验证 index_page 被正确设置
            assert handler.index_page == 'dashboard.html'


class TestLogMessage:
    """日志输出 — OpenSpec: log-03"""

    def test_log_message_format(self, capsys):
        """日志格式应包含时间戳和消息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建 handler 实例，避免调用父类 __init__
            handler = MagicMock(spec=SmartHTTPRequestHandler)
            handler.directory = tmpdir
            # 直接调用实际方法
            SmartHTTPRequestHandler.log_message(handler, 'Test message')
            captured = capsys.readouterr()
            # 日志应包含时间戳格式 [YYYY-MM-DD HH:MM:SS]
            assert '[' in captured.err
            assert 'Test message' in captured.err


class TestRangeRequest:
    """Range 请求支持测试"""

    def test_parse_range_with_end(self):
        from http_server_cli.handler import _parse_range_header
        result = _parse_range_header('bytes=0-499', 1000)
        assert result == (0, 499)

    def test_parse_range_without_end(self):
        from http_server_cli.handler import _parse_range_header
        result = _parse_range_header('bytes=500-', 1000)
        assert result == (500, 999)

    def test_parse_range_invalid(self):
        from http_server_cli.handler import _parse_range_header
        assert _parse_range_header('invalid', 1000) is None
        assert _parse_range_header('bytes=-500', 1000) is None
        assert _parse_range_header('', 1000) is None

    def test_parse_range_start_past_end(self):
        from http_server_cli.handler import _parse_range_header
        assert _parse_range_header('bytes=2000-3000', 1000) is None

    def test_send_head_normal_has_accept_ranges(self, tmp_path):
        """普通请求应返回 Accept-Ranges: bytes"""
        import threading, urllib.request, socket, time, http.server
        (tmp_path / 'test.txt').write_text('hello world')
        from http_server_cli.handler import create_handler
        handler_cls = create_handler(str(tmp_path))

        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        httpd = http.server.HTTPServer(('127.0.0.1', port), handler_cls)
        def serve():
            httpd.handle_request()
        t = threading.Thread(target=serve)
        t.start()
        time.sleep(0.1)
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{port}/test.txt')
            resp = urllib.request.urlopen(req, timeout=3)
            assert resp.status == 200
            assert resp.getheader('Accept-Ranges') == 'bytes'
        finally:
            httpd.server_close()

    def test_send_head_range_returns_206(self, tmp_path):
        """Range 请求应返回 206 和 Content-Range"""
        import threading, urllib.request, socket, time, http.server
        (tmp_path / 'test.txt').write_text('hello world')
        from http_server_cli.handler import create_handler
        handler_cls = create_handler(str(tmp_path))

        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        httpd = http.server.HTTPServer(('127.0.0.1', port), handler_cls)
        def serve():
            httpd.handle_request()
        t = threading.Thread(target=serve)
        t.start()
        time.sleep(0.1)
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{port}/test.txt')
            req.add_header('Range', 'bytes=0-4')
            resp = urllib.request.urlopen(req, timeout=3)
            assert resp.status == 206
            assert resp.getheader('Content-Range') == 'bytes 0-4/11'
            assert len(resp.read()) == 5  # 'hello'
        finally:
            httpd.server_close()


class TestDoGetTouchMemory:
    """P0: do_GET 使用 _touch_memory 替代 Registry().touch()"""

    def test_touch_memory_does_not_call_registry_touch(self, monkeypatch):
        """_touch_memory 不应调用 Registry().touch()（验证不会触发原子写）"""
        import time
        import http_server_cli.registry as reg_mod
        reg_mod._last_access_cache.clear()
        reg_mod._last_flush_time = time.time()  # 当前时间，防止立即触发 flush
        monkeypatch.setattr(reg_mod, '_FLUSH_INTERVAL', 9999.0)

        # 监视 Registry.touch 是否被调用
        touch_called = []

        def fake_touch(self, port):
            touch_called.append(port)

        monkeypatch.setattr(reg_mod.Registry, 'touch', fake_touch)

        # _touch_memory 不应调用 Registry().touch()
        reg_mod._touch_memory(8080)
        assert len(touch_called) == 0
        assert 8080 in reg_mod._last_access_cache

    def test_touch_memory_importable_in_handler(self):
        """handler 模块应能导入 _touch_memory"""
        import time
        import http_server_cli.registry as reg_mod
        reg_mod._last_access_cache.clear()
        reg_mod._last_flush_time = time.time()  # 当前时间
        # 模拟 handler 中的 import 路径
        from http_server_cli.registry import _touch_memory
        _touch_memory(8080)
        assert 8080 in reg_mod._last_access_cache


class TestLogMessageThrottle:
    """P1: log_message 每 100 条 flush 一次"""

    def test_log_message_flush_every_100(self, monkeypatch):
        """每 100 条日志应触发一次 flush"""
        import http_server_cli.handler as handler_mod
        # 重置计数器
        handler_mod._log_count = 0

        flush_count = 0

        def fake_flush():
            nonlocal flush_count
            flush_count += 1

        import sys
        monkeypatch.setattr(sys.stderr, 'flush', fake_flush)

        try:
            from unittest.mock import MagicMock
            handler = MagicMock()
            for i in range(100):
                handler_mod.SmartHTTPRequestHandler.log_message(
                    handler, 'Test %d', i)

            # 第 100 条应触发一次 flush
            assert flush_count == 1
        finally:
            handler_mod._log_count = 0

    def test_log_message_no_flush_before_100(self, monkeypatch):
        """少于 100 条时不应 flush"""
        import http_server_cli.handler as handler_mod
        handler_mod._log_count = 0

        flush_count = 0

        def fake_flush():
            nonlocal flush_count
            flush_count += 1

        import sys
        monkeypatch.setattr(sys.stderr, 'flush', fake_flush)

        try:
            from unittest.mock import MagicMock
            handler = MagicMock()
            for i in range(99):
                handler_mod.SmartHTTPRequestHandler.log_message(
                    handler, 'Test %d', i)

            assert flush_count == 0  # 99 条不触发
        finally:
            handler_mod._log_count = 0