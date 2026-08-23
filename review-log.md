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
| HS-SEC-011 | bookmark.py docstring 旧数据目录 | 🟡 | P2 | Open |
| HS-SEC-012 | history.py docstring 旧数据目录 | 🟡 | P2 | Open |
| HS-SEC-013 | dashboard GitHub URL 旧名 | 🟡 | P2 | Open |
| HS-SEC-014 | MANIFEST.in 悬空 include | 🟡 | P1 | Open |
| HS-SEC-015 | spec.yaml 内容 drift | 🟡 | P1 | Open |
| HS-SEC-016 | handoff 旧名标题 + /Users 路径 | 🟡 | P2 | Open |

OBS-1: CHANGELOG 1.1.0 date 2026-08-19 vs commit date 08-23 (🟢 record-only)
OBS-2: scan-commits.py default enum lacks feat@; project convention uses feat@ (governance §5 enum gap, 🟢)
