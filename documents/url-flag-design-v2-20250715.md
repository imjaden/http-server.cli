# --url 标志设计方案 v2

日期: 2025-07-15
状态: 待评审
类型: 功能设计
前版: v1 (已评审: 合理性🟡 严格性🟡 安全性🔴)

## 变更摘要 (v1 → v2)

| 编号 | 来源 | 变更 |
|------|------|------|
| H1 | 合理性-Q4 | 明确: URL 仅当 index_page ≠ `index.html` 时追加路径（与 `--json` data.url 一致） |
| H2 | 合理性-daemon | 澄清: `--url` 一条命令完成，跳过 daemon tail-f 和 foreground 阻塞 |
| M1 | 严格性-➊ | --url 错误路径: 直接 `print(msg, file=sys.stderr)`，不走 `eprint()` |
| M2 | 严格性-➋ | URL 构建加 `urllib.parse.quote(index_page, safe='')` |
| M3 | 严格性-➌ | 文档标记并发竞态为已知限制 |
| M4 | 严格性-➍ | 退出码保持 0/1/2，stderr 输出可读错误文本 |
| M5 | 严格性-➎ | 文档补充: `hs start` 不支持 `--port`（端口自动分配） |
| M6 | 严格性-➏ | `--url -o` 保留 `time.sleep(0.5)`，纯 `--url`（无 `-o`）无需等待 |
| S1 | 安全性-➊ | 不全局修改 `eprint()`，靶向修复 `--url` 错误路径 |
| S2 | 安全性-➋ | 示例改为 `"$(hs . --url)"` 双引号；index_page 禁 `/` `..` |
| S3 | 安全性-➌ | index_page 正则校验 + URL 编码；domain 校验纳入 `hs set domain` |

## 目标

为 `hs start` 命令新增 `--url` 标志：启动（或定位已运行的）HTTP 服务后，仅向 stdout 输出完整 URL 字符串，其余静默。配合 `"$(...)"` 或管道，一条命令完成 `启动 → 获取 URL → 传入下一个工具`。

## 决策清单（已确认）

| 编号 | 决策 | 选型 |
|------|------|------|
| Q1 | 作用范围 | A: 仅 `hs start`（含路径快捷方式 `hs .` / `hs path`） |
| Q2 | 与 `--json` 关系 | 互斥，同时给出报错 exit 2 |
| Q3 | 错误时行为 | stdout 空 + exit 1，stderr 输出可读错误文本 |
| Q4 | 输出格式 | 完整 URL。index_page ≠ `index.html` 时追加 `/xxx.html`，默认 `index.html` 不追加（与 `--json` data.url 一致） |

## CLI 接口

### 基本用法

```bash
hs . --url                          # → stdout: http://localhost:8080
hs . -i app.html --url              # → stdout: http://localhost:8080/app.html
hs start ~/my-site --url            # → stdout: http://localhost:8080
open "$(hs . --url)"                # macOS 一键打开浏览器
export URL="$(hs . --url)"          # shell 脚本注入
```

### URL 构建规则

```
URL = http://{domain}:{port}
if index_page is not None and index_page != 'index.html':
    URL += '/' + quote(index_page)    # urllib.parse.quote 编码
```

| index_page 值 | URL 输出 |
|---------------|----------|
| `None` 或 `'index.html'` | `http://localhost:8080` |
| `'app.html'` | `http://localhost:8080/app.html` |
| `'我的页面.html'` | `http://localhost:8080/%E6%88%91%E7%9A%84%E9%A1%B5%E9%9D%A2.html` |

### 与 `--json` 互斥

```bash
hs . --url --json                   # stderr: --url and --json are mutually exclusive, exit 2
```

### 错误行为

| 场景 | stdout | stderr | exit |
|------|--------|--------|------|
| 路径不存在 | (空) | `❌ Path does not exist or is not a directory: ...` | 1 |
| 端口全满 | (空) | `❌ Ports 8080-10000 all in use, cannot start` | 1 |
| 启动异常 | (空) | `❌ Start failed: ...` | 1 |
| 已运行服务 | URL | (空) | 0 |
| 新启动成功 | URL | (空) | 0 |

### 与其他 flag 组合

