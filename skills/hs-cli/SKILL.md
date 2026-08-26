---
name: hs-cli
description: HTTP Server CLI 总览 — 安装、命令速查、数据目录、--json 信封、启动方式。AI 使用 hs 前先读此篇。
---

# hs-cli — HTTP Server CLI 使用总览

## 简介

零依赖 Python 静态文件服务器 CLI（PyPI 包名 `http-server-cli`，命令 `hs`）。
自动分配端口（默认 8080 冲突递增）、持久化追踪服务、Web 面板与 MCP AI 集成。
与 npm 的 `http-server` 包无关。

## 安装

```bash
pip install http-server-cli
# 升级
pip install --upgrade http-server-cli
```

## 命令速查

### 日常预览

```bash
hs -o                    当前目录启动 + 打开浏览器
hs ~/my-site -o          指定目录启动 + 打开浏览器
hs . -i app.html         指定首页文件
hs . -d                  后台运行（不占用终端）
hs . --url               仅返回服务 URL（与 --json 互斥）
hs                       默认等于 hs .（当前目录启动）
hs start [path]          显式启动（-o 打开浏览器 / -d 后台 / -i <file> 首页）
hs /path/*.html          通配符解析最近修改的 HTML
```

### 服务管理

```bash
hs list [--port|--path|--short] [--json]   列出运行中服务
hs status <port|path> [--json]             查询单服务状态
hs kill <port|path|name> [--json]          关闭服务
hs kill-all [--json]                       一键关闭所有
hs history [--json]                        历史启动记录
hs search <keyword> [--json]               模糊搜索实例
```

### 图形与集成

```bash
hs dashboard -o           打开 Web 管理面板（默认 8180）
hs dashboard [stop|status|restart] [--json]
hs mcp                     启动 MCP Server（后台 SSE，AI 集成）
hs mcp [stop|status|restart] [--json]
hs mcp --stdio             前台 stdio 模式
hs mcp --config            输出 mcpServers 接入配置
hs prompt [<skill>]       输出技能使用说明（本命令）
```

### 配置

```bash
hs config [--json]          查看配置
hs set port <value>         修改默认端口（1024-65535）
hs set domain <value>       修改绑定域名
hs version [--json]         版本号
```

### 书签

```bash
hs bookmark add <name> [path] [-i index] [--force] [--json]
hs bookmark update <name> [path] [-i index] [--json]
hs bookmark list [--json]
hs bookmark show <name> [--json]
hs bookmark remove <name> [--json]
```

## --json 信封约定

所有管理命令追加 `--json` 输出结构化信封：

```json
{"success": true, "command": "list", "data": {...}, "error": null}
```

错误时 `success: false` + `error` 字段。AI 解析以此为准。

## 数据目录

`~/.http-server.cli/`（1.1.0 起；旧目录 `~/.http-server-cli` 自动迁移）：

```
config.json            # 默认配置（port/domain）
registry.json          # 运行中服务（port/path/pid/domain/started_at/index_page）
registry-managed.json  # 托管服务（dashboard / MCP SSE）
history.json           # 历史记录
bookmarks.json         # 书签
logs/{port}.log        # 服务日志
```

## 设计要点

- 零外部依赖（仅 Python 3.7+ 标准库）
- Range 请求支持（206 视频拖动）
- 智能首页：无 index.html 时自动重定向最近修改的 html
- 进程组管理：daemon 模式 os.killpg 防孤儿进程
- 原子写入防并发脏读
