# bookmark 同项目多页面书签设计方案 v1.1

日期: 2026-08-19
状态: 待复审
类型: 功能设计
前版: v1.0 (已评审: 合理性🟡 严格性🟡 → CONDITIONAL PASS)

## 变更摘要 (v1.0 → v1.1)

| # | 来源 | 变更 |
|---|------|------|
| M1 | review 1-➊ 🔴 | add() 归一化 index_page('' → None),组合键比较统一,修复 ''/None 双键 bug;复审补 force-delete 分支(line 71)同归一化 |
| M2 | review 1-➋ 🟡 | 明确 --force 仅覆盖组合键冲突、不覆盖 name 唯一性约束 |
| M3 | review 1-➌ 🟡 | 明确 update() 不提供对称 --force,先 remove+add 代替(defer) |
| M4 | review 2-➋ 🟡 | §4 补充 _list_servers 文本模式 join 代码 |
| M5 | review 2-➌ 🟡 | JSON bookmark 字段 no-match 语义明确为 [] 空数组 |
| M6 | review 连锁-🟢 | 影响范围表补充 server.py / history.py 无连锁影响声明 |

## 背景

当前 BookmarkStore 以 **path 唯一** 为约束(bookmark.py:88-90):不同 name 不可指向同一 path。
用户无法为同一项目的不同页面(index_page)分别注册书签。

现状实测(2026-08-19):

```bash
hs bookmark show html-gen
# 📌 html-gen
#    📁 ~/CodeSpace/html-gen
#    📄 Default index: demos/index.html

hs bookmark add drama-demo . -i demos/drama/daming-overview.html
# ❌ path already bookmarked as 'html-gen'
```

目标:同一项目不同页面可注册多个书签,各自快捷启动 `hs <name> -o` 直达对应页面。

## 决策记录(已确认)

| # | 事项 | 决策 |
|---|------|------|
| D1 | 唯一键 | A: (path, index_page) 组合唯一,同 path 不同 index_page 可共存 |
| D2 | 同键冲突 | 若 (path, index_page) 已存在,`hs bookmark add` 支持 `--force` 覆盖旧 bookmark。**--force 仅覆盖组合键冲突,不覆盖 name 唯一性约束**(name 冲突仍报错,见 §3 边界) |
| D3 | get_for_path | 同 path 多条目时返回全部(name 列表),`hs list` 显示全部书签标签 |

## 方案

### 1. `bookmark.py` — 唯一键改为组合键 + `force` 参数

```python
def add(self, name: str, path: str, index_page: Optional[str] = None,
        force: bool = False) -> None:
    bookmarks = self._read_all()
    if any(b['name'] == name for b in bookmarks):
        raise ValueError(f"bookmark '{name}' already exists")
    # 归一化: '' 与 None 语义等价(均表示默认 index.html),统一组合键
    index_page = index_page or None
    # 组合唯一键: (path, index_page)。index_page None 表示默认 index.html
    conflict = next(
        (b for b in bookmarks
         if b['path'] == path and (b.get('index_page') or None) == index_page),
        None)
    if conflict:
        if not force:
            existing = conflict['name']
            raise ValueError(
                f"path+index already bookmarked as '{existing}'")
        # force: 删除旧条目, 替换为新条目
        bookmarks = [b for b in bookmarks
                     if not (b['path'] == path
                             and (b.get('index_page') or None) == index_page)]
    bookmarks.append({
        'name': name,
        'path': path,
        'index_page': index_page,
        'created_at': timestamp(),
    })
    self._write_all(bookmarks)
```

`update()` 的冲突校验同步改为组合键(server 层无改动):

```python
# update 内部 path/index_page 变化时, 检查目标组合是否已被其它 name 占用
if any(b2['name'] != name
       and b2['path'] == new_path
       and (b2.get('index_page') or None) == new_index
       for b2 in bookmarks):
    raise ValueError("path+index already bookmarked as '<name>'")
```

**update() 不提供对称 --force(defer)**:update 场景少(把某书签改到已被占用的
组合键),可先用 `hs bookmark remove` + 重新 add 代替,不引入第二处覆盖语义。
如后续有需求再补 `update --force`,与 add 行为对称。