| 组合 | 行为 |
|------|------|
| `--url -o` | 输出 URL + time.sleep(0.5) + 打开浏览器 |
| `--url -d` | 输出 URL + 服务后台运行，不进入 tail -f 阻塞 |
| `--url -f` | 输出 URL + 服务前台运行，不进入 proc.wait() 阻塞 |

**注**: `--url` 模式跳过 daemon 的 `tail -f` 日志跟踪和 foreground 的 `proc.wait()` 阻塞，服务进程已在后台运行。输出 URL 后立即返回。这仍是一条命令——服务启动了，URL 拿到了，调用方可以继续。

### `--port` 不可用

`hs start` 不支持 `--port` 参数（端口从默认端口递增自动分配）。`--url` 模式沿用同样规则。如需指定端口，可先 `hs set port 3000` 修改默认值。

## 实现方案

### 1. cli.py: `_cmd_start()`

```python
parser.add_argument('--url', action='store_true')

# 互斥检查（在 parse_known_args 之后）
# 注: CLI 层互斥错误也走 stderr，保证 "$(hs . --url 2>/dev/null)" 不受污染
if parsed.url and parsed.json:
    print('⚠️ --url and --json are mutually exclusive', file=sys.stderr)
    sys.exit(2)

# 传入 manager
result = manager.start(
    path=path,
    open_browser=parsed.open,
    daemon=parsed.daemon,
    foreground=parsed.foreground,
    json=False,             # url_only 时强制 json=False
    url_only=parsed.url,
    index_page=index_page,
)

# 根据返回值设退出码
if parsed.url:
    sys.exit(0 if result else 1)
```

### 2. server.py: `ServerManager.start()`

新增参数 `url_only: bool = False`，返回值从 `None` 改为 `Optional[bool]`：

```python
def start(self, path=None, open_browser=False,
          daemon=False, foreground=False, json=False,
          url_only=False, index_page=None) -> Optional[bool]:
```

**index_page 校验**（在路径解析之后，URL 构建之前）：

```python
import re
# raw string 中将 \u4e00 原样传给 re 引擎，re 支持 \uXXXX Unicode 转义
_INDEX_RE = re.compile(r'^[a-zA-Z0-9\u4e00-\u9fff][a-zA-Z0-9\u4e00-\u9fff._-]*$')

def _validate_index_page(name: str) -> Optional[str]:
    """校验 index_page 文件名。返回错误消息或 None。"""
    if not name:
        return 'index_page cannot be empty'
    if '..' in name or '/' in name or '\\' in name:
        return f'index_page contains invalid path characters: {name}'
    if not _INDEX_RE.match(name):
        return f'index_page contains invalid characters: {name}'
    return None
```

**URL 构建辅助函数**：

```python
from urllib.parse import quote

def _build_url(domain: str, port: int, index_page: str = None) -> str:
    """构建完整 URL。默认 index.html 不追加后缀。"""
    url = f'http://{domain}:{port}'
    if index_page and index_page != 'index.html':
        url += f'/{quote(index_page, safe="")}'
    return url
```

#### 决策点分支（三分支：url_only / json / 文本）

| 位置 | 场景 | url_only 行为 | 返回值 |
|------|------|---------------|--------|
| L0 | index_page 非法 | `print(msg, file=sys.stderr)` | `False` |
| L1 | 路径不存在 | `print(msg, file=sys.stderr)` | `False` |
| L2 | 已注册且存活 | `print(url)` 到 stdout | `True` |
| L3 | 端口全满 | `print(msg, file=sys.stderr)` | `False` |
| L4 | 启动异常 | `print(msg, file=sys.stderr)` | `False` |
| L5 | 新启动成功 | `print(url)` 到 stdout | `True` |
| L6 | 跳过交互 | 与 L5 合并，`return True` | `True` |

**流程顺序**: 路径解析 → index_page 通配符展开 → **L0: index_page 校验** → 目录存在检查(L1) → 注册表查询(L2) → 端口查找(L3) → 子进程启动(L4) → 注册写入 → URL 输出(L5) → 提前返回(L6)

**示例 — L1（路径不存在）**：

