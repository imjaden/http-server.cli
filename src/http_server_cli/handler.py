#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义 HTTP 请求处理器：首页智能跳转。

当访问根路径 `/` 时：
1. 若存在 index.html，正常返回
2. 若不存在，查找目录下所有 *.html 文件，按修改时间排序
3. 返回最近修改的 html 文件（HTTP 302 重定向）
"""

import os
import glob
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


class SmartHTTPRequestHandler(SimpleHTTPRequestHandler):
    """智能首页跳转的 HTTP 请求处理器"""

    def __init__(self, *args, directory=None, **kwargs):
        # 确保 directory 参数正确设置
        if directory is None:
            directory = os.getcwd()
        self.directory = directory
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self):
        """处理 GET 请求，首页智能跳转"""
        
        # 解析 URL，获取纯路径（忽略查询参数）
        parsed_path = urlparse(self.path).path
        
        # 仅处理根路径请求
        if parsed_path == '/' or parsed_path == '':
            # 检查是否存在 index.html
            index_path = os.path.join(self.directory, 'index.html')
            if os.path.isfile(index_path):
                # 存在 index.html，正常返回
                self.log_message('✅ 首页存在 index.html，正常返回')
                return super().do_GET()

            # 不存在 index.html，查找最近修改的 html 文件
            latest_html = self._find_latest_html()

            if latest_html:
                # 重定向到最近修改的 html 文件
                self.log_message(f'🔀 首页无 index.html，重定向到: {latest_html}')
                self.send_response(302)
                self.send_header('Location', f'/{latest_html}')
                self.end_headers()
                return
            else:
                self.log_message('⚠️ 首页无 index.html 且无其他 html 文件，返回目录列表')

        # 其他路径，使用默认处理（包括静态资源）
        return super().do_GET()

    def _find_latest_html(self) -> Optional[str]:
        """查找目录下最近修改的 html 文件"""
        html_files = glob.glob(os.path.join(self.directory, '*.html'))

        if not html_files:
            return None

        # 按修改时间排序，获取最近修改的文件
        latest_file = max(html_files, key=lambda f: os.path.getmtime(f))
        return os.path.basename(latest_file)

    def log_message(self, format, *args):
        """自定义日志格式，输出到 stderr"""
        import sys
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = format % args if args else format
        sys.stderr.write(f'[{timestamp}] {message}\n')
        sys.stderr.flush()


def create_handler(directory: str):
    """创建绑定指定目录的处理器类"""
    class DirectoryHandler(SmartHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

    return DirectoryHandler