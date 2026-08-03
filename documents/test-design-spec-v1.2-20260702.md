# http-server-cli 测试用例设计规范

> 基于 OpenSpec 的测试驱动质量体系
> 版本: v1.2-20260702

---

## 一、核心理念

**测试是活的规范文档，不是事后验证。**

- 每个测试类对应一个功能模块或用户场景
- 每个测试方法验证一条明确的业务规则
- 测试失败能直接告诉开发者：**哪个模块的哪个功能出了问题**
- 测试用例 = 可执行的 OpenSpec 条目

---

## 二、OpenSpec 编码体系

### 2.1 编码规则

```
<模块前缀>-<序号>[: <描述>]

格式:  xx-NNN
       │└─ 两位序号，支持范围 01~99
       └─ 模块代码（2~4字母）
```

### 2.2 模块代码表（已有）

| 代码 | 模块 | 说明 |
|:----|:-----|:------|
| `lifecycle` | 服务生命周期 | 启动/停止/列表/状态 |
| `port` | 端口分配 | 默认端口/自动递增/全占满 |
| `cfg` | 配置管理 | 默认配置/读写/持久化 |
| `reg` | 注册表 | 条目 CRUD/持久化 |
| `cli` | CLI 入口 | 命令分派/帮助/版本/别名 |
| `home` | 智能首页 | 首页跳转/查询参数 |
| `log` | 日志 | 日志写入/清理 |
| `res` | 资源监控 | CPU/内存/时长格式化 |
| `history` | 历史记录 | 记录/查询/清理 |
| `mcp` | MCP Server | MCP 工具注册/调用 |
| `dashboard` | Web 仪表盘 | dashboard 管理 |
| `url` | URL 构建 | 启动/已运行服务的 URL 输出（含 index_page） |

### 2.3 命名约定

```
test_server.py  → 模块标题: ServerManager 模块测试 — OpenSpec: lifecycle-01 ~ lifecycle-04, port-01 ~ port-03
test_cli.py     → 模块标题: CLI 入口测试 — OpenSpec: cli-01 ~ cli-03
```

**文件 docstring 格式：**

```python
"""
<模块名> — OpenSpec: <编码列表>

<补充说明>
"""
```

**类 docstring 格式：**

```python
class TestStart:
    """lifecycle-01 / port-01~03: 启动服务 + 端口分配"""
```

**方法 docstring 格式：**

```python
def test_start_no_port_available(self, ...):
    """所有端口被占时应报错"""
```

---

## 三、测试文件结构

### 3.1 标准模板

```python
# -*- coding: utf-8 -*-
"""
<模块名> — OpenSpec: <编码列表>
"""

import json
import os
import pytest

from http_server_cli.<module> import <Class>

pytestmark = pytest.mark.spec("<spec-group>")

# ── 夹具 ──────────────────────────────────────────

@pytest.fixture
def my_fixture():
    ...

# ── <功能组1> ─────────────────────────────────────

class TestFeature1:
    """<编码>: <描述>"""

    def test_case_x(self):
        ...

# ── <功能组2> ─────────────────────────────────────

class TestFeature2:
    """<编码>: <描述>"""
    ...
```

### 3.2 类组织原则

- **按功能场景分组**，而非按测试类型
- 每个类一个 `"""<编码>: <描述>"""` docstring
- 两个类之间用 `# ── <分隔标题> ──` 注释行分隔
- 从属功能/子场景放在同一个类的方法中

### 3.3 测试方法命名

| 模式 | 应用场景 | 示例 |
|:-----|:---------|:-----|
| `test_<行为>` | 单一功能测试 | `test_kill_by_port` |
| `test_<行为>_<条件>` | 带条件变体 | `test_kill_unregistered_port` |
| `test_<场景>_<状态>` | 状态变体 | `test_status_port_occupied_by_other` |
| `test_<动词>_<否定>` | 边缘/异常 | `test_kill_no_arg` |
| `test_<场景>_url_<条件>` | URL 输出验证 | `test_start_url_with_index_flag` |

---

## 四、夹具（Fixture）规范

### 4.1 层级

```
conftest.py  (全局)
├── _isolate_data_dir        # autouse: 隔离临时目录
├── fresh_config             # 干净 Config 实例
├── fresh_registry           # 空 Registry
├── pre_filled_registry      # 2 条预填充记录
└── temp_project             # 含 index.html 的临时目录

test_xxx.py  (模块级夹具)
├── _mock_system_calls       # autouse: mock 系统调用
└── <其他模块特定夹具>
```