```python
if not os.path.isdir(abs_path):
    msg = f'Path does not exist or is not a directory: {format_path(abs_path)}'
    if url_only:
        print(f'❌ {msg}', file=sys.stderr)
        return False
    elif json:
        json_output(False, 'start', error=msg)
    else:
        eprint(msg, '❌')
    return
```

**示例 — L5（新启动成功）**：

```python
url = _build_url(domain, port, index if index != 'index.html' else None)
if url_only:
    print(url)
    return True
elif json:
    json_output(True, 'start', data={...})
else:
    print(f'✅  {url}')
    ...
```

### 3. 帮助文本更新

```text
  hs . -d                  后台运行（不占用终端）
  hs                       默认等于 hs .（当前目录启动）
+ hs . --url               仅返回服务 URL（与 --json 互斥）

  --json                   所有命令后追加此参数可获取结构化 JSON 输出
+ --url                    启动后仅输出完整 URL 字符串（仅 start，与 --json 互斥）
```

## 退出码约定

| 退出码 | 含义 |
|--------|------|
| 0 | 成功，stdout 输出 URL |
| 1 | 失败（路径无效 / 端口全满 / 启动异常），stdout 空，stderr 有错误文本 |
| 2 | 参数错误（--url 与 --json 互斥） |

注：不进一步细分退出码（如 3=端口满, 4=路径无效）。stderr 输出已包含可读错误文本。若未来需要机器可消费的错误信息，可通过 stderr JSON 信封统一解决。

## 测试计划

### test_server.py: `TestStartUrlOnly`（新增）

1. `test_url_only_new_start` — 新启动成功，stdout 仅 URL 字符串，无 JSON 结构
2. `test_url_only_already_running` — 已运行服务，返回已有服务的 URL
3. `test_url_only_already_running_custom_index` — 已运行 + 自定义 index，URL 含 `/{quoted_index}`
4. `test_url_only_invalid_path` — 无效路径，stdout 空，stderr 有错误文本
5. `test_url_only_no_port_available` — mock 端口全满，stdout 空，stderr 有错误文本
6. `test_url_only_with_custom_index` — `index_page='app.html'` 验证 URL 含 `/app.html`
7. `test_url_only_default_index_omitted` — `index_page='index.html'` 验证 URL 不含 `/index.html`
8. `test_url_only_invalid_index_page` — `index_page='../etc/passwd'` 验证 index_page 校验拒绝

### test_cli.py: `TestUrlFlag`（新增）

9. `test_url_json_mutual_exclusion` — `_cmd_start` 同时给 `--url --json`，验证 SystemExit(2)
10. `test_url_flag_passed_to_manager` — 验证 `url_only=True` 正确传入 manager.start()

### 回归

- 现有 `TestStartJson` 全部 7 个测试必须保持通过
- `start()` 返回值改为 `Optional[bool]` 不影响现有调用方（返回值被丢弃）
- `eprint()` 函数签名和行为均不改变

## 已知限制

| 限制 | 说明 | 计划 |
|------|------|------|
| 并发启动竞态 | 两个 `hs . --url` 同时执行可能拿到同一端口，后者启动失败 | 低频场景，不修复 |
| 服务器就绪时序 | URL 打印时 HTTP 服务可能尚未接受连接（仅影响 `--url -o`，已有 `time.sleep(0.5)` 缓解） | 不修复 |
| exit 1 语义过载 | 多种错误共享出口码 1，调用脚本无法仅凭退出码区分错误类型 | 后续 stderr JSON 信封统一解决 |
| domain 输入校验 | `hs set domain` 无 hostname 格式校验 | 后续在 `_handle_set` 中独立修复 |

## 变更文件清单

| 文件 | 变更类型 |
|------|----------|
| `src/http_server_cli/cli.py` | 新增 `--url` flag + 互斥检查 + 退出码 + 帮助文本 |
| `src/http_server_cli/server.py` | 新增 `url_only` 参数 + `_validate_index_page` + `_build_url` + 6 个决策点三分支 + 返回值 `Optional[bool]` |
| `tests/test_server.py` | 新增 `TestStartUrlOnly` 类（8 个测试） |
| `tests/test_cli.py` | 新增 `TestUrlFlag` 类（2 个测试） |
