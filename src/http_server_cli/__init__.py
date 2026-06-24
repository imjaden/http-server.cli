# -*- coding: utf-8 -*-
"""
http-server-cli — 本地 HTTP 服务管理器
=====================================
基于 python3 -m http.server，自动检测可用端口、记录项目映射、管理服务生命周期。

Description
- 本地 HTTP 服务管理器，零外部依赖
- 自动检测可用端口，记录项目映射
- 支持服务生命周期管理（启动/停止/列表/状态）

Related Paths
- 数据目录: ~/.http-server-cli/
- 配置文件: ~/.http-server-cli/config.json
- 注册表: ~/.http-server-cli/registry.json
- 日志目录: ~/.http-server-cli/logs/

Dependency
- 零外部依赖，仅依赖 Python 标准库

触发条件
- 本地开发需要快速启动 HTTP 服务时
- 需要管理多个 HTTP 服务时
"""

__version__ = '1.0.7'
