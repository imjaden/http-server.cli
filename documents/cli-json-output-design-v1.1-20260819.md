# hs CLI --json 输出补全设计方案 v1.1

日期: 2026-08-19
状态: 待复审
类型: 功能设计
前版: v1.0 (已评审: 合理性🟢 严格性🟡 → CONDITIONAL PASS)

## 变更摘要 (v1.0 → v1.1)

| # | 来源 | 变更 |
|---|------|------|
| M1 | review 2-➊ 🟡 | 明确 json 模式禁用 eprint(eprint 实际写 stdout),错误统一走 json_output |
| M2 | review 2-➋ 🟡 | bookmark 子命令捕获 DataCorruptionError 走错误信封 |
| M3 | review 2-➌ 🟢 | 声明 --json 与 --url 错误哲学差异 |

## 背景

hs CLI 已定义统一 JSON 信封规范(utils.py:272 `json_output(success, command, data, error)`)。
但覆盖面不全:部分命令已支持 `--json`,bookmark 5 个子命令与 mcp/dashboard 管理子命令完全缺失。

现状实测(2026-08-19):

```bash
hs bookmark list --json
# 📊 1 bookmark(s):        ← 忽略 --json,纯文本输出
hs dashboard status --json
# 🟢 hs dashboard → http://127.0.0.1:8180   ← 同上
```

目标:全量命令支持 `--json`,所有错误路径在 json 模式下走信封、不污染 stdout。

## 决策记录(已确认)

| # | 事项 | 决策 |
|---|------|------|
| J1 | 补全范围 | A: 全量 — bookmark 5 子命令 + mcp/dashboard status/stop/restart |
| J2 | 错误路径 | json 模式下所有错误走 json_output(False,...),不 eprint 污染 stdout |
| J3 | 信封格式 | 复用 utils.json_output(success, command, data, error) 统一信封 |

## 方案

### 1. `bookmark` 子命令 --json(cli.py)

| 子命令 | command 值 | data 结构 |
|--------|-----------|-----------|
| add    | bookmark-add | `{'name','path','index_page','created_at'}` |
| update | bookmark-update | `{'name','path','index_page'}` |
| list   | bookmark-list | `{'count','bookmarks':[...]}` |
| show   | bookmark-show | `{'name','path','index_page','created_at'}` |
| remove | bookmark-remove | `{'name'}` |

每个子命令 argparse 增加 `--json`;成功走 `json_output(True, cmd, data=data)`,
校验失败/未找到走 `json_output(False, cmd, error=...)`,不再 `print(..., file=sys.stderr)`。

**json 模式禁用 eprint**:eprint(utils.py:28-33)实际写 stdout(print 无 file=sys.stderr),
任何残留 eprint 都会污染 JSON 输出。实现约束:json 分支内所有错误必须走
`json_output(False, ...)`,禁止调用 eprint / print。

**DataCorruptionError 捕获**:bookmark.py 的 _read_all() 在 bookmarks.json 损坏时抛
DataCorruptionError。各 bookmark 子命令需 try/except 包裹 store 操作,损坏时走
`json_output(False, cmd, error='bookmarks file corrupted')`,不允许 traceback 冒泡到 stderr。

### 2. `mcp` 管理子命令 --json(cli.py `_manage_mcp`)

| 子命令 | command 值 | data 结构 |
|--------|-----------|-----------|
| status | mcp-status | `{'name','port','pid','alive','transport','duration'}` |
| stop   | mcp-stop | `{'name','port','stopped':true}` |
| restart| mcp-restart | `{'name','port','restarted':true}` |

未运行状态:json 模式返回 `json_output(False, 'mcp-status', error='MCP not running')`,不 print。

### 3. `dashboard` 管理子命令 --json(cli.py `_manage_dashboard`)

| 子命令 | command 值 | data 结构 |
|--------|-----------|-----------|
| status | dashboard-status | `{'name','port','pid','alive','duration','log'}` |
| stop   | dashboard-stop | `{'name','port','stopped':true}` |
| restart| dashboard-restart | `{'name','port','restarted':true}` |

未运行状态:json 模式返回 `json_output(False, 'dashboard-status', error='dashboard not running')`。

### 4. help 无需 --json

`help` 是交互式文档,不属数据查询,不加入 json 支持。

### 5. --json 与 --url 错误哲学差异

| 模式 | 错误时 stdout | 退出码 |
|------|--------------|--------|
| `--url` | 空(无输出) | 1 |
| `--json` | JSON 信封 `{"success": false, "error": ...}` | 1 |

两者哲学相反但有意为之:`--url` 输出给 shell 消费(`$(hs . --url)` 需干净),
`--json` 输出给机器解析(错误也是结构化 JSON)。实现者不可将两者混用:
`--json` 模式下错误必须出现在 stdout 信封内,`--url` 模式下 stdout 必须保持为空。

## 影响范围

| 文件 | 变更 |
|------|------|
| `src/http_server_cli/cli.py` | bookmark 5 子命令 + _manage_mcp/_manage_dashboard 增加 json 分支 |
| `tests/test_cli.py` | 新增各子命令 --json 用例 |
| `tests/test_bookmark.py` | 无需改(store 层不变) |

## 测试计划(TC)

| # | 测试 | 验收 |
|---|------|------|
| TC-01 | `hs bookmark list --json` | stdout 为合法 JSON,含 count+bookmarks,无 emoji |
| TC-02 | `hs bookmark show <name> --json` | 成功返回详情信封 |
| TC-03 | `hs bookmark show <缺失> --json` | 错误走信封,error 非空,success=false |
| TC-04 | `hs bookmark add --json` | 成功返回 data 含 name/path/index_page |
| TC-05 | `hs bookmark add --json` 冲突 | 错误走信封(与 multi-page 设计 TC-02/03 联动) |
| TC-06 | `hs bookmark remove --json` | 成功/未找到均走信封 |
| TC-07 | `hs bookmark update --json` | 成功/未找到均走信封 |
| TC-08 | `hs mcp status --json` / 未运行 | 运行成功信封;未运行 error 信封 |
| TC-09 | `hs mcp stop --json` / restart | 成功信封 |
| TC-10 | `hs dashboard status --json` / 未运行 | 同 TC-08 |
| TC-11 | `hs dashboard stop --json` / restart | 成功信封 |
| TC-12 | json 模式错误不污染 stdout | `hs bookmark show nope --json` stdout 单行 JSON,emoji 仅 stderr 或不存在 |
| TC-13 | bookmarks.json 损坏时 json 输出 | 各 bookmark 子命令返回 `success:false` + error='bookmarks file corrupted',无 traceback |

## 实施计划

1. cli.py: bookmark 5 子命令加 --json(每个子命令一个 patch)
2. cli.py: _manage_mcp / _manage_dashboard 加 --json 分支
3. 测试: test_cli.py 新增 TC-01~13
4. 全量 pytest 回归

## 参考

- utils.py:272 json_output 信封定义
- bookmark-multi-page-design-v1.1-20260819.md(bookmark add --force 联动)
- http-server-cli.spec.yaml
