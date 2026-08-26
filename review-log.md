# http-server-cli — review-log

> Append-only security audit log. P0🔴/P1🟡/P2🟢 grading, HS-SEC-NNN tracking.
> Entries written by review profile, never deleted.

---

## 2026-07-22 — Code review: perf@handler implementation (P0/P1/P2)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2 (code with file I/O — handler.py, registry.py)
- **Scope**: `commit 20509f4` — 4 files, +322/-13 (handler.py, registry.py, test_handler.py, test_registry.py)
- **Verdict**: ✅ PASS
- **Score**: 95 / 100 (Rating: A)

### Summary

Implementation review of the hot-path optimization: `_touch_memory()` replaces per-request
`Registry().touch()`, `log_message` flush throttled to every 100 requests, and Registry
lazy-init via mtime caching. Implementation faithfully follows the approved design (v1.1).
308 tests pass (293 original + 15 new). One 🟡 finding: lost-update race in
`_flush_access_cache` when external process modifies registry.json within the same
APFS second as the flush.

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| HS-SEC-010 | 🟡 | _flush_access_cache lost-update within same mtime second | registry.py:55-68 | Open |

### Positives

- Defensive `list()` copy in `_flush_access_cache` iteration
- `except OSError` fallback for missing registry file in `_get_cached_data`
- `touch()` docstring updated to redirect hot-path callers to `_touch_memory()`
- 15 new tests cover all P0/P1/P2 paths, edge cases (empty cache, missing entry, interval)
- monkeypatch-based negative assertion: verify Registry.touch is NOT called
- Test isolation: `_reset_cache()` helper cleans module state before each test

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| HS-SEC-010 | _flush_access_cache lost-update (same-second) | 🟡 | P2 | Open |

---

## 2026-07-22 — Design doc review: perf-hot-path-optimization v1.1

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L1 (design document — no executable code changes)
- **Scope**: `documents/perf-hot-path-optimization-design-v1.1-20260722.md` (commit `69101fd`)
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)

### Summary

Design document review for a hot-path performance optimization: replacing per-request
`Registry.touch()` atomic writes with in-memory marking + 60s batch flush. The document
is data-driven (root cause analysis with concrete numbers), well-structured (3-tier fix
prioritization), and complete (impact assessment, risk table, decision records). Two
minor rigor gaps identified (flush latency analysis, mtime race window) — neither blocks
implementation. No security findings. Commit and naming conventions fully compliant.

### Positives

- Root cause call-chain trace (do_GET → touch → save → write_json → mkstemp → json.dump → os.replace)
- Before/after impact table with 7 quantifiable metrics
- Backward compatibility explicitly verified (API, JSON schema, Registry.touch preserved)
- TDD-first implementation plan (test → implement → full regression)
- Single-thread HTTPServer assumption validated — no false thread-safety flags

### Rigor Notes

| # | Level | Note |
|:--|:-----|:-----|
| 1 | 🟡 | `_flush_access_cache()` synchronous in request thread — undocumented latency budget |
| 2 | 🟡 | mtime cache 1-second race window with external registry writes — undocumented |

### Tracking

No security findings. No tracking IDs assigned.

---

## 2026-08-23 — Commit audit: rename batch http-server-cli → http-server.cli (7 commits)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2 (code with file I/O — data dir migration)
- **Scope**: rename batch, 7 unpushed commits (ahead 7)
- **Commit(s)**: 040c08f, 3b58879, a696253, b0e7bab, ec4b31a, 4ba0c57, f6a6909
- **Verdict**: ⏳ CONDITIONAL PASS
- **Score**: 70 / 100 (Rating: B)

### Summary

Commit audit of the rename batch (project name http-server-cli → http-server.cli, GitHub repo
renamed). Migration logic verified sound: `os.rename` atomic move (utils.py:62) with `copytree`
fallback on OSError (utils.py:67) and warn-and-continue on double failure (utils.py:71-74);
live probe confirmed old dir removed, config/registry/bookmarks/logs all migrated, idempotent
second run, new-dir-exists skip. 343 tests pass (incl. 5 new migration tests). `hs version --json`
outputs name=http-server.cli / version=1.1.0. Commit format 7/7 `type@scope: subject`, grouped by
attribute. Feature commits 89ed981/da5cfcb (bookmark composite key, --json) confirmed already on
origin/main. But "改名后无残留旧名" acceptance criterion FAILS: 6 active-file residuals
(SEC-011~016) — bookmark/history docstrings, dashboard github URLs, MANIFEST.in dangling include
(packaging regression), spec.yaml content drift (name/version/output-string/log paths), handoff
doc old title + /Users absolute paths. Per governance: no push; back to ops for fixes.

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| HS-SEC-011 | 🟡 | bookmark.py docstring 残留旧数据目录 | src/http_server_cli/bookmark.py:31 | Open |
| HS-SEC-012 | 🟡 | history.py docstring 残留旧数据目录 | src/http_server_cli/history.py:4 | Open |
| HS-SEC-013 | 🟡 | dashboard 模板残留旧 GitHub URL | src/http_server_cli/dashboard.html:183, dashboard.en.html:188 | Open |
| HS-SEC-014 | 🟡 | MANIFEST.in 悬空 include（sdist 打包回归） | MANIFEST.in:1 | Open |
| HS-SEC-015 | 🟡 | spec.yaml 内容 drift（name/version/输出串/日志路径） | http-server.cli.spec.yaml:1-2,282,408,419 | Open |
| HS-SEC-016 | 🟡 | handoff 文档旧名标题 + /Users 绝对路径 | documents/handoff/handoff-http-server.cli-review.md:11,21,53 | Open |

