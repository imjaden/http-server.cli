# http-server-cli 功能特性

> 版本: 1.0.7
> 更新: 2026-06-24

## CLI 命令

| 命令 | 说明 |
|:-----|:------|
| `hs . [-o] [-d] [-f] [-i <file>]` | 启动服务（快捷方式，等价 `hs start .`） |
| `hs start [path] [-o] [-d] [-f] [-i <file>]` | 启动服务 |
| `hs list [--port\|--path\|--short] [--json]` | 列出服务，支持过滤选项 |
| `hs status <port\|path> [--json]` | 查询状态 |
| `hs kill <port\|path> [--json]` | 关闭服务 |
| `hs kill-all [--json]` | 关闭所有 |
| `hs history [--json]` | 历史记录 |
| `hs search <keyword> [--json]` | 搜索实例 |
| `hs dashboard [-p <port>] [-o]` | Web 管理面板 |
| `hs config [--json]` | 配置管理 |
| `hs set port\|domain <value>` | 修改配置 |
| `hs help` | 帮助 |
| `hs version [--json]` | 版本 |

## 功能亮点

1. **零外部依赖** — 仅 Python 标准库
2. **自动端口分配** — 默认 8080，冲突自动递增
3. **项目追踪** — registry.json 持久化 port↔path 映射
4. **智能首页** — 无 index.html 时自动重定向到最近修改的 html
5. **进程资源监控** — CPU、内存、运行时长
6. **多种启动模式** — daemon / foreground / 普通
7. **原子写入** — 防多进程并发脏读
8. **进程组管理** — daemon 模式使用 os.killpg 防孤儿进程
9. **JSON 输出** — 所有命令支持 `--json`
10. **Web Dashboard** — 图形化管理面板

## 数据结构

### registry.json
```json
{
  "servers": [
    {"port": 8080, "path": "/abs/path", "pid": 12345,
     "domain": "localhost", "daemon": false, "foreground": false,
     "started_at": "2026-06-20T00:00:00",
     "last_access_at": "2026-06-20T12:00:00",
     "index_page": "index.html"}
  ]
}
```

### history.json
```json
{
  "records": [
    {"port": 8080, "path": "/abs/path",
     "started_at": "2026-06-20T00:00:00",
     "ended_at": "2026-06-20T12:00:00",
     "memory_mb": 15.2, "domain": "localhost"}
  ]
}
```

## 发布脚本

- `release-local.sh` — 本地安装（`--editable` / `--versions`）
- `release-pypi.sh` — PyPI 发布（`--production` / `--versions`）