### 4.2 隔离原则

- **`_isolate_data_dir`**（conftest, autouse）— 每个测试用例独立临时目录，互不污染
- SQLite 等效的"每次测试重置"策略，而非"测试间共享"策略

### 4.3 Mock 规范

| 工具 | 用途 | 注意事项 |
|:-----|:-----|:---------|
| `monkeypatch` | 函数/属性替换 | 首选，自动还原 |
| `unittest.mock.MagicMock` | 复杂对象模拟 | 仅在需要 spec/return_value 时使用 |
| `unittest.mock.patch` | 上下文管理器 | 仅用于需要精确控制范围的场景 |

### 4.4 陷阱：import-by-value

```python
# ❌ 错误：只 patch 源模块
monkeypatch.setattr('http_server_cli.utils.is_port_in_use', lambda p: False)

# ✅ 正确：消费者模块也 patch
monkeypatch.setattr('http_server_cli.server.is_port_in_use', lambda p: False)
monkeypatch.setattr('http_server_cli.registry.is_port_in_use', lambda p: False)
```

> **解释：** `from utils import is_port_in_use` 将函数的引用**按值**绑定到消费者模块的命名空间。只 patch 源模块不影响已导入的引用。

---

## 五、断言规范

### 5.1 断言什么

| 层级 | 断言目标 | 示例 |
|:-----|:---------|:-----|
| **输出内容** | 关键文本存在性 | `assert '✅' in captured.out` |
| **输出结构** | JSON 字段类型/值 | `assert result['data']['found'] is True` |
| **状态变化** | 注册表/配置变更 | `assert mgr.registry.count() == 0` |
| **副作用** | 文件/进程/日志 | `assert not os.path.isfile(log_path)` |

### 5.2 不要断言什么

- ❌ 不必要的精确格式（emoji 位置、空格数量、排版细节）
- ❌ 与业务逻辑无关的内部实现细节
- ❌ 非本测试范围的参数

### 5.3 输出捕获

- 使用 `capsys` 捕获 stdout/stderr
- 调用目标函数前需要 `capsys.readouterr()` 清空缓冲（避免夹具/启动的噪音）
- 不要假设输出顺序（iterable 函数可能顺序不固定）

```python
mgr.start(path=temp_project)
capsys.readouterr()  # ← 清空启动输出
mgr.kill(['8080'])
captured = capsys.readouterr()
assert '🛑' in captured.out
```

---

## 六、测试范围分层

### L1: 纯逻辑（无副作用）

| 模块 | 测试策略 | 示例 |
|:-----|:---------|:-----|
| Config | 直接实例化 + assert 字段值 | `fresh_config.port == 8080` |
| Registry | 直接实例化 + CRUD 操作 | `reg.add/find/remove/count` |
| HistoryStore | 同 Config | `store.add/records/clear/close` |
| utils | 纯函数调用 | `format_duration(3600) → '1小时'` |

### L2: 有外部队部（需 Mock）

| 模块 | Mock 目标 | 验证方式 |
|:-----|:----------|:---------|
| ServerManager.start | subprocess.Popen, webbrowser, is_port_in_use | stdout 输出 + registry 状态 + URL 路径 |
| ServerManager.kill | os.killpg, registry.remove | stdout 输出 + registry.count |
| ServerManager.status | is_port_in_use, is_process_alive | stdout 输出内容 |
| ServerManager.list | registry.active_servers | 格式化输出验证 |

### L3: 集成测试（暂不实现）

| 场景 | 说明 |
|:-----|:------|
| 真实端口启动/停止 | 依赖环境，CI 中可选运行 |
| 多进程抢占端口 | 需要并发控制 |
| MCP 端到端调用 | 需要真实 MCP 客户端 |

---

## 七、Spec 场景 vs Python 测试用例边界

### 7.1 核心理念

```
spec.yaml          → 声明式契约：「应该做什么」（WHAT）
tests/test_*.py    → 可执行验证：「代码怎么做到」（HOW）
```

**OpenSpec 场景描述的是系统行为规范，Python 测试是行为的可执行保证。**
两者互补但不重叠——不是每个 spec 场景都需要一个对应的 Python 测试。

### 7.2 什么情况下 spec 场景就够了，不需要独立 Python 测试

