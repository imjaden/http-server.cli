# hs ports — 端口占用检测与诊断 v1.1

日期: 2025-07-16
状态: 待评审
类型: 功能设计
前版: v1.0 (已评审: 合理性🟢 严格性🟡 安全性🟢)

## 变更摘要 (v1.0 → v1.1)

| 编号 | 来源 | 变更 |
|------|------|------|
| H1 | 严格性-➊ | hs 🔴 拆分为三种子状态：hs-zombie / hs-conflict / hs-dead |
| H2 | 严格性-➋ | get_ports_info() 补充 lsof -F 解析伪代码 |
| H3 | 严格性-➍ | _parse_port_range 边界校验表 |
| H4 | 严格性-➎ | 文本列宽自适应：PROJECT 截断 + 动态列宽 |
| H5 | 严格性-➌ | --all 性能：registry 预索引为 {port: entry} dict |

## CLI 接口

### 命令矩阵

```bash
hs ports                     # 扫描默认范围 config.port ~ +20
hs ports 8083                # 单端口详情
hs ports 8080-8090           # 范围扫描
hs ports --all               # 全量 1024-10000
hs ports --json              # JSON 输出（可与以上任意组合）
```

### 输出格式（文本）

```
PORT   STATUS         PROCESS            PID   ADDRESS      PROJECT
8080   hs ✅ running  http-server-cli    1234  127.0.0.1    ~/CodeSpace/llm-radar
8081   hs 👻 zombie   http-server-cli    5678  127.0.0.1    ~/CodeSpace/hermes
8082   hs ⚡ conflict  —                  —     [::1]        ~/CodeSpace/daily
8083   hs 💀 dead     —                  —     —            ~/tmp
8084   occupied       Python             9012  0.0.0.0      —
8085   free           —                  —     —            —
```

### STATUS 五态详解

```
hs registry 中有记录?
  ├─ PID 存活?
  │   ├─ lsof 端口被占用?
  │   │   ├─ lsof PID == registry PID → hs ✅ running   (正常)
  │   │   └─ lsof PID != registry PID → hs ⚡ conflict   (端口被其他进程抢占)
  │   └─ lsof 端口空闲?
  │       └─ hs ⚠️ mismatch  (进程在但端口不对，极少见)
  └─ PID 已死?
      ├─ lsof 端口被占用? → hs 👻 zombie  (进程 crash，端口被抢)
      └─ lsof 端口空闲?   → hs 💀 dead    (进程 crash，端口空闲，可重启)
```

| STATUS | 图标 | 含义 | 用户操作 |
|--------|------|------|----------|
| `running` | ✅ | hs 管理，正常运行 | 无需操作 |
| `zombie` | 👻 | hs 进程 crash，端口已被其他进程占用 | **先 kill 占用进程，再重启 hs** |
| `conflict` | ⚡ | hs 进程存活，但端口被其他进程抢占 | **kill 占用进程** |
| `dead` | 💀 | hs 进程 crash，端口空闲 | **直接重启 hs** |
| `occupied` | — | 非 hs 进程占用 | 参考 `hs ports <port>` 详情 |
| `free` | — | 空闲 | 可启动新服务 |

### 单端口详情

```bash
$ hs ports 8083

PORT 8083 — hs 👻 zombie
  Project:  ~/CodeSpace/daily-tracker
  Started:  2026-07-16 15:30
  Now on port: [::1]:8083  ← Python (PID 22551)
  Command:    /Library/.../Python3 -m http.server 8083 --bind jaden.local
  Note:       hs process is dead, port taken by another process.
              Kill PID 22551 first, then restart hs.
```

### JSON 输出

```json
{
  "command": "ports",
  "range": "8080-8100",
  "ports": [
    {
      "port": 8080,
      "status": "running",
      "process": "http-server-cli",
      "pid": 1234,
      "address": "127.0.0.1",
      "address_family": "IPv4",
      "project": "/Users/jadenli/CodeSpace/llm-radar.jaden.tech",
      "bookmark": null,
      "started_at": "2026-07-16T18:00:00",
      "url": "http://localhost:8080"
    },
    {
      "port": 8083,
      "status": "zombie",
      "registry_pid": 5678,
      "actual_pid": 22551,
      "actual_process": "Python",
      "actual_command": "python3 -m http.server 8083 --bind jaden.local",
      "address": "[::1]",
      "address_family": "IPv6",
      "project": "/Users/jadenli/CodeSpace/daily-tracker",
      "started_at": "2026-07-16T15:30:00"
    },
    {
      "port": 8085,
      "status": "free"
    }
  ]
}
```

## 决策清单

| # | 问题 | 选型 |
|---|------|------|
| Q1 | 命令名 | `hs ports` |
| Q2 | 默认扫描范围 | config.port ~ +20 |
| Q3 | 无参数行为 | 扫描默认范围 |
| Q4 | 非 hs 进程信息 | PID + 命令 + 用户 + address |
| Q5 | `--all` 范围 | 1024-MAX_PORT |
| Q6 | 端口范围语法 | `8080-8090` |
| Q7 | `--watch` 持续监控 | v1.0 不支持 |

## 实现方案

### 1. `_parse_port_range` 边界校验

