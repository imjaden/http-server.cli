# hs dashboard — Web 仪表盘设计

> 版本: 2.0
> 更新: 2026-06-29

## 架构

```
用户浏览器  ←→  hs dashboard (HTTPServer, 默认 8180)
                  │
                  ├── / (HTML 页面 — 中文)
                  ├── /en (HTML 页面 — 英文)
                  ├── /api/servers (GET)  — 服务列表
                  ├── /api/status/{port} (GET) — 服务详情
                  ├── /api/kill/{port} (POST) — 关闭服务
                  └── /api/kill-all (POST) — 关闭全部
```

零外部依赖，内嵌 HTML 页面，使用 Python `http.server` 模块。
中英文双 HTML 文件: `dashboard.html`（中文） + `dashboard.en.html`（英文），通过右上角 lang-toggle pill 切换。

## 页面布局

```
┌─────────────────────────────────────────────────────┐
│  📊 HTTP Server Dashboard  [GitHub图标]              │
│  ┌──────────┐ ┌──────────┐  ┌─────┐ ┌──────┐ ┌──────┐│
│  │ 实例数 3  │ │ 总内存 45MB│  │ 60s│ │ 🔄  │ │🛑Kill││
│  └──────────┘ └──────────┘  └─────┘ └──────┘ └──────┘│
├──────────────────────────────────────────────────────┤
│ URL (Port)   │ Status │ CPU │ Memory │ Last Access │ Action│
│─────────────┼────────┼─────┼────────┼─────────────┼───────│
│ :8080       │ 🟢 Run │ 0%  │ 15MB   │ 12:00       │  ⏹    │
│ :8081       │ 🟢 Run │ 2%  │ 22MB   │ 11:30       │  ⏹    │
└──────────────────────────────────────────────────────┘

仅显示 STATUS 为 Running 的实例。Stopped 实例不展示。
点击 Status 徽章弹出 confirm() 显示详情（端口/路径/PID/内存/启动时间/日志路径/最近访问）。
URL 列渲染为 `<a href="{{url}}" target="_blank">` 超链接。
```

## API 响应格式

所有 API 返回统一 JSON 格式：

```json
{"success": true, "command": "list", "data": {...}}
```

### GET /api/servers

返回字段:

| 字段 | 类型 | 说明 |
|:-----|:-----|:------|
| `url` | string | 完整 URL（含 domain+port） |
| `port` | int | 端口号 |
| `path` | string | 绝对路径 |
| `path_display` | string | 缩写路径 |
| `pid` | int | 进程 PID |
| `alive` | bool | 是否存活 |
| `mode` | string | daemon / foreground / normal |
| `started_at` | string | ISO 时间 |
| `last_access_at` | string | 最近访问时间 |
| `duration` | string | 运行时长 |
| `log_path` | string | 日志文件路径 |
| `stats.cpu` | string | CPU 占用 |
| `stats.memory` | string | 内存占用 |
| `stats.memory_num` | float | 内存 MB 数值 |

### GET /api/status/{port}

同上，但仅返回单个服务。

## 功能清单

### v1（2026-06-24）
- [x] 统计指标卡片（Total Instances / Ports / Paths / Memory）
- [x] 实例清单表格（port/path/pid/status/CPU/memory/started_at/last_access_at）
- [x] URL 点击打开新标签页
- [x] 关闭按钮 + 确认弹框（显示进程信息）
- [x] 关闭全部按钮 + 确认
- [x] 自动刷新（5s）
- [x] 日志文件查看（Managed Services 区域）

### v2（2026-06-29）
- [x] 中英文语言切换（🇨🇳 `/` ↔ 🇺🇸 `/en`），右上角悬浮 pill
- [x] 顶部统计精简为实例数 + 总内存，移除 Ports/Paths
- [x] 工具栏：60s 倒计时自动刷新 + Refresh 按钮 + Kill All 按钮
- [x] 表格：URL(Port) | Status | CPU | Memory | Last Access | Action（移除 PATH/PID/STARTED）
- [x] URL 列用 `url` 字段渲染为 `<a target="_blank">` 超链接
- [x] Status 点击弹框：显示端口/路径/PID/内存/启动时间/日志路径/最近访问
- [x] `window.onerror` + `unhandledrejection` 全局异常捕捉覆盖层
- [x] API 增加 `url` + `log_path` + `last_access_at` 字段
- [x] 仅显示 Running 实例，Stopped/Dead 不展示
- [x] H1 标题右侧添加 GitHub 图标，点击跳转至仓库
- [x] 测试用例 18 个
