# http-server.cli docs 同步批 — review报告 v1.0

- **日期**: 2026-08-24
- **审计员**: Security Reviewer (review profile)
- **范围**: 4 个未 push commit — 纯文档/打包配置同步批
- **Commit(s)**: 1fdc0e1, d9933cc, d661ac9, 801c573
- **等级**: L2 (docs/chore 批 + 全量测试回归)
- **结论**: ✅ PASS 100/100 (A)

---

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:----:|
| 1 | features.md 测试数 343 与实际一致 | `grep -c 'def test_' tests/test_*.py` 求和 38+68+11+30+20+6+29+11+31+65+34 = 343; `.venv` pytest 实测 | ✅ 343 passed in 1.29s |
| 2 | MCP 工具名与源码一致 | mcp.py L47-91 `_TOOLS` 定义 6 个: hs_list/hs_status/hs_start/hs_kill/hs_kill_all/hs_config | ✅ 与 features.md L87 完全一致 (hs_search 已修正为 hs_config) |
| 3 | MANIFEST.in 引用文件真实存在 | `ls README.md README.zh.md README.en.md` | ✅ README.md + README.zh.md 存在; README.en.md 不存在,已从 include 移除 (1fdc0e1) |
| 4 | pyproject readme 对齐 | pyproject.toml L9 `readme = "README.md"`; CHANGELOG 1.1.0 修正记录 | ✅ 与 CHANGELOG 记录一致 |
| 5 | index 双页 Bookmark 组与源码输出一致 | cli.py:873 `_bookmark_add` → `✅ Bookmark 'alpha' → path`; cli.py:918-921 `_bookmark_list` → `📊 N bookmark(s):` + `📌 name` + `📁 path` | ✅ 结构/文案逐项吻合 (EN/ZH 各 +12 行) |
| 6 | 端口 8080 与 README 示例一致 | README.md L60 `# ✅ http://localhost:8080 → ~/project-alpha` | ✅ 一致 |
| 7 | registry-managed 声明属实 | server.py:622 kill_all 仅遍历 `self.registry.all()` (用户 registry.json); ManagedRegistry 独立存 registry-managed.json (registry_managed.py:24) | ✅ `hs kill-all` 确实不关闭托管服务 |
| 8 | 中英双页对称 | index.html vs index.zh.html; README.md vs README.zh.md | ✅ 组数一致、内容对应 (README.zh.md 多 2 行为管道符转义修复) |
| 9 | 改动未触碰 spec.yaml / 源码 / 测试 | `git diff 801c573~4..HEAD --name-only` | ✅ 仅 6 文件: MANIFEST.in, README.md, README.zh.md, features.md, index.html, index.zh.html |
| 10 | 范围 diff 无凭证/无 /Users 字面路径 | `git log -p | grep -c '/Users'` = 0; `+` 行凭证模式扫描 = 0 | ✅ |

---

## 维度评估

### 一、审计规范执行 (审计基础设施)

| 检查项 | 状态 | 说明 |
|:-------|:---:|:-----|
| `.review-level.yaml` 存在 + review_history | ✅ | 项目根, 5 条历史 (2026-07-22 ~ 2026-08-23), tracking ID 连续 |
| `review-log.md` 存在 (Style B 追加) | ✅ | 项目根, 5 条条目, 本轮将追加第 6 条 |
| 每个 finding 有 tracking ID | ✅ | 本轮 0 findings, tracking: none |

> 注: `scripts/verify-review-level.py` 序列化 tracking ID 检查在本项目报 §A5 已知漂移 — 脚本假设 `PROJ-SEC-NNN` 连续编号,而本项目惯例用 `none`(零发现审计)与 range-notation (`HS-SEC-011 ~ HS-SEC-016` + `(closed)` 后缀)。该 FAIL 在 HEAD 版本即存在(与追加前完全同类),非本轮引入。脚本的语义检查(必填键 / verdict 枚举 / score 范围)全部通过,条目数 5 → 6 且日期无重复。

### 二、Commit 规范检查

| Commit | Subject | type@scope | 分组 | 判定 |
|:-------|:--------|:--:|:--:|:--:|
| 1fdc0e1 | chore@package: fix MANIFEST.in readme ref (README.en.md → README.zh.md) | ✅ | ✅ 打包配置 | ✅ |
| d9933cc | docs@features: sync test count 343, MCP tool hs_config, spec link | ✅ | ✅ 文档 (features) | ✅ |
| d661ac9 | docs@index: add Bookmark scenario group (EN/ZH) | ✅ | ✅ 文档 (index) | ✅ |
| 801c573 | docs@readme: add Bookmark section and registry-managed note (EN/ZH) | ✅ | ✅ 文档 (readme) | ✅ |

- 格式 `{type}@{scope}: {subject}` 4/4 ✅; type 全部在项目历史类型集 (docs 6/chore 4/feat 3/audit 3/fix 2/test 1)
- 描述自描述, 无 "fix bug" 类空泛 subject ✅
- 按属性分组干净: 1 chore@package + 3 docs@(features/index/readme), 每个 commit 单一日志变更 ✅
- 无 /Users 字面路径出现在 subject 或 diff ✅

### 三、命名规范检查

- 本轮无新增/重命名文件 (仅修改既有 6 文件), 命名维度无违规项 ✅
- Commit subject 英文为主; 缩写 (MANIFEST.in / README.en.md / README.zh.md / MCP / hs_config / spec) 与产品名 (Bookmark) 原样保留大小写 ✅

---

## 安全事项

无 🔴/🟡 发现。范围 diff 凭证扫描零命中, 无新增文件引入外部资源 (无 CDN/无 SRI 相关变更)。

记录项 (不扣分):
- 🟢 OBS-1: 工作区有未提交 `.hermes-project.yaml` 修改 (project: http-server.cli → http-server, 含 handoff doc 路径改名) — 与本批 4 commit 无关, 未纳入审计范围, 未提交, 待 ops 确认处理时机。
- 🟢 OBS-2: review-log 挂账项 — governance enum 缺 feat@ (沿用历史约定本轮不动)。

---

## 评分

Base: 100
扣分: 无 (0 🔴 + 0 🟡 + 0 🟢 扣分项)
最终: 100 / 100 (Rating: A)

🔴 0 · 🟡 0 · 🟢 2 (记录项)

---

## 结论

**PASS** — 4 commit 纯文档/打包同步批, 数据验证 10/10 通过, commit 格式 4/4 合规, 无命名违规, 无安全发现, 343 测试全绿。按治理规范放行 push。

---

## 待确认清单

- [x] 审计通过 → push origin main (含审计轨迹 commit)
- [ ] OBS-1: .hermes-project.yaml 工作区改名 — 由 ops 确认是否下一批提交
- [ ] OBS-2: governance enum 缺 feat@ — 挂账 (约定不动)