| 场景类型 | 例子 | 原因 |
|:---------|:-----|:------|
| **纯 HTTP 合约** | 状态码 200、响应字段存在 | 一个 curl 命令即可验证，不需要 mock |
| **端到端顺风路径** | "启动服务 → 返回 URL" | 集成测试覆盖一次即可，单元测试太碎 |
| **外部环境依赖** | "hs 未安装 → 返回 500" | 卸载工具运行测试即可验证，mock 只验证异常捕获路径 |
| **配置/文件路径** | "~ 路径被展开" | 真实文件系统行为，mock 反而容易错过 os.path.expanduser 实现细节 |

### 7.3 什么情况下 spec 场景必须对应 Python 测试

| 场景类型 | 动机 |
|:---------|:------|
| **分支逻辑** | `if cmd_name == 'hs'` / `else` — 不同分支走不同代码路径，必须 mock 验证参数 |
| **异常链** | JSONDecodeError → "格式异常" / FileNotFoundError → "未找到" — 每个异常有独立错误消息，必须 mock 验证 |
| **参数变换** | 命令参数拼接、`--json` 追加、路径展开 — mock 捕获 `subprocess.run` / 函数调用参数列表 |
| **边界值** | 空参数、带空格路径、特殊字符 — 容易被忽视的隐性分支 |
| **回归红线** | 重构后旧调用路径是否断掉（方法改名、签名变更、模块重组织） |

### 7.4 判断流程图

```
某条 OpenSpec 场景
       │
       ├─ 描述的是外部 API 响应行为？（状态码、字段存在）
       │     → ✅ spec 场景本身就够
       │
       ├─ 涉及代码内部判断逻辑？（if/else/异常捕获/参数拼接）
       │     → ✅ 需要 Python 测试
       │
       ├─ 涉及 Mock 验证的副作用？（写文件、杀进程、开浏览器）
       │     → ✅ 需要 Python 测试
       │
       └─ 涉及多种输入变体的同一条逻辑？
             → ✅ 需要参数化 Python 测试
```

### 7.5 实例对照：tool-nav-manager 的 cmd-resolve 场景

**spec.yaml 中的场景：**

```yaml
- name: 不加 --json
  given: 'POST {"cmd_name": "hs", "command": "/path"}'
  when: subprocess.run 被调用
  then: 参数严格为 ['hs', '/path']，不自加 --json
```

**对应的 Python 测试：**

```python
def test_hs_no_json_no_start(self, manager):
    with mock.patch.object(tnm.subprocess, 'run') as mock_sp:
        mock_sp.return_value = _mock_run(
            stdout=json.dumps({'success': True, 'data': {'url': '...'}})
        )
        result = manager.handle_cmd_resolve('hs', '/p')
    assert result['ok'] is True
    assert mock_sp.call_args[0][0] == ['hs', '/p']
```

**两者的关系：**

| 维度 | spec.yaml | Python 测试 |
|:-----|:----------|:------------|
| 读者 | PM / QA / 架构师 | 开发者 |
| 语言 | 自然语言 + YAML | Python + pytest |
| 可执行 | ❌ 不能运行 | ✅ pytest 直接运行 |
| 精确度 | 描述意图 | 断言具体行为 |
| 覆盖范围 | 关键场景 | 所有分支 + 边界 |
| 变更响应 | 功能变化时更新 | 代码变化时更新 |

### 7.6 一条实用原则

> **当你在写 Python 测试时，如果发现是在验证 curl 就能确认的东西（状态码、字段存在性），说明这里不需要单元测试——把这条场景留给集成测试或 spec 文档本身。**
>
> **反过来，当你在写 spec 场景时，如果发现描述的是"当 X 条件成立时内部走 Y 分支且参数变为 Z"，这条场景必须对应一个 Python 测试——因为只有 mock 才能精确验证内部行为。**

---

## 八、新增功能测试清单（Checklist）

每次新增功能时，按以下维度评估测试覆盖：

```
[  ] 正常路径（happy path）—— 功能按预期工作的场景
[  ] 边界条件 —— 边界值/空列表/单元素列表
[  ] 异常路径 —— 无效输入/未注册/权限不足
[  ] JSON 模式 —— --json 输出的结构和字段完整性
[  ] 向后兼容 —— 已有调用方式仍正常工作
[  ] CLI 入口 —— 命令注册/别名/help 文本
[  ] Mock 覆盖 —— 所有外部依赖被 mock，测试不依赖环境
```

### 8.1 示例：多端口 kill 的测试覆盖

| 测试 | 维度 | 验证点 |
|:-----|:-----|:-------|
| `test_multi_kill_two_ports` | 正常路径 | "Killing 2 service(s)" + registry 清空 |
| `test_multi_kill_with_unregistered` | 混合 | 已注册的被 kill + 未注册的提示 |
| `test_multi_kill_json` | JSON 模式 | `total: 2, results.length: 2` |

