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

---

## 2026-08-26 — Commit audit: CL-SEC21 hs AI 互通沉淀三件套 (efddb48, d5a3ce1, a156a89, 851bbf1)

- **Date**: 2026-08-26
- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 + 功能实测）
- **Scope**: 4 commits（efddb48, d5a3ce1, a156a89, 851bbf1），基底 origin/main 863b85c（4 commits 全部未 push）
- **Commit(s)**: efddb48..851bbf1
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-ai-interchange-settle-audit-v1.0-20260826.md

### Summary

8 项审计全过。①SKILL.md 内容真实性 11 条断言逐字对照 src/ 全真:`--transport stdio`（cli.py:789/800,全仓 --stdio 0 hits）、8181（cli.py:790/812,8765 0 hits）、-32602（mcp.py:207,未 initialize → ValueError → mcp.py:370）、_TOOL_MAP 双类参数映射（mcp.py:172-185 + 299-322 短 flag 两段式/布尔 True 才追加）、Resources 缺失 '{}'（mcp.py:435-439）、registry-managed 边界（_TOOL_MAP 11 项全用户 registry 命令）、11=6 管理+5 数据（mcp.py:74-170）、--json 信封、SKILLS_DIR parents[2]（cli.py:669）、SERVER_VERSION 1.1.0 + hs:// 三 URI。②hs prompt 实测:无参 5 篇列表、`prompt ai-interchange` 全文与仓库一致、--json status ok + 5 项、--brief、不存在 exit 1。③index 双源:group-title=6/cmd-row=17/code-block=4/tr=6 双页一致,test_index_sync 14 passed,AI 组命令与 data-copy 逐字一致,Manage 去 hs mcp 行、8765→8181、badge 双源同步。④README EN/ZH 对称:YAML 片段 L77 双端一致、6 tools→11（与 _TOOLS 逐名一致）+3 Resources、双表合并降级（Comparison/对比一览 0 残留）、v1.2.x vs 实测 `http-server v1.2.0`、MCP 表 +--config/+prompt 行。⑤features.md skills 4→5 + ai-interchange 行。⑥subject vs diff 4/4（test_prompt 4→5、断言 5→6/14→17、README 双端 61 行对称、features 3+/2−）。⑦**378 passed in 1.34s**（.venv,用例数不变仅断言修改）。⑧diff 敏感信息 0 hits,~/.hermes 镜像说明属有意记录。2×🟢 记录项（SEC-021-1 CHANGELOG v1.2.0 L6 "无参列出 4 篇" 未随第 5 篇同步,按不 bump 版本决策;SEC-021-2 design doc "6 工具" 历史快照）,0 扣分。**push origin main（efddb48..851bbf1, 4 commits）**。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| SEC-021-1 | 🟢（记录） | CHANGELOG v1.2.0 条目 "无参列出 4 篇" 未同步第 5 篇 ai-interchange（不 bump 版本决策,发布快照） | CHANGELOG.md:6 | 记录,待确认 |
| SEC-021-2 | 🟢（记录） | design doc "6 工具" 为设计时点快照（实现已扩展 11）,本批未触碰 | documents/hs-ai-integration-design-v1.0-20260825.md:10,143 | 记录,保持不动 |

### Positives

- SKILL.md 每条实证断言都有 src/ 行号证据（-32602 走 ValueError→mcp.py:370 全链路,非仅静态常量）
- hs prompt 四行为 + exit code + stderr/stdout 分流运行时实测;全文输出与仓库文件逐字一致
- index 双源防漂移用 grep 计数 + pytest 双证;data-copy 与显示命令逐字核对
- README 双端对称逐一比对（YAML 片段 / 工具清单 / 表合并 / 版本）,`hs version` 实测 v1.2.0 而非信 subject
- 全量 378 用项目 .venv;diff 敏感信息 0 hits;cache/ gitignored 确认不入 commit

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| SEC-021-1 | CHANGELOG v1.2.0 "无参列出 4 篇" 未同步（记录项） | 🟢 | — | 记录 |
| SEC-021-2 | design doc "6 工具" 历史快照（记录项） | 🟢 | — | 记录 |

---

## 2026-08-27 — Commit audit: HTTP-SERVER-CL001 hs web 跨项目 Web 服务注册管理 (2528128, 61d8ed7, 0a8e57d)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 + 功能实测）
- **Scope**: 3 commits（2528128 feat@web, 61d8ed7 tests@web, 0a8e57d docs@web），基底 origin/main 99e104b（3 commits 全部未 push）
- **Commit(s)**: 2528128..0a8e57d
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-web-registration-audit-v1.0-20260827.md

### Summary

HTTP-SERVER-CL001 闭环（hs web 一级子命令：ServiceStore + CLI 全套 + 版本 1.3.0）11 项审计全过。功能完整性：六子命令（add/list/show/remove/update/`<name>`）+ help + 六 `--json` 信封 command（web-add/web-list/web-show/web-remove/web-update/web-run）逐名一致（cli.py:1271-1702）。执行语义四分支 + open 策略四态以 mock 断言 + 运行时实测双证：`hs web nonexistent` → stderr 报错 + `Available: daily.checker, jaden.tech` + exit 1；`--no-probe` 强制执行；url 可达 → 跳过 cmd（幂等）直开；cmd 非 0 退出码 → stderr warning 不阻断（cli.py:1681-1702）。存储隔离：`~/.http-server.cli/services.json` 独立于 bookmarks.json，ensure_storage 初始化，DataCorruptionError 损坏检测，url 空串归一 None。校验：name `[a-zA-Z0-9][a-zA-Z0-9._-]*` 最长 128 + cmd 非空 + open_mode 四态 + url `^https?://` + name 拦内置命令（实测 `hs web add list` → conflict）。零外部依赖（urllib 探测，pyproject 无 dependencies）。**442 passed in 1.56s**（.venv，test_web 64 例；features.md 13 模块/442 同步）。文档四同步：CHANGELOG 1.3.0 / features.md / README×2 Web 服务注册节 / `__version__` 1.3.0，`hs version` 实测 `http-server v1.3.0`。注册表两条 intact（daily.checker url + jaden.tech null-url open=cmd，pytest 前后一致，conftest monkeypatch 隔离不触碰真实数据）。全局薄壳 `~/.local/bin/web`（mode 755，`exec hs web "$@"`）`web list` exit 0。diff 敏感信息 0 hits，shell=True 仅 1 处（cli.py:1678，设计 2C 明示语义，攻击面限于用户自有 services.json，无外部输入流入）。2×🟢 记录项（SEC-022-1 名称冲突仅拦顶层命令、未拦 web 子命令；SEC-022-2 合法 JSON 错误形状 → 裸 traceback 非 DataCorruptionError）+ 1×🟡 待确认 OBS-3（spec.yaml version 1.1.0 既有漂移，本批范围外），0 扣分。**push origin main（2528128..0a8e57d, 3 commits + audit）**。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| SEC-022-1 | 🟢（记录） | name 冲突校验仅覆盖顶层命令（_COMMANDS），未覆盖 web 子命令 add/show/remove/update —— 该名服务注册成功但恒被解析为子命令、永无法运行 | cli.py:1342 | 记录 |
| SEC-022-2 | 🟢（记录） | services.json 合法 JSON 错误形状（如 `[1,2,3]`）→ `_read_all` 抛裸 AttributeError，非 DataCorruptionError | services.py:42-49 | 记录 |
| OBS-3 | 🟡（待确认） | spec.yaml version 字段 L2 + version 场景 L291 停 1.1.0（落后 1.2.0/1.3.0 两次 bump），且输出串 `http-server.cli` ≠ 实测 `http-server` —— 既有漂移，本批未触碰 spec.yaml | http-server.cli.spec.yaml:2,291 | ⏳ 待确认 |

### Positives