### Positives

- Migration logic correct and defensively layered (move → copytree → warn-continue), old data never destroyed
- 5 targeted migration unit tests + live environment probe both green; 343/343 full suite
- Commit grouping by attribute (docs/test/feat/chore) clean and atomic
- Feature commits 89ed981/da5cfcb already pushed — no scope creep in this batch

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| HS-SEC-011 | bookmark.py docstring 旧数据目录 | 🟡 | P2 | ✅ Closed (0dcbab2) |
| HS-SEC-012 | history.py docstring 旧数据目录 | 🟡 | P2 | ✅ Closed (0dcbab2) |
| HS-SEC-013 | dashboard GitHub URL 旧名 | 🟡 | P2 | ✅ Closed (0dcbab2) |
| HS-SEC-014 | MANIFEST.in 悬空 include | 🟡 | P1 | ✅ Closed (0dcbab2, sdist 实测) |
| HS-SEC-015 | spec.yaml 内容 drift | 🟡 | P1 | ✅ Closed (0dcbab2) |
| HS-SEC-016 | handoff 旧名标题 + /Users 路径 | 🟡 | P2 | ✅ Closed (fd07634) |

OBS-1: CHANGELOG 1.1.0 date 2026-08-19 vs commit date 08-23 (🟢 record-only) → ✅ Closed (fd07634)
OBS-2: scan-commits.py default enum lacks feat@; project convention uses feat@ (governance §5 enum gap, 🟢) → ✅ Closed (2026-08-24, design-review skill v1.8.0: DEFAULT_TYPES 补入 feat; feat@ 扫描实测 ok，见下方 skill-fix 条目)

> ✅ RESOLVED → v1.1 re-audit (2026-08-23): PASS 100/100，见下方 re-audit 条目。

---

## 2026-08-23 — Commit re-audit: rename batch fix closure (HS-SEC-011~016 + OBS-1)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2 (code with file I/O — data dir migration)
- **Scope**: fix commits 0dcbab2 + fd07634（纯文本替换，8 文件 14 行 + 2 文件 4 行）
- **Commit(s)**: 0dcbab2, fd07634
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)

### Summary

Re-audit of the two fix commits closing all 6 🟡 findings (HS-SEC-011~016) plus OBS-1 from the 2026-08-23 rename batch audit (CONDITIONAL PASS 70/B). Every item verified against current file state + fix-commit diff: bookmark.py:31 / history.py:4 docstrings → `~/.http-server.cli/...`; dashboard.html:183 + dashboard.en.html:188 GitHub href → `imjaden/http-server.cli`; MANIFEST.in include → `http-server.cli.spec.yaml` with sdist build 实测（`uv build --sdist`，tarball 内含新 spec，无旧名）；spec.yaml name/version/输出串/日志路径全同步（http-server.cli / 1.1.0 / L282 / L408+L419）并连带同步 release-*.sh 显示串；handoff 标题 → `http-server.cli-review`、/Users 路径 → `$HOME`。343 测试全绿。全局旧名扫描仅剩合理保留（PyPI 包名 1A、LEGACY_DATA_DIR 迁移逻辑、历史文档、CHANGELOG 历史条目、迁移测试描述）。`hs version` 实测输出 `http-server.cli v1.1.0` 与 spec L282 一致。修复提交无新增问题。OBS-2 按约定挂账（🟢 记录项，不影响评分）。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| — | — | 无新增发现（上轮 6 🟡 + OBS-1 全部闭合） | — | — |

### Positives

- 修复提交最小化且外科式：14 + 4 行纯文本替换，无 scope creep
- sdist 打包回归用真实构建 + tarball 检查验证（不止改 MANIFEST.in 文本）
- release 脚本显示串同步超出 SEC-015 清单范围（bonus 一致性）
- CLI 运行时输出与 spec 场景 L282 交叉验证（行为一致性）

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| HS-SEC-011~016 | rename residuals (6 🟡) | 🟡 | P1/P2 | ✅ Closed (0dcbab2/fd07634) |
| OBS-1 | CHANGELOG date drift | 🟢 | — | ✅ Closed (fd07634) |
| OBS-2 | governance enum lacks feat@ | 🟢 | — | ⏸ 挂账（约定本轮不动） |

---

## 2026-08-23 — Commit audit: fix@spec YAML quoting (ac69262)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2 (spec 文件 + 全量测试回归)
- **Scope**: 1 个未 push commit — fix@spec: quote scenario values with colons to fix YAML syntax
- **Commit(s)**: ac69262
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)

