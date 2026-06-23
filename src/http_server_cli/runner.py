#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP 服务启动脚本：使用自定义处理器启动服务。

用法: python3 runner.py <port> <directory> [--bind <domain>] [--index <file>]
"""

import argparse
import os
import sys
from http.server import HTTPServer

# 添加包路径（上一级目录，使 http_server_cli 包可被导入）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http_server_cli.handler import create_handler


def main():
    parser = argparse.ArgumentParser(description='启动智能 HTTP 服务')
    parser.add_argument('port', type=int, help='监听端口')
    parser.add_argument('directory', help='服务目录')
    parser.add_argument('--bind', default='localhost', help='绑定域名')
    parser.add_argument('--index', default='index.html', help='首页文件名（默认 index.html）')
    args = parser.parse_args()

    # 创建处理器
    handler_class = create_handler(args.directory, index_page=args.index)

    # 启动服务
    server_address = (args.bind, args.port)
    httpd = HTTPServer(server_address, handler_class)

    print(f'Starting HTTP server on http://{args.bind}:{args.port}')
    print(f'Serving directory: {args.directory}')

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped.')
        httpd.shutdown()


if __name__ == '__main__':
    main()