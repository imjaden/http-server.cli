# http-server-cli 知识库

> 本文档记录项目开发过程中涉及的技术知识点。

## Python 标准库

### http.server

**用途**：提供简单的 HTTP 服务器实现

**关键类**：
- `HTTPServer`：HTTP 服务器基类
- `SimpleHTTPRequestHandler`：简单请求处理器，支持 GET 和 HEAD

**自定义处理器**：
```python
from http.server import SimpleHTTPRequestHandler

class CustomHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # 自定义 GET 请求处理
        if self.path == '/':
            # 处理根路径
            pass
        else:
            # 其他路径使用默认处理
            return super().do_GET()
```

**directory 参数**（Python 3.7+）：
```python
# 指定服务目录
handler = SimpleHTTPRequestHandler(request, client_address, server, directory='/path/to/dir')
```

### subprocess

**用途**：启动和管理子进程

**关键方法**：
- `subprocess.Popen()`：启动子进程
- `preexec_fn=os.setsid`：创建新进程组（用于 daemon 模式）

**示例**：
```python
import subprocess
import os

proc = subprocess.Popen(
    [sys.executable, 'script.py', 'arg1'],
    stdout=log_file,
    stderr=subprocess.STDOUT,
    preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
)
```

### signal

**用途**：进程信号处理

**关键信号**：
- `signal.SIGTERM`：终止信号
- `signal.SIGKILL`：强制终止信号
- `signal 0`：检测进程是否存活

**示例**：
```python
import signal
import os

# 检测进程是否存活
try:
    os.kill(pid, 0)  # signal 0
    return True  # 进程存活
except ProcessLookupError:
    return False  # 进程不存在

# 终止进程组
pgid = os.getpgid(pid)
os.killpg(pgid, signal.SIGTERM)
```

### os

**用途**：操作系统接口

**关键方法**：
- `os.getcwd()`：获取当前工作目录
- `os.path.isdir()`：检查是否为目录
- `os.path.isfile()`：检查是否为文件
- `os.path.getmtime()`：获取文件修改时间
- `os.setsid()`：创建新会话/进程组
- `os.getpgid()`：获取进程组 ID
- `os.killpg()`：向进程组发送信号

### pathlib

**用途**：路径操作

**关键方法**：
- `Path.expanduser()`：展开 ~ 为用户目录
- `Path.resolve()`：解析为绝对路径

**示例**：
```python
from pathlib import Path

abs_path = str(Path('~/.config').expanduser().resolve())
```

### glob

**用途**：文件模式匹配

**示例**：
```python
import glob

# 查找所有 HTML 文件
html_files = glob.glob('/path/to/dir/*.html')

# 按修改时间排序
latest = max(html_files, key=lambda f: os.path.getmtime(f))
```

## macOS 系统命令

### lsof

**用途**：列出打开的文件和网络连接

**端口检测**：
```bash
# 检测端口是否被占用
lsof -i :8080 -P -n -F p

# 获取所有 LISTEN 状态的端口
lsof -iTCP -sTCP:LISTEN -P -n
```

**参数说明**：
- `-i :port`：指定端口
- `-P`：显示端口号而非服务名
- `-n`：不解析主机名
- `-F p`：仅输出 PID
- `-sTCP:LISTEN`：仅显示 LISTEN 状态

### ps

**用途**：进程状态查询

**获取进程资源使用**：
```bash
# 获取 CPU、内存、RSS
ps -p <pid> -o pcpu,pmem,rss
```

**输出字段**：
- `pcpu`：CPU 使用百分比
- `pmem`：内存使用百分比
- `rss`：驻留内存大小（KB）

## HTTP 协议

### 302 重定向

**用途**：临时重定向

**实现**：
```python
self.send_response(302)
self.send_header('Location', '/new-path')
self.end_headers()
```

## JSON 处理

### 原子写入

**用途**：防止并发写入导致数据损坏

**实现**：
```python
import tempfile
import os

# 写临时文件，再原子 rename
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(filepath), suffix='.tmp')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
        f.write('\n')
    os.replace(tmp, filepath)  # 原子操作
except BaseException:
    os.unlink(tmp)
    raise
```

## 设计模式

### 单例模式（Config/Registry）

**实现**：每次调用时重新读取文件，确保数据一致性

```python
class Config:
    def __init__(self):
        self._data = dict(DEFAULT_CONFIG)
        self._merge_file()  # 从磁盘读取最新配置
```

### 工厂模式（create_handler）

**用途**：动态创建绑定指定目录的处理器类

```python
def create_handler(directory: str):
    class DirectoryHandler(SmartHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)
    return DirectoryHandler
```

## 最佳实践

### 进程管理

1. **daemon 模式**：使用 `preexec_fn=os.setsid` 创建新进程组
2. **终止进程组**：使用 `os.killpg()` 确保子进程也被终止
3. **优雅终止**：先 SIGTERM，等待 0.5 秒，再 SIGKILL

### 端口检测

1. **批量检测**：使用 `lsof -iTCP -sTCP:LISTEN` 一次性获取所有占用端口
2. **避免重复调用**：减少 lsof 调用次数，提高性能

### 路径处理

1. **展开 ~**：使用 `Path.expanduser()`
2. **解析符号链接**：使用 `Path.resolve()`
3. **格式化输出**：将 HOME 替换为 ~，提高可读性

### 错误处理

1. **捕获特定异常**：PermissionError、FileNotFoundError、OSError
2. **提供友好提示**：使用 Emoji 前缀增强可读性
3. **清理残留数据**：检测到僵尸进程时清理注册表