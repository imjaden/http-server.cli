# hs dashboard — Web 仪表盘设计

> 版本: 1.0
> 更新: 2026-06-24

## 架构

```
用户浏览器  ←→  hs dashboard (HTTPServer, 默认 8180)
                  │
                  ├── / (HTML 页面)
                  ├── /api/servers (GET)  — 服务列表
                  ├── /api/status/{port} (GET) — 服务详情
                  ├── /api/kill/{port} (POST) — 关闭服务
                  └── /api/kill-all (POST) — 关闭全部
```

零外部依赖，内嵌 HTML 页面，使用 Python `http.server` 模块。

## 页面布局

```
┌─────────────────────────────────────────────────────┐
│  📊 hs dashboard                                    │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐  ┌──────┐  │
│  │Total │ │Total │ │Total │ │Total   │  │关闭  │  │
│  │Inst. │ │Ports │ │Paths │ │Memory  │  │全部  │  │
│  └──────┘ └──────┘ └──────┘ └────────┘  └──────┘  │
├─────────────────────────────────────────────────────┤
│ URL (Port) │ 路径 │ PID │ 状态 │ CPU │ 内存 │ 启动时间 │ 最新访问 │ 操作 │
│───────────┼──────┼─────┼──────┼─────┼──────┼─────────┼──────────┼──────│
│ :8080     │ ~/a  │ 123 │ 🟢   │ 0%  │ 15MB │ 10:00   │ 12:00    │ [关闭]│
│ :8081     │ ~/b  │ 456 │ 🔴   │ -   │ -    │ 10:05   │ 11:00    │ [启动]│
└─────────────────────────────────────────────────────┘
```

## API 响应格式

所有 API 返回统一 JSON 格式：

```json
{"success": true, "command": "list", "data": {...}}
```

## 功能清单

- [x] 统计指标卡片（Total Instances / Ports / Paths / Memory）
- [x] 实例清单表格（port/path/pid/status/CPU/memory/started_at/last_access_at）
- [x] URL 点击打开新标签页
- [x] 关闭按钮 + 确认弹框（显示进程信息）
- [x] 关闭全部按钮 + 确认
- [x] 自动刷新
- [x] 日志文件查看（Managed Services 区域）
