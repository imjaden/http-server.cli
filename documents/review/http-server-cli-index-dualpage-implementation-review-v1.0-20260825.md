# CL-SEC17 index 双页优化批 — implementation review报告 v1.0

> 日期: 2026-08-25
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 待 push commit: a032a5e, a231294, 6d42946
> review维度: 提交审计（审计规范 §6 + commit规范 §5 + 命名规范 §1）
> 闭环: CL-SEC17 — index 双页优化批（T1: Manage 场景组 / T2: 双源防漂移测试 / T3: aria-pressed + footer 域名 / T4: features.md 同步）

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 未 push commit 恰为 3 个 | `git log origin/main..HEAD --oneline` | ✅ a032a5e / a231294 / 6d42946 |
| src/ 无源码变更 | `git diff origin/main..HEAD --stat` | ✅ 仅 4 文件: features.md + index.html + index.zh.html + tests/test_index_sync.py |
| 双页组数 = 5 | `grep -c 'class="group-title"'` | ✅ EN 5 / ZH 5（EN: Start/View/Kill/Bookmark/Manage；ZH: 启动/查看/关闭/书签/管理） |
| 对比表 <tr> = 6 | `grep -c '<tr>'` | ✅ EN 6 / ZH 6（1 表头 + 5 工具） |
| aria-pressed 初始态 + JS 同步 | 读 diff + grep | ✅ 双页 `aria-pressed="false"`；setTheme 内 `btn.setAttribute('aria-pressed', ...)` 双页一致 |
| footer 域名 + CNAME | 读 diff + `cat CNAME` | ✅ 双页 `https://http-server.cli.jaden.tech`；CNAME 同域 |
| dashboard 场景输出 vs 源码 | 读 src + grep | ✅ 页面 `📊  Dashboard → http://localhost:8180` 与 dashboard.py:160 URL 模型 `http://{domain}:{port}`（domain 默认 localhost）及 cli.py:615 `{icon}  hs dashboard  →  http://127.0.0.1:{port}` 结构一致；8180 = cli.py:53 文档化默认端口 |
| MCP 场景输出 vs 源码 | `read_file cli.py:700-733` | ✅ 页面 `🤖  hs mcp (SSE)  →  http://127.0.0.1:8765/sse` 与 cli.py:731 `{icon}  hs mcp (SSE)  →  http://127.0.0.1:{port}/sse` 逐字一致（8765 为展示值，非硬编码断言） |
| 无旧仓库链接残留 | `grep 'github.com/imjaden/http-server-cli'` | ✅ 0 hits（双页） |
| 无 /Users 字面路径 | `git diff origin/main..HEAD \| grep '/Users'` | ✅ 0 hits |
| features.md 同步 | `git diff -- features.md` | ✅ 343→350、模块 11→12；`grep -c 'def test_'` 求和 = 350 实测一致 |
| 全量测试绿 | `pytest tests/ -q` | ✅ **350 passed in 1.28s**（含 test_index_sync.py 7/7） |
| commit 格式合规 | `scan-commits.py . origin/main..HEAD --type feat,test,docs` | ✅ 3/3 ok，0 violations，exit 0 |
| 命名规范 | 变更文件清单 | ✅ 新增 tests/test_index_sync.py 符合 test_*.py 约定；无新设计文档；现有文件未改名 |

## 审计规范评估（§6）

| # | 检查项 | 结果 |
|:--|:-------|:-----|
| A1 | index 双页对称 — Manage/管理 组、aria-pressed、footer 域名三处 EN/ZH 一一对应 | ✅ 双页 +16/+16 逐块对称（diff 逐行比对） |
| A2 | 场景输出与源码一致 — dashboard/MCP 输出格式 | ✅ 结构逐字匹配（见数据验证）；示例端口 8180/8765 为展示值，测试未断言端口 |
| A3 | test_index_sync.py 断言与实际页面一致 | ✅ 组数 5、对比表 <tr> 6、无旧链接、aria-pressed JS、Bookmark+Manage 组存在 — 全部与实测页面一致 |
| A4 | 350 tests 全绿 | ✅ 实测 350 passed |
| A5 | 改动未触碰源码逻辑 | ✅ src/ 0 变更；改动面 = 2 落地页 + 1 测试 + 1 文档 |

test_index_sync.py 7 用例逐一核对：both_pages_exist / structure_features_in_both（14 项结构特征）/ scenario_group_count_equal（=5）/ compare_table_rows_equal（=6）/ bookmark_and_manage_groups_present / theme_js_sync_in_both / no_stale_github_link — 全部为纯文件断言，无 Selenium、无端口硬编码，与落地页实测一致。

## commit规范评估（§5）

| # | 检查项 | 结果 |
|:--|:-------|:-----|
| C1 | subject 格式 `type@scope: subject` | ✅ feat@index / test@index / docs@features — 3/3，scope 均非空 |
| C2 | 分组按属性 | ✅ a032a5e 仅 index 双页（feat）；a231294 仅测试文件（test）；6d42946 仅 features.md（docs）— 单一属性提交，无混批 |
| C3 | 无 /Users 字面路径 | ✅ 0 hits |
| C4 | 无敏感信息 | ✅ diff 无密钥/凭证/token |

附注：3 commit body 为空 — 与本项目既有历史惯例一致（近 8 个 commit 均无 body），小提交 subject 自含信息，不构成违规。

## 命名规范评估（§1）

- ✅ 新增文件仅 `tests/test_index_sync.py` — `test_*.py` 前缀符合 pytest 发现约定（pyproject.toml `python_files = ["test_*.py"]`），下划线用法为 pytest 既定例外
- ✅ 未新增设计文档，无命名规范适用面
- ✅ 既有文件（index.html / index.zh.html / features.md）未改名

## 安全事项

🟢 SEC-017-1 — dashboard 主机名展示值：落地页用 `http://localhost:8180`，cli.py:615 启动输出用 `http://127.0.0.1:{port}`；dashboard.py:160 URL 数据模型 domain 默认 `localhost`，页面与数据模型一致。localhost 与 127.0.0.1 均为 loopback，展示性等价，记录不扣分。

🟢 SEC-017-2 — MCP 图标展示值：落地页静态 `🤖` 装饰图标，源码 cli.py:731 为状态相关 `🟢/🔴`。`{icon}` 为格式占位，终端模拟页用静态图标属正常展示设计，结构串一致，记录不扣分。

## 评分

| 项目 | 扣分 |
|:-----|:----|
| Base | 100 |
| 🔴 HIGH × 0 | −0 |
| 🟡 MEDIUM × 0 | −0 |
| 🟢 LOW × 2（SEC-017-1/2） | −0 |
| **得分** | **100 / 100 → Rating A** |

## 结论

**✅ PASS（100/100, A）** — CL-SEC17 四任务全部核验通过：双页三处特征对称、场景输出与源码逐字一致（端口为展示值）、防漂移测试断言与页面实测吻合、350 全绿、src/ 零变更。commit/命名规范 3/3 合规。**授权 push**（仅 review 可 push）。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| — | 无未决项 | — |

工作区 `.hermes-project.yaml` 修改为并发会话 WIP（承上批 OBS-1，未提交，不随本批 push），已排除于审计范围。