```python
def _parse_port_range(arg: Optional[str], default_start: int,
                      max_port: int) -> Optional[Tuple[int, int]]:
    """解析端口范围，返回 (start, end) 或 None（错误）。

    行为:
      None         → (default_start, default_start + 20)
      '8083'       → (8083, 8083)
      '8080-8090'  → (8080, 8090)
      反向范围     → 自动交换
      超界         → 裁剪到 [1024, max_port]
      非数字       → None（错误）
    """
    if arg is None:
        end = min(default_start + 20, max_port)
        return (default_start, end)

    parts = arg.split('-')
    if len(parts) == 1:
        try:
            p = int(parts[0])
        except ValueError:
            return None
        return (p, p)
    elif len(parts) == 2:
        try:
            a, b = int(parts[0]), int(parts[1])
        except ValueError:
            return None
        start, end = min(a, b), max(a, b)  # 自动交换反向范围
        start = max(start, 1024)
        end = min(end, max_port)
        return (start, end)
    return None
```

### 2. `get_ports_info()` — lsof -F 解析

```python
def get_ports_info() -> dict:
    """获取所有 LISTEN 端口的进程详情。

    返回: {port: {'pid': int, 'command': str, 'user': str,
                  'address': str, 'family': 'IPv4'|'IPv6'}, ...}

    实现: 调用 lsof -iTCP -sTCP:LISTEN -P -n -F pcTLn
    -F 输出为每行一个字段（前缀+值），空行分隔记录：
      p22551        ← PID
      cPython        ← command (前 9 字符)
      L22548        ← PPID
      ujadenli      ← user
      n[::1]:8083   ← bind address
      TST=LISTEN     ← TCP state

    非 macOS: lsof 不可用时返回空 dict（端口状态仅依赖 registry + is_port_in_use）。
    """
    import sys, subprocess

    if sys.platform != 'darwin':
        return {}  # 非 macOS: 回退

    try:
        result = subprocess.run(
            ['lsof', '-iTCP', '-sTCP:LISTEN', '-P', '-n', '-F', 'pcTLun'],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='ignore',
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}

    if result.returncode != 0:
        return {}

    ports = {}
    current = {}
    for line in result.stdout.strip().split('\n'):
        if not line:
            # 空行 = 记录结束，flush
            if 'address' in current and 'pid' in current:
                ports.setdefault(current['port'], current)
            current = {}
            continue
        prefix, value = line[0], line[1:]
        if prefix == 'p':
            current['pid'] = int(value)
        elif prefix == 'c':
            current['command'] = value
        elif prefix == 'u':
            current['user'] = value
        elif prefix == 'n':
            # n[::1]:8083 或 n127.0.0.1:8083
            addr_str = value
            current['address'] = addr_str
            # 提取 port + family
            if addr_str.startswith('['):
                current['family'] = 'IPv6'
                host_part = addr_str.rsplit(']:', 1)
            else:
                current['family'] = 'IPv4'
                host_part = addr_str.rsplit(':', 1)
            if len(host_part) == 2:
                try:
                    current['port'] = int(host_part[1])
                except ValueError:
                    pass

    # flush last record
    if current and 'address' in current and 'pid' in current:
        ports.setdefault(current['port'], current)

    return ports
```

### 3. 主逻辑：交叉 registry + lsof

```python
def _cmd_ports(manager, args):
    parser = argparse.ArgumentParser(prog='hs ports', add_help=False)
    parser.add_argument('range', nargs='?', default=None)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--all', action='store_true')
    ...

    start, end = _parse_port_range(...)
    lsof_data = get_ports_info()

    # 预索引 registry（O(1) 查找替代 O(n) 线性扫描）
    reg_map = {}
    for s in manager.registry.active_servers():
        reg_map[s['port']] = s

    from http_server_cli.bookmark import BookmarkStore
    bm_store = BookmarkStore()

    results = []
    for port in range(start, end + 1):
        entry = reg_map.get(port)
        lsof_entry = lsof_data.get(port)

        if entry:
            pid_alive = is_process_alive(entry.get('pid'))
            if pid_alive and lsof_entry:
                if lsof_entry['pid'] == entry['pid']:
                    status = 'running'
                else:
                    status = 'conflict'
            elif pid_alive and not lsof_entry:
                status = 'mismatch'  # 极少见
            elif not pid_alive and lsof_entry:
                status = 'zombie'
            else:
                status = 'dead'
        elif lsof_entry:
            status = 'occupied'
        else:
            status = 'free'

        results.append({...})

    _output_ports(results, json=parsed.json)
```

### 4. 文本列宽自适应

```python
def _output_ports_text(results):
    # 获取终端宽度，默认 80
    try:
        term_width = os.get_terminal_size().columns
    except (OSError, ValueError):
        term_width = 80

    # 列宽: PORT(7) + STATUS(17) + PROCESS(10) + PID(7) + ADDRESS(17) = 58 固定
    fixed_width = 58
    project_width = max(term_width - fixed_width, 15)

    header = (f"{'PORT':<7}{'STATUS':<17}{'PROCESS':<10}"
              f"{'PID':<7}{'ADDRESS':<17}{'PROJECT':<{project_width}}")
    ...
    for r in results:
        project = format_path(r.get('project', '—'))
        if len(project) > project_width:
            project = '…' + project[-(project_width - 1):]
```

## 文件变更清单

| 文件 | 变更 |
|------|------|
| `src/http_server_cli/utils.py` | 新增 `get_ports_info()` + `_parse_port_range` |
| `src/http_server_cli/cli.py` | 新增 `_cmd_ports` + `_output_ports_text/json` + 注册 + 帮助 |
| `tests/test_utils.py` | `get_ports_info` + `_parse_port_range` 测试 |
| `tests/test_cli.py` | `hs ports` 集成测试 |

## 不纳入 v1.0

| 项目 | 理由 |
|------|------|
| `--watch` 持续监控 | 后续迭代 |
| 非 macOS lsof 替代方案（/proc/net/tcp 解析） | 复杂度高，v1.0 仅 mac |
