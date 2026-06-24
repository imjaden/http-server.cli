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
5. **ManagedRegistry 自注册** — 仪表盘自身注册到 `registry-managed.json`，与用户服务隔离，`kill-all` 不影响
6. **自动刷新** — 前端每 5 秒通过 `fetch(/api/servers)` 自动刷新数据

---

## 二、用法

```bash
hs dashboard                 # 默认端口 8180、daemon 模式
hs dashboard -p 8181 -f      # 指定端口、foreground 模式
hs dashboard -p 8181 -d -o   # 后台启动并打开浏览器
hs dashboard --json          # JSON 格式返回仪表盘数据（一次性查询，含 managed 服务）
```

### 端口策略

- 默认端口：`8180`
- 冲突时自动递增，规则同 `hs start`
- 注册到 `registry-managed.json`（ManagedRegistry），与用户服务 `registry.json` 分离
- `kill-all` 仅关闭用户服务，不影响仪表盘本身

---

## 三、页面路由

| 路由 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 仪表盘主页（HTML） |
| `/api/servers` | GET | JSON：包含用户服务列表 + 基础设施服务(managed) |
| `/api/status/<port>` | GET | JSON：单个服务状态 |
| `/api/kill/<port>` | POST | 关闭指定服务，清理日志文件 |
| `/api/kill-all` | POST | 关闭所有用户服务，清理日志 |
| `/api/restart/<port>` | POST | 重启指定服务（daemon 模式） |

### API 响应结构

```jsonc
// GET /api/servers
{
  "success": true,
  "command": "list",
  "data": {
    "count": 3,
    "servers": [
      {
        "port": 8080,
        "path": "/Users/j/project-a",
        "path_display": "~/project-a",
        "pid": 1234,
        "alive": true,
        "domain": "localhost",
        "mode": "daemon",
        "started_at": "2025-01-01T00:00:00",
        "duration": "1h 23m",
        "index_page": "index.html",
        "stats": { "cpu": "0.0%", "memory": "12.3 MB" }
      }
    ],
    "managed": [
      {
        "name": "dashboard",
        "port": 8180,
        "pid": 5678,
        "_alive": true,
        "type": "http",
        "transport": "",
        "started_at": "2025-01-01T00:00:00",
        "stats": { "cpu": "0.1%", "memory": "8.2 MB" }
      }
    ]
  }
}
```

```jsonc
// POST /api/restart/<port>
{
  "success": true,
  "command": "restart",
  "data": {
    "path": "~/project-a",
    "old_port": 8080,
    "new_port": 8081   // 重新分配端口
  }
}
```

### 对应 CLI 命令映射

```
/api/servers  GET   → handler._get_server_list()
/api/status/  GET   → handler._handle_get_status(port)
/api/kill/    POST  → 读取 entry → os.killpg(SIGTERM→SIGKILL) → registry.remove → 删除日志
/api/kill-all POST  → 遍历 registry → killpg → remove → 删除日志
/api/restart/ POST  → kill(port) → manager.start(path, daemon=True) → 返回新端口
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
- **CSS**: 内联 `<style>`，简洁卡片风格（GitHub Dark 色系），响应式
- **JS**: 内联 `<script>`，`fetch()` 调用 API，`setInterval()` 定时刷新
- **图标**: Unicode / 纯 CSS 状态指示器（避免外部资源）
- **数据刷新**: 前端每 5 秒 `fetch(/api/servers)` 自动刷新

### 前端数据绑定

```javascript
// 前端通过 data.data.servers 和 data.data.managed 获取数据
fetchAPI('/api/servers', 'GET', function(err, data) {
  var servers = (data.data && data.data.servers) || [];
  var managed = (data.data && data.data.managed) || [];
  render(servers, managed);
});

// render() 函数处理两个列表：
// - managed: 显示为"🔧 基础设施服务"区域，只读（无操作按钮）
// - servers: 用户服务，显示状态、CPU、内存、操作按钮
```

### 页面结构

```html
<!-- Managed Services 区域 -->
<tr class="managed-header"><td colspan="7">🔧 基础设施服务</td></tr>
<!-- 每个 managed 条目：显示 name、port、_alive、stats，无操作 -->

<!-- User Servers 区域 -->
<!-- 每个 server 条目：显示 port、path_display、pid、alive、stats、操作按钮 -->
```

---

## 五、后端实现

### 新增文件：`src/http_server_cli/dashboard.py`

约 650 行，包含：
- `DashboardHandler` — HTTP 请求处理器
- `serve()` — 启动入口（含 daemon 模式、重复检测、JSON 模式）
- `_HTML_PAGE` — 内联 HTML/CSS/JS

#### DashboardHandler 核心结构

```python
class DashboardHandler(BaseHTTPRequestHandler):
    manager: ServerManager = None  # 在 HTTPServer 启动前设置

    # ── GET ──
    def do_GET(self):
        if self.path == '/':
            self._html(_HTML_PAGE)
        elif self.path == '/api/servers':
            self._handle_get_servers()
        elif self.path.startswith('/api/status/'):
            port_str = self.path.split('/')[-1]
            ...

    # ── POST ──
    def do_POST(self):
        if self.path.startswith('/api/kill/'):
            port_str = self.path.split('/')[-1]
            ...
        elif self.path == '/api/kill-all':
            self._handle_kill_all()
        elif self.path.startswith('/api/restart/'):
            port_str = self.path.split('/')[-1]
            ...
