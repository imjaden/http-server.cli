# bookmark 书签功能设计方案 v1.0

日期: 2025-07-15
状态: 待评审
类型: 功能设计

## 目标

为 `hs` 新增具名项目书签（bookmark）功能：将常用项目路径 + index_page 绑定到一个简短名称，后续直接用名称替代完整路径执行所有操作（启动/停止/查询/获取 URL）。

```bash
# 注册一次
hs bookmark add myapp ~/CodeSpace/my-project -i app.html

# 之后永久使用
hs myapp --url                # → http://localhost:8080/app.html
hs myapp -o                   # 启动 + 打开浏览器
hs kill myapp                 # 停止
hs status myapp                # 查询状态
open "$(hs myapp --url)"      # 搭配 --url 一键消费
```

## 决策清单（已确认）

| 编号 | 决策 | 选型 |
|------|------|------|
| Q1 | 术语命名 | bookmark |
| Q2 | 注册方式 | A: CLI 子命令 + C: `add` 不传 path 时默认 cwd |
| Q3 | 别名 vs 路径冲突 | A: 别名优先 → 未命中 fallback 路径 |
| Q4 | 运行时 override | 支持，运行时 flag 覆盖 bookmark 默认值 |
| Q5 | 名称规范 | `[a-zA-Z0-9][a-zA-Z0-9._-]*`，不与 `_COMMANDS` 冲突 |
| Q6 | 现有命令联动 | kill/status/list 先查 bookmark 再查 port/path |
| Q7 | 存储结构 | 独立 `~/.http-server-cli/bookmarks.json` |
| Q8 | CLI 命令矩阵 | CRUD + 隐式启动 + 管理联动 |

## CLI 接口

### 子命令: `hs bookmark`

```bash
hs bookmark add <name> [path] [-i index_page]    # 新增
hs bookmark list                                   # 列出所有
hs bookmark show <name>                            # 查看单个详情
hs bookmark remove <name>                          # 删除
```

**`add` 行为**:
- `path` 不传默认取当前工作目录 `os.getcwd()`
- `path` 传入时用 `resolve_path()` 展开为绝对路径
- `-i` 指定默认 index_page，不传则 `None`（启动时默认 `index.html`）
- 名称冲突时报错提示 `bookmark '<name>' already exists`
- 名称与 `_COMMANDS` 键冲突时报错（如 `start`, `list`, `kill` 等）

**名称规范**:
```python
_BOOKMARK_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$')
# 额外检查：不与 _COMMANDS 键冲突
```

**示例**:
```bash
hs bookmark add docs ~/Downloads/Courses
hs bookmark add myapp . -i dashboard.html          # cwd + 指定 index
hs bookmark add site ~/CodeSpace/my-project        # 默认 index.html
hs bookmark list                                    # 列出所有书签
hs bookmark show myapp                              # 查看 myapp 详情
hs bookmark remove site                             # 删除名为 site 的书签
```

### 隐式启动: `hs <name> [flags]`

```bash
hs myapp                          # 启动书签绑定的项目
hs myapp -o                       # + 打开浏览器
hs myapp -i other.html            # 运行时覆盖 index_page
hs myapp --url                    # 仅返回 URL
hs myapp --json                   # JSON 信封输出
hs myapp -d                       # daemon 后台运行
```

**路由逻辑**（在 `main()` 中的 `cmd not in _COMMANDS` 分支之前）:

```
1. cmd == 'bookmark'           → bookmark 子命令
2. cmd in _COMMANDS            → 正常命令
3. cmd in bookmarks            → cmd='start', args=[path, -i index, ...原始flags]
4. cmd.startswith(('.', '/', '~')) or os.path.exists(cmd) → 路径快捷方式
5. 否则                        → Unknown command, exit 1
```

**第 3 步展开逻辑**:
```python
if cmd in bookmarks:
    bm = bookmarks[cmd]
    # 将 bookmark 的默认值作为隐式 args 前置
    implicit = [bm['path']]
    if bm.get('index_page'):
        implicit += ['-i', bm['index_page']]
    # 用户显式 flag 追加在后面，argparse 会自动覆盖隐式值
    parsed.args = implicit + parsed.args
    cmd = 'start'
```

该设计保证:
- 用户 `-i other.html` 会覆盖 bookmark 的默认 index_page（argparse 后面的值覆盖前面）
- `--url` `--json` `-o` `-d` `-f` 正常传递

### 管理命令联动