### 8.2 示例：start URL 的测试覆盖

| 测试 | 维度 | 验证点 |
|:-----|:-----|:-------|
| `test_start_url_default_index` | 正常路径 | 默认 `index.html` → 裸 URL |
| `test_start_url_with_index_flag` | 正常路径 | `--index custom.html` → URL 包含 `/custom.html` |
| `test_start_url_with_file_path` | 边界条件 | 文件路径参数 → URL 包含 basename |
| `test_start_already_running_url_with_index` | 混合 | 已运行服务 + 新 --index → URL 包含新页面 |
| `test_start_json_url_with_file_path` | JSON 模式 | JSON 中 `url` 字段包含 basename |

---

## 九、OpenSpec 索引

所有已定义的 OpenSpec 条目：

| 编码 | 模块 | 文件 | 说明 |
|:----|:-----|:-----|:------|
| `lifecycle-01` | ServerManager | `test_server.py` | 启动服务 |
| `lifecycle-02` | ServerManager | `test_server.py` | 列出服务 |
| `lifecycle-03` | ServerManager | `test_server.py` | 查询状态 |
| `lifecycle-04` | ServerManager | `test_server.py` | 关闭服务 |
| `port-01` | ServerManager | `test_server.py` | 默认端口分配 |
| `port-02` | ServerManager | `test_server.py` | 冲突时自动递增 |
| `port-03` | ServerManager | `test_server.py` | 无可用端口 |
| `cfg-01` | Config | `test_config.py` | 默认配置 |
| `cfg-02` | Config | `test_config.py` | 配置读写 |
| `cfg-03` | Config | `test_config.py` | 配置持久化 |
| `cfg-04` | Config | `test_config.py` | 错误处理 |
| `reg-01` | Registry | `test_registry.py` | 写入与持久化 |
| `reg-02` | Registry | `test_registry.py` | 查询与过滤 |
| `reg-03` | Registry | `test_registry.py` | 删除与清理 |
| `cli-01` | CLI | `test_cli.py` | 命令注册 |
| `cli-02` | CLI | `test_cli.py` | 帮助输出 |
| `cli-03` | CLI | `test_cli.py` | 版本命令 |
| `home-01` | Handler | `test_handler.py` | 首页智能跳转 |
| `home-02` | Handler | `test_handler.py` | 查询参数处理 |
| `home-03` | Handler | `test_handler.py` | 路径安全 |
| `res-01` | Utils | `test_utils.py` | 进程监控输出 |
| `res-02` | Utils | `test_utils.py` | 异常进程处理 |
| `res-03` | Utils | `test_utils.py` | 时长格式化 |
| `log-01` | ServerManager | `test_server.py` | 日志文件创建 |
| `log-02` | ServerManager | `test_server.py` | 日志文件删除 |
| `log-03` | Handler | `test_handler.py` | 日志输出格式 |
| `history` | HistoryStore | `test_history.py` | 历史记录全功能 |
| `mcp-*` | MCP | `test_mcp.py` | MCP 工具集 |
| `dashboard-*` | Dashboard | `test_dashboard.py` | Dashboard 管理 |
| `lifecycle-05` | ServerManager | `test_server.py` | URL 输出：默认 index.html 为裸 URL |
| `lifecycle-06` | ServerManager | `test_server.py` | URL 输出：--index / 文件路径时包含路径 |

> 新条目按顺序追加，不重编号。

---

## 十、运行方式

```bash
# 全部测试
python3.12 -m pytest tests/ -v

# 指定模块
python3.12 -m pytest tests/test_server.py -v

# 指定测试类
python3.12 -m pytest tests/test_server.py::TestKill -v

# 指定单条
python3.12 -m pytest tests/test_server.py::TestKill::test_kill_by_port -v

# 带覆盖率
python3.12 -m pytest tests/ --cov=http_server_cli --cov-report=term-missing

# Quick 模式（跳过慢速标记测试）
python3.12 -m pytest tests/ -m "not slow" -v
```

---

## 📋 元信息

| 项目 | 内容 |
|:---|:---|
| 助手名称 | IRIS (byHermes) |
| 创建时间 | 2026-07-02 |
| 最后更新 | 2026-07-02 |
| 测试总数 | 236 |
| 关联文件 | `tests/conftest.py`, `tests/test_*.py` |