- 执行语义四分支 + open 策略四态均以 mock 断言（subprocess/webbrowser/url_reachable）+ 运行时实测（`hs web nonexistent` exit 1 + 可用列表）双证，非仅静态比对
- 442 全量零回归用项目 .venv；conftest.py:57 monkeypatch 隔离，pytest 不触碰真实 services.json（审计前后两次读取均 intact）
- 零外部依赖坐实：pyproject 无 dependencies 段 + url_reachable 用标准库 urllib；diff 敏感信息/密钥//Users/eval 0 hits
- 文档四同步以 `hs version` 实测 v1.3.0 为准，非信 subject；README EN/ZH Web 服务注册节双端对称
- commit 3/3 type@scope 合规（feat@web/tests@web/docs@web），分组按属性无混批

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| SEC-022-1 | web 子命令名未拦截（记录项） | 🟢 | — | ✅ Closed (2026-08-27, PASS 100/100, pushed) |
| SEC-022-2 | 合法 JSON 错误形状裸 traceback（记录项） | 🟢 | — | ✅ Closed (2026-08-27, PASS 100/100, pushed) |
| OBS-3 | spec.yaml version 1.1.0 既有漂移（待确认） | 🟡 | P2 | ✅ Closed (197c27a, CL002 docs@spec 同步) |


## 2026-08-27 — Commit audit: HTTP-SERVER-CL002 hs web --domain 入参 + hs-web skill 推广 + CL001 遗留 (38e4ee0, 5e1e20a, 197c27a)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 + 功能实测 + CL001 遗留闭环）
- **Scope**: 3 commits（38e4ee0 feat@web, 5e1e20a tests@web, 197c27a docs@web），基底 origin/main cf40dcb（3 commits 全部未 push）
- **Commit(s)**: 38e4ee0..197c27a
- **Verdict**: ✅ PASS
- **Score**: 95 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-cl002-web-domain-promo-audit-v1.0-20260827.md

### Summary

HTTP-SERVER-CL002 闭环（hs web --domain 入参 + hs-web skill 推广 + CL001 遗留三项）10 项审计 9 项全过 + 1 项部分通过。①--domain 功能：add `--domain`（store_true）→ use_domain=True；update `--domain`/`--no-domain`（no_domain 优先清除，cli.py:1610-1615）；执行 `use_domain=True` → `cmd_line = f"{cmd_line} --domain \"{Config().domain}\""`（cli.py:1704-1707）+ json `cmd_effective`；open/url 探测路径未受影响（cli.py:1690 仍走 url）。②SEC-022-1 闭环：`_WEB_SUBCOMMANDS = {'add','update','list','show','remove','help'}`（cli.py:1272）+ `_web_add` 冲突判断扩展 `name in _COMMANDS or name in _WEB_SUBCOMMANDS` → 拦截 + 不写入。③SEC-022-2 闭环：`_read_all` 三类形状校验（非空 JSON 语法错 / 合法 JSON 非 dict / services 非 list → DataCorruptionError，services.py:53-69），空文件仍 OK。④OBS-3 闭环：spec.yaml version 1.1.0→1.3.0（L2）+ version 场景输出串修正 `http-server v1.3.0`（L291）。⑤hs-web skill：SKILL.md frontmatter 合法，`hs prompt` 6 篇含 hs-web，镜像 ~/.hermes/profiles/ops/skills/devops/hs-web/SKILL.md 与源逐字节一致，test_prompt EXPECTED_SKILLS 6 全等。⑥文档四同步：README EN/ZH Ships 6 skills + Web 节 --domain、features.md Web 节 14 条 + AI 对接 6 篇 + 测试 459、CHANGELOG 1.3.0 扩充、__version__ = spec.yaml = `hs version` 实测 `http-server v1.3.0`。**459 passed in 1.36s**（.venv，test_web 81 例）。diff 10 文件无越界（bookmark/index 未动，版本未 bump），敏感信息 0 hits。1×🟢 记录（SEC-023-1）+ 1×🟡（SEC-023-2 注册表 `dk` 残留）。**push origin main（origin/main 推进至 197c27a）**。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| SEC-023-1 | 🟢（记录） | `--domain` 注入 `Config().domain` 到 shell=True cmd（仅双引号包裹，`"`/`$(...)`/反引号可破出），`set_domain` 无校验（`set_port` 有范围校验）；攻击面 = 用户自有 config.json，无外部输入，与 `svc['cmd']` shell=True 同类（design 2C） | cli.py:1707;config.py:set_domain | 记录 |
| SEC-023-2 | 🟡 | services.json 第三条 `dk` 测试残留（cmd `dk server start --daemon --open`，无 use_domain，created 08:10:11），与审计项 9「两条 intact」不符；demo-cl002 已清但 dk 未清。非安全（dk 为真实命令，缺字段向后兼容），`hs web remove dk` 一条命令清理 | ~/.http-server.cli/services.json | ⏳ 待 ops 清理 |

### Positives

- --domain 全链路以 mock 断言（`mock_run.call_args.args[0]` 逐字断言注入串 + `mock_probe.assert_not_called()` 证探测不受影响）+ 源码逐行核验双证
- CL001 遗留三项（SEC-022-1/2 + OBS-3）逐一闭环，且各配定向测试（冲突 2 例 / 形状 3 例 / spec version 与场景输出串）
- SEC-022-2 形状校验覆盖三类（语法错 / 非 dict / services 非 list），空文件与 legit dict 回归不破坏
- hs-web skill 镜像逐字节比对（非存在性检查）；`hs prompt` 列表/全文/--brief 运行时实测
- 459 全量零回归用项目 .venv（Python 3.11.15）；版本四同步以 `hs version` 实测 v1.3.0 为准，非信 subject

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| SEC-023-1 | --domain shell 注入 defense-in-depth（记录项） | 🟢 | — | ✅ Closed (03ca74b/14e08cf/b33e2f1, CL002 复核) |
| SEC-023-2 | 注册表 dk 测试残留（第三条） | 🟡 | P2 | ✅ Closed (2026-08-27 ops 清理, services.json 2 条 intact) |
| SEC-022-1 | web 子命令名冲突（CL001 遗留） | 🟢 | — | ✅ Closed (38e4ee0) |
| SEC-022-2 | services.json 形状校验（CL001 遗留） | 🟢 | — | ✅ Closed (38e4ee0) |
| OBS-3 | spec.yaml version 漂移（CL001 遗留） | 🟡 | — | ✅ Closed (197c27a) |

---

## 2026-08-27 — Commit re-audit: HTTP-SERVER-CL002 复核 — SEC-023-1 set_domain 字符集校验 (03ca74b, 14e08cf, b33e2f1)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 + 定向测试 + SEC-023-1 闭环）
- **Scope**: 3 commits（03ca74b feat@config, 14e08cf tests@config, b33e2f1 docs@config），基底 origin/main 09d9e3b（CL002 PASS 95/100）
- **Commit(s)**: 03ca74b..b33e2f1
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-cl002-sec023-1-domain-validation-rereview-v1.1-20260827.md

### Summary

CL002 遗留 🟢 记录项 SEC-023-1 闭环（`set_domain` 字符集校验 defense-in-depth）。①校验实现：config.py:12 `_DOMAIN_RE = ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$` + config.py:63-67 先校验后赋值（`not isinstance(value, str) or not match → raise ValueError`，非法不落盘）。②CLI 捕获：cli.py:146-159 `_handle_set` domain 分支 `try/except ValueError` → json 信封 `json_output(False, 'set', error=str(e))` / 文本 `eprint(str(e), '❌')` + `return`，不写 config；port 分支未触碰。③注入不受影响：cli.py:1715 `cmd_line = f"{cmd_line} --domain \"{Config().domain}\""` 未改，`set_domain` 是 domain 唯一写入口，config.json `jaden.local` 合法。④测试：`TestSetDomainValidation` 21 例（6 合法 + 14 非法 + 1 不持久化）+ `TestSetDomainCli` 3 例 = **24 passed**；全量 **483 passed in 1.35s** 零回归，features.md 459→483。⑤范围：仅 6 文件，`__version__ 1.3.0` 未 bump，bookmark/web 执行逻辑未动。⑥文档：CHANGELOG SEC-023-1 条目 + features 483 同步。附带确认 SEC-023-2（注册表 `dk` 残留）已由 ops 清理（services.json 现 daily.checker + jaden.tech 两条 intact）。零新发现。**push origin main（origin/main 推进至 b33e2f1）**。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| — | — | 无新发现 | — | — |

### Positives