### Summary

3 处 `then:` 值内含 `: `（半角冒号+空格）导致 YAML plain scalar 解析报错，整值以单引号包裹修复（L389/L394/L429）。`yaml.safe_load` 实测通过（8 specs），全量扫描无其他未加引号冒号值，输出串语义逐字未变。commit 格式 `fix@spec: subject` 符合 type@scope 约定，单行描述自描述。无新增/重命名文件。343 测试全绿（Python 3.12 + PYTHONPATH=src 实测）。无新增发现。

### Tracking

无新增发现，无 tracking ID。

---

## 2026-08-24 — Commit audit: docs 同步批 (MANIFEST/features/index/README, 4 commits)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2 (docs/chore 批 + 全量测试回归)
- **Scope**: 4 个未 push commit — 纯文档/打包配置同步批（MANIFEST.in readme ref / features.md 同步 / index Bookmark 组 / README Bookmark + registry-managed）
- **Commit(s)**: 1fdc0e1, d9933cc, d661ac9, 801c573
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)

### Summary

4 commit 全部为文档/打包配置改动，无源码逻辑变更。数据验证 10/10 通过：features.md 343 = `grep -c 'def test_'` 求和（38+68+11+30+20+6+29+11+31+65+34）且 pytest 实测 343 passed in 1.29s；MCP 工具名 6 个（hs_list/hs_status/hs_start/hs_kill/hs_kill_all/hs_config）与 mcp.py L47-91 `_TOOLS` 一致（hs_search → hs_config 修正正确）；MANIFEST.in include README.md + README.zh.md 均存在、README.en.md 不存在（1fdc0e1 修复正确，与 pyproject L9 readme=README.md / CHANGELOG 1.1.0 对齐）；index 双页 Bookmark 组与 cli.py:873 `✅ Bookmark 'alpha' → path`、cli.py:918-921 `📊 N bookmark(s):`+`📌 name`+`📁 path` 逐项吻合，端口 8080 与 README L60 示例一致；registry-managed 声明属实（server.py:622 kill_all 仅遍历用户 registry.json，托管服务独立 registry-managed.json，kill-all 不关）；中英双页对称（index +12/+12，README +14/+16，zh 多 2 行为管道符转义修复）。范围文件仅 6 个（MANIFEST.in/README.md/README.zh.md/features.md/index.html/index.zh.html），未触碰 spec.yaml/源码/测试。commit 格式 4/4 type@scope 合规（chore@package/docs@features/docs@index/docs@readme），type 均在项目历史类型集；无 /Users 字面路径；无凭证。无新增发现。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| — | — | 无新增发现 | — | — |

### Positives

- 数据同步全部以源码实证为据（grep 求和 + pytest 实测 + mcp.py/cli.py 输出串逐一比对），非凭描述
- MANIFEST.in 修复与 pyproject readme 字段、CHANGELOG 1.1.0 记录三方对齐，无悬空引用
- README.zh.md 顺带修复 dashboard 子命令表管道符未转义（EN 已转义，ZH 补齐对称）
- Bookmark 组终端模拟格式与源码输出逐字一致（含 emoji 前缀），场景可复现

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| OBS-1 | 工作区 .hermes-project.yaml 改名（http-server.cli → http-server）未提交 | 🟢 | — | ⏸ 待 ops 确认（与本批无关） |
| OBS-2 | governance enum 缺 feat@ | 🟢 | — | ✅ Closed (2026-08-24, skill v1.8.0) |

无新增发现，无 tracking ID。

---

## 2026-08-24 — Skill-fix: design-review scan-commits.py DEFAULT_TYPES 补入 feat (OBS-2 翻转)

- **Reviewer**: Security Reviewer (review profile)
- **Commit(s)**: 无（skill 修复位于 review profile 技能目录，非本项目代码）
- **Verdict**: ✅ OBS-2 Closed

### Summary

治理规范处理 OBS-2：design-review skill 自带扫描脚本
`~/.hermes/profiles/review/skills/software-development/design-review/scripts/scan-commits.py`
`DEFAULT_TYPES`（原 L21）枚举缺 `feat`，导致扫描 `feat@` commit 时被标 BAD。
本轮最小修复：

- scan-commits.py `DEFAULT_TYPES` 补入 `feat`（其他类型不变，`--type` 显式覆盖语义不变）
- SKILL.md 版本 1.7.0 → 1.8.0；batch-scan 说明 + §5 stale pitfall + 两个 reference
  （push-gate-audit-pattern.md / governance-handbook-reference.md）同步枚举复述
- 实测：http-server.cli HEAD~40..HEAD feat 7/7 ok、hermes-manager HEAD~60..HEAD feat 5/5 ok；
  回归 add/docs/chore/test 等其余类型行为不变；`--type feat,audit` 覆盖生效、
  `--type` 旧枚举（无 feat）时 feat@ 仍标 BAD（覆盖语义未变）
