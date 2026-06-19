# http-server-cli

> 忘记端口，只管预览 — Forget ports. Just preview.
>
> 基于 `python3 -m http.server`，零外部依赖。项目目录下 `hs . -o` 一键预览。

## 为什么用 `hs`

同时开发多个前端项目时，总在记 "A 用了几号端口" 和 "8080 被谁占了" 之间切换。

`hs` 把**启动 → 追踪 → 列出 → 关闭**闭环了：自动找空闲端口、记住哪个项目用哪个端口、随时查看和关闭。

## 对比一览

| 场景 | 以前 | 用 `hs` |
|:---------|:-----|:--------|
| 启动预览 | `python3 -m http.server 8080` + 手动开浏览器 | `hs . -o` |
| 查哪个项目在用 8080 | `lsof -i :8080`，再 `ps` 看路径 | `hs list` |
| 关掉某个服务 | `lsof` 查 PID → `kill` | `hs kill 8080` |
| 换个项目 | 先关旧的，再开新的（或冲突） | `hs start ../project-b` |
| 关掉所有 | 挨个查 PID 逐个 kill | `hs kill-all` |

## 安装

```bash
pip install -i https://test.pypi.org/simple/ http-server-cli
```

验证：
```
hs version     # → http-server-cli v1.0.3
hs . -o        # 当前目录启动 + 打开浏览器
```

## 用法

### 日常三件事

```bash
# 1. 到项目下无脑预览
cd ~/project-alpha
hs . -o                     # 自动找空闲端口，打开浏览器

# 2. 看看都起了哪些
hs list
# ✅  http://localhost:8080   →  ~/project-alpha
# ✅  http://localhost:8081   →  ~/project-beta  (daemon)

# 3. 关掉不需要的
hs kill 8080                # 按端口
hs kill ~/project-alpha     # 按路径
hs kill-all                 # 一键全关
```

### 所有命令

| 命令 | 说明 |
|:-----|:------|
| `hs . [-o] [-d] [-f]` | **快捷方式**，等价 `hs start .` |
| `hs start [path] [-o] [-d] [-f]` | 启动服务（path 默认 `.`；`-o` 打开浏览器；`-d` daemon 模式；`-f` 前台模式） |
| `hs list` | 列出所有运行中服务 |
| `hs list --json` | JSON 格式列出所有服务 |
| `hs status [port\|path]` | 查询单个服务状态 |
| `hs status --json [port\|path]` | JSON 格式查询服务状态 |
| `hs kill <port\|path>` | 关闭指定服务 |
| `hs kill-all` | 关闭所有服务 |
| `hs config` | 显示配置 |
| `hs config --json` | JSON 格式显示配置 |
| `hs set port <num>` | 修改默认端口（默认 8080） |
| `hs set domain <str>` | 修改绑定域名（默认 localhost） |

### 小贴士

- **`hs . -o`** = `hs start . -o`，敲起来更快
- **`hs . -d`**：daemon 模式，后台运行，可用 `hs list` 查看
- **`hs . -f`**：前台模式，Ctrl+C 终止服务
- **`hs`** 不带参数 = `hs start .`（当前目录启动）

## 数据目录

```
~/.http-server-cli/
├── config.json       # 默认端口/域名配置
├── registry.json     # port → {path, pid, domain, daemon, foreground, started_at}
└── logs/{port}.log   # http.server 日志
```

## 平台要求

当前仅支持 **macOS**（依赖 `lsof` 命令）。Linux/Windows 支持开发中。

## 本地开发

```bash
git clone git@github.com:imjaden/http-server-cli.git
cd http-server-cli
pip install -e .
python3 -m pytest tests/
```

## 这是在造轮子么

| 工具 | 启动服务 | 自动分配端口 | 追踪项目↔端口 | 列出所有 | 按名杀死 | 打开浏览器 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `python3 -m http.server` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `http-server` (npm) | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `serve` (npm) | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `live-server` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `kill-port-cli` (npm) | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| `lsof` / `netstat` | ❌ | ❌ | ❌ | 手动 | 手动 | ❌ |
| **`http-server-cli`** | **✅** | **✅** | **✅** | **✅** | **✅** | **✅** |
