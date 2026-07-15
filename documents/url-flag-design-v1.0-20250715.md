# --url 标志设计方案 v1

日期: 2025-07-15
状态: 待评审
类型: 功能设计

## 目标

为 `hs start` 命令新增 `--url` 标志：启动（或定位已运行的）HTTP 服务后，仅向 stdout 输出完整 URL 字符串，其余静默。配合 `$(...)` 或管道，一条命令完成 `启动 → 获取 URL → 传入下一个工具`。

## 决策清单（已确认）

| 编号 | 决策 | 选型 |
|------|------|------|
| Q1 | 作用范围 | A: 仅 `hs start`（含路径快捷方式 `hs .` / `hs path`） |
| Q2 | 与 `--json` 关系 | 互斥，`--url` 优先级最高，同时给出报错 exit 2 |
| Q3 | 错误时行为 | A: stdout 空 + exit 1 |
| Q4 | 输出格式 | B: 完整 URL 含 index_page（如 `http://localhost:8080/app.html`） |

## CLI 接口

### 基本用法

```bash
hs . --url                    # → stdout: http://localhost:8080
hs start ~/my-site --url      # → stdout: http://localhost:8080/index.html
hs . -i app.html --url        # → stdout: http://localhost:8080/app.html
open $(hs . --url)            # macOS 一键打开浏览器（典型用例）
export URL=$(hs . --url)      # shell 脚本注入
```

### 与 `--json` 互斥

```bash
hs . --url --json             # stderr: --url and --json are mutually exclusive, exit 2
```

### 错误行为

```bash
hs /nonexistent --url         # stdout 空, exit 1
hs . --url                    # 端口 8080-10000 全满: stdout 空, exit 1
```

### 与其他 flag 组合

| 组合 | 行为 |
|------|------|
| `--url -o` | 输出 URL + 打开浏览器。兼容可用 |
| `--url -d` | 输出 URL + daemon 后台运行。兼容可用 |
| `--url -f` | 输出 URL + foreground 前台运行。兼容可用 |

## 实现方案

### 1. cli.py: `_cmd_start()`

```python
# 新增 flag
parser.add_argument('--url', action='store_true')

# 互斥检查（在 parse_known_args 之后）
if parsed.url and parsed.json:
    eprint('--url and --json are mutually exclusive', '⚠️')
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
def start(self, ..., url_only: bool = False) -> Optional[bool]:
```

**URL 构建规则**（与 `--json` 模式下 `data.url` 一致）：

```
url = f'http://{domain}:{port}'
if index_page:              # 新启动时用传入的 index_page
    url += f'/{index_page}'
elif entry_index:           # 已运行时用 registry 中的 index_page
    url += f'/{entry_index}'
# 默认 index.html 不追加后缀
```

#### 决策点分支

共 6 个决策点，当前已有 `if json: ... else: ...` 双分支，现扩展为三分支：

| 位置 | 场景 | url_only 行为 | 返回值 |
|------|------|---------------|--------|
| L1 (line 79) | 路径不存在 | 仅 stderr 输出错误 | `False` |
| L2 (line 88) | 已注册且存活 | `print(url)` | `True` |
| L3 (line 137) | 端口全满 | 仅 stderr 输出错误 | `False` |
| L4 (line 159-182) | 启动异常 (5种) | 仅 stderr 输出错误 | `False` |
| L5 (line 201) | 新启动成功 | `print(url)` | `True` |
| L6 (line 233) | JSON/URL 跳过交互 | `return True`（与 L5 合并） | `True` |

#### L2 已注册且存活 — URL 构建特殊处理

```python
# url_only 模式下，URL 采用传入的 index_page 或 registry 中的 index_page
url = f'http://{domain}:{port}'
if index_page:
    url += f'/{index_page}'
else:
    entry_index = entry.get('index_page', 'index.html')
    if entry_index and entry_index != 'index.html':
        url += f'/{entry_index}'
print(url)
```

#### 关于 daemon/foreground 模式

`--url` 模式与 `--json` 一样，在 L6 处提前返回，不进入 daemon `tail -f` 或 foreground `proc.wait()` 交互阻塞。用户若需要 daemon + URL，先 `--url` 获取 URL，再自行决定是否进入交互模式。

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
| 1 | 失败（路径无效 / 端口全满 / 启动异常），stdout 空 |
| 2 | 参数错误（--url 与 --json 互斥） |

## 测试计划

### test_server.py: `TestStartUrlOnly`（新增）

1. `test_url_only_new_start` — 新启动成功，验证 stdout 仅输出 URL 字符串（无 JSON 结构）
2. `test_url_only_already_running` — 已运行服务，验证返回已有服务的 URL
3. `test_url_only_already_running_custom_index` — 已运行 + 自定义 index，验证 URL 含自定义 index
4. `test_url_only_invalid_path` — 无效路径，验证 stdout 空
5. `test_url_only_no_port_available` — mock 端口全满，验证 stdout 空
6. `test_url_only_with_custom_index` — `-i app.html --url` 验证 URL 含 index

### test_cli.py: `TestUrlFlag`（新增）

7. `test_url_json_mutual_exclusion` — `_cmd_start` 同时给 `--url --json`，验证 exit 2
8. `test_url_flag_passed_to_manager` — 验证 `url_only=True` 正确传入 manager.start()

### 回归

- 现有 `TestStartJson` 全部 6 个测试必须保持通过
- `start()` 返回值改为 `Optional[bool]` 不影响现有调用方（返回值被丢弃）

## 风险

| 风险 | 缓解 |
|------|------|
| `start()` 返回值签名改变 | 现有调用方不消费返回值，向后兼容 |
| `--url` 模式下的 URL 与 `--json` `data.url` 不一 | 复用同一套 URL 构建逻辑，测试覆盖对齐 |
| `--url` 模式下 open_browser 行为 | 不做特殊处理——`--url -o` 依然打开浏览器，URL 已输出到 stdout |

## 变更文件清单

| 文件 | 变更类型 |
|------|----------|
| `src/http_server_cli/cli.py` | 新增 `--url` flag + 互斥检查 + 退出码 + 帮助文本 |
| `src/http_server_cli/server.py` | 新增 `url_only` 参数 + 6 处分支配 URL 输出 + 返回值 `Optional[bool]` |
| `tests/test_server.py` | 新增 `TestStartUrlOnly` 类（6 个测试） |
| `tests/test_cli.py` | 新增 `TestUrlFlag` 类（2 个测试） |
