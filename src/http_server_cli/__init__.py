# -*- coding: utf-8 -*-
"""
Karpathy Principles - AI编程四大原则
=====================================
1. 先思考 - 不假设，不隐藏困惑 → 不确定就问，多种解释列出
2. 保持简单 - 最小代码解决问题 → 无多余抽象
3. 精准修改 - 只改必须改的 → 不"顺便"改进邻接代码
4. 目标驱动 - 测试先行，验证闭环 → "修bug"→"写测试复现→让测试通过"

http-server-cli — 本地 HTTP 服务管理器
=====================================
基于 python3 -m http.server，自动检测可用端口、记录项目映射、管理服务生命周期。

Version: 1.1(2026-06-20)
Description
- 本地 HTTP 服务管理器，零外部依赖
- 自动检测可用端口，记录项目映射
- 支持服务生命周期管理（启动/停止/列表/状态）

【指令清单】
| 指令 | 功能说明 |
|------|---------|
| start [path] [-o] [-d] [-f] | 启动服务（path 默认 .；-o 打开浏览器；-d daemon；-f foreground） |
| list [--json] | 列出所有运行中的服务（--json 输出 JSON） |
| status [--json] [port|path] | 查询单个服务状态（--json 输出 JSON） |
| kill <port|path> | 关闭指定服务 |
| kill-all | 关闭所有服务 |
| config [--json] | 显示当前配置（--json 输出 JSON） |
| set port <num> | 修改默认端口 |
| set domain <str> | 修改绑定域名 |
| help | 显示帮助信息 |
| version | 显示版本号 |

【辅助工具】
| 工具方法 | 功能说明 |
|---------|---------|
| eprint() | 智能打印，自动匹配 Emoji 前缀 |
| format_path() | 路径格式化，支持 ~ 简写 |
| ensure_storage() | 确保数据目录存在 |
| get_process_stats() | 获取进程资源使用情况 |

Related Paths
- 数据目录: ~/.http-server-cli/
- 配置文件: ~/.http-server-cli/config.json
- 注册表: ~/.http-server-cli/registry.json
- 日志目录: ~/.http-server-cli/logs/

Environments:
- Mac macOS
- Python 3.7+
- IDE TRAE CN

Dependency
- 零外部依赖，仅依赖 Python 标准库

触发条件
- 本地开发需要快速启动 HTTP 服务时
- 需要管理多个 HTTP 服务时

版本说明
- 主版本号默认为 1，修订号从 0 开始
- 每次代码修改后修订号 +1
- 重大架构变更时主版本号 +1，修订号归零
"""

__version__ = '1.0.4'