```

#### 服务列表生成 (`_get_server_list`)

```python
def _get_server_list(self) -> dict:
    """获取服务列表 + managed 基础设施服务"""
    # 1. 用户服务（来自 registry.json）
    entries = self.manager.registry.active_servers()
    servers = []
    for entry in entries:
        servers.append({
            'port': entry['port'],
            'path': entry['path'],
            'path_display': format_path(entry['path']),
            'pid': pid,
            'alive': entry['_alive'],
            'domain': entry.get('domain', 'localhost'),
            'mode': 'daemon' if entry.get('daemon') else ...,
            'started_at': started,
            'duration': format_duration(started),
            'index_page': entry.get('index_page', 'index.html'),
            'stats': get_process_stats(pid),
        })

    # 2. 基础设施服务（来自 registry-managed.json）
    mreg = ManagedRegistry()
    managed = []
    for entry in mreg.active_servers():
        managed.append({
            'name': entry.get('name', ''),
            'port': entry['port'],
            'pid': entry.get('pid'),
            '_alive': entry['_alive'],
            'type': entry.get('type', ''),
            'transport': entry.get('transport', ''),
            'started_at': entry.get('started_at', ''),
            'stats': get_process_stats(entry.get('pid')),
        })
    return {'servers': servers, 'managed': managed}
```

#### API 响应格式

```python
def _handle_get_servers(self):
    result = self._get_server_list()
    self._json({'success': True, 'command': 'list', 'data': {
        'count': len(result['servers']),
        'servers': result['servers'],
        'managed': result['managed'],
    }})
```

#### 关闭服务逻辑 (`_handle_kill`)

```python
def _handle_kill(self, port: int):
    entry = self.manager.registry.find(port=port)
    if not entry:
        self._error(f'端口 {port} 未注册')
        return
    pid = entry.get('pid')
    if pid and is_process_alive(pid):
        os.killpg(os.getpgid(pid), signal.SIGTERM)  # 进程组终止
        time.sleep(0.3)
        if is_process_alive(pid):
            os.killpg(os.getpgid(pid), signal.SIGKILL)  # 强制
    self.manager.registry.remove(port=port)
    # 删除日志文件
    log_path = os.path.join(LOG_DIR, f'{port}.log')
    if os.path.isfile(log_path):
        os.remove(log_path)
```

#### 重启服务逻辑 (`_handle_restart`)

先 kill 旧进程，再以 daemon 模式启动，返回新分配的端口号。

#### `serve()` 入口函数

```python
def serve(port: int = 8180, open_browser: bool = False,
          json_output_mode: bool = False, daemon: bool = False) -> None:
```

启动流程：

1. **JSON 输出模式** — 一次性输出用户服务 + managed 服务，不启动 HTTP 服务
2. **重复运行检测** — 检查 ManagedRegistry 中是否已有同名的 dashboard 条目：
   - 如果进程存活 → 打印当前状态并退出（不重复启动）
   - 如果进程已死 → 清理残留记录，继续启动
3. **端口冲突处理** — 检测端口被占用时自动递增
4. **Daemon 模式** — fork 子进程启动 HTTP 服务：
   - 父进程（当前 CLI 进程）立即返回
   - 父进程负责打开浏览器（如果有 `-o` 参数）
   - 子进程注册到 ManagedRegistry
5. **Foreground 模式**（默认）— 当前进程直接启动 `HTTPServer.serve_forever()`
   - 注册 ManagedRegistry
   - 打开浏览器（如果有 `-o` 参数）
   - Ctrl+C 时清理 ManagedRegistry 并关闭服务器

---

## 六、CLI 入口

### 修改 `cli.py`

```python
@_register
def _cmd_dashboard(manager, args):
    """hs dashboard — Web 仪表盘"""
    parser = argparse.ArgumentParser(prog='hs dashboard', add_help=False)
    parser.add_argument('-p', '--port', type=int, default=8180)
    parser.add_argument('-o', '--open', action='store_true')
    parser.add_argument('-d', '--daemon', action='store_true')
    parser.add_argument('--json', action='store_true')
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return
    from http_server_cli.dashboard import serve
    serve(port=parsed.port, open_browser=parsed.open,
          json_output_mode=parsed.json, daemon=parsed.daemon)
```

---

## 七、工作量估算（实际）

| 模块 | 文件 | 代码量 | 时间 |
|------|------|--------|------|
| CLI 入口 | `cli.py` | +12 行 | 0.5h |
| 后端 Handler + 启动入口 | `dashboard.py` | ~420 行 | 3h |
| HTML/CSS/JS | 内联在 dashboard.py | ~260 行 | 3h |
| ManagedRegistry | `registry_managed.py` | ~100 行 | 1h |
| API 联调 | 测试 | ~50 行 | 1h |
| **合计** | | **~840 行** | **~2 天** |