### 2. `bookmark.py` — `get_for_path` 返回全部

```python
def get_for_path(self, path: str) -> list[str]:
    """根据路径查找书签名。同 path 可有多条, 返回全部名称列表。"""
    return sorted(
        b['name'] for b in self._read_all() if b['path'] == path)
```

### 3. `cli.py` — `_bookmark_add` 增加 `--force`

```bash
hs bookmark add <name> [path] [-i index] [--force]
```

- 无 `--force` + 组合键冲突 → 报错提示 `path+index already bookmarked as '<existing>'`
- 有 `--force` → 旧条目删除、新条目创建(旧 name 随之失效)

**--force 边界**:仅覆盖组合键冲突,不覆盖 name 唯一性约束。
`hs bookmark add html-gen X -i demos/index.html --force`(name 已存在)仍报
`bookmark 'html-gen' already exists`;要改同名书签用 `update`,要换名用
`remove` + `add`。

### 4. `cli.py` — `_list_servers` 适配多标签

`get_for_path` 返回值从 `Optional[str]` 变为 `list[str]`:

- 文本模式(cli.py:308-309 现有逻辑改为 join):

```python
bm_names = bm_store.get_for_path(entry['path'])
bm_label = f'  [{",".join(bm_names)}]' if bm_names else ''
```

- JSON 模式(cli.py:258):`bookmark` 字段改为名称列表,no-match 语义为 **[] 空数组**
  (与旧 `null` 不同;下游消费者以数组长度判断有无书签,空数组即为无)

### 5. 隐式启动 / kill / status 无改动

`hs <name>`(main():930-948)、`hs kill <name>`、`hs status <name>` 均按 name 精确查
`store.get(name)`,与唯一键无关,行为不变。

## 影响范围

| 文件 | 变更 |
|------|------|
| `src/http_server_cli/bookmark.py` | add() 组合键 + force;update() 组合键校验;get_for_path() 返回 list |
| `src/http_server_cli/cli.py` | _bookmark_add 加 --force;_list_servers 多标签适配 |
| `tests/test_bookmark.py` | 更新 path 唯一用例 → 组合键用例;新增 force 用例 |
| `tests/test_cli.py` | bookmark add --force、list 多标签用例 |
| `server.py` | **无连锁影响**(不调用 get_for_path,index_page 由 CLI 透传;已核实) |
| `history.py` | **无连锁影响**(bookmark 字段是启动时捕获的单 name,与组合键无关;已核实) |

存量数据兼容:旧条目 index_page 为 null,组合键按 (path, null) 处理,与不传 -i 的新增行为一致,不破坏。

## 测试计划(TC)

| # | 测试 | 验收 |
|---|------|------|
| TC-01 | 同 path 不同 index_page 添加 | 两个 bookmark 均成功,list 含 2 条 |
| TC-02 | 同 path 同 index_page 添加(无 force) | ValueError 提示 path+index already bookmarked |
| TC-03 | 同 path 同 index_page + --force | 旧条目被替换,旧 name 查询返回 None |
| TC-04 | get_for_path 同 path 多条目 | 返回 sorted 名称列表,含全部 |
| TC-05 | get_for_path 无匹配 | 返回空列表 |
| TC-06 | hs list 多标签 | 文本显示 `[a,b]`,JSON bookmark 为数组 |
| TC-07 | hs list JSON no-match | 无书签服务 bookmark 字段为 `[]`(非 null) |
| TC-08 | 存量无 index_page 条目 | 组合键按 (path, null),可正常查询 |
| TC-09 | hs <name> 隐式启动回归 | 仍按 name 查 path+index_page,行为不变 |
| TC-10 | update 改组合键冲突 | 目标组合已被其它 name 占用 → ValueError |

## 实施计划

1. bookmark.py: add() force + 组合键;update() 组合键校验;get_for_path() 返回 list
2. cli.py: _bookmark_add --force;list 多标签
3. 测试: 更新 test_bookmark.py / test_cli.py,新增 TC-01~10
4. 全量 pytest 回归

## 参考

- bookmark-feature-design-v1.1-20250715.md(基线设计,路径唯一约束来源)
- http-server-cli.spec.yaml
