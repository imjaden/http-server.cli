# handler 热路径性能优化方案

> 项目: http-server-cli
> 版本: v1.1 (2026-07-22)
> 状态: 设计阶段（待评审）
> 关联: handler.py L138-174 / registry.py L86-93 / utils.py L65-77
>
> v1.0 → v1.1 变更: Q1 60s / Q2 每 100 条 flush / Q3 懒初始化一并实施

---

## 一、问题现象

### 1.1 内存持续上涨（无请求时）

```
7.1MB → 15.7MB → 24.7MB → 25.0MB  （2 分钟内）
```

### 1.2 单文件下载极慢

```
$ time curl http://jaden.local:8081/.../file.html (99KB)
→ 1:07.82 total  （正常应 < 0.1s）
```

### 1.3 与 python3 -m http.server 对比

`python3 -m http.server` 无持久化开销，请求处理路径纯净。hs 服务在同样场景下异常慢。

---

## 二、根因分析

### 2.1 核心问题：`do_GET` 热路径上的持久化操作

`handler.py` 第 138-147 行，**每个 HTTP GET 请求**都执行：

```python
def do_GET(self):
    # ↓ 热路径：每次请求都触发
    from http_server_cli.registry import Registry
    reg = Registry()                    # ① read_json(registry.json) + json.load
    reg.touch(self.server.server_port)  # ② 遍历 → 更新 last_access_at → save()

    # ... 然后才是实际请求处理 ...
    return super().do_GET()
```

调用链展开：

```
do_GET()
  ├─ Registry()                                  # 读 registry.json + JSON 解析
  ├─ touch(port)
  │   ├─ 遍历 servers[] 找匹配条目
  │   ├─ entry['last_access_at'] = timestamp()
  │   └─ save()
  │       └─ write_json(REGISTRY_PATH, data)
  │           ├─ os.makedirs()                  # syscall（即使 exist_ok=True）
  │           ├─ tempfile.mkstemp()             # 创建临时文件
  │           ├─ json.dump(data, indent=2)       # 序列化整个 registry
  │           └─ os.replace(tmp, filepath)       # 原子 rename
  └─ super().do_GET()                            # 实际文件服务
```

**影响面**：所有请求（HTML、CSS、JS、图片、favicon）都经过此路径。一个页面 20 个资源 = 20 次原子写。

### 2.2 次要问题：`log_message` 强制 `stderr.flush()`

`handler.py` 第 187-193 行：

```python
def log_message(self, format, *args):
    sys.stderr.write(...)
    sys.stderr.flush()  # ← 每请求强制刷盘
```

基类 `SimpleHTTPRequestHandler.log_request()` 每个请求调用一次 `log_message`。stderr 重定向到日志文件时，每次 flush 触发磁盘写入。

### 2.3 综合 I/O 开销（单请求）

| 步骤 | 操作 | 类别 |
|:---|:---|:---|
| Registry() | `open` + `read` + `json.load` | 读 I/O |
| touch() → save() | `mkstemp` + `json.dump` + `os.replace` | 写 I/O（原子） |
| log_message | `write` + `flush` | 写 I/O（同步） |

### 2.4 内存增长机制

- 每次请求: `Registry()` 分配新 dict → `json.load` 分配字符串/列表 → `json.dump` 分配缓冲区
- Python 堆内存分配后不会立即归还 OS（正常行为），工作集稳定在 ~22MB
- 初始 7→25MB 是堆从冷启动到稳态的扩张过程

### 2.5 67 秒延迟的可能触发场景

67 秒异常不是每次都出现（当前同一服务器请求仅需 ~5ms）。可能触发条件：
- 请求并发时多个 `touch()` 争抢同一文件的原子写
- macOS 文件系统瞬时压力（iCloud 同步、Spotlight 索引）
- `mkstemp` + `os.replace` 在 DATA_DIR 上的延迟累积

---

## 三、修复方案

### 3.1 P0🔴：移除 `do_GET` 中的 per-request `touch()` → 内存标记 + 60s 刷盘