**`hs kill <name>`**:
```
1. arg.isdigit()    → 按 port 处理（现有逻辑）
2. arg in bookmarks → 按 bookmark path 处理（查 registry 找对应端口 → kill）
3. 否则              → 按 path 处理（现有逻辑）
```

**`hs status <name>`**:
```
同上三路分发。
```

**`hs list`**:
现有输出中新增一列显示 bookmark 名称（如果有匹配）:
```
✅  http://localhost:8080  [myapp]
    📁  ~/CodeSpace/my-project
    ...
```

`hs list --json` 在 `data.servers[].bookmark` 字段输出（`null` 表示无匹配）:
```json
{"port": 8080, "bookmark": "myapp", ...}
```

**`hs search <keyword>`**:
搜索范围扩展至 bookmark 名称（不区分大小写）:
```python
matches = [s for s in servers
           if keyword in str(s.get('port', ''))
           or keyword in s.get('path', '').lower()
           or keyword in bookmarks.get_for_path(s['path'], '').lower()]
```

**`hs kill-all`**:
不做特殊处理——清理所有服务，独立于 bookmark。

**`hs history`**:
`history --json` 输出中添加 `bookmark` 字段（启动时记录）。不影响文本输出格式。

---

## 存储结构

`~/.http-server-cli/bookmarks.json`:

```json
{
  "bookmarks": [
    {
      "name": "myapp",
      "path": "/Users/jadenli/CodeSpace/my-project",
      "index_page": "app.html",
      "created_at": "2026-07-15T18:00:00"
    },
    {
      "name": "docs",
      "path": "/Users/jadenli/Downloads/Courses",
      "index_page": null,
      "created_at": "2026-07-15T18:05:00"
    }
  ]
}
```

### BookmarkStore 类（`bookmark.py`）

```python
class BookmarkStore:
    def __init__(self) -> None:
        self._path = BOOKMARKS_PATH  # ~/.http-server-cli/bookmarks.json
        self._ensure_file()

    def add(self, name: str, path: str, index_page: str = None) -> None
    def remove(self, name: str) -> bool          # True if deleted
    def get(self, name: str) -> Optional[dict]    # None if not found
    def list_all(self) -> list[dict]             # sorted by created_at
    def get_for_path(self, path: str) -> Optional[str]  # name or None
    def names(self) -> set[str]                   # set of all names
```

字段说明:
- `name`: 必填，主键，全局唯一
- `path`: 必填，`resolve_path()` 展开后的绝对路径
- `index_page`: 可选，默认 `None`（启动时走 `index.html`）
- `created_at`: ISO 时间戳
- 不存 `port`, `domain` ——这些是运行时决定的

### 与 utils.py 集成

```python
# 新增常量
BOOKMARKS_PATH = os.path.join(DATA_DIR, 'bookmarks.json')

# ensure_storage() 中新增
if not os.path.exists(BOOKMARKS_PATH):
    write_json(BOOKMARKS_PATH, {'bookmarks': []})
```

---

## 实现方案

### 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/http_server_cli/bookmark.py` | **新增** | BookmarkStore 类 |
| `src/http_server_cli/utils.py` | 修改 | 新增 `BOOKMARKS_PATH` 常量 + `ensure_storage()` 初始化 |
| `src/http_server_cli/cli.py` | 修改 | `hs bookmark` 4 个子命令 + `main()` 路由 + `_cmd_kill/status/list/search` 适配 |
| `src/http_server_cli/history.py` | 修改 | `add()` 新增 `bookmark` 字段 |
| `src/http_server_cli/server.py` | 无需改 | path/index_page 由 CLI 层透传 |
| `tests/test_bookmark.py` | **新增** | BookmarkStore CRUD + 名称冲突 + 校验 |
| `tests/test_cli.py` | 修改 | bookmark 子命令 + 隐式启动 + 冲突路由 |

### 1. `bookmark.py` — 新增

