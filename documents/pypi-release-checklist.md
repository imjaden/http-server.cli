# PyPI 正式发布检查清单

> 分析日期：2026-06-23
> 当前版本：1.0.x
> 适用：从 TestPyPI 过渡到 PyPI 正式发布
>
> **更新状态：** 本文档最初为分析报告。以下标记 ✅ 的项目已在 1.0.x 开发周期中完成。

---

## P0 — 发布前必须解决

### 1. 跨平台支持

**问题**：`_check_macos()` 在 Linux/Windows 上直接拒绝服务

```
hs version → "⚠️ http-server-cli 当前仅支持 macOS"
```

**当前实现**：

| 函数 | 实现 | 平台限制 |
|------|------|---------|
| `is_port_in_use()` | `lsof -i :port` | macOS only |
| `get_all_occupied_ports()` | `lsof -iTCP -sTCP:LISTEN` | macOS only |
| `get_pid_by_lsof()` | `lsof -i` 查 PID | macOS only |

**方案**：用 `socket.connect_ex()` 纯 Python 检测，走 fallback 而非硬拒绝

```python
def is_port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0
```

`lsof` 保留作为 macOS 加速路径（批量查端口时更快），非 macOS 走纯 socket。

**改动范围**：`utils.py`
**工作量**：~半天

✅ 已完成：已实现 socket 直连检测，非 macOS 不再拒绝服务。保留 lsof 作为 macOS 加速路径。

---

### 2. MANIFEST.in 缺 LICENSE

**当前**：
```
include http-server-cli.spec.yaml
include README.md
include README.en.md
include pyproject.toml
```

**需要**：追加 `include LICENSE`

**影响**：PyPI 要求分发包包含许可证文件，缺失会发出构建警告。

**工作量**：1 行

✅ 已完成

---

### 3. OS 分类器

**当前**：
```toml
"Operating System :: MacOS"
```

**需要**（如果跨平台解决）：
```toml
"Operating System :: MacOS",
"Operating System :: POSIX :: Linux",
"Operating System :: Microsoft :: Windows",
```

**工作量**：1 行

✅ 已完成：已补充 Linux/Windows classifiers

---

## P1 — 强烈建议

### 4. README 同步

pyproject.toml 指向 `README.en.md`（正确），但内容过时：

- 安装段落包含 TestPyPI 命令
- 版本号写死 `v1.0.x`
- 缺少 `--index`、`--json` 新功能说明
- 命令表缺少 `-i` 参数

✅ 已完成：已更新 --json/--index 说明，移除 TestPyPI 安装命令

**工作量**：~30 分钟

---

### 5. CI/CD（GitHub Actions）

当前无 CI。至少需要：
```yaml
- push: python -m pytest tests/
- push: python -m build
- release: twine upload dist/*
```

**工作量**：~1 小时

---

### 6. 安全：删除硬编码 Token

`cache/release-testpypi.sh` 和 `documents/release-testpypi.sh` 中明文暴露 TestPyPI Token。

虽然 cache/ 已被 `.gitignore` 排除，但硬编码 Token 仍是安全反模式。

**方案**：统一走 `TWINE_PASSWORD` 环境变量 + `.env` 文件。

**工作量**：5 分钟

✅ 已完成：Token 移至 ~/.pypirc，脚本通过 awk 解析

---

### 7. 添加 CHANGELOG.md

当前无版本记录。后续每次发布建议记录变更。

**工作量**：~15 分钟

✅ 已完成

---

## P2 — 可选优化

### 8. 开发状态 classifier
```
"Development Status :: 4 - Beta"  →  "5 - Production/Stable"（功能稳定后）
```

### 9. 端口竞争重试
`find_available_port()` 和 `subprocess.Popen()` 之间有时间窗口，另一进程可能抢占该端口。

### 10. `py.typed` 空文件
`pyproject.toml` 已声明 `http_server_cli = ["py.typed"]`，但实际文件不存在。

✅ 已完成

### 11. 子命令 `--help`
当前 `hs start --help` 被 `add_help=False` 吞掉。

### 12. 增加 `tox.ini`
声明支持 3.7-3.13 但只在 3.12 上测试过。

---

## 实施优先级

```
P0 ████████████████░  |  跨平台 + MANIFEST + classifiers
P1 ████████░░░░░░░░░  |  README + CI + Token + CHANGELOG
P2 ████░░░░░░░░░░░░░  |  分类器升级 + 重试 + py.typed
```

## 三、发布常见问题

### ~/.pypirc 认证

`~/.pypirc` 是 Python 官方认证文件，格式为 INI：

```ini
[testpypi]
  username = __token__
  password = pypi-xxxxx
[pypi]
  username = __token__
  password = pypi-yyyyy
```

发布脚本通过 awk 自动解析对应 section 的 password。详见 `documents/pip-release-steps.md`。

### 版本冲突

PyPI 不允许覆盖已存在的版本。遇到 `400 File already exists` 错误时，唯一解决方法是升版本号。

### 镜像源同步

新包发布后，国内镜像源（tuna、阿里云等）通常有 15分钟~数小时的同步延迟。首次发布最慢。
临时方案：`pip install -i https://pypi.org/simple/ http-server-cli`
