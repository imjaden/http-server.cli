# http-server-cli 功能特性

> 版本: 1.0.8
> 更新: 2026-07-01

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
10. **仅运行中** — `hs list` / `hs search` 仅显示运行中的实例
11. **智能历史** — `hs history` 自动过滤系统临时目录
12. **英文 CLI 输出** — 统一英文消息，规范格式化
13. **Web Dashboard** — 图形化管理面板
    - 中英文语言切换（🇨🇳 `/?lang=zh` ↔ 🇺🇸 `/en`），右上角悬浮 pill
    - 工具栏：60s 倒计时自动刷新、刷新按钮、Kill All 一键关闭
    - 服务器表格：URL(Port) | Health | Status | CPU | Memory | Last Access | Action
    - Status 点击弹框：显示端口/路径/PID/内存/启动时间/日志路径/最近访问 + 最近 50 行日志
    - `window.onerror` 全局异常捕捉，覆盖层弹框显示完整 stack trace
    - 健康检查探活：🟢/🟡/🔴 圆点标识 HTTP 响应状态
    - 搜索过滤框：实例 >10 时自动显示，实时按端口/路径关键字过滤
    - 一键复制 URL：📋 按钮点击复制到剪贴板
    - 底部版本号 + 可折叠命令参考
    - API：list / status / kill / kill-all / ping / log / info

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
