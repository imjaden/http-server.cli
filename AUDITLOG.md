# http-server-cli — Audit Log

## 2026-07-22 — Design document review: perf-hot-path-optimization-design v1.1

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L1 (design document — no executable code changes)
- **Scope**: `documents/perf-hot-path-optimization-design-v1.1-20260722.md` (commit `69101fd`)
- **Verdict**: PASS
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

## 2026-07-22 — Code review: perf@handler implementation (P0/P1/P2)

- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2 (code with file I/O — handler.py, registry.py)
- **Scope**: `commit 20509f4` — 4 files, +322/-13 (handler.py, registry.py, test_handler.py, test_registry.py)
- **Verdict**: PASS
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