- 治理手册 §5 类型清单本身（v1.3-20260823）仍未含 feat/audit/fix/perf —— 属手册侧缺口，
  已在 governance-handbook-reference.md 加注记，按 GOV observation 处理（非本轮范围）

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| OBS-2 | scan-commits.py default enum lacks feat@ | 🟢 | — | ✅ Closed (2026-08-24) |

---

## 2026-08-25 — Commit audit: CL-SEC17 index 双页优化批 (a032a5e, a231294, 6d42946)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 — 落地页/测试/文档批 + 全量测试回归）
- **Scope**: 3 个未 push commit — CL-SEC17 闭环（T1: Manage/管理 场景组 / T2: 双源防漂移测试 / T3: aria-pressed + footer 域名 / T4: features.md 同步）
- **Commit(s)**: a032a5e, a231294, 6d42946
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-index-dualpage-implementation-review-v1.0-20260825.md

### Summary

3 commit 全部核验通过，数据验证 14/14：未 push 恰为 3 个；src/ 零变更（diff 仅 features.md/index.html/index.zh.html/tests/test_index_sync.py 4 文件）；双页组数 = 5（EN Start/View/Kill/Bookmark/Manage ↔ ZH 启动/查看/关闭/书签/管理）、对比表 <tr> = 6、aria-pressed 初始态 + setTheme JS 同步、footer 域名 + CNAME 四方一致；dashboard 场景输出 `📊 Dashboard → http://localhost:8180` 与 dashboard.py:160 URL 模型（domain 默认 localhost）及 cli.py:615 结构一致（8180 = cli.py:53 默认端口）；MCP 场景输出 `🤖 hs mcp (SSE) → http://127.0.0.1:8765/sse` 与 cli.py:731 逐字一致（示例端口 8180/8765 为展示值，测试未断言端口）；无旧仓库链接残留（0 hits）；无 /Users 字面路径；features.md 343→350/11→12 与 `grep -c 'def test_'` 求和 350 实测吻合；pytest 实测 **350 passed in 1.28s**（含 test_index_sync.py 7/7）。commit 格式 3/3 type@scope 合规（feat@index/test@index/docs@features），分组按属性无混批，scan-commits.py 0 violations；命名规范：新增 test_*.py 符合 pytest 约定。🟢 仅 2 条展示值记录（SEC-017-1 dashboard 主机名 localhost vs cli.py:615 的 127.0.0.1，与数据模型一致；SEC-017-2 MCP 静态 🤖 vs 源码状态 🟢/🔴），0 扣分。已 push（见 Tracking 关闭说明）。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| SEC-017-1 | 🟢 | dashboard 展示主机名 localhost（与 dashboard.py:160 数据模型一致；cli.py:615 启动输出为 127.0.0.1，loopback 等价） | index.html:343 | 记录 |
| SEC-017-2 | 🟢 | MCP 展示图标为静态 🤖（源码 cli.py:731 为状态 🟢/🔴，`{icon}` 为占位） | index.html:345 | 记录 |

### Positives

- 场景输出与源码逐字/逐结构比对（cli.py:615/731 + dashboard.py:160），非凭描述；示例端口明确为展示值且测试零端口断言
- 双页 +16/+16 逐块对称，diff 逐行比对无漂移
- T2 防漂移测试为纯文件断言（无 Selenium），14 项结构特征 + 组数/行数/残留三类计数，覆盖面与落地页实测吻合
- 3 commit 单一属性分组（feat=双页 / test=测试 / docs=features.md），scope 语义准确

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| SEC-017-1 | dashboard 展示主机名（展示值说明） | 🟢 | — | ✅ Closed (2026-08-25, PASS 100/100, pushed) |
| SEC-017-2 | MCP 展示图标（展示值说明） | 🟢 | — | ✅ Closed (2026-08-25, PASS 100/100, pushed) |
| OBS-1 | 工作区 .hermes-project.yaml 修改未提交（并发会话 WIP，承上批） | 🟢 | — | ⏸ 待 ops 确认（与本批无关，未随 push） |

---

## 2026-08-25 — Commit audit: CL-SEC18 spec 补域 T5 (7352fbd)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 — spec.yaml 补域 + 全量测试回归）
- **Scope**: 1 个未 push commit — CL-SEC18 闭环（T5: spec.yaml 补齐 9 个新 capabilities，8→17）
- **Commit(s)**: 7352fbd
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-spec-capabilities-review-v1.0-20260825.md

### Summary