**方案**：将 `touch()` 从请求热路径移除，改为内存标记 + 定期刷盘（60 秒间隔）。

```python
# handler.py — 修改后
def do_GET(self):
    # 内存标记（极轻量，仅更新 dict，不写盘）
    try:
        from http_server_cli.registry import _touch_memory
        _touch_memory(self.server.server_port)
    except Exception:
        pass

    # 保持原有智能首页逻辑不变
    parsed_path = urlparse(self.path).path
    if parsed_path == '/' or parsed_path == '':
        # ... 智能首页重定向 ...
    return super().do_GET()
```

```python
# registry.py — 新增内存级 touch（不触发 save）
import time as _time

_last_access_cache: dict = {}       # {port: timestamp}
_last_flush_time: float = 0.0
_FLUSH_INTERVAL: float = 60.0       # Q1 决策: 60 秒刷一次盘

def _touch_memory(port: int) -> None:
    """内存级标记访问时间，不写盘。"""
    _last_access_cache[port] = _time.time()
    # 定期刷盘（60s 间隔，Q1=B）
    if _time.time() - _last_flush_time >= _FLUSH_INTERVAL:
        _flush_access_cache()

def _flush_access_cache() -> None:
    """将缓存中的 last_access_at 批量写入 registry。"""
    global _last_flush_time
    if not _last_access_cache:
        return
    reg = Registry()
    for port, ts in _last_access_cache.items():
        entry = reg.find(port=port)
        if entry:
            from datetime import datetime
            entry['last_access_at'] = datetime.fromtimestamp(ts).isoformat(
                timespec='seconds')
    reg.save()
    _last_access_cache.clear()
    _last_flush_time = _time.time()
```

**理由**：
- `last_access_at` 是低频读取字段（仅 dashboard 状态弹框展示），60 秒精度足够
- 消除 per-request 的 `Registry()` 构造 + `read_json` + `write_json`
- 热路径从「读+解析+序列化+原子写」变为「dict 赋值 + 条件判断（60s 一次时间戳比较）」

### 3.2 P1🟡：`log_message` 降频 flush（每 100 条一次）

```python
# handler.py — 修改后
_log_count: int = 0
_FLUSH_EVERY: int = 100            # Q2 决策: 每 100 条 flush 一次

def log_message(self, format, *args):
    import sys
    from datetime import datetime
    global _log_count
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = format % args if args else format
    sys.stderr.write(f'[{timestamp}] {message}\n')
    _log_count += 1
    if _log_count % _FLUSH_EVERY == 0:
        sys.stderr.flush()
```

**理由**：
- 每 100 条请求才刷一次盘，99% 减少 flush 系统调用
- 日志丢失窗口 ≤ 100 条（非关键场景可接受）
- 保留基本实时性（高频站点约几秒刷新一次）

### 3.3 P2🟢：Registry 懒初始化（mtime 缓存）

```python
# registry.py — 新增模块级缓存
import os as _os

_registry_cache: Optional[dict] = None
_registry_cache_mtime: float = 0.0

def _get_cached_data() -> dict:
    """惰性读取 registry，mtime 未变时复用缓存。"""
    global _registry_cache, _registry_cache_mtime
    try:
        mtime = _os.path.getmtime(REGISTRY_PATH)
    except OSError:
        mtime = 0.0
    if _registry_cache is not None and mtime == _registry_cache_mtime:
        return _registry_cache
    _registry_cache = read_json(REGISTRY_PATH)
    if 'servers' not in _registry_cache:
        _registry_cache['servers'] = []
    _registry_cache_mtime = mtime
    return _registry_cache


class Registry:
    def __init__(self) -> None:
        self._data = _get_cached_data()  # ← 改为走缓存

    def save(self) -> None:
        write_json(REGISTRY_PATH, self._data)
        # 写后刷新缓存 mtime
        global _registry_cache, _registry_cache_mtime
        _registry_cache = self._data
        try:
            _registry_cache_mtime = _os.path.getmtime(REGISTRY_PATH)
        except OSError:
            _registry_cache_mtime = 0.0
```

