# bookmark 书签功能设计方案 v1.1

日期: 2025-07-15
状态: 待评审
类型: 功能设计
前版: v1.0 (已评审: 合理性🟡 严格性🟡 安全性🔴→PASS 条件)

## 变更摘要 (v1.0 → v1.1)

| 编号 | 来源 | 变更 |
|------|------|------|
| H1 | 合理性-➊ + SEC-004 | 名称长度上限 128 字符 |
| H2 | 合理性-➋ | 补充 `_bookmark_show` 完整实现 |
| M1 | 严格性-➊ | 读-改-写竞态标记为已知限制 |
| M2 | 严格性-➋ | `add` 时检查路径唯一约束（不同 name 不可指向同一 path） |
| M3 | 严格性-➌ | `list_all` 排序默认值 `'1970-01-01T00:00:00'` |
| M4 | 严格性-➍ + SEC-006 | `_bookmark_add` 中复用 `_validate_index_page()` |
| M5 | 严格性-➎ + SEC-005 | `_read_all()` 损坏检测：非空文件解析失败→ DataCorruptionError |
| M6 | 风格 🟢 | bookmark 子命令错误统一走 `print(..., file=sys.stderr)` |

## 目标

为 `hs` 新增具名项目书签（bookmark）功能：将常用项目路径 + index_page 绑定到一个简短名称，后续直接用名称替代完整路径执行所有操作（启动/停止/查询/获取 URL）。

```bash
# 注册一次
hs bookmark add myapp ~/CodeSpace/my-project -i app.html

# 之后永久使用
hs myapp --url                # → http://localhost:8080/app.html
hs myapp -o                   # 启动 + 打开浏览器
hs kill myapp                 # 停止
hs status myapp               # 查询状态
open "$(hs myapp --url)"      # 搭配 --url 一键消费
```

## 决策清单（已确认）

| 编号 | 决策 | 选型 |
|------|------|------|
| Q1 | 术语命名 | bookmark |
| Q2 | 注册方式 | A: CLI 子命令 + C: `add` 不传 path 时默认 cwd |
| Q3 | 别名 vs 路径冲突 | A: 别名优先 → 未命中 fallback 路径 |
| Q4 | 运行时 override | 支持，运行时 flag 覆盖 bookmark 默认值 |
| Q5 | 名称规范 | `[a-zA-Z0-9][a-zA-Z0-9._-]*`，≤128 字符，不与 `_COMMANDS` 冲突 |
| Q6 | 现有命令联动 | kill/status/list 先查 bookmark 再查 port/path |
| Q7 | 存储结构 | 独立 `~/.http-server-cli/bookmarks.json` |
| Q8 | CLI 命令矩阵 | CRUD + 隐式启动 + 管理联动 |

### Q5 补充：名称长度上限

```python
MAX_BOOKMARK_NAME_LEN = 128
# 校验顺序：长度 → 正则 → 命令冲突
```

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
- 路径冲突时报错提示 `path already bookmarked as '<existing_name>'`
- 名称与 `_COMMANDS` 键冲突时报错
- 名称超长（>128 字符）时报错
- index_page 不合法时（含 `/`、`..`、非法字符）报错

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

### 管理命令联动

同 v1.0，无变更。

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
    }
  ]
}
```

### 损坏检测

```python
class BookmarkStore:
    def _read_all(self) -> list:
        """读取所有书签。损坏文件抛出 DataCorruptionError。"""
        raw = read_json(self._path)
        # 文件非空但解析失败（read_json 返回 {}）→ 损坏
        if not raw and os.path.getsize(self._path) > 0:
            raise DataCorruptionError(
                f'{self._path} is corrupted. '
                f'Please check the file or restore from backup.'
            )
        return raw.get('bookmarks', [])

