# Changelog

## 1.0.7 (2026-06-24)

### Added
- `hs dashboard` — Web dashboard for GUI management of HTTP services
  - REST API: list, status, kill, kill-all, restart
  - Dark-themed inline HTML/CSS/JS, 5s auto-refresh
  - `--json` one-shot query mode, `-d` daemon mode
  - Duplicate run detection: shows status if already running
  - Dashboard API now includes managed infrastructure services (MCP SSE)
  - Managed registry integration (registry-managed.json)
- `hs mcp` — MCP Server for AI Agent integration
  - JSON-RPC 2.0 over SSE (default) or stdio transport
  - Default mode: SSE + daemon (background)
  - 6 tools: hs_list, hs_status, hs_start, hs_kill, hs_kill_all, hs_config
  - SSE mode registers to managed registry, stdio mode does not
  - Duplicate run detection for SSE mode
  - Package CLI via subprocess (方案A), zero external dependencies
- `registry-managed.json` — separate registry for infrastructure services
  - Dashboard and MCP SSE services tracked here
  - `hs list` merges both registries, managed services marked with 🔧
  - `hs kill-all` does NOT affect managed services
- Web dashboard fix: frontend JS now correctly reads `data.data.servers` (bug fix for empty table)
- Test suite for registry_managed, updated dashboard/mcp tests (48 new tests)

### Changed
- `hs mcp` default transport changed from stdio to SSE
- `hs mcp` now supports `-d`/`--daemon` flag
- `hs list` now shows managed infrastructure services with 🔧 marker
- `__version__` bumped to 1.0.7

## 1.0.6 (2026-06-23)

### Added
- `--json` flag for all commands (start/list/status/kill/kill-all/config/set/version)
  - Unified response envelope: `{ success, command, data, error }`
  - Designed for API/MCP consumption
- `-i`/`--index` flag for `hs start` to specify custom index HTML page
  - Persisted to registry, shown in `list --json` and `status --json`
- Cross-platform port detection (socket-based, no longer macOS-only)
- `CHANGELOG.md` for project version history

### Changed
- All JSON output now uses unified `json_output()` envelope function
- `hs config --json`, `hs list --json`, `hs status --json` improved format
- `hs start --json` returns `stats`, `duration`, `index_page` fields
- `hs status --json` now returns `stats` and `duration` fields

### Fixed
- Duplicate `index` variable assignment in `server.py:start()`
- Missing `include LICENSE` in MANIFEST.in
- Hardcoded TestPyPI token in release scripts

### Security
- Removed hardcoded API token from release scripts; now loaded via `.env`