- 字符集拒绝全部双引号内可破出的元字符（`"`/`$`/反引号/`\`）+ 双引号外分隔符（`;`/`&`/`|`/空格/换行/重定向），defense-in-depth 完整
- 非法值「先校验后持久化」，不会落盘半成品；CLI json/text 双通道错误信封与 port 分支风格一致
- 24 例定向测试覆盖广（含 `$(rm -rf /)`、反引号、引号、`;`/`&`/`|`/括号、空串、首尾横线）
- 全量 483 零回归（.venv Python 3.11.15）；范围控制到位（仅 6 文件，版本未 bump）

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| SEC-023-1 | --domain shell 注入 defense-in-depth（记录项） | 🟢 | — | ✅ Closed (03ca74b/14e08cf/b33e2f1) |
| SEC-023-2 | 注册表 dk 测试残留（第三条） | 🟡 | P2 | ✅ Closed (2026-08-27 ops 清理) |

---

## 2026-09-08 — Commit audit: docs-consolidation 归档+索引批（P5 推广 #4 方案 A）

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 — 纯文档归档 + 索引 + 引用修正 + 全量测试回归）
- **Scope**: 2 个未 push commit（156087b docs@archive, 55502ac docs@sync），基底 origin/main 60381af；P5 推广 #4 方案 A（窄幅归档 + 原位保留, 非手册化）
- **Commit(s)**: 156087b, 55502ac
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-docs-consolidation-audit-v1.0-20260908.md

### Summary

2 commit 纯文档归档 + 索引批, 8 项审计全过。①归档：3 份 superseded 文档（pypi-release-checklist 20260623 / pypi-release-steps 20260624 / github-ci-issues 20260704）经 R100 纯 rename 落 documents/archive/root-20260908/（0 insert/0 delete, 历史保留）, 桶内计数 = 3, 无他人文件误移, 无 vault 侧改动（vault 外部镜像, 仓库零变更）。②README 索引：定位句（Q1=A 窄幅归档决策）+ 11 主题原位保留表（CLI/书签/Web 注册/HTTP 性能/Dashboard/MCP/AI/CI-CD/review 桶/素材交接/治理面）+ 归档段用 partial stem 不嵌完整 basename（桶内清单以 git ls-files 为准）, 15/15 相对链接 resolve。③引用修正 5/5 exists：features L55 → CL001/CL002 review 实路径（web-registration-audit + cl002-web-domain-promo-audit + sec023-1-domain-validation-rereview）、L60 → dev skill range-request-support.md（~/.hermes/profiles/dev/skills/software-development/http-server-cli-dev/references/）、.hermes-project.yaml:18 handoff.doc → documents/handoff/handoff-http-server.cli-review.md（实盘文件名核实, 旧名已消失）。④引用零残留：full basename（含版本日期）× 非 archive/非历史 = 0；stem 仅 README 归档段（有意）+ rename-fix-rereview 历史报告「历史文档」类别描述（豁免合理）。⑤**490 passed in 1.36s**（.venv Python 3.11.15; 483 为旧时点基线, 零回归）。⑥git 卫生：2 commit 各只含目标文件（156087b 仅 3×R100, 55502ac 仅 3 文件）, worktree clean, review-log/.review-level 未被 dev 改, 无 -A。⑦安全面：纯文档/路径/.hermes-project 指针, 源码零改动。附带闭环 OBS-1（工作区 .hermes-project.yaml handoff.doc 改名由 55502ac 完成）。1×🟢 记录项 OBS-4（范围外：features.md:126 测试数 483 未随 60381af 同步至 490）。**push origin main**。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| — | — | 无新增发现（范围外 1×🟢 记录 OBS-4） | — | — |

### Positives

- 归档用 R100 纯 rename 保历史（非 delete+add），git 可追溯, 0 内容改动
- README 归档段刻意 partial stem + git ls-files 口径, 规避「索引自引用导致零残留误报」, 且 15 个相对链接全部 resolve
- 引用修正以实盘文件存在性逐条核验（5/5 exists + 旧 handoff 名已消失），非信描述
- 全量 490 零回归用项目 .venv（Python 3.11.15）; diff 精确 6 条无 -A 越界, review-log/.review-level 未被 dev 触碰

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| OBS-1 | 工作区 .hermes-project.yaml handoff.doc 改名（承上批挂账） | 🟢 | — | ✅ Closed (55502ac, 本轮闭环) |
| OBS-4 | features.md:126 测试数 483 未随 60381af 同步至 490（范围外既有漂移） | 🟢 | — | ⏳ 待 dev/ops 后续同步 |

---

## 2026-09-08 — Commit audit: docs@sync features 测试数 483→490（OBS-4 闭环）

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（提交审计 — 单行计数同步 + 全量测试回归）
- **Scope**: 1 个未 push commit（09b65aa docs@sync），基底 origin/main 65c2d26
- **Commit(s)**: 09b65aa
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)

### Summary

OBS-4 闭环：features.md:126 测试数 483→490 同步（本应随 60381af feat@web 同步而遗漏，上批挂账）。①diff 精确 1 行（1 insertion / 1 deletion，features.md 483→490），无越界文件。②实测 .venv pytest **490 passed in 1.37s**，与 features.md 计数逐字一致。③源码零改动（纯文档计数），无敏感信息变更。④git 卫生：工作树 clean，commit 仅含 features.md 单文件，无 -A。**push origin main**。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| — | — | 无新增发现 | — | — |

### Positives

- diff 精确 1 行，计数与实测 490 passed 逐字一致
- 纯文档同步，源码零改动，无安全面变更
- 工作树 clean，无 -A 越界

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| OBS-4 | features.md:126 测试数 483 未随 60381af 同步至 490（范围外既有漂移） | 🟢 | — | ✅ Closed (09b65aa, 本轮闭环) |

---

## 2026-09-22 — Design doc review: HTTP-SERVER-CL003 端口参数 + 未识别参数告警 + 周边端口面 (7f3376d)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（设计评审 — 只审设计文档与现状事实，不审实现）
- **Scope**: 1 个未 push commit（7f3376d docs@design），基底 origin/main 1ff81e6（ahead 1）
- **Commit(s)**: 7f3376d
- **Verdict**: ⏳ CONDITIONAL PASS
- **Score**: 82 / 100 (Rating B+)
- **Report**: documents/review/http-server-cli-cl003-design-review-v1.0-20260922.md

### Summary

设计 v1.0 的根因定位（P1–P4）、决策定案（D1–D13）、接口设计、测试清单均经源码 + 实测逐条核对，实质正确。数据验证：P4 假成功实测 `hs dashboard -p abc` exit=0；P2 `allow_reuse_address=1`；D8 `hs -p 8089` → `Unknown command: 8089` exit=1；`parse_known_args` 站点实测 **22** 处（与设计一致）；测试基线 **490 collected**（`def test_`=472，features.md:126=490）；`hs version` = v1.3.1。D1–D13 无互相矛盾，用户「全采推荐」完整覆盖。

存在 5 处必改（F-1~F-5）+ 9 处非阻断（F-6~F-14），均为设计文档一致性/完备性修订，无决策重选。核心：F-1 校验顺序链未定义（幂等检查 server.py:137 先于 -p 保留/占用校验，否则 `-p 8099` 已在运行会被误判「占用」、`-p 8180` 已在别端口运行会误报「保留端口」）；F-2 §4.3 dashboard restart 现状「未运行回 8180」与 cli.py:610-616/678 事实不符（现状为「not running」+ 硬编码 8180）；F-3 A14 四同步 grep 无法落地（pyproject 无版本字面量、漏 spec.yaml/features）；F-4 spec.yaml 补 capability 遗漏 json-output（port 字段）+ dashboard（restart --port）；F-5 §4.6 退出码表隐含「路径不存在 0→1」变更（实测 exit 0）未在风险表/CHANGELOG 标注。按治理规范：回 ops 出设计 v1.1，修复后走 rereview。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| F-1 | 🟡 | 校验顺序链未定义：幂等检查(server.py:137) 应先于 -p 保留/占用校验(195)，否则「-p 等于运行端口」误判占用、「-p 保留端口」误报保留 | 设计 §4.1 | ⏳ 待 ops 修复 |
| F-2 | 🟡 | dashboard restart 现状描述失实：未运行 → not running（cli.py:610-616）非「回 8180」；已运行 → 硬编码 8180（cli.py:678）非 entry['port'] | 设计 §4.3 | ⏳ 待 ops 修复 |
| F-3 | 🟡 | A14 四同步 grep 无法落地：pyproject version 为 dynamic 无字面量；漏 spec.yaml version 字段 + features.md | 设计 §8 A14 | ⏳ 待 ops 修复 |
| F-4 | 🟡 | spec.yaml 补 capability 遗漏 json-output（start --json 增 port 字段）+ dashboard（restart --port） | 设计 §5/§9 item 4 | ⏳ 待 ops 修复 |
| F-5 | 🟡 | 退出码表内部不一致：exit 1 列「路径不存在」但触发仅 D1/D2；隐含路径不存在 0→1 变更（实测 exit 0）未标注 | 设计 §4.6 | ⏳ 待 ops 修复 |
| F-6 | 🟢 | -p 占用检查继承 O1 假占用缺陷（刚释放端口假拒绝）未标注 | 设计 §11 | 记录 |
| F-7 | 🟢 | http-server-ops --usage-file 命名范式已满足且属跨仓，§9 item 8 冗余 | 设计 §9 item 8 | 记录 |
| F-8 | 🟢 | O3 枚举不完整：hs-cli-design-v1.0:506 亦含「不占用终端」 | 设计 §10 O3 | 记录 |
| F-9 | 🟢 | services.py 存储字段未完全明确（use_port bool + port int 两字段） | 设计 §4.4/§5 | 记录 |
| F-10 | 🟢 | D8「等价于 1781-1785 推广」不精确：`hs -p 8089` 时 command='8089'（端口值泄漏），需重组 args | 设计 §4.1 D8 | 记录 |
| F-11 | 🟢 | §5 影响矩阵 web 行号漂移（_web_add=1321、_web_update=1574） | 设计 §5 | 记录 |
| F-12 | 🟢 | 版本链既有 1.3.1 漂移（CHANGELOG/spec 停 1.3.0） | __init__.py:28 / CHANGELOG / spec.yaml:2 | 记录 |
| F-13 | 🟢 | D4 区间 1024-65535 与 MAX_PORT=10000（find_available_port 上限）差异未注明 | 设计 §4.1 / utils.py:29 | 记录 |
| F-14 | 🟢 | `-p 8180` 且 dashboard 实际占用时报「保留端口」非「已被占用」（可选优化） | 设计 §4.1 | 记录 |

### Positives

- 根因定位 P1–P4 全部源码 + 实测双证（exit=0 / allow_reuse_address=1 / Unknown command:8089），非凭描述
- D1–D13 无互相矛盾，fail-closed / 幂等优先 / CLI>config 不回写 / 保留端口硬拦四原则边界清晰
- §7 十三条测试覆盖全部分支 + 未给 -p 的 +1 漂移回归保护 + conftest 隔离，A1–A13 均为「命令 + 可观测 + 非恒真」
- 未识别参数告警 22 站点实测计数与设计一致，白名单覆盖 html 通配/kill·status 位置参数/search 关键词/web --cmd，stderr-only 零污染论证充分
- 范围控制 N1–N6 与 D1–D13 自洽，O1 另批理由充分（广波及非必要前置），遗留率 1/6=0.17 成立

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| F-1 | 校验顺序链未定义 | 🟡 | P1 | ⏳ 待 ops 修复 |
| F-2 | dashboard restart 现状描述失实 | 🟡 | P1 | ⏳ 待 ops 修复 |
| F-3 | A14 四同步 grep 无法落地 | 🟡 | P1 | ⏳ 待 ops 修复 |
| F-4 | spec capability 遗漏 json-output/dashboard | 🟡 | P1 | ⏳ 待 ops 修复 |
| F-5 | 退出码表不一致 + 路径不存在 0→1 未标注 | 🟡 | P1 | ⏳ 待 ops 修复 |
| F-6~F-14 | 记录项（9 条） | 🟢 | P2 | ⏳ 记录，同批勘误 |

---

## 2026-09-22 — Design doc rereview: HTTP-SERVER-CL003 端口参数 + 未识别参数告警 + 周边端口面 v1.1

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（设计评审 rereview — 只审设计文档与现状事实，不审实现）
- **Scope**: 2 个未 push commit（7d2b88c docs@design v1.1 修订 + 076d30b docs@design v1.1 勘误），基底 origin/main 1ff81e6（HEAD 076d30b，ahead 3）；被审对象 documents/http-server-port-flag-design-v1.1-20260922.md（389 行）
- **Commit(s)**: 7d2b88c, 076d30b（另有 7f3376d v1.0 承上轮）
- **Verdict**: ✅ PASS
- **Score**: 96 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-cl003-design-rereview-v1.1-20260922.md

### Summary

设计 v1.1 对上轮 5 必改（F-1~F-5）+ 9 记录（F-6~F-14）+ 3 待确认（1/2/3）全部闭合/处置/定案，逐条源码 + 实测核对。F-1 执行顺序链（路径→幂等→-p 校验→启动）成文且与 server.py:126-134/137-185/187-192/195-206 一致，两个反例说明到位；F-2 §4.3 勘误与 cli.py:610-616/678 逐字相符；F-3 A14 改 hs version + grep __init__.py/CHANGELOG + grep ^version: spec.yaml（删 pyproject dynamic）；F-4 五 capability 与 spec.yaml:34/143/268/600/712 逐行吻合；F-5 三态表自洽 + D14 改 1 + §11 风险 + A15 + CHANGELOG Changed 三处落地。§4.7 start() 返回契约失败点 121/134/204/229/238/247/256 逐字吻合、成功出口 json 314-315/daemon-foreground 之后/url 281 成文、两调用方 cli.py:220 与 dashboard.py:401（后者不看返回值）grep 核实仅此两处。数据复核：src/ 零变更（diff origin/main..HEAD 仅 v1.1 文档 +389 行）、parse_known_args 22、pytest 490 collected、kill 59999 实测 exit 0、版本链 1.3.1/1.3.0/1.3.0 漂移成立。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| R-1 | 🟡 | D14「服务未找到（hs kill 未注册端口）改 1」有声明+断言(A15)+CHANGELOG(§9)+风险(§11)+Step3 作用域，但无函数级实现落点：§4.7 仅 start() 返回契约、§5 无 kill 退出码行、§7 无 kill 退出码单测（现状 server.py kill() 返回 None、cli.py _cmd_kill:383-408 无 sys.exit） | 设计 §4.7/§5/§7 | 建议折入 Step 3 fix@cli |
| R-2 | 🟢 | §4.7 成功出口枚举遗漏 server.py:185（非 url/json 幂等命中 return None → 应 return True）；合同「含幂等命中」+ §7 测试 7 已隐含 | 设计 §4.7 | 记录 |
| R-3 | 🟢 | §5 _web_list/_web_show 标注 1420-1527，实 def 起于 1411（1420 为 except 行），9 行偏差系沿用 F-11 建议值 | 设计 §5 | 记录 |

### Positives

- F-1~F-5 全部闭合，每项以源码行号逐字核对（幂等 137-185 先于 find_available_port 194-206；dashboard 678 硬编码 8180；spec 五 capability 逐行命中），非凭描述
- 记录项 F-6~F-14 九条全部处置到位（§4.1 重组规则四形态实测表、§4.4 use_port/port 双字段、§6/§10 documents/ 统一豁免）
- §4.7 返回契约失败点七处逐字吻合（url_only 六处已 return False 无需改的判定也正确），两调用方 grep 复核「仅两处」属实
- 待确认 1/2/3 → D14/D15/D16 一一对应且各有落点（§4.6/A15/§9/§11 + §4.1 差异段/测试 4 + §4.1 双态/测试 3/A16）
- 数据复核以 diff --stat + grep -c + pytest collect + 实测 kill/status 双证，非仅引用上轮

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| F-1~F-14 | HTTP-SERVER-CL003 设计 v1.0 发现（5 必改 + 9 记录） | 🟡/🟢 | P1/P2 | ✅ Closed（v1.1 全闭合/处置） |
| R-1 | kill 退出码函数级实现落点缺失 | 🟡 | P2 | ⏳ 建议折入 Step 3 |
| R-2 | §4.7 line 185 成功出口枚举遗漏 | 🟢 | — | 记录 |
| R-3 | §5 _web_list 起始行 9 行偏差 | 🟢 | — | 记录 |

---

## 2026-09-22 — Implementation audit: HTTP-SERVER-CL003 端口参数面实现（-p/--port + 退出码三态 + dashboard/web 端口面）

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（实现审计 — 审代码与设计一致性 / 回归风险 / 文档同步真实性）
- **Scope**: 4 个未 push commit（3919da7 feat@cli / 484e0ec tests@cli / 8f041cd docs@sync / 231452e verify@ops），基底 origin/main d410738；被审对象 src/{cli.py,server.py,services.py} + tests/test_port_flag.py(45 新增) + test_web.py(1 更新) + 四同步（README×2/skills/features/CHANGELOG/__init__/spec.yaml）+ ops 核查产物
- **Commit(s)**: 3919da7, 484e0ec, 8f041cd, 231452e
- **Verdict**: ✅ PASS
- **Score**: 95 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-cl003-audit-v1.0-20260922.md

### Summary

实现忠实落地设计 v1.1 全部 D 项，逐项以「实证命令 + 实测输出」独立复算（不采信 ops 31/31）。`-p` 面：绑定 8099 且不回写 config；顺序链两反例（幂等先于 -p 校验）实测成立；fail-closed 三态（占用 rc=1 + 占用者 PID/路径、保留端口双态 rc=1、区间/非法值 rc=2、-p 20000 直绑越 MAX_PORT）；退出码三态（路径不存在 1 / kill 未注册 1 / status 未注册 0）；解析报错 exit 2（P4 消灭假成功）；未识别参数仅 stderr 零污染；--json 信封 data.port 新建/幂等两路径；dashboard restart --port 透传 + 无 port 沿用 entry；web --port/--no-port 字段 + cmd_effective + 注入顺序 domain 先 port 后。四同步以实测为准（hs version v1.4.0 + __init__/CHANGELOG/spec 三处 1.4.0 + README 非 v1.2.x）；A12「不占用终端」src/skills/README 0 命中（documents/ 豁免）。全量 535 passed 零回归；utils.py 零变更（is_port_in_use 裸 bind / find_available_port MAX_PORT=10000 / eprint 写 stdout 均保持）；真实数据目录审计前后 registry 11/services 11 无污染（仅 8085 last_access_at 自然漂移）。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| AUD-1 | 🟡 | 顶层 `hs -i <在 CWD 存在的文件> -p <port> <dir>`：main()「路径快捷方式」分支(os.path.exists(cmd))先于 D8 重组分支触发 ⇒ -i(在 unknown)被丢、<file>当 path、<dir>被当「未识别参数」忽略 ⇒ 服务落 CWD 而非 <dir>（端口仍正确）。设计 D8 显式收窄「非存在路径/globs」，实现与设计一致，非偏差；但设计 §4.1 表/单测(no-such)/ops A8-2(仅断言端口)均未捕获此边界 | cli.py:1898-1907 | 记录，建议随 O1 另批 |
| AUD-2 | 🟢 | `hs web add/update --port 99` / `--port 9001 --no-port` 拒绝时 rc=0（软拒绝），与 `hs start -p 99` rc=2 口径不一致（设计 §4.4 未对 web 子命令强制退出码，属既有 web 校验风格） | cli.py:1429-1442,1702-1715 | 记录 |
| AUD-3 | 🟢 | 「stale registry entry」清理只 registry.remove 不 kill 进程：启动后 bind 前(~50ms) is_port_in_use=False ⇒ 幂等检查误判 stale ⇒ 留孤儿（无登记，hs kill 不可达）。既有行为，O1 同源；审计自测复现并已清理 PID 37510 | server.py:175-234（既有） | 记录，建议并入 O1 |

### Positives

- 逐项「实证命令 + 实测输出」独立复算 19 项，未采信 ops 31/31（含 fail-closed 三态各用独立目录、顺序链两反例、--json 新建/幂等两路径、dashboard restart 三种形态、web --port 系列拒绝路径）
- 执行顺序链源码核对：幂等分支(server.py:173-234)严格先于 -p 校验块(:236-269)，F-1 两反例实测成立
- 返回契约逐分支核对：server.start 失败路径显式 False、成功出口显式 True、kill 未注册/空参 False，cli 侧 exit 1 落点正确
- 22 处 parse_known_args 全部经 _parse_known_args helper，唯一 except SystemExit 在 helper 内转 exit 2（P4 无残留）
- 四同步以实测为准（非 commit subject）：hs version + 三处 grep + README 版本示例 + spec yaml.safe_load
- 真实数据目录审计前后两次快照对照，cl003 残留 0；审计临时服务/条目/孤儿进程全部清理

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| F-1~F-14 | HTTP-SERVER-CL003 设计 v1.0 发现 | 🟡/🟢 | P1/P2 | ✅ Closed（v1.1 全闭合） |
| R-1~R-3 | 设计 rereview 记录（kill 落点/行号） | 🟡/🟢 | P2 | ✅ Closed（折入 Step 3） |
| AUD-1 | 顶层 -i <CWD 存在文件> + -p 边界缺陷 | 🟡 | P2 | ⏳ 建议随 O1 另批 |
| AUD-2 | web 软拒绝 rc=0 口径 | 🟢 | — | 记录 |
| AUD-3 | stale-entry 清理留孤儿（O1 同源） | 🟢 | — | 记录（并入 O1） |

---

## 2026-09-22 — Design doc review: HTTP-SERVER-CL004 端口探测假占用根因 + CL003 遗留三项（-i 泄漏/web 退出码/stale 孤儿）

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（设计评审 — 只审设计文档与现状事实，不审实现）
- **Scope**: 1 个未 push commit（6edb021 docs@design），基底 origin/main c58f222（ahead 1）；被审对象 documents/http-server-port-residual-design-v1.0-20260922.md（242 行）
- **Commit(s)**: 6edb021
- **Verdict**: ⏳ CONDITIONAL PASS
- **Score**: 90 / 100 (Rating A-)
- **Report**: documents/review/http-server-cli-cl004-design-review-v1.0-20260922.md

### Summary

设计 v1.0 四项根因（P1–P4）全部源码 + 独立实测双证成立：P1 `is_port_in_use` 裸 bind 无 SO_REUSEADDR（socket 级反例实测：TIME_WAIT 裸 bind FAIL(48)/SO_REUSEADDR OK，真 LISTEN 两者均 FAIL(48) ⇒ 不放宽真占用）；P2 main() ➋路径快捷方式先于➌重组（`hs -i index.html(CWD存在) -p <port> <dir>` 实测「未识别参数(忽略 <dir>) + -i 被当 path」vs `-i no-such` 形态 -i 保留/path=tmp）；P3 web 校验失败 rc=0（`--port 99`/`--port 9001 --no-port` 均 exit 0 实测）；P4 stale 只删登记不 kill（同目录并发两次 `hs <dir> -d --url` 5 次尝试 4 次复现孤儿，含「registry 0 条可见 + 1 listener」完全隐形形态）。八项决策（D1–D8）核心正确：D1 反例实测、D2 五形态推演无破坏、D3 落点可落地（`_cmd_web` 直调无 try/except，`sys.exit(2)` 穿透）、D4/D5 三态边界大体覆盖、D7 并入未发布 1.4.0 合理、D8 四同步方向正确。基线：535 passed 零回归、`hs version` v1.4.0、工作树 clean。

2 处必改 + 7 处记录，均非方向性冲突、非阻断。按治理规范：不提交、不 push，回 ops 出设计 v1.1 修订后 rereview。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| F-1 | 🟡 | D6「两者均不污染 stdout（其余沿用现状）」自相矛盾：json/默认 模式 stale 文案经 eprint 写 stdout 污染 JSON 信封（实测 JSONDecodeError） | 设计 D6/§4.4 | ⏳ 待 ops 修复 |
| F-2 | 🟡 | §8 A4 孤儿检测口径不足：「该路径 1 条 + ps 同名」无法捕获「registry 0 条可见 + 1 listener」隐形孤儿（list --json 按 _alive 过滤死 pid） | 设计 §8 A4 | ⏳ 待 ops 修复 |
| R-1 | 🟢 | CHANGELOG 1.4.0 `### Notes`（L26）「假占用 本批不修（O1）」须随 `### Fixed` 同步删除/更新 | 设计 §6/§9 | 记录 |
| R-2 | 🟢 | spec.yaml 仅补 P1/P4 场景，P3（web 退出码）/P2（分支序）未入 spec | 设计 §6/§9 | 记录 |
| R-3 | 🟢 | §7 T2「留 TIME_WAIT」未指定关闭方向（需服务端主动 close） | 设计 §7 T2 | 记录 |
| R-4 | 🟢 | §4.4 伪码 killpg(pid) 未定 SIGTERM→SIGKILL 升级 + getpgid 取值（prose/伪码不一致） | 设计 §4.4 | 记录 |
| R-5 | 🟢 | D4 宽限后 kill 前应再判 is_port_in_use（避免 kill 刚就绪慢绑定 runner） | 设计 §4.4 | 记录 |
| R-6 | 🟢 | pid 复用边界（signal-0 无法区分复用 pid，killpg 理论误杀） | 设计 §4.4 | 记录 |
| R-7 | 🟢 | ② 宽限轮询仅端口级判定，未验证监听者 pid | 设计 §4.4 | 记录 |