**理由**：
- CLI 命令（`hs list` / `hs status`）短时间内多次 `Registry()` 不再反复读盘
- mtime 缓存确保外部修改（如 `hs kill` 写 registry）后缓存自动失效
- 测试隔离安全：`monkeypatch.setattr(REGISTRY_PATH, tmp_path)` 改变文件路径 → mtime 不同 → 自动重新加载

---

## 四、影响评估

### 4.1 性能改善

| 指标 | 修复前 | 修复后 |
|:---|:---|:---|
| 每请求 I/O 操作 | 1 读 + 1 原子写 + 1 flush | 0 读 + 0 写（仅 stderr write，100 条 flush 一次） |
| 每请求 Python 对象分配 | Registry + dict + json 缓冲区 | 0 额外分配 |
| 内存稳态 | ~22MB（json 缓冲区碎片） | ~15MB（无频繁 json.dump 碎片） |
| touch 写盘频率 | 每请求 | 每 60 秒 |
| last_access_at 精度 | 实时 | ≤60 秒延迟 |
| 日志 flush 频率 | 每请求 | 每 100 请求 |
| Registry 读盘频率 | 每次构造 | mtime 未变时 0 次 |

### 4.2 向后兼容

- `Registry.touch()` 方法**保留**（其他调用方如 dashboard API 仍可直接使用）
- `registry.json` 结构不变
- `hs status` / dashboard 读取 `last_access_at` 不变
- 对外 API 无变化

### 4.3 风险

| 风险 | 等级 | 缓解 |
|:---|:---|:---|
| `last_access_at` 精度下降（60s） | 低 | Q1=B，仅 dashboard 展示用，非关键路径 |
| 进程异常退出丢失 ≤60s 访问记录 | 低 | 数据非关键，重启后自动恢复 |
| 日志丢失 ≤100 条 | 低 | Q2 降频，非审计场景可接受 |
| 缓存 mtime 为 0 时（文件不存在）每次重建 | 低 | `ensure_storage()` 保证文件初始化 |

---

## 五、实施计划

### 5.1 改动范围

| 文件 | 变更 | 预估行数 |
|:---|:---|:---|
| `src/http_server_cli/registry.py` | 新增 module 级缓存 + `_touch_memory` + `_flush_access_cache` | +40 |
| `src/http_server_cli/handler.py` | `do_GET` 改为 `_touch_memory()` | ~5 |
| `src/http_server_cli/handler.py` | `log_message` 降频 flush（每 100 条） | +5 |
| `tests/test_handler.py` | 新增 `touch_memory` + `log_flush` 测试 | +20 |
| `tests/test_registry.py` | 新增 `flush_access_cache` + 缓存 mtime 测试 | +25 |
| **净增** | | **~95** |

### 5.2 实施步骤

1. 方案评审通过 → v1.1
2. TDD: 先写 `test_registry.py` 缓存测试 + `test_handler.py` touch/log 测试
3. 实现 `registry.py`: `_get_cached_data()` + `_touch_memory()` + `_flush_access_cache()`
4. 实现 `registry.py`: `Registry.__init__` 改为走缓存，`save()` 刷新缓存
5. 修改 `handler.py`: `do_GET` 改为 `_touch_memory()` + `log_message` 降频 flush
6. 全量回归 `pytest tests/` (293 tests)
7. commit: `perf@handler: remove per-request touch() and stderr.flush() overhead`

---

## 六、决策记录

| # | 决策点 | 选项 | 决定 |
|---|--------|------|:--:|
| Q1 | `_FLUSH_INTERVAL` 间隔 | A. 30s / **B. 60s** / C. 其他 | ✅ B |
| Q2 | `log_message` flush 策略 | A. 完全去掉 / **B. 每 100 条 flush** | ✅ B |
| Q3 | P2 懒初始化 Registry | **A. 本次一并实施** / B. 后续评估 | ✅ A |
