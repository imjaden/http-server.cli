# hs-cli 架构设计文档

> 项目: http-server-cli
> 文件: `hs` CLI 工具 — 忘记端口，只管预览
> 数据目录: `~/.http-server-cli/`

---

## 目录

1. [CLI 入口：argparse 分派](#1-cli-入口argparse-分派)
2. [命令注册模式（@\_register 装饰器）](#2-命令注册模式_register-装饰器)
3. [ServerManager 类](#3-servermanager-类)
4. [注册表系统](#4-注册表系统)
5. [数据流：CLI → ServerManager → Registry](#5-数据流cli--servermanager--registry)
6. [JSON 输出信封](#6-json-输出信封)
7. [端口管理](#7-端口管理)
8. [进程生命周期](#8-进程生命周期)

---

## 1. CLI 入口：argparse 分派

**入口模块**: `src/http_server_cli/cli.py`
**入口函数**: `main()`

### 命令行入口

```
python -m http_server_cli        # via __main__.py
hs [command] [args]              # via pip-installed entry point
```

### main() 解析流程

```
main()
  ├── argparse 顶层解析（command + REMAINDER args）
  ├── 命令名规范化（连字符 → 下划线, e.g. kill-all → kill_all）
  ├── 隐式命令检测：
  │   ├── -h / --help          → cmd = 'help'
  │   ├── 无命令 / -v/__version → cmd = 'version'
  │   ├── cmd is None           → cmd = 'start'（默认行为）
  │   ├── 以 . / ~ / / 开头      → 视为 start path 参数
  │   └── 不在 _COMMANDS 中      → 报错 + 显示帮助
  ├── ensure_storage()          → 初始化 ~/.http-server-cli/
  ├── ServerManager() 实例化
  └── _COMMANDS[cmd](manager, args)  → 分派到命令处理器
```

### 关键设计决策

- **不依赖 argparse 子解析器**，而是使用简单的 `nargs=argparse.REMAINDER` 捕获所有剩余参数，再由每个命令处理器自行构造子 `ArgumentParser`。这样做的好处是子命令可以独立处理 `--json`、`--help` 等标记，避免 argparse 子解析器的耦合。
- **隐式 start 命令**: 用户输入 `hs .` 或 `hs ~/my-site` 时，首个参数以路径特征开头（`.`、`/`、`~`），自动转为 `start` 命令。
- **--json 标志**: 每个子命令通过 `parsed.json` 或 `'--json' in args` 检测。JSON 模式改变输出格式（见第 6 节），并跳过交互行为（如 `tail -f`、浏览器打开）。

---

## 2. 命令注册模式（@\_register 装饰器）

### 装饰器定义

```python
_COMMANDS = {}

def _register(func):
    """装饰器：注册命令处理函数"""
    _COMMANDS[func.__name__.replace('_cmd_', '')] = func
    return func
```

### 工作机制

1. 每个命令处理函数命名约定为 `_cmd_<command_name>`。
2. `@_register` 去掉 `_cmd_` 前缀后注册到 `_COMMANDS` 字典。
3. 所有注册函数签名相同: `(manager: ServerManager, args: list[str]) -> None`。
4. 调用时通过 `_COMMANDS[cmd](manager, parsed.args)` 执行。

### 已注册命令一览

| 命令 | 函数 | 功能 |
|------|------|------|
| `start` | `_cmd_start` | 启动 HTTP 服务 |
| `list` | `_cmd_list` | 列出所有服务（含 managed） |
| `status` | `_cmd_status` | 查询单个服务状态 |
| `kill` | `_cmd_kill` | 关闭单个服务 |
| `kill-all` | `_cmd_kill_all` | 关闭所有用户服务 |
| `killall` | `_cmd_killall` | `kill-all` 的别名 |
| `config` | `_cmd_config` | 显示配置 |
| `set` | `_cmd_set` | 修改配置项 |
| `help` | `_cmd_help` | 显示帮助 |
| `version` | `_cmd_version` | 显示版本号 |
| `dashboard` | `_cmd_dashboard` | 启动 Web 管理面板 |
| `mcp` | `_cmd_mcp` | 启动 MCP Server |

### 设计意图

- **声明式注册**: 新增命令只需写一个 `_cmd_xxx` 函数并加 `@_register` 即可，无需修改分派逻辑。
- **零配置**: 不需要单独的 YAML/TOML 命令配置，代码即注册表。
- **一致性**: 所有命令处理器接受相同的参数签名，便于统一测试和扩展。

---

## 3. ServerManager 类

**模块**: `src/http_server_cli/server.py`
**类名**: `ServerManager`

### 角色

`ServerManager` 是整个 CLI 的核心业务逻辑层，封装 HTTP 服务的**全生命周期管理**。它不直接处理 CLI 参数解析（交给命令处理器），也不直接负责 JSON 序列化（交给 `json_output`），而是聚焦于领域逻辑。

### 类结构

```python
class ServerManager:
    def __init__(self):
        self.config = Config()       # 用户配置（端口、域名）
        self.registry = Registry()   # 用户服务注册表

    # 核心方法
    def start(self, path, open_browser, daemon, foreground, json, index_page)
    def list(self, json)
    def status(self, arg, json)
    def kill(self, arg, json)
    def kill_all(self, json)
```

### ServerManager.start() 核心流程

```
start()
  ├── 路径解析与验证（resolve_path, os.path.isdir）
  ├── 检查 registry 中该路径是否已运行
  │   ├── 已注册 + 进程存活 + 端口占用 → 直接打开浏览器返回
  │   └── 残留记录 → 清理后重新启动
  ├── 查找可用端口（find_available_port）
  ├── 启动子进程（subprocess.Popen + runner.py）
  ├── 写入 registry（registry.add）
  ├── 可选打开浏览器（webbrowser.open）
  ├── daemon 模式：tail -f 日志 + Ctrl+C 仅退出日志查看
  └── foreground 模式：proc.wait() + Ctrl+C 终止服务
```

### ServerManager 与其他组件的关系

```
command handler (CLI layer)
    │
    ▼
ServerManager (business logic layer)
    │
    ├── Config          → 读取 port / domain 配置
    ├── Registry        → 读写用户服务注册表
    ├── utils.py:
    │   ├── find_available_port  → 端口扫描
    │   ├── is_port_in_use       → 端口占用检测
    │   ├── is_process_alive     → 进程存活检测
    │   ├── get_process_stats    → CPU/内存统计
    │   ├── json_output          → JSON 信封输出
    │   └── ...
    └── runner.py       → 实际 HTTP 服务进程（HTTPServer）
```

---

## 4. 注册表系统

采用**双注册表架构**，将用户服务与基础设施服务分离存储，互不干扰。

### 4.1 Registry — 用户 HTTP 服务

**文件**: `~/.http-server-cli/registry.json`
**模块**: `src/http_server_cli/registry.py`
**类名**: `Registry`

#### JSON 结构

```json
{
  "servers": [
    {
      "port": 8081,
      "path": "/Users/jadenli/my-site",
      "pid": 12345,
      "domain": "localhost",
      "daemon": true,
      "foreground": false,
      "started_at": "2026-06-17T17:30:00",
      "index_page": "index.html"
    }
  ]
}
```

#### 核心 API

| 方法 | 功能 |
|------|------|
| `all()` | 返回所有条目 |
| `find(port, path)` | 按端口或路径查找 |
| `active_servers()` | 返回存活状态装饰后的条目（附加 `_alive` 字段） |
| `add(port, path, pid, ...)` | 添加条目 + 即时持久化 |
| `remove(port, path)` | 删除匹配条目 + 即时持久化 |
| `clear()` | 清空 + 即时持久化 |
| `count()` | 条目计数 |

#### 设计要点

- **变更即时持久化**：每次 `add`/`remove`/`clear` 后立即调用 `save()`。
- **状态装饰模式**：`active_servers()` 不修改原始数据，而是返回新的 dict 列表，每个条目附加 `_alive` 字段（`is_process_alive(pid) and is_port_in_use(port)`）。
- **零外部依赖**: 纯 Python JSON I/O，无数据库。
- **原子写入**：通过 `write_json()` 的临时文件 + `os.replace` 机制防止并发脏读。

### 4.2 ManagedRegistry — 基础设施服务

**文件**: `~/.http-server-cli/registry-managed.json`
**模块**: `src/http_server_cli/registry_managed.py`
**类名**: `ManagedRegistry`

#### JSON 结构

```json
{
  "services": [
    {
      "name": "dashboard",
      "type": "dashboard",
      "port": 8180,
      "pid": 54321,
      "transport": "",
      "started_at": "2026-06-17T17:30:00"
    },
    {
      "name": "mcp",
      "type": "sse",
      "port": 8181,
      "pid": 54322,
      "transport": "sse",
      "started_at": "2026-06-17T17:30:00"
    }
  ]
}
```

#### 与 Registry 的差异

| 特性 | Registry | ManagedRegistry |
|------|----------|-----------------|
| 存储文件 | `registry.json` | `registry-managed.json` |
| 记录对象 | 用户 HTTP 服务 | 基础设施服务（dashboard、MCP） |
| 主键 | port / path | name / port |
| `kill-all` 影响 | ✅ 关闭所有 | ❌ 不受影响 |
| `hs list` 展示 | ✅ 显示 | ✅ 独立区段展示 |
| `dashboard` 展示 | ✅ 显示 | ✅ 独立区段展示 |

#### 设计意图

- **关注点分离**：用户服务（`hs start` 启动的）与工具自身服务（dashboard、MCP）分开管理。
- **独立生命周期**：`hs kill-all` 只关闭用户服务，不关闭基础设施（用户期望 dashboard/MCP 持续运行）。
- **统一展示**：`hs list` 和 dashboard 的 `/api/servers` 端点会合并两注册表结果，但用区段区分。

---

## 5. 数据流：CLI → ServerManager → Registry

### 启动服务（hs start）数据流

```
用户输入:
  hs . -o -d
    │
    ▼
main() — argparse 解析顶层命令
    │  cmd = 'start', args = ['.', '-o', '-d']
    ▼
_cmd_start(manager, ['.', '-o', '-d'])
    │  子 parser 解析: path='.', open=True, daemon=True
    ▼
manager.start(path='.', open_browser=True, daemon=True, ...)
    │
    ├── Config()  → port=8080, domain='localhost'
    ├── resolve_path('.')  → abs_path='/Users/jadenli/CodeSpace/my-site'
    │
    ├── registry.find(path=abs_path)  → 检查是否已运行
    │   └── Registry.read_json('registry.json')  → 磁盘 I/O
    │
    ├── find_available_port(8080)  → 从 8080 递增扫描
    │   └── is_port_in_use(port)  → socket 检测
    │
    ├── subprocess.Popen(runner.py, ..., preexec_fn=os.setsid)
    │   └── runner.py → HTTPServer.serve_forever()
    │
    ├── registry.add(port=port, path=path, pid=pid, ...)
    │   └── write_json('registry.json', data)  → 原子写入
    │
    ├── webbrowser.open(f'http://localhost:{port}')
    │
    └── [daemon mode] subprocess.run(['tail', '-f', log_path])
```

### 关闭服务（hs kill）数据流

```
用户输入:
  hs kill 8080
    │
    ▼
_cmd_kill(manager, ['8080'])
    │
    ▼
manager.kill('8080')
    │
    ├── registry.find(port=8080)  → {port, path, pid, ...}
    │
    ├── os.killpg(pgid, SIGTERM)  → 发送终止信号
    │   └── 如果超时未退出 → os.killpg(pgid, SIGKILL)
    │
    ├── registry.remove(port=8080)  → 清理注册条目
    │
    └── os.remove(log_path)  → 清理日志文件
```

### 列出服务（hs list）数据流

```
_cmd_list(manager, args)
    │
    ├── Registry.active_servers()
    │   └── 遍历 → is_process_alive(pid) + is_port_in_use(port)
    │       → 返回 [{port, path, pid, ..., _alive}, ...]
    │
    ├── ManagedRegistry.active_servers()
    │   └── 类似逻辑 → [{name, port, pid, ..., _alive}, ...]
    │
    └── [JSON mode] json_output(success=True, command='list',
                                data={servers: [...], managed: [...]})
```

---

## 6. JSON 输出信封

**模块**: `src/http_server_cli/utils.py`
**函数**: `json_output()`

### 信封格式

```json
{
  "success": true,
  "command": "start",
  "data": { ... },
  "error": null
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 操作是否成功 |
| `command` | `str` | 命令名（start/list/status/kill/kill-all/config/set/version） |
| `data` | `any` | 业务数据 payload，失败时为 `null` |
| `error` | `str\|null` | 失败时的错误描述，成功时为 `null` |

### 设计意图

- **机器可解析**: 标准结构供 MCP、dashboard API、CI 脚本、AI Agent 消费。
- **人类友好**: 也通过 `print(json.dumps(...))` 输出，终端用户仍可阅读。
- **MCP 集成**: MCP Server 的 `_execute_hs()` 方法解析此信封，提取 `data` 作为 JSON-RPC 结果。
- **一致性**: 所有命令（start、list、kill、config、version）使用同一输出函数，避免各自实现。

### 使用模式

```python
# 成功
json_output(True, 'start', data={
    'url': 'http://localhost:8081',
    'port': 8081, 'path': '/site', 'pid': 12345,
    ...
})

# 失败
json_output(False, 'start', error='端口 8080-10000 已全部被占用，无法启动')
```

---

## 7. 端口管理

**模块**: `src/http_server_cli/utils.py`

### 端口检测

```python
def is_port_in_use(port: int) -> bool:
    """socket 直连检测端口是否被占用（跨平台）"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            return s.connect_ex(('127.0.0.1', port)) == 0
        except (socket.gaierror, OSError):
            return False
```

- 使用 **TCP socket 连接检测**而非 `lsof`，确保跨平台兼容（Linux/Windows/macOS）。
- 超时 `0.5s` 避免长时间阻塞。

### 空闲端口查找

```python
def find_available_port(start_port: int) -> Optional[int]:
    """从 start_port 递增查找空闲端口，MAX_PORT 封顶"""
    port = start_port
    while port <= MAX_PORT:    # MAX_PORT = 10000
        if not is_port_in_use(port):
            return port
        port += 1
    return None
```

- 从用户配置的 `default_port`（默认 8080）开始递增查找。
- **上限 MAX_PORT = 10000**，避免无限循环。
- 查找失败时返回 `None`，调用方输出友好错误信息。

### 批量端口检测（macOS 优化）

```python
def get_all_occupied_ports() -> set:
    """一次性获取所有 LISTEN 状态的端口（仅 macOS 优化）"""
    # 调用 lsof -iTCP -sTCP:LISTEN -P -n
    # 返回占用端口的集合
```

- macOS 上通过 `lsof` 快速获取所有 LISTEN 端口，用于批量检测。
- 非 macOS 平台回退到空集，`find_available_port` 逐个检测。

### 端口冲突处理

1. **服务已注册且存活**: `ServerManager.start()` 检测到已注册条目进程存活 + 端口占用 → 直接返回已有 URL，不重新启动。
2. **默认端口被占用**: 自动递增查找下一个可用端口，并提示用户 `端口 8080 已被占用，自动分配端口 8081`。
3. **端口耗尽**: 如果 `default_port` 到 `MAX_PORT` 全部占用，报错退出。
4. **端口被非本工具服务占用**: `hs status <port>` 可检测端口被其他进程占用的情况，并显示进程信息。
5. **残留注册记录**: 注册条目存在但进程已死 → 清理后重新启动。

---

## 8. 进程生命周期

### 架构概览

```
                    ┌─────────────────────────────┐
                    │     hs CLI (parent process)  │
                    │     main() → ServerManager   │
                    └─────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
    │ normal mode │   │ daemon mode  │   │foreground    │
    │ (deprecated)│   │ (subprocess  │   │ mode         │
    │             │   │  + setsid)   │   │ (proc.wait() │
    └─────────────┘   └──────────────┘   │ + Ctrl+C)   │
                                          └──────────────┘
                     ▲                   ▲
                     │                   │
              ┌──────┴──────┐   ┌────────┴────────┐
              │ runner.py   │   │ tail -f log     │
              │ HTTPServer  │   │ (daemon sub-    │
              │ (child)     │   │  process)        │
              └─────────────┘   └─────────────────┘
```

### 8.1 Daemon 模式（推荐）

**用户命令**: `hs . -d` 或 `hs start . -d`

**行为**:

```
1. CLI 启动子进程（runner.py）:
   subprocess.Popen(
       [sys.executable, runner.py, port, path, ...],
       preexec_fn=os.setsid,    # 创建新进程组
   )

2. runner.py 在后台运行 HTTPServer:
   httpd = HTTPServer((domain, port), HandlerClass)
   httpd.serve_forever()

3. CLI 进入日志查看模式:
   subprocess.run(['tail', '-f', log_path])

4. 用户按 Ctrl+C:
   - 仅终止 `tail -f` 进程
   - 日志查看结束，HTTP 服务继续在后台运行
   - 提示: "日志查看已停止，服务 http://localhost:8081 仍在后台运行"
```

**关键设计点**:

- **`preexec_fn=os.setsid`**: 在子进程 `fork` 后立即调用 `setsid()` 创建新 session 和新进程组。当父进程（CLI）退出时，子进程不会收到 SIGHUP，确保后台服务持续运行。
- **进程组管理**: 后续 `kill` 操作通过 `os.getpgid(pid)` 获取进程组 ID，再使用 `os.killpg(pgid, SIGTERM)` 终止整个进程组，确保 runner.py 及可能产生的子进程全部被清理。
- **日志分离**: 子进程 stdout/stderr 重定向到 `~/.http-server-cli/logs/<port>.log`，不占用终端。
- **日志尾部查看**: 使用 `tail -f` 跟随日志，用户直观看到服务输出；Ctrl+C 仅终止 `tail` 不伤及后台服务。

### 8.2 Foreground 模式

**用户命令**: `hs . -f` 或 `hs start . --foreground`

**行为**:

```
1. CLI 启动子进程（runner.py）:
   subprocess.Popen(..., preexec_fn=os.setsid)

2. CLI 进入等待模式:
   try:
       proc.wait()   # 阻塞等待子进程退出
   except KeyboardInterrupt:
       os.killpg(pgid, SIGTERM)
       time.sleep(0.5)
       if alive: os.killpg(pgid, SIGKILL)
       registry.remove(port=port)
```

**与 daemon 模式的区别**:

| 特性 | Daemon | Foreground |
|------|--------|------------|
| Ctrl+C 效果 | 停止日志查看，服务继续 | 终止服务进程 |
| 终端占用 | 否（退出日志查看后） | 是（需要保持终端运行） |
| 典型用途 | "启动后继续工作" | "开发调试" |

### 8.3 Normal 模式

**用户命令**: `hs .`（无 -d 也无 -f）

**行为**: 启动子进程后，CLI 立即退出。进程在后台以 orphan 状态运行（继承父进程的进程组，可能受终端事件影响）。此模式存在是因为历史原因，新代码应使用 daemon 模式。

### 8.4 进程终止

**`kill` 操作**:

```python
pgid = os.getpgid(pid)
os.killpg(pgid, signal.SIGTERM)   # 先发 SIGTERM（优雅终止）
time.sleep(0.5)
if is_process_alive(pid):
    os.killpg(pgid, signal.SIGKILL)  # 无响应则 SIGKILL（强制终止）
```

- **两步终止**: 先 SIGTERM 让 HTTP 服务有机会完成当前请求和清理，0.5 秒后未退出再 SIGKILL。
- **进程组终止**: 确保 runner 及其所有子进程（如 CGI 子进程）被完整清理。

### 8.5 MCP / Dashboard 的进程管理

- **Dashboard**: 通过 `serve()` 函数启动，daemon 模式下使用 `subprocess.Popen(preexec_fn=os.setsid)` + `ManagedRegistry.add()` 注册。
- **MCP SSE**: 类似 daemon 模式，通过子进程启动 HTTPServer 并注册到 `ManagedRegistry`。
- **Managed 服务的生命周期**遵循同样的 setsid/进程组管理原则，但不受 `kill-all` 影响。

### 8.6 进程状态检测

```python
def is_process_alive(pid):
    """信号 0 检测 PID 是否存活"""
    try:
        os.kill(pid, 0)    # 信号 0 不发送实际信号，仅做存活检测
        return True
    except (OSError, ProcessLookupError):
        return False
```

- 使用 POSIX `kill(pid, 0)` 检测进程是否存在，标准且高效，不产生子进程。
- 与 `is_port_in_use()` 组合使用（`_alive = alive and port_active`），避免孤儿进程但端口已被释放的虚假存活状态。

---

## 附录 A: 文件结构

```
~/.http-server-cli/
├── config.json              # 用户配置（port, domain）
├── registry.json            # 用户 HTTP 服务注册表
├── registry-managed.json    # 基础设施服务注册表（dashboard, MCP）
└── logs/
    ├── 8081.log             # 端口 8081 服务的日志
    ├── 8180.log             # dashboard 日志
    └── 8181.log             # MCP SSE 日志

src/http_server_cli/
├── __init__.py              # 包初始化 + 版本号
├── __main__.py              # python -m http_server_cli 入口
├── cli.py                   # CLI 入口：argparse + 命令注册 + 分派
├── server.py                # ServerManager：服务全生命周期管理
├── registry.py              # Registry：用户服务注册表
├── registry_managed.py      # ManagedRegistry：基础设施服务注册表
├── config.py                # Config：配置读写
├── utils.py                 # 工具函数：端口、进程、JSON I/O
├── runner.py                # HTTP 服务启动脚本（HTTPServer）
├── handler.py               # HTTP 请求处理器
├── dashboard.py             # Web 管理面板（HTML + REST API）
└── mcp.py                   # MCP 协议服务器（stdio + SSE）
```

---

## 附录 B: 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| CLI 框架 | `argparse` | Python 标准库，零外部依赖 |
| HTTP 服务 | `http.server.HTTPServer` | Python 标准库 HTTP 服务器 |
| 进程管理 | `subprocess.Popen` | 子进程启动 + setsid 后台化 |
| 数据持久化 | `json` (文件) | 原子写入（临时文件 + rename） |
| 端口检测 | `socket.connect_ex` | 跨平台 TCP 连接检测 |
| 进程检测 | `os.kill(pid, 0)` | POSIX 信号 0 存活检测 |
| MCP 协议 | 自定义 JSON-RPC 2.0 | stdio / SSE 传输 |
| Web UI | 内联 HTML + CSS + JS | dashboard 单页应用 |
| 外部依赖 | **零** | 全 Python 标准库实现 |