# DataCorruptionError: 自定义异常，继承 RuntimeError
```

### 路径唯一约束

```python
def add(self, name: str, path: str, index_page: Optional[str] = None) -> None:
    bookmarks = self._read_all()
    if any(b['name'] == name for b in bookmarks):
        raise ValueError(f"bookmark '{name}' already exists")
    if any(b['path'] == path for b in bookmarks):
        existing = next(b['name'] for b in bookmarks if b['path'] == path)
        raise ValueError(f"path already bookmarked as '{existing}'")
    # ... proceed with add
```

### list_all 排序边界

```python
def list_all(self) -> list[dict]:
    return sorted(self._read_all(),
                  key=lambda x: x.get('created_at', '1970-01-01T00:00:00'))
```

缺失 `created_at` 的记录始终排在列表末尾。

---

## 实现方案

### 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/http_server_cli/bookmark.py` | **新增** | BookmarkStore 类 + DataCorruptionError |
| `src/http_server_cli/utils.py` | 修改 | 新增 `BOOKMARKS_PATH` 常量 + `ensure_storage()` 初始化 |
| `src/http_server_cli/cli.py` | 修改 | `hs bookmark` 4 个子命令 + `main()` 路由 + kill/status/list/search 适配 |
| `src/http_server_cli/history.py` | 修改 | `add()` 新增 `bookmark` 字段 |
| `src/http_server_cli/server.py` | 无需改 | path/index_page 由 CLI 层透传 |
| `tests/test_bookmark.py` | **新增** | BookmarkStore CRUD + 损坏检测 + 校验 |
| `tests/test_cli.py` | 修改 | bookmark 子命令 + 隐式启动 + 冲突路由 |

### 1. `bookmark.py` — 新增（完整版）

```python
import os
import re
from typing import Optional
from http_server_cli.utils import (
    BOOKMARKS_PATH, read_json, write_json, resolve_path, timestamp,
)

MAX_BOOKMARK_NAME_LEN = 128
_BOOKMARK_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$')


class DataCorruptionError(RuntimeError):
    """书签文件损坏异常。"""
    pass


class BookmarkStore:
    """书签持久化存储。"""

    def __init__(self) -> None:
        self._path = BOOKMARKS_PATH
        self._ensure_file()

    # ── 内部 I/O ──

    def _ensure_file(self) -> None:
        if not os.path.exists(self._path):
            write_json(self._path, {'bookmarks': []})

    def _read_all(self) -> list:
        """读取所有书签。损坏文件抛出 DataCorruptionError。"""
        raw = read_json(self._path)
        if not raw and os.path.getsize(self._path) > 0:
            raise DataCorruptionError(
                f'{self._path} is corrupted. '
                f'Please check the file or restore from backup.'
            )
        return raw.get('bookmarks', [])

    def _write_all(self, bookmarks: list) -> None:
        write_json(self._path, {'bookmarks': bookmarks})

    # ── CRUD ──

    @staticmethod
    def validate_name(name: str) -> Optional[str]:
        """校验书签名。返回错误消息或 None。"""
        if not name:
            return 'bookmark name cannot be empty'
        if len(name) > MAX_BOOKMARK_NAME_LEN:
            return f'bookmark name exceeds {MAX_BOOKMARK_NAME_LEN} characters'
        if not _BOOKMARK_NAME_RE.match(name):
            return 'bookmark name must match [a-zA-Z0-9][a-zA-Z0-9._-]*'
        return None

    def add(self, name: str, path: str, index_page: Optional[str] = None) -> None:
        bookmarks = self._read_all()
        if any(b['name'] == name for b in bookmarks):
            raise ValueError(f"bookmark '{name}' already exists")
        if any(b['path'] == path for b in bookmarks):
            existing = next(b['name'] for b in bookmarks if b['path'] == path)
            raise ValueError(f"path already bookmarked as '{existing}'")
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
        return sorted(self._read_all(),
                      key=lambda x: x.get('created_at', '1970-01-01T00:00:00'))

    def get_for_path(self, path: str) -> Optional[str]:
        """根据路径查找书签名。路径唯一约束保证最多一个匹配。"""
        for b in self._read_all():
            if b['path'] == path:
                return b['name']
        return None

    def names(self) -> set[str]:
        return {b['name'] for b in self._read_all()}
```

