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

