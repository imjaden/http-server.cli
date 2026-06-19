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
from unittest.mock import MagicMock, patch

import pytest

from http_server_cli.handler import SmartHTTPRequestHandler

pytestmark = pytest.mark.spec("smart-homepage")


class TestHomepageRedirect:
    """首页智能跳转 — OpenSpec: home-01, home-02"""

    def test_find_latest_html_returns_none_when_no_html(self):
        """无 HTML 文件时返回 None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = SmartHTTPRequestHandler(
                MagicMock(), MagicMock(), MagicMock(), directory=tmpdir
            )
            result = handler._find_latest_html()
            assert result is None

    def test_find_latest_html_returns_single_html(self):
        """单个 HTML 文件时返回该文件名"""
        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = os.path.join(tmpdir, 'test.html')
            with open(html_file, 'w') as f:
                f.write('<html><body>Test</body></html>')

            handler = SmartHTTPRequestHandler(
                MagicMock(), MagicMock(), MagicMock(), directory=tmpdir
            )
            result = handler._find_latest_html()
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

            handler = SmartHTTPRequestHandler(
                MagicMock(), MagicMock(), MagicMock(), directory=tmpdir
            )
            result = handler._find_latest_html()
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

            handler = SmartHTTPRequestHandler(
                MagicMock(), MagicMock(), MagicMock(), directory=tmpdir
            )
            result = handler._find_latest_html()
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


class TestLogMessage:
    """日志输出 — OpenSpec: log-03"""

    def test_log_message_format(self, capsys):
        """日志格式应包含时间戳和消息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = SmartHTTPRequestHandler(
                MagicMock(), MagicMock(), MagicMock(), directory=tmpdir
            )
            handler.log_message('Test message')
            captured = capsys.readouterr()
            # 日志应包含时间戳格式 [YYYY-MM-DD HH:MM:SS]
            assert '[' in captured.err
            assert 'Test message' in captured.err