### 2. `cli.py` — `_bookmark_add`（含 index_page 校验）

```python
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
    name_err = BookmarkStore.validate_name(parsed.name)
    if name_err:
        print(f'❌ {name_err}', file=sys.stderr)
        return
    if parsed.name in _COMMANDS:
        print(f"❌ '{parsed.name}' conflicts with built-in command", file=sys.stderr)
        return

    # index_page 校验（复用 server.py 的 _validate_index_page，支持子目录路径如 a/b.html）
    if parsed.index:
        from http_server_cli.server import _validate_index_page
        idx_err = _validate_index_page(parsed.index)
        if idx_err:
            print(f'❌ {idx_err}', file=sys.stderr)
            return

    # 路径处理
    path = parsed.path or os.getcwd()
    abs_path = resolve_path(path)
    if not os.path.isdir(abs_path):
        print(f'❌ Path does not exist or is not a directory: {abs_path}', file=sys.stderr)
        return

    store = BookmarkStore()
    try:
        store.add(parsed.name, abs_path, parsed.index)
        print(f"✅ Bookmark '{parsed.name}' → {format_path(abs_path)}")
        if parsed.index:
            print(f"   📄 Default index: {parsed.index}")
    except ValueError as e:
        print(f'❌ {e}', file=sys.stderr)
```

### 3. `_bookmark_show` 实现

```python
def _bookmark_show(args):
    if not args:
        print('❌ Usage: hs bookmark show <name>', file=sys.stderr)
        return
    name = args[0]
    store = BookmarkStore()
    bm = store.get(name)
    if not bm:
        print(f'❌ bookmark \'{name}\' not found', file=sys.stderr)
        return
    print(f"📌 {bm['name']}")
    print(f"   📁 {format_path(bm['path'])}")
    if bm.get('index_page'):
        print(f"   📄 Default index: {bm['index_page']}")
    print(f"   🕐 Created: {bm.get('created_at', '-')}")
```

### 4. `_bookmark_list` 实现

```python
def _bookmark_list(args):
    store = BookmarkStore()
    bookmarks = store.list_all()
    if not bookmarks:
        print('No bookmarks registered', file=sys.stderr)
        return
    print(f'📊 {len(bookmarks)} bookmark(s):')
    print()
    for bm in bookmarks:
        print(f"  📌 {bm['name']}")
        print(f"     📁 {format_path(bm['path'])}")
        if bm.get('index_page'):
            print(f"     📄 Default index: {bm['index_page']}")
        print()

# 注: list 无 --json 模式（数据量小，文本已够用）。如有需要后续补。
```

### 5. `_bookmark_remove` 实现

```python
def _bookmark_remove(args):
    if not args:
        print('❌ Usage: hs bookmark remove <name>', file=sys.stderr)
        return
    name = args[0]
    store = BookmarkStore()
    if store.remove(name):
        print(f"✅ Bookmark '{name}' removed")
    else:
        print(f"❌ bookmark '{name}' not found", file=sys.stderr)
```

---

## 测试计划

### test_bookmark.py（新增）

