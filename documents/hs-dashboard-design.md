# hs dashboard — 设计文档

> 基于 Python 标准库 http.server 的 Web 仪表盘，零外部依赖。

---

## 一、概述

`hs dashboard` 启动一个本地 Web 服务，提供图形化界面管理 `hs` 托管的 HTTP 服务。

### 设计原则

1. **零外部依赖** — 仅使用 Python 标准库（`http.server`, `json`, `html`）
2. **复用现有逻辑** — 直接调用 `ServerManager`，不重复实现 registry/process 操作
3. **与 CLI 共享数据** — 读取同一份 `registry.json`，操作结果即时同步
4. **轻量内联** — HTML/CSS/JS 全部内联在 Python 代码中，无外部文件

---

## 二、用法

```bash
hs dashboard                 # 默认端口 8180、daemon 模式
hs dashboard -p 8181 -f      # 指定端口、foreground 模式
hs dashboard -p 8181 -d -o   # 后台启动并打开浏览器
hs dashboard --json          # JSON 格式返回仪表盘数据（一次性查询）
```

### 端口策略

- 默认端口：`8180`
- 冲突时自动递增，规则同 `hs start`
- 不写入 registry（仪表盘不是托管服务）

---

## 三、页面路由

| 路由 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 仪表盘主页（HTML） |
| `/api/servers` | GET | JSON：所有服务列表（同 `list --json`） |
| `/api/status/<port>` | GET | JSON：单个服务状态 |
| `/api/kill/<port>` | POST | 关闭指定服务 |
| `/api/kill-all` | POST | 关闭所有服务 |
| `/api/restart/<port>` | POST | 重启指定服务 |

### 对应 CLI 命令映射

```
/api/servers  GET   → server.list(json=True)
/api/status/  GET   → server.status(arg=port, json=True)
/api/kill/    POST  → server.kill(arg=port)
/api/kill-all POST  → server.kill_all()
/api/restart/ POST  → server.kill(port) → 获取 path → server.start(path)
```

---

## 四、前端页面设计

### 布局

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  hs dashboard                                                                    │
│  ┌──────┐ ┌──────┐ ┌──────┐                                                      │
│  │ 运行中│ │ 已停止│ │ 总端口│                                                      │
│  │  3   │ │  1   │ │  4   │                                                      │
│  └──────┘ └──────┘ └──────┘                                                      │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │ URL(Port)              │ 路径          │ PID  │ 状态 │ CPU │ 内存  │ 操作 │      │
│  │────────────────────── ┼───────────────┼──────┼──────┼─────│──────│──────│     │
│  │ http://localhost:8180 │ ~/project-a   │ 1234 │ 🟢   │ 0.0% │ 0.0% │  ⏹  │      │
│  │ http://localhost:8181 │ ~/project-b   │ 1235 │ 🟢   │ 0.0% │ 0.0% │  ⏹  │      │
│  │ http://localhost:8182 │ ~/project-c   │ 1236 │ 🔴   │ 0.0% │ 0.0% │  ▶  │      │
│  └─────────────────────────────────────────────────────────────────────────┘      │
│                                                                                   │
│  [ 一键关闭全部 ]                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 技术实现

- **HTML**: 内联，单页应用
- **CSS**: 内联 `<style>`，简洁卡片风格，响应式
- **JS**: 内联 `<script>`，`fetch()` 调用 API，`setInterval()` 定时刷新
- **图标**: Unicode / 纯 CSS 状态指示器（避免外部资源）
- **数据刷新**: 前端每 5 秒 `fetch(/api/servers)` 自动刷新

---

## 五、后端实现

### 新增文件：`src/http_server_cli/dashboard.py`

```python
class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self._serve_html()
        elif self.path == '/api/servers':
            self._json_response(manager.list(json=True))
        elif self.path.startswith('/api/status/'):
            port = self.path.split('/')[-1]
            self._json_response(manager.status(arg=port, json=True))
        else:
            self._json_response({'error': 'not found'}, 404)

    def do_POST(self):
        if self.path == '/api/kill-all':
            manager.kill_all()
            self._json_response({'success': True})
        elif self.path.startswith('/api/kill/'):
            port = int(self.path.split('/')[-1])
            manager.kill(str(port))
            self._json_response({'success': True})
        elif self.path.startswith('/api/restart/'):
            port = int(self.path.split('/')[-1])
            # kill + get path + start
            ...
```

### HTML 内联生成

HTML 页面作为 Python 多行字符串内联在 `dashboard.py` 中：

```python
_HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>hs dashboard</title>
  <style>
    /* 所有样式内联，约 100 行 */
  </style>
</head>
<body>
  <!-- 页面结构 -->
  <script>
    // 所有 JS 内联，约 80 行
  </script>
</body>
</html>"""
```

---

## 六、CLI 入口

### 修改 `cli.py`

```python
@_register
def _cmd_dashboard(manager, args):
    parser = argparse.ArgumentParser(prog='hs dashboard', add_help=False)
    parser.add_argument('-p', '--port', type=int, default=8180)
    parser.add_argument('-o', '--open', action='store_true')
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    # 启动仪表盘
    from http_server_cli.dashboard import serve
    serve(port=parsed.port, open_browser=parsed.open, json_output=parsed.json)
```

---

## 七、工作量估算

| 模块 | 文件 | 代码量 | 时间 |
|------|------|--------|------|
| CLI 入口 | `cli.py` | +5 行 | 0.5h |
| 后端 Handler | `dashboard.py` | ~120 行 | 2h |
| HTML/CSS/JS | 内联在 dashboard.py | ~200 行 | 3h |
| API 联调 | 测试 | ~50 行 | 1h |
| **合计** | | **~375 行** | **~1 天** |
