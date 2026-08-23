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
OBS-2: scan-commits.py default enum lacks feat@; project convention uses feat@ (governance §5 enum gap, 🟢) → ⏸ 挂账（re-audit 约定本轮不动）

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