### Positives

- P1 用 socket 级反例实测（TIME_WAIT vs 真 LISTEN × 裸 bind vs SO_REUSEADDR）证明 D1 只放宽残留态、不放宽真占用，判据非恒真
- P4 用并发两次 `hs <dir> -d --url` 5 次尝试独立复现孤儿，并发现设计 §1 未覆盖的「完全隐形孤儿」形态（registry 0 条可见 + 1 listener）
- D2 五形态逐形态推演（含 `-p`/`-i`/路径/`-o`/无路径），确认无破坏性快捷方式回归；D3 落点核到 `_cmd_web` 分派无 try/except 包裹
- D1 调用点全量 grep（server/registry/registry_managed/dashboard/cli/mcp 共 12 处），与设计「调用方不变」清单无遗漏
- 基线 535 passed 零回归 + 版本三处 1.4.0 + 真实数据目录审计前后无 cl004 残留

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| F-1 | D6 文案通道自相矛盾（json 污染） | 🟡 | P1 | ⏳ 待 ops 修复 |
| F-2 | A4 孤儿检测口径不足 | 🟡 | P1 | ⏳ 待 ops 修复 |
| R-1~R-7 | 记录项（7 条） | 🟢 | P2 | ⏳ 记录，同批勘误 |

---

## 2026-09-22 — Design doc rereview: HTTP-SERVER-CL004 设计 v1.1（F-1/F-2 复审 + R-1~R-7 处置）

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（设计复审 — 只审设计文档与现状事实，不审实现）
- **Scope**: 1 个未 push commit（3b0d37a docs@design 设计 v1.1），被审对象 documents/http-server-port-residual-design-v1.1-20260922.md（304 行）
- **Commit(s)**: 3b0d37a
- **Verdict**: ⏳ CONDITIONAL PASS
- **Score**: 93 / 100 (Rating A)
- **Report**: documents/review/http-server-cli-cl004-design-rereview-v1.0-20260922.md