```python
class BookmarkStore:
    """书签持久化存储。"""

    def __init__(self) -> None:
        from http_server_cli.utils import BOOKMARKS_PATH, read_json, write_json
        self._path = BOOKMARKS_PATH
        self._read = read_json
        self._write = write_json
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not os.path.exists(self._path):
            self._write(self._path, {'bookmarks': []})

    def _read_all(self) -> list:
        return self._read(self._path).get('bookmarks', [])

    def _write_all(self, bookmarks: list) -> None:
        self._write(self._path, {'bookmarks': bookmarks})

    def add(self, name: str, path: str, index_page: Optional[str] = None) -> None:
        bookmarks = self._read_all()
        if any(b['name'] == name for b in bookmarks):
            raise ValueError(f"bookmark '{name}' already exists")
        bookmarks.append({
            'name': name,
            'path': path,
            'index_page': index_page,
            'created_at': timestamp(),
        })
        self._write_all(bookmarks)

    def remove(self, name: str) -> bool:
        bookmarks = self._read_all()
        new_list = [b for b in bookmarks if b['name'] != name]
        if len(new_list) == len(bookmarks):
            return False
        self._write_all(new_list)
        return True

    def get(self, name: str) -> Optional[dict]:
        for b in self._read_all():
            if b['name'] == name:
                return b
        return None

    def list_all(self) -> list[dict]:
        return sorted(self._read_all(), key=lambda x: x.get('created_at', ''))

    def get_for_path(self, path: str) -> Optional[str]:
        """根据路径查找书签名，返回 name 或 None。"""
        for b in self._read_all():
            if b['path'] == path:
                return b['name']
        return None

    def names(self) -> set[str]:
        return {b['name'] for b in self._read_all()}
```

### 2. `cli.py` — `_cmd_bookmark` + 路由修改

#### 子命令

```python
@_register
def _cmd_bookmark(manager, args):
    """hs bookmark — 书签管理"""
    sub = args[0] if args else None
    if sub == 'add':
        _bookmark_add(args[1:])
    elif sub == 'list':
        _bookmark_list(args[1:])
    elif sub == 'show':
        _bookmark_show(args[1:])
    elif sub == 'remove':
        _bookmark_remove(args[1:])
    elif sub in ('help', '-h', '--help'):
        _bookmark_help()
    else:
        eprint('Usage: hs bookmark <add|list|show|remove> [args]', '⚠️')
        _bookmark_help()
```

#### `_bookmark_add`

```python
_BOOKMARK_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$')

def _bookmark_add(args):
    parser = argparse.ArgumentParser(prog='hs bookmark add', add_help=False)
    parser.add_argument('name')
    parser.add_argument('path', nargs='?', default=None)
    parser.add_argument('-i', '--index', default=None)
    try:
        parsed, _ = parser.parse_known_args(args)
    except SystemExit:
        return

    # 名称校验
    if not _BOOKMARK_NAME_RE.match(parsed.name):
        eprint(f"Invalid bookmark name '{parsed.name}' (allowed: [a-zA-Z0-9][a-zA-Z0-9._-]*)", '❌')
        return
    if parsed.name in _COMMANDS:
        eprint(f"'{parsed.name}' conflicts with built-in command", '❌')
        return

    # 路径处理
    path = parsed.path or os.getcwd()
    abs_path = resolve_path(path)
    if not os.path.isdir(abs_path):
        eprint(f'Path does not exist or is not a directory: {abs_path}', '❌')
        return

    store = BookmarkStore()
    try:
        store.add(parsed.name, abs_path, parsed.index)
        eprint(f"Bookmark '{parsed.name}' → {format_path(abs_path)}", '✅')
        if parsed.index:
            eprint(f"  Default index: {parsed.index}", '📄')
    except ValueError as e:
        eprint(str(e), '⚠️')
```

#### `main()` 路由修改

```python
def main():
    # ... 现有 parser ...
    cmd = parsed.command
    # ... 现有规范化 ...

    # ── bookmark 路由（在路径快捷方式之前） ──
    if cmd == 'bookmark':
        cmd = 'bookmark'
    elif cmd in _COMMANDS:
        # ... 现有命令路由 ...
        pass
    elif cmd is not None:
        # 查 bookmark
        from http_server_cli.bookmark import BookmarkStore
        store = BookmarkStore()
        bm = store.get(cmd)
        if bm:
            # 构建隐式 args: path + index_page（如果存在）
            implicit = [bm['path']]
            if bm.get('index_page'):
                implicit += ['-i', bm['index_page']]
            # 用户显式 flags 追加到后面（argparse 会覆盖前面的）
            parsed.args = implicit + parsed.args
            cmd = 'start'
            # 继续走 start 逻辑
        elif (cmd.startswith(('.', '/', '~')) or cmd == '..'
                or os.path.exists(cmd) or glob.glob(cmd)):
            parsed.args = [parsed.command] + parsed.args
            cmd = 'start'
        else:
            eprint(f'Unknown command: {cmd}', '❌')
            _cmd_help(None, [])
            sys.exit(1)
```

#### `_cmd_kill` 适配

```python
# 在 kill 逻辑中，arg 非 digit 时：
from http_server_cli.bookmark import BookmarkStore as BStore
bm_store = BookmarkStore()
bm = bm_store.get(arg)
if bm:
    abs_path = bm['path']
else:
    abs_path = resolve_path(arg)
```