单 commit 纯 spec 变更核验通过，数据验证 25/25：capabilities 声明 17 = specs 定义 17，一一对应无缺失无冗余（yaml.safe_load 实测）；9 新 capability req/scenario 计数与需求声明逐一吻合（bookmark 5/11、http-serving 2/5、registry-managed 2/3、dashboard 4/9、mcp-integration 3/6、json-output 2/5、url-flag 1/2、glob-resolution 2/2、data-migration 1/4 = 22 reqs/47 scenarios）；47 个新 scenarios 与源码行为全部一致——bookmark 组合键 (path,index_page)+--force 覆盖（bookmark.py:94-107）、DataCorruptionError（bookmark.py:23/49-53）、内置命令冲突（cli.py:827-833）、通配符原样/字面量校验（cli.py:846-859）；mcp _TOOLS 6 工具逐名一致（mcp.py:45-95）、initialize 校验（mcp.py:271-272）、stdio 不登记托管 vs SSE 登记（mcp.py:485-488/516-518）；handler Range 206+Content-Range+416（handler.py:110-131）；dashboard /api/* 路由 + /en + ?lang=zh（dashboard.py:85-129）、默认 8180 + -p + stop/status/restart（cli.py:551/546-548）；--url 与 --json 互斥（cli.py:172-174）+ url_only 退出码；json 信封 {success,command,data,error}（utils.py:306-322）；_migrate_legacy_data 4 场景（utils.py:47-74：无旧目录→return/新目录存在→return/move 失败→copytree 兜底/双失败→警告继续）；kill-all 隔离托管（server.py:620-622 仅遍历用户 registry）；YAML 语法有效；pytest 实测 **350 passed in 1.23s**（.venv）；src/ 零变更（diff 仅 http-server.cli.spec.yaml +390 行）；无 /Users 字面路径（0 hits）；commit 格式 docs@spec: 合规（scope 非空，无 body 亦可）。命名规范：capability 17/17 kebab-case（正则实测）。🟢 仅 2 条记录（SEC-018-1 dashboard CORS * + 无认证但绑定 127.0.0.1 loopback 边界明确；SEC-018-2 bookmark.py:33 docstring 与新组合键语义不一致，属源码遗留文案，本 commit 未触碰 src/），0 扣分。已 push（见 Tracking 关闭说明）。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| SEC-018-1 | 🟢 | dashboard API 无认证 + Access-Control-Allow-Origin: *（绑定 127.0.0.1 loopback，本地工具边界明确） | src/http_server_cli/dashboard.py:64,521 | 记录 |
| SEC-018-2 | 🟢 | bookmark.py:33 docstring "路径唯一约束" 与组合键新语义（同 path 不同 index_page 可并存）不一致 — 源码遗留文案，spec 未断言 | src/http_server_cli/bookmark.py:33 | 记录 |

### Positives

- capabilities 17=17 用 yaml.safe_load 程序化比对（非人工数数），缺失/冗余/重复三类全查
- 9 个新 capability 全部锚定到具体源码行（bookmark.py/mcp.py/handler.py/dashboard.py/cli.py/utils.py/server.py），无凭空声明
- 测试回归用项目 .venv 环境（350 passed in 1.23s），非系统 python3（系统 3.9 无包导致 collect 失败已识别）
- 单文件纯 spec 变更 +390 行，无代码混入，commit 分组干净

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| SEC-018-1 | dashboard CORS/认证（记录项） | 🟢 | — | ✅ Closed (2026-08-25, PASS 100/100, pushed) |
| SEC-018-2 | bookmark.py:33 docstring 组合键语义（记录项） | 🟢 | — | ✅ Closed (2026-08-25, PASS 100/100, pushed) |
| OBS-1 | 工作区 .hermes-project.yaml 修改未提交（并发会话 WIP，承上批） | 🟢 | — | ⏸ 待 ops 确认（与本批无关，未随 push） |

---

## 2026-08-25 — Commit audit: CL-SEC19 index 落地页 page-index 对齐批 (92250f4, 95cf6f7, a039321, 5f7028e, 84f53d9)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 — index 双页 page-index 对齐 + data-copy 修正 + 全量测试回归）
- **Scope**: 5 个未 push commit — CL-SEC19 闭环（T1 两列首屏 / T2 场景网格 3 列 / T3 对齐 html-gen page-index 结构 / T4 手工微调定案 + data-copy 修正）
- **Commit(s)**: 92250f4, 95cf6f7, a039321, 5f7028e, 84f53d9
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-index-page-index-audit-v1.0-20260825.md

### Summary

5 commit index 对齐批核验通过，数据验证 19/19：src/ 零变更（diff 仅 index 双页 + test_index_sync.py + features.md + 建议文档）；双页对称全项对应——组数 5/5（Start+Bookmark/View/Kill+Manage↔启动+书签/查看/关闭+管理）、场景 cmd-row 14/14、首屏 code-block 4/4（hs -o / hs --open --index index.html / hs list / hs kill 8081）、对比表 <tr> 6/6、title 全称 HTTP Server、window.innerHeight - 55 双页；**data-copy 与 .cmd 显示命令 19/19 逐字一致且不含 $ prompt**（84f53d9 修正闭环，脚本提取比对）；page-index 结构要素 25 项抽验 + 测试 37 项全在（hero-title 渐变/hero-blocks/code-block/scroll-bounce/templates-title/sub/grid 1500/1100 断点/back-top/site-footer/id="top"）；旧结构残留 8/8 模式 0 hits（含连字符旧链接）；test_index_sync.py 14/14 定向 passed；全量 **357 passed in 1.44s**（.venv）；features.md 计数 352→357 三段随 commit 原子同步；favicon 3/3 URL 200（设计 3A 要求实测）；无敏感信息；commit 格式 scan-commits.py 5/5 ok（feat@index ×4 + docs@review ×1）；.hermes-project.yaml 未混入。🟢 仅 3 条记录（SEC-019-1 features.md 计数内嵌 feat commit 与前批独立 docs commit 惯例不同但保持原子一致；SEC-019-2 建议文档 2 处 /Users 参考源路径属文档惯例；SEC-019-3 新建议文档无版本段属 §1 工作文件豁免），0 扣分。**已 push：fa853e3..84f53d9 main -> main，origin/main 新 tip = 84f53d9**。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| SEC-019-1 | 🟢 | features.md 测试计数内嵌 feat@index commit（352→355→356→357，与前批独立 docs commit 惯例不同；每 commit 文档-代码原子一致，无漂移窗口） | features.md:98 | 记录 |
| SEC-019-2 | 🟢 | 建议文档含 2 处 /Users 参考源路径（既有已 push review/design 文档均含，文档惯例，非代码/配置） | documents/review/html-gen-optimize-suggestions-20260825.md:4,72 | 记录 |
| SEC-019-3 | 🟢 | 新建议文档命名无 v{major}.{minor} 版本段（§1 工作文件豁免；目标项目为 html-gen，跨项目回哺语义清晰） | documents/review/html-gen-optimize-suggestions-20260825.md | 记录 |

### Positives

- data-copy 修正项用脚本程序化比对 19 处（非抽查），双页 .cmd 显示与复制值逐字一致、无 $ prompt 混入
- page-index 对齐核验双层：独立脚本 25 项 + 测试 STRUCTURE_FEATURES 37 项，与落地页实测全部吻合
- 旧结构残留 8 模式全查（含连字符旧链接/qs-col/cmp-col/jaden.local 等隐蔽类），0 hits 有据
- favicon 可访问性实测 3/3 200，落实设计 3A "验证 200" 要求
- 84f53d9 手工微调 diff 逐行核验（title/命令增删/height 修正/data-copy 同步/测试断言同步 EN/ZH 对称）

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| SEC-019-1 | features.md 计数内嵌 feat commit（记录项） | 🟢 | — | ✅ Closed (2026-08-25, PASS 100/100, pushed) |
| SEC-019-2 | 建议文档 /Users 参考源路径（记录项） | 🟢 | — | ✅ Closed (2026-08-25, PASS 100/100, pushed) |
| SEC-019-3 | 建议文档命名无版本段（记录项） | 🟢 | — | ✅ Closed (2026-08-25, PASS 100/100, pushed) |
| OBS-1 | 工作区 .hermes-project.yaml 修改未提交（并发会话 WIP，承上批） | 🟢 | — | ⏸ 待 ops 确认（与本批无关，未随 push） |

---

## 2026-08-26 — Commit audit: CL-SEC20 hs AI 对接批次一 (5e9f7aa, 6fafaa1, cf21184, 8aaca27, 3a82cd9)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 — hs prompt 子命令 + MCP 数据工具/Resources + mcp --config + 版本 1.2.0）
- **Scope**: 5 个未 push commit — CL-SEC20 闭环（prompt 供给站 / MCP 5 数据工具 + Resources / mcp --config / 版本 1.2.0）
- **Commit(s)**: 5e9f7aa, 6fafaa1, cf21184, 8aaca27, 3a82cd9
- **Verdict**: ⚠️ CONDITIONAL PASS
- **Score**: 70 / 100 (Rating: B)
- **Report**: documents/review/http-server-cli-ai-integration-audit-v1.0-20260825.md

### Summary

批次主体核验通过:hs prompt 全路径 5/5 实测（列表 4 skill / 详情全文 / --brief / --json 信封正常+错误 / 不存在 exit 1）;MCP 11 工具（6 管理 + 5 数据）tools/list 实测 + _TOOL_MAP 全覆盖;`_build_hs_args` 回归 8 例（旧 6 工具不变,kill 特例保留）+ bookmark_add 三形态 3 例;Resources 3 项 list/read 实测 + 缺失容错 '{}' + initialize capabilities.resources;新工具端到端 tools/call 5/5（隔离 HOME）;`hs mcp --config` YAML 合法 + --json 信封正确;版本 1.2.0 五处一致（__init__/CHANGELOG/`hs version`/features.md/pyproject dynamic）;**378 passed in 1.36s**（.venv）;diff 12 文件无越界;无敏感信息 0 hits;.hermes-project.yaml 未混入;commit 格式 5/5 + 命名规范合规。

**🔴 SEC-020-1（阻断）**:`hs mcp --config` 输出的 stdio 配置不可用 —— 实测 `hs mcp`（= config 的 `args:["mcp"]` + transport stdio）管道握手输出 `SSE daemon -> http://127.0.0.1:8181/sse` 后退出,无任何 JSON-RPC 响应,后台 daemon 监听 8181（lsof + registry-managed.json 双证）;对照 `--transport stdio` 全部正常。根因:cli.py:789 仅识别 `--transport`,config args 缺 `--transport stdio`;设计 §四:116 错误前提 "`--stdio` 已存在" 被照抄。连带 🟡 SEC-020-2（--stdio/8765 文档失实 6 处:cli.py:812, hs-cli:55, hs-mcp:16-17, design:64/115/116 —— 实测默认端口 8181,8765 系本批笔误）+ 🟡 SEC-020-3（hs-mcp:73 错误码 -32601 vs 实测 -32602）+ 🟡 SEC-020-4（8aaca27 subject "tests (21)" 实测 12,21 为批次总量）+ 🟢 SEC-020-5/6/7（bookmark JSON 示例 command、design 模板表格漂移、skills 缺失测试场景未落地）。**未 push**,修复清单回 ops,复审通过后 push。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| SEC-020-1 | 🔴 | `hs mcp --config` 输出 stdio 配置不可用（args ["mcp"] 启动后台 SSE daemon,无 JSON-RPC 握手;设计错误前提 "--stdio 已存在" 被照抄） | src/http_server_cli/cli.py:800,809,812 | ⏳ 待 ops 修复 |
| SEC-020-2 | 🟡 | 文档声称 `--stdio` flag（不存在,仅 `--transport stdio`）与端口 8765（实测默认 8181,本批笔误） | cli.py:812;skills/hs-cli/SKILL.md:55;skills/hs-mcp/SKILL.md:16,17;documents/hs-ai-integration-design-v1.0-20260825.md:64,115,116 | ⏳ 待 ops 修复 |
| SEC-020-3 | 🟡 | 边界错误码 -32601 与实现不符（实测 -32602） | skills/hs-mcp/SKILL.md:73 | ⏳ 待 ops 修复 |
| SEC-020-4 | 🟡 | commit subject "tests (21)" 计数失实（该 commit 新增 12,21 为批次总量） | commit 8aaca27 | ⏳ 待 ops 决定（amend 或记录） |
| SEC-020-5 | 🟢 | JSON 示例 command 值 "bookmark" 与实现 'bookmark-list' 不符（示例文案） | skills/hs-bookmark/SKILL.md:52 | 记录 |
| SEC-020-6 | 🟢 | design §三 hs_bookmark_add 模板示例漂移（缺 -i/--force;param_map 'index'→'index_page';实现为超集,决策级一致） | documents/hs-ai-integration-design-v1.0-20260825.md:76,85 | 记录 |
| SEC-020-7 | 🟢 | 测试计划 "skills 缺失场景（monkeypatch SKILLS_DIR）" 未落地（SKILLS_DIR 为函数内局部变量;代码路径存在且正确） | tests/test_prompt.py;documents/hs-ai-integration-design-v1.0-20260825.md:126 | 记录 |

### Positives

- hs prompt 全路径 5/5 实测（含 exit code 与 stderr/stdout 分流）,非仅单测
- MCP 新工具端到端 tools/call 5/5 在隔离 HOME（/tmp/hs-audit-home）实测,不触碰真实用户数据
- `--config` 问题用行为证据闭环:管道握手 + lsof + registry-managed.json 双证,并对照 `--transport stdio` 正常路径
- 测试 378 全绿用项目 .venv（Python 3.11.15）,非系统 python3
- diff 范围 12 文件逐一核对,无越界;敏感信息 0 hits

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| SEC-020-1 | mcp --config stdio 配置不可用（args 缺 --transport stdio） | 🔴 | P0 | ⏳ 待 ops 修复 |
| SEC-020-2 | --stdio/8765 文档失实 6 处 | 🟡 | P1 | ⏳ 待 ops 修复 |
| SEC-020-3 | 错误码 -32601 vs -32602 | 🟡 | P1 | ⏳ 待 ops 修复 |
| SEC-020-4 | 8aaca27 subject 计数失实 | 🟡 | P2 | ⏳ 待 ops 决定 |
| SEC-020-5 | bookmark JSON 示例 command（记录项） | 🟢 | — | ⏳ 记录 |
| SEC-020-6 | design 模板表格漂移（记录项） | 🟢 | — | ⏳ 记录 |
| SEC-020-7 | skills 缺失测试场景未落地（记录项） | 🟢 | — | ⏳ 记录 |

---

## [v1.1 re-review] CL-SEC20 hs AI 对接批次一 — 修复闭环 re-review PASS

- **Date**: 2026-08-26
- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 re-review — SEC-020 修复复核 + push 闭环）
- **Scope**: 批次 6 commit（5e9f7aa, 6fafaa1, cf21184, 6371725, e693ba6, 7f0ab1c）+ review-fix f734042 + audit@review;baead3b 已在 origin/main
- **Commit(s)**: 5e9f7aa..7f0ab1c + f734042 + audit@review
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-ai-integration-audit-v1.1-20260826.md

### Summary

7 项首审条目逐条复核:SEC-020-1 代码修复（cli.py:800-812 config args → `['mcp','--transport','stdio']` + YAML/--json 同步 + 注释 8181/--transport stdio）经**端到端实测**:按 config args 启动子进程（隔离 HOME）stdio JSON-RPC initialize → serverInfo 1.1.0 + capabilities{tools,resources}、notifications/initialized 静默、tools/list 11 工具、resources/list 3 项（hs://registry|bookmarks|config）全应答;SEC-020-2 六处勘误（cli.py:812 / hs-cli:55 / hs-mcp:16,17 / design:64,115,116 → `--transport stdio` / `127.0.0.1:8181/sse`）+ SEC-020-3（hs-mcp:73 → -32602）+ SEC-020-5（hs-bookmark:52 `command:"bookmark-list"`）+ SEC-020-6（design §三:73 模板与 mcp.py:180-181 逐字一致）全部到位,skills/ 残留扫描 8765/--stdio/-32601 = 0 hits;SEC-020-4 经 amend:6371725 subject `tests (12)` 与 diff 计数一致（test_mcp 29→41,+12:BuildArgs 7 + Resources 5,改名 1 例非新增）,e693ba6 docs@changelog（"378 tests" 实测一致）;SEC-020-7 记录接受（SKILLS_DIR 函数内局部变量 cli.py:666,monkeypatch 成本高,代码路径 cli.py:668-675 正确）。**全量 pytest 378 passed in 1.30s**（.venv）。复查另发现 **SEC-020-8 🟡**:design doc §四:111/114 残留 `args:["mcp"]`（首审 P0 修复建议"设计文档 §四 勘误"未完全执行,7f0ab1c 仅勘误 115/116 备注行）— 由 review-fix **f734042** 推前闭环（args `['mcp','--transport','stdio']`）。**push origin main 完成**（baead3b 已在远端,实际推送 6 + 2 = 8 commits）。

### Findings (re-review)

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| SEC-020-1 | 🔴 | `hs mcp --config` 输出 stdio 配置不可用 | src/http_server_cli/cli.py:800-812 | ✅ 已修（7f0ab1c）+ E2E 实测握手 |
| SEC-020-2 | 🟡 | --stdio/8765 文档失实 6 处 | cli.py:812;skills/hs-cli:55;skills/hs-mcp:16,17;design:64,115,116 | ✅ 已修（7f0ab1c） |
| SEC-020-3 | 🟡 | 错误码 -32601 vs -32602 | skills/hs-mcp/SKILL.md:73 | ✅ 已修（7f0ab1c） |
| SEC-020-4 | 🟡 | commit subject "tests (21)" 计数失实 | commit 8aaca27→6371725 | ✅ 已修（amend subject "tests (12)",29→41 实测一致） |
| SEC-020-5 | 🟢 | JSON 示例 command 值失实 | skills/hs-bookmark/SKILL.md:52 | ✅ 已修（7f0ab1c） |
| SEC-020-6 | 🟢 | design §三 hs_bookmark_add 模板漂移 | documents/hs-ai-integration-design-v1.0-20260825.md:73 | ✅ 已修（7f0ab1c） |
| SEC-020-7 | 🟢 | skills 缺失测试场景未落地 | tests/test_prompt.py;design:126 | 记录接受 |
| SEC-020-8 | 🟡 | design §四:111,114 残留 args:["mcp"]（§四勘误未完全执行） | documents/hs-ai-integration-design-v1.0-20260825.md:111,114 | ✅ 已修（f734042,推前闭环） |

### Positives

- SEC-020-1 修复用行为证据闭环:按 `hs mcp --config` 输出原样启动子进程（隔离 HOME）,initialize/tools-list/resources-list 全应答,非仅静态比对
- 全量 378 passed 用项目 .venv（Python 3.11.15）;skills 残留扫描 0 hits 覆盖 3 个失实 token
- subject 计数用 git show 逐 diff 核验（29→41 = +12 改名 1 例）,非凭 subject 自述
- 复查新增发现（SEC-020-8）推前闭环,不把已知"文档教坏配置"推上远端
- baead3b 状态实测（已在 origin/main）纠正简报计数,避免重复 push

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| SEC-020-1 | mcp --config stdio 配置不可用（args 缺 --transport stdio） | 🔴 | P0 | ✅ 已修 + E2E 实测 |
| SEC-020-2 | --stdio/8765 文档失实 6 处 | 🟡 | P1 | ✅ 已修 |
| SEC-020-3 | 错误码 -32601 vs -32602 | 🟡 | P1 | ✅ 已修 |
| SEC-020-4 | 8aaca27 subject 计数失实 | 🟡 | P2 | ✅ 已修（amend 6371725） |
| SEC-020-5 | bookmark JSON 示例 command（记录项） | 🟢 | — | ✅ 已修 |
| SEC-020-6 | design 模板表格漂移（记录项） | 🟢 | — | ✅ 已修 |
| SEC-020-7 | skills 缺失测试场景未落地（记录项） | 🟢 | — | 记录接受 |
| SEC-020-8 | design §四:111/114 args 残留 | 🟡 | P1 | ✅ 已修（f734042） |