### Summary

设计 v1.1 闭合 F-1：D6 重写为「stale/宽限/kill 三态一律 `print(..., file=sys.stderr)`」并删净「其余沿用现状」（grep 确认仅 §0/D6 行提及旧文）；污染点坐实（`server.py:229-234` json/默认走 `eprint`→stdout，`utils.py:33-38` eprint 实写 stdout）；§4.4 L171 伪码唯一文案出口为 stderr；幂等路径（①）标注「不变（既有三态输出）」且实测 `server.py:174-227` 无新 stdout 污染，§4.5 通道表三态一致。R-1~R-7 逐条源码核对到位：R-4 对齐 `server.py:645-651`（getpgid→SIGTERM→0.5s→SIGKILL）、R-6 依赖的 `get_process_info`（`utils.py:205`）+ runner 命令行双 token（`server.py:292`）实存、R-7 监听者核验落点明确、R-1（CHANGELOG L26「本批不修/另批处理」）/R-2（spec cli-interface）/R-3（T2 服务端主动 close）均落实。

F-2 方向已修正（lsof LISTEN 端口级判据 + 删除 `ps` 判据 + 修前反证非恒真），但 A4 判据残留 1 处必改（3 子点）：① 显式写 registry.json 绝对路径 `~/.http-server.cli/registry.json` 并禁 `hs list --json`（`cli.py:321` 按 `_alive` 过滤死 pid 条目，且 §8 A10 仍用过滤视图不自洽）；② 明确「逐端口」枚举范围（可见孤儿 listener 落另一端口，须全量 LISTEN 端口 × registry pid 交叉比对）；③ 补 pid 同一性断言（lsof LISTEN pid == registry 条目 pid），消除「1 dead-pid entry + 1 orphan listener」计数相等(1==1)假阴性。另 2 处 🟢 记录（R-8 A11 dead-entry 手法未写明 / R-9 R-7 与 A4 的 lsof LISTEN 过滤口径差异）。