| # | 测试 | 覆盖 |
|---|------|------|
| 1 | `test_add_and_get` | 正常添加 + 读取 |
| 2 | `test_add_duplicate_name` | 同名冲突 → ValueError |
| 3 | `test_add_duplicate_path` | 同路径冲突 → ValueError（v1.1 新增） |
| 4 | `test_add_with_index` | 添加带 index_page 的书签 |
| 5 | `test_remove_existing` | 删除成功 |
| 6 | `test_remove_nonexistent` | 删除不存在 → False |
| 7 | `test_list_all_sorted` | 列表按 created_at 排序 |
| 8 | `test_list_all_missing_created_at` | 缺字段记录默认 epoch → 排末尾（v1.1 新增） |
| 9 | `test_get_for_path` | 路径反查书签名 |
| 10 | `test_get_for_path_none` | 无匹配路径 → None |
| 11 | `test_names` | 返回所有书签名集合 |
| 12 | `test_validate_name_too_long` | 名称 >128 字符 → 错误（v1.1 新增） |
| 13 | `test_validate_name_special_chars` | 非法字符校验 |
| 14 | `test_validate_name_starts_with_dash` | 以 `-` 开头 → 拒绝 |
| 15 | `test_corrupted_json_raises` | 损坏 JSON → DataCorruptionError（v1.1 新增） |
| 16 | `test_corrupted_json_empty_file` | 空文件 → 正常返回 []（v1.1 新增） |

### test_cli.py（修改 + 新增）

| # | 测试 | 覆盖 |
|---|------|------|
| 17 | `test_bookmark_add_default_cwd` | `hs bookmark add myapp` 默认取 cwd |
| 18 | `test_bookmark_add_with_index` | `hs bookmark add myapp . -i app.html` |
| 19 | `test_bookmark_add_invalid_index` | `-i '../../etc/passwd'` → 拒绝（v1.1 新增） |
| 20 | `test_bookmark_show` | `hs bookmark show myapp` 显示详情（v1.1 新增） |
| 21 | `test_bookmark_show_not_found` | 查询不存在的书签 → 错误（v1.1 新增） |
| 22 | `test_bookmark_implicit_start` | `hs myapp` 隐式启动 → `_cmd_start` 被调用 |
| 23 | `test_bookmark_implicit_start_override` | `hs myapp -i other.html` 运行时覆盖 |
| 24 | `test_bookmark_conflict_with_path` | 别名优先于同名路径 |
| 25 | `test_bookmark_kill_by_name` | `hs kill myapp` 按书签名 kill |
| 26 | `test_bookmark_status_by_name` | `hs status myapp` 按书签名查询 |

### 回归

- 所有现有 239 个测试必须保持通过
- `ensure_storage()` 新增 `bookmarks.json` 初始化不影响现有测试

---

## 已知限制

| 限制 | 说明 | 计划 |
|------|------|------|
| 读-改-写竞态 | `add()`/`remove()` 无文件锁，并发写入可能互相覆盖 | 单用户交互工具，不修复。registry/history 存储同理 |
| bookmark list 无 --json | 数据量小（通常 <10 条），文本输出已够用 | 后续有需求再加 |
| `ensure_storage()` 初始化 `bookmarks.json` | 首次运行自动创建空文件 | 与 config/registry/history 行为一致 |

## 风险

| 风险 | 缓解 |
|------|------|
| `hs bookmark` 名称与未来新增命令冲突 | 名称校验检查 `_COMMANDS` 键 + 长度上限 |
| bookmarks.json 手动编辑损坏 | `_read_all()` 损坏检测 + DataCorruptionError |
| `resolve_path()` 对不存在的 path 报错 | `add` 时校验路径存在 |
| `list` 输出新增 `[bookmark]` 标记破坏解析 | JSON 模式通过 `bookmark` 字段传递；文本标记仅视觉提示 |
| index_page 在注册时即被校验 | `_bookmark_add` 复用 `_validate_index_page()` |

## 变更文件清单

| 文件 | 变更类型 |
|------|----------|
| `src/http_server_cli/bookmark.py` | **新增**（~130 行） |
| `src/http_server_cli/utils.py` | 修改（+2 行常量 + 1 行 ensure_storage） |
| `src/http_server_cli/cli.py` | 修改（~120 行新增） |
| `src/http_server_cli/history.py` | 修改（~5 行） |
| `tests/test_bookmark.py` | **新增**（~16 测试） |
| `tests/test_cli.py` | 修改（~10 测试新增） |
