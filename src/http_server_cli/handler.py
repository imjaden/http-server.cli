#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义 HTTP 请求处理器：首页智能跳转 + Range 请求支持。

当访问根路径 `/` 时：
1. 若存在 index.html，正常返回
2. 若不存在，查找目录下所有 *.html 文件，按修改时间排序
3. 返回最近修改的 html 文件（HTTP 302 重定向）

Range 请求支持：
- 所有非目录文件返回 Accept-Ranges: bytes
- 收到 Range 头时返回 206 Partial Content
- 支持单范围请求（bytes=START-END / bytes=START-）
"""

import os
import glob
import re
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse


# Range 头解析: bytes=START-END 或 bytes=START-
_RANGE_RE = re.compile(r'^bytes=(\d+)-(\d*)$')


def _parse_range_header(range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
    """解析 Range 请求头，返回 (start, end) 或 None。

    >>> _parse_range_header('bytes=0-499', 1000)
    (0, 499)
    >>> _parse_range_header('bytes=500-', 1000)
    (500, 999)
    """
    m = _RANGE_RE.match(range_header.strip())
    if not m:
        return None
    start = int(m.group(1))
    end_str = m.group(2)
    if end_str:
        end = min(int(end_str), file_size - 1)
    else:
        end = file_size - 1
    if start > end or start >= file_size:
        return None
    return (start, end)


class SmartHTTPRequestHandler(SimpleHTTPRequestHandler):
    """智能首页跳转 + Range 请求支持的 HTTP 请求处理器"""

    def __init__(self, *args, directory=None, index_page='index.html', **kwargs):
        if directory is None:
            directory = os.getcwd()
        self.directory = directory
        self.index_page = index_page
        super().__init__(*args, directory=directory, **kwargs)

    def send_head(self):
        """重写 send_head，添加 Range 请求支持。

        在父类逻辑基础上：
        - 所有非目录文件响应添加 Accept-Ranges: bytes
        - 收到 Range 头时返回 206 Partial Content + Content-Range
        """
        path = self.translate_path(self.path)

        # 目录处理（与父类一致）
        if os.path.isdir(path):
            import urllib.parse
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith('/'):
                self.send_response(301)
                new_parts = (parts[0], parts[1], parts[2] + '/',
                             parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            for index_name in self.index_pages:
                index = os.path.join(path, index_name)
                if os.path.isfile(index):
                    path = index
                    break
            else:
                return self.list_directory(path)

        if path.endswith("/"):
            self.send_error(404, "File not found")
            return None

        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        try:
            fs = os.fstat(f.fileno())
            file_len = fs[6]

            # Range 请求处理
            range_header = self.headers.get('Range')
            if range_header:
                parsed = _parse_range_header(range_header, file_len)
                if parsed is None:
                    # 无效 Range → 416 Range Not Satisfiable
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{file_len}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    f.close()
                    return None
                start, end = parsed
                self.send_response(206)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_len}')
                self.send_header('Content-Length', str(end - start + 1))
                f.seek(start)
            else:
                self.send_response(200)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Length', str(file_len))

            ctype = self.guess_type(path)
            self.send_header('Content-type', ctype)
            self.send_header('Last-Modified', self.date_time_string(fs.st_mtime))
            self.end_headers()
            return f
        except:
            f.close()
            raise

    def do_GET(self):
        """处理 GET 请求，首页智能跳转，记录访问时间"""
        
        # 记录最新访问时间
        try:
            from http_server_cli.registry import Registry
            reg = Registry()
            reg.touch(self.server.server_port)
        except Exception:
            pass
        
        # 解析 URL，获取纯路径（忽略查询参数）
        parsed_path = urlparse(self.path).path
        
        # 仅处理根路径请求
        if parsed_path == '/' or parsed_path == '':
            # 检查是否存在指定的首页文件
            index_path = os.path.join(self.directory, self.index_page)
            if os.path.isfile(index_path):
                self.log_message(f'✅ 首页存在 {self.index_page}，正常返回')
                return super().do_GET()

            # 不存在首页文件，查找最近修改的 html 文件
            latest_html = self._find_latest_html()

            if latest_html:
                self.log_message(f'🔀 首页无 {self.index_page}，重定向到: {latest_html}')
                self.send_response(302)
                from urllib.parse import quote
                self.send_header('Location', f'/{quote(latest_html)}')
                self.end_headers()
                return
            else:
                self.log_message(f'⚠️ 首页无 {self.index_page} 且无其他 html 文件，返回目录列表')

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


def create_handler(directory: str, index_page: str = 'index.html'):
    """创建绑定指定目录的处理器类"""
    class DirectoryHandler(SmartHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, index_page=index_page, **kwargs)

    return DirectoryHandler