按治理规范：不提交、不 push，回 ops 出设计 v1.2 补强 A4 后再次 rereview。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| F-2 残留 | 🟡 | A4 判据仍需补强三处：显式 registry.json 路径+禁 hs list --json / 明确逐端口枚举范围 / 补 pid 同一性断言（消除 1==1 计数假阴性） | 设计 §8 A4 | ⏳ 待 ops v1.2 |
| R-8 | 🟢 | A11「构造 dead entry」手法未写明，不可复跑（应给 registry.json 写死 pid entry 的 recipe） | 设计 §8 A11 / §7 T11 | 记录 |
| R-9 | 🟢 | R-7 用 get_pid_by_lsof（无 -sTCP:LISTEN）与 A4 的 -sTCP:LISTEN 口径不一致 | 设计 §4.4 ② | 记录 |

### Positives

- F-1 闭环证据链完整：eprint 通道坐实（`utils.py:33-38`）+ 污染点代码定位（`server.py:229-234`）+ D6 重写 + §4.4 L171 stderr + 幂等路径未误改，逐态可执行
- R-1~R-7 七项全部源码核对到位（R-4 对齐 `server.py:645-651`、R-6 依赖函数/命令行双 token 实存），非仅文案声明
- F-2 方向正确：lsof LISTEN 端口级判据 + 删除 `ps` 同名判据 + 修前反证非恒真，捕获「可见/隐形」两种形态的机制成立

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| F-2 残留 | A4 判据补强三处（path/逐端口/pid 同一性） | 🟡 | P1 | ⏳ 待 ops v1.2 |
| R-8 | A11 dead-entry 手法 recipe | 🟢 | P2 | 记录 |
| R-9 | R-7 lsof LISTEN 过滤口径 | 🟢 | P2 | 记录 |

---

## 2026-09-22 — Design doc rereview: HTTP-SERVER-CL004 设计 v1.2（F-2(a)(b)(c) 闭合 + R-8/R-9 落实）

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（设计复审 — 只审设计文档与现状事实，不审实现）
- **Scope**: 1 个未 push commit（6017695 docs@design 设计 v1.2），被审对象 documents/http-server-port-residual-design-v1.2-20260922.md（325 行）
- **Commit(s)**: 6017695
- **Verdict**: ⏳ CONDITIONAL PASS
- **Score**: 95 / 100 (Rating A)
- **Report**: documents/review/http-server-cli-cl004-design-rereview-v1.0-20260922-round2.md

### Summary

设计 v1.2 逐点闭合上轮 F-2 残留三子点，R-8/R-9 落实到位。F-2(a)：§8 头注写明 `~/.http-server.cli/registry.json`（utils.py:23 REGISTRY_PATH，实测 DATA_DIR 一致）+ 显式禁 `hs list --json` + A10 改原始 `json.load` 读文件 + A5 连带从「hs list --json path 一致」改「读 registry.json」——全文 grep `hs list|list --json|_alive` 12 处逐条核验，仅修订表/规则/A10 提及，§7/A9/§12 零残留。F-2(b)：`lsof -nP -iTCP -sTCP:LISTEN -F p` 实测 23 pid（跨全端口，含孤儿另一端口）；归属规则双 token（runner.py + abs_path，server.py:291-292）唯一定位，`hs list` 不 spawn runner、判定用 per-pid `ps -o args=` 非 grep 管道 ⇒ 无恒真/恒假风险。F-2(c)：`len(R)==1` 前置（显式）+ `O == R_pids == {该条目 pid}` 同一性，`∅==∅` 恒真排除；可见形态（O={A,B}⊋{B}=R_pids）/隐形形态（R_pids=∅，O={A}≠∅）反证推演均成立。R-8：A11 recipe 四步可复跑，`started_at` 非必需（registry.py:26-40 加载仅 read_json+servers 兜底，stale 路径不读 started_at）。R-9：`get_pid_by_lsof(port, listen_only=True)` 追加 `-sTCP:LISTEN` 实测 rc=0 有效，N9 成立（调用点 server.py:60/520 均不传第二参，默认 False 不变），T13 覆盖差异。

新增 1 🟡 必改 F-3：A4③/A10/A11 的 `<tmpdir>` 未声明「解析后 abs_path」口径。macOS `/var`→`/private/var`、`/tmp`→`/private/tmp` 符号链接使 `mkdtemp()` 返回 `/var/folders/...`（实测 equal: False vs realpath），而 server.py:128 `abs_path=resolve_path(path)`（Path.resolve()）+ registry.add(path=abs_path)+runner 命令行均用解析路径 ⇒ `path == <tmpdir>`（原始）恒 False（A4 假失败）、A11 注入 `"path":"<tmpdir>"` 永不命中（find(path=abs_path) 不匹配，stale 不触发）。单行口径声明即可收口。

按治理规范：不提交、不 push，回 ops 出设计 v1.3 补强 F-3 后收口。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| F-3 | 🟡 | A4③/A10/A11 的 `<tmpdir>` 未声明解析后 abs_path 口径（macOS /var→/private/var 符号链接 ⇒ path==<tmpdir> 恒 False、A11 注入永不命中） | 设计 §8 A4③/A10/A11 + 头注归属规则 | ⏳ 待 ops v1.3 |
| 待确认 1 | 🟢 | 归属规则 `abs_path in command` 子串匹配对前缀/嵌套路径（/tmp/foo vs /tmp/foobar）过度包含（harness 假失败；生产 ⊙2 理论误杀边界） | 设计 §8 归属规则 / §4.4 ⊙2 | 待确认 |
| 待确认 2 | 🟢 | A4 修前反证依赖 <100ms 双启动复现竞态（5 次 4 次），1/5 未复现时反证假失败 | 设计 §8 A4 修前反证 | 待确认 |
| 待确认 3 | 🟢 | A4 采集 O/L 前需等 runner 达 LISTEN（--url 在 registry.add 后立即返回） | 设计 §8 A4 | 待确认 |

### Positives

- F-2(a)(b)(c) 逐点以源码 + 实测双证闭合（registry 路径 utils.py:23 / lsof 全量 23 pid / 归属规则 server.py:291-292 / len(R)==1 前置 + 反证推演），非仅文案声明
- R-8/R-9 均实证：registry 加载逻辑坐实 started_at 非必需；`-sTCP:LISTEN` 写法实测 rc=0；N9 调用点 grep 复核（server.py:60/520）
- A5 连带清除 `hs list --json` 过滤视图（超出 F-2(a) 点名范围，bonus 一致性）
- §0.2 已闭合标注与上轮结论逐项一致；v1.2 增量无方向性冲突/自相矛盾/恒真断言，D11 与 N9 自洽

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| F-2(a)(b)(c) | A4 判据补强三处（path/逐端口/pid 同一性） | 🟡 | P1 | ✅ Closed（v1.2 逐点闭合） |
| R-8 | A11 dead-entry 手法 recipe | 🟢 | P2 | ✅ Closed（v1.2 落实） |
| R-9 | R-7 lsof LISTEN 过滤口径 | 🟢 | P2 | ✅ Closed（v1.2 D11 + T13 落实） |
| F-3 | A4/A10/A11 路径解析口径声明 | 🟡 | P1 | ✅ Closed（v1.3 §8 头注口径声明 + A4/A5/A11 三模板一致） |
| 待确认 2 | 反证样本口径（幂等命中剔除） | 🟢 | P2 | ✅ Closed（v1.3 可判，处置得当） |
| 待确认 3 | 采集前等 runner 达 LISTEN | 🟢 | P2 | ✅ Closed（v1.3 ≤2.0s 就绪等待，超时诚实弃样） |
| 待确认 1 | 子串匹配过度包含 | 🟢 | P2 | ⏳ 部分闭合 → v1.4（§8 token 匹配闭合 harness；§4.4 ⊙2 仍 `in`，转 F-4） |

---

## 2026-09-22 — Design doc rereview: HTTP-SERVER-CL004 设计 v1.3（F-3 闭合 + 3 待确认处置）

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（设计复审 — 只审设计文档与现状事实，不审实现）
- **Scope**: 1 个未 push commit（c7e2afb docs@design 设计 v1.3），被审对象 documents/http-server-port-residual-design-v1.3-20260922.md（335 行）
- **Commit(s)**: c7e2afb
- **Verdict**: ⏳ CONDITIONAL PASS
- **Score**: 96 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-cl004-design-rereview-v1.0-20260922-round3.md

### Summary

设计 v1.3 闭合上轮唯一必改 F-3：§8 头注（L267）新增「路径口径（F-3，强制）」声明 `<tmpdir>` 一律指 `resolve_path(<tmpdir>)`（`Path.resolve()`）+ 命令模板；A4（L276）/A5（L277）/A11（L283）三处命令模板逐处改用 `$TD`（解析后）。口径与源码实际写入值逐字核对一致：`utils.py:285-287 resolve_path = str(Path(...).resolve())`、`server.py:128 abs_path = resolve_path(path)`、`server.py:337-341 registry.add(path=abs_path)`、`server.py:291-292` runner 命令行含 `abs_path`、`server.py:174 find(path=abs_path)`。「恒 False」论断经实证坐实：`mkdtemp()=/var/folders/…` vs `resolve()=/private/var/folders/…` **equal: False**（`/var→private/var`、`/tmp→private/tmp` 均 symlink）；`resolve_path` 幂等性实测（`resolve(resolved)==resolved` True）保证 A11 注入 `$TD`（解析后）可命中 `find(path=abs_path)`。全文 grep `<tmpdir>/<TD>` 8 处：仅 A3（L275）为裸 `<tmpdir>` 但属输入路径（断言仅核端口，`hs` 内部自 resolve）、L27/L28 为 §0.2 历史留档，无残留裸 `<tmpdir>` 用于路径匹配；§10/§12 零命中。

3 项 🟢 待确认处置：待确认 2（反证样本口径「同端口同 pid ⇒ 非反证样本」可判、不足如实记录）✅ 得当；待确认 3（就绪等待 ≤2.0s = 20–40× 实测 ~50–100ms 启动、超时诚实弃样不掩盖）✅ 得当；待确认 1 **部分闭合**——§8 归属规则（L269）已改 token 精确匹配（`basename(token)==runner.py` + token `== abs_path`，显式禁 `in`，`basename` 覆盖绝对路径 token），但 **§4.4 ⊙2（L179）生产 kill 门仍用 `'runner.py' in command and abs_path in command` 子串匹配**，与 §8「禁用 `in`」自相矛盾、生产理论误杀边界（`/tmp/foo` vs `/tmp/foobar`）未闭环。

按治理规范：不提交、不 push，回 ops 出设计 v1.4 对齐 §4.4 ⊙2 后收口。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| F-4 | 🟡 | §4.4 ⊙2 生产 kill 门仍用 `in` 子串匹配，与 §8「禁用 in 子串判断」自相矛盾；`/tmp/foo` vs `/tmp/foobar` 嵌套路径误杀另一目录 runner | 设计 §4.4 L179 | ⏳ 待 ops v1.4 |
| R-10 | 🟢 | 待确认 2「同端口同 pid」判定略强（修前签名为漂移新端口，`--url` 比对同端口即可判别，无需显式读 pid） | 设计 §8 A4 | 记录 |
| R-11 | 🟢 | 待确认 3 就绪等待「单数 LISTEN」时序（修前双 runner 下先 LISTEN 即采集，反证 `O != R_pids` 仍成立，仅展示不干净） | 设计 §8 A4 | 记录 |
| R-12 | 🟢 | §0.3 F-3 行落点未列 A5（正文 A5 用「TD 同上 F-3 口径」正确，落点表列举遗漏） | 设计 §0.3 | 记录 |

### Positives