#### `_cmd_status` 适配（同理）

#### `_cmd_list` 适配

```python
# _list_servers 中，显示每个 server 时：
from http_server_cli.bookmark import BookmarkStore
bm_store = BookmarkStore()
for entry in user_servers:
    bm_name = bm_store.get_for_path(entry['path'])
    # 文本模式：附加 [bm_name] 标记
    # JSON 模式：data.servers[].bookmark = bm_name
```

### 3. `history.py` — 新增 `bookmark` 字段

```python
def add(self, port, path, started_at, domain='localhost',
        daemon=False, foreground=False, bookmark=None):
    record = {
        'port': port, 'path': path, 'started_at': started_at,
        'domain': domain, 'daemon': daemon, 'foreground': foreground,
    }
    if bookmark:
        record['bookmark'] = bookmark
    # ... 写入
```

调用方（`server.py` 或 `_cmd_start`）启动时传入 bookmark 名称。

---

## 测试计划

### test_bookmark.py（新增）

| # | 测试 | 覆盖 |
|---|------|------|
| 1 | `test_add_and_get` | 正常添加 + 读取 |
| 2 | `test_add_duplicate` | 同名冲突 → ValueError |
| 3 | `test_add_with_index` | 添加带 index_page 的书签 |
| 4 | `test_remove_existing` | 删除成功 |
| 5 | `test_remove_nonexistent` | 删除不存在的 → False |
| 6 | `test_list_all_sorted` | 列表按 created_at 排序 |
| 7 | `test_get_for_path` | 路径反查书签名 |
| 8 | `test_names` | 返回所有书签名集合 |
| 9 | `test_add_invalid_name` | 非法名称校验（特殊字符、以 - 开头） |
| 10 | `test_add_command_conflict` | 名称与 `_COMMANDS` 冲突 |

### test_cli.py（修改 + 新增）

| # | 测试 | 覆盖 |
|---|------|------|
| 11 | `test_bookmark_add_default_cwd` | `hs bookmark add myapp` 默认取 cwd |
| 12 | `test_bookmark_add_with_index` | `hs bookmark add myapp . -i app.html` |
| 13 | `test_bookmark_implicit_start` | `hs myapp` 隐式启动 → `_cmd_start` 被调用 |
| 14 | `test_bookmark_implicit_start_override` | `hs myapp -i other.html` 运行时覆盖 |
| 15 | `test_bookmark_conflict_with_path` | 别名优先于同名路径 |
| 16 | `test_bookmark_kill_by_name` | `hs kill myapp` 按书签名 kill |
| 17 | `test_bookmark_status_by_name` | `hs status myapp` 按书签名查询 |

### 回归

- 所有现有 239 个测试必须保持通过
- `ensure_storage()` 新增 `bookmarks.json` 初始化不影响现有测试

---

## 风险

| 风险 | 缓解 |
|------|------|
| `hs bookmark` 名称与未来新增命令冲突 | 名称校验时检查 `_COMMANDS` 键，新命令加前先检查已有 bookmarks |
| `resolve_path()` 对不存在的 path 报错 | `add` 时校验路径存在 |
| `list` 输出新增 `[bookmark]` 列破坏解析脚本 | JSON 模式通过 `bookmark` 字段传递，文本模式仅视觉提示，无结构性变化 |
| bookmark path 与 registry 路径匹配使用字符串比较 | 两者都经 `resolve_path()` 标准化，保证一致 |
| `--json` 和隐式 bookmark 组合传递 | `main()` 中只构建隐式 args，不改变 `--json`/`--url` 标记的传递 |

## 变更文件清单

| 文件 | 变更类型 |
|------|----------|
| `src/http_server_cli/bookmark.py` | **新增** |
| `src/http_server_cli/utils.py` | 修改 |
| `src/http_server_cli/cli.py` | 修改 |
| `src/http_server_cli/history.py` | 修改 |
| `tests/test_bookmark.py` | **新增** |
| `tests/test_cli.py` | 修改 |

## 不纳入本次范围

| 项目 | 理由 |
|------|------|
| `hs config` 中显示 bookmarks | 独立 `hs bookmark list` 已覆盖，不与 config 耦合 |
| bookmark 导入/导出 | 手动 cp `bookmarks.json` 已足够 |
| bookmark 支持 `--port` 固定端口 | 端口自动分配是核心设计原则 |
| bookmark 嵌套/分组 | 过度设计，当前扁平结构足够 |
