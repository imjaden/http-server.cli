---
name: hs-dashboard
description: Web 管理面板 — 启动/停止/状态、REST API、中英文切换、健康检查、日志查看。
---

# hs-dashboard — Web 管理面板

## 简介

图形化管理面板：表格展示全部服务（URL/健康/状态/CPU/内存/最近访问），支持一键关闭、搜索过滤、日志查看、状态弹框。

## 启动与管理

```bash
hs dashboard -o             # 打开面板（自动后台运行，默认端口 8180）
hs dashboard                # 仅启动不打开
hs dashboard status         # 查看面板状态
hs dashboard stop           # 停止面板
hs dashboard restart        # 重启
hs dashboard --json         # 一次性查询服务列表（不启动面板）
```

## 界面能力

1. 中英文切换：🇨🇳 `/?lang=zh` ↔ 🇺🇸 `/en`（右上角悬浮 pill）
2. 工具栏：60s 倒计时自动刷新 / 刷新按钮 / Kill All 一键关闭
3. 服务器表格：URL(Port) | Health | Status | CPU | Memory | Last Access | Action
4. 健康检查探活：🟢/🟡/🔴 圆点标识 HTTP 响应状态
5. 搜索过滤框：实例 >10 时自动显示，实时按端口/路径关键字过滤
6. 状态弹框：端口/路径/PID/内存/启动时间/日志路径/最近访问 + 最近 50 行日志
7. 一键复制 URL 📋
8. 全局异常捕捉：window.onerror 覆盖层弹框显示完整 stack trace

## REST API

| 端点 | 说明 |
|------|------|
| /api/list | 服务列表 |
| /api/status?port= | 单服务状态 |
| /api/kill?port= | 关闭服务 |
| /api/kill-all | 全部关闭 |
| /api/ping | 健康探活 |
| /api/log?port=&lines= | 服务日志 |
| /api/info | 面板/版本信息 |

## 数据

- 面板自身为 registry-managed 托管服务（registry-managed.json）
- 服务数据来自用户 registry（~/.http-server.cli/registry.json）

## 关联文档

- documents/hs-dashboard-design-v2.0-20260629.md