- F-3 以源码逐字核对 + 独立实测双证闭合（`resolve_path` 实现 / registry.add path=abs_path / runner 命令行 abs_path / `find` 解析路径匹配四层一致 + `equal:False` 实测 + resolve 幂等性坐实 A11 可命中），非凭设计自述
- 全文 `<tmpdir>` 残留用 grep 全量 8 处逐条核验（区分「输入路径」「历史留档」「路径匹配」三类），无遗漏
- 待确认 1 harness 侧闭合到位：token 精确匹配 + `basename` 覆盖 runner.py 绝对路径 token，`/tmp/foo` vs `/tmp/foobar` 过度包含消除
- 待确认 2/3 处置均有明确可判口径（同端口同 pid / ≤2.0s×10 + 超时诚实弃样），不引入假通过

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| F-3 | A4/A10/A11 路径解析口径声明 | 🟡 | P1 | ✅ Closed（v1.3） |
| F-4 | §4.4 ⊙2 `in` 残留（待确认 1 生产侧未闭环） | 🟡 | P1 | ✅ Closed（v1.4） |
| R-10 | 同端口同 pid 判定略强 | 🟢 | P2 | ✅ Closed（v1.4 落实） |
| R-11 | 单数 LISTEN 时序展示 | 🟢 | P2 | ✅ Closed（v1.4 落实） |
| R-12 | §0.3 F-3 落点未列 A5 | 🟢 | P2 | ✅ Closed（v1.4 落实） |

---

## 2026-09-22 — Design doc rereview: HTTP-SERVER-CL004 设计 v1.4（F-4 闭合 + R-10/R-11/R-12 落实，收口）

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（设计复审 — 只审设计文档与现状事实，不审实现）
- **Scope**: 1 个未 push commit（f3db2d0 docs@design 设计 v1.4），被审对象 documents/http-server-port-residual-design-v1.4-20260922.md（347 行）
- **Commit(s)**: f3db2d0
- **Verdict**: ✅ PASS
- **Score**: 100 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-cl004-design-rereview-v1.0-20260922-round4.md

### Summary

设计 v1.4 收口：闭合上轮唯一必改 F-4——§4.4 ⊙2 生产 kill 门由 `in` 子串匹配改为与 §8 同口径 token 精确匹配（`parts = (info or {}).get('command','').split()`；`is_ours = bool(info) and any(os.path.basename(t)=='runner.py' for t in parts) and abs_path in parts`，`abs_path in parts` 为列表成员判定 = 完全相等非子串）。四子点经源码 + 语义独立复核全过：`get_process_info` 返回 `{'command'}`（utils.py:205-222）、`abs_path=resolve_path(path)`（server.py:128）、runner 命令行含 `runner_path`+`abs_path` 双 token（server.py:287/291-292）三处坐实；`os.path.basename` 唯一命中 runner_path、`abs_path in parts` 唯一命中 abs_path，无恒真/恒假；全文 grep 零残留 `in` 子串式归属判断（3 命中全为历史引用/迭代器语法/列表成员判定）。嵌套路径 `/tmp/foo` vs `/tmp/foobar` 误杀边界消除。R-10（反证样本判据简化为「以端口判定幂等命中」）、R-11（就绪等待改「pid 集合稳定：连续两次 O 一致」）、R-12（§0.3 F-3 落点补 A5）三项 🟢 全部落实。v1.4 增量无新必改，仅 1 处 🟢 措辞级记录 R-13（§0.4 落点表简写 `command.split()` vs §4.4 正文 `(info or {}).get('command','').split()`，正文为权威且更精确）。**push origin main**。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| — | — | 无新增必改（1×🟢 措辞级记录 R-13） | — | — |

### Positives

- F-4 以源码逐字核对 + 语义独立复核双证闭合（get_process_info / abs_path=resolve_path / runner 双 token 三处坐实 + `in` 列表成员语义 + 零残留 grep），非凭设计自述
- R-10/R-11/R-12 逐项核实落点（§8 A4 反证口径 / 就绪等待 / §0.3 F-3 行），与正文一致
- v1.4 增量无方向性冲突/恒真断言/规格缺失；§4.4 ⊙2 伪码 null-safe（`(info or {})` 守卫），优于 round-3 建议的 `cmd.split()`

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| F-4 | §4.4 ⊙2 `in` 残留（待确认 1 生产侧未闭环） | 🟡 | P1 | ✅ Closed（v1.4 token 精确匹配） |
| R-10 | 反证样本判据以端口判定幂等命中 | 🟢 | P2 | ✅ Closed（v1.4 落实） |
| R-11 | 就绪等待 pid 集合稳定 | 🟢 | P2 | ✅ Closed（v1.4 落实） |
| R-12 | §0.3 F-3 落点补 A5 | 🟢 | P2 | ✅ Closed（v1.4 落实） |
| R-13 | §0.4 落点表简写 vs §4.4 正文（措辞级） | 🟢 | — | 记录（非阻断） |

---

## 2026-09-22 — Implementation audit: HTTP-SERVER-CL004 实现审计 v1.0（D1′ 偏差复核 + 四同步实测）

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2（实现审计 — 代码↔设计一致性 / 偏差正当性 / 回归 / 文档同步真实性）
- **Scope**: 6 笔未 push commit（36b1e91 fix@cli 探测 / 2651511 fix@cli 归位+退出码 / 4ecf537 fix@cli stale 三态 / 6f8392f tests@cli / 275ae93 docs@sync + 设计 §13 / 127db13 test@verify ops harness）
- **Commit(s)**: 36b1e91, 2651511, 4ecf537, 6f8392f, 275ae93, 127db13
- **Verdict**: ✅ PASS
- **Score**: 99 / 100 (Rating: A)
- **Report**: documents/review/http-server-cli-cl004-audit-v1.0-20260922.md

### Summary

CL004 合并单一批（探测根因 O1 + CL003 遗留 AUD-1/2/3）实现审计：18 项逐条「实证命令 + 实测输出 + 判定」。关键偏差 D1′（探测主路径由「纯 socket + SO_REUSEADDR」改为「darwin 以 lsof LISTEN 为准 + socket 回退」）经独立最小实验复核成立——实测 3×3 探测矩阵与设计 §13.1 逐格一致（macOS SO_REUSEADDR 允许「不同本地地址同端口」共存，纯 socket 会漏判 127.0.0.1/LAN 绑定真监听；lsof LISTEN 全地址命中）⇒ 偏差正当且比原设计更强。stale 三态 + ≤1.0s 宽限 + 归属校验（token 精确匹配 runner.py+abs_path，禁 in 子串）+ 文案通道三态 stderr 以 pid 同一性实测成立（A4 双击 registry 单条、listener_pids==registry_pids），R-6/R-7 不 kill 他人。全量 557 passed 零回归、CL003 harness 31/31、ops A1–A11 独立复跑 13/13、真实数据目录审计前后 registry/services sha256 逐字节一致（残留 0、无主 runner listener 0）。非阻断 1×🟢 AUD-1（features.md 模块数 18→16）+ 2×🟢 记录（§13.3 D3 行号漂移 3 行 / 回退 socket 在 darwin 的文档化降级漏判）。**push origin main（仅 github，无 gitee 镜像）**。

### Findings

| # | Severity | Title | File:Line | Status |
|:--|:--------|:------|:----------|:------|
| AUD-1 | 🟢 | features.md 测试模块数「18」实测为 16（基线 15 + 本批 1）；测试用例数 557 正确 | features.md:133 | 记录（建议下次 docs@sync 改 16） |
| OBS-1 | 🟢 | 设计 §13.3 D3 对照行号 cli.py:1705-1718 实测 1702-1715（漂移 3 行，非实质） | 设计 §13.3 | 记录 |
| OBS-2 | 🟢 | lsof 不可用回退 socket+SO_REUSEADDR 在 darwin 仍跨地址漏判（§13.1 已声明降级） | utils.py:165-174 | 记录 |

### Positives

- D1′ 偏差独立复核：自建最小 socket 实验（端口 55148/55149/55150）复现 §13.1 矩阵 3 场景逐格一致 + lsof 全命中，非采信设计自述
- R-6/R-7 防误杀：_is_our_runner 与 harness listen_pids 同口径 token 精确匹配，test_t12a/t12b 断言不 kill 他人；A4 双击 pid 同一性判据（非计数）
- 数据目录无污染：审计前后 registry.json/services.json sha256 逐字节一致，比「条数不变」更严的判据
- 未越界：eprint()/hs set port/hs list --port/8180-8181 硬拦/CL003 -p 校验链零变更（N5 落实）

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------|:--------|:------|
| AUD-1 | features.md 模块数 18→16（文档同步失真） | 🟢 | P2 | 记录（非阻断） |


