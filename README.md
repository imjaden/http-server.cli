<p align="center">
  <a href="README.zh.md">🇨🇳</a> · <a href="README.md">🇬🇧</a>
</p>

<h1 align="center">
  <svg viewBox="0 0 16 16" width="28" height="28" style="vertical-align:middle;margin-right:6px;"><circle cx="8" cy="8" r="7.5" fill="#e0e0e0"/><text x="8" y="11.5" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="900" font-size="9" fill="#333">hs</text></svg>
  http-server
</h1>

<p align="center">
  <a href="https://github.com/imjaden/http-server.cli"><img src="https://github.com/favicon.ico" width="16" height="16" alt="GitHub"> GitHub</a>
  <span> · </span>
  <a href="https://pypi.org/project/http-server-cli"><img src="https://pypi.org/static/images/favicon.35549fe8.ico" width="16" height="16" alt="PyPI"> PyPI</a>
</p>

> Forget ports. Just preview.
>
> Based on `python3 -m http.server`, zero external dependencies. Just `hs -o` to preview your project.
>
> hs is an independent tool — unrelated to the npm package "http-server".

- [x] **Zero External Dependencies** — Python 3.7+, macOS/Linux/Windows (`pip install http-server-cli`)
- [x] **Auto Port + Smart Index** — Default 8080, auto-increment on conflict; auto-open most-recent HTML when no index.html; specify with `-i` (`hs -o`)
- [x] **Project Management** — Track port↔path mapping, monitor CPU/memory, JSON output (`hs list`)
- [x] **Multiple Launch Modes** — Daemon or foreground (`-d`/`-f`)
- [x] **Web Dashboard** — `hs dashboard -o` GUI (CN/EN toggle, 60s countdown, Kill All, error handler)
- [x] **AI Agent Integration** — `hs mcp` MCP Server (SSE/stdio, 11 tools + 3 resources), `hs prompt` usage docs, `hs mcp --config` one-line connect

## Why `hs`

Multiple frontend projects → constant context switching: "Which port is A on?" "Who's occupying 8080?".

`hs` closes the loop: **Start → Track → List → Kill**.

- Start server: `hs -o` — auto-find free port, open browser (instead of `python3 -m http.server 8080` + manual open)
- View servers: `hs list` (instead of `lsof -i :8080` + `ps`)
- Switch projects: `hs ../project-b` (no need to kill first)
- Kill server: `hs kill 8080` (instead of `lsof` → `kill <pid>`)

## AI Interchange

`hs` speaks three channels with AI agents — **docs, data, and one-line connect**.

### 1. Docs — `hs prompt`

```bash
hs prompt                # list all skills (name + description)
hs prompt hs-cli         # full usage guide for one skill
hs prompt hs-mcp --brief # condensed summary
hs prompt --json         # machine-readable envelope
```

Ships 5 skills: `hs-cli` / `hs-bookmark` / `hs-mcp` / `hs-dashboard` / `ai-interchange`.

### 2. Data & Actions — MCP Server

```bash
hs mcp                    # background SSE server → http://127.0.0.1:8181/sse
hs mcp --transport stdio  # foreground stdio mode (for Claude Code / Cursor / Hermes)
hs mcp stop|status|restart
```

11 tools (6 management: `hs_list` / `status` / `start` / `kill` / `kill_all` / `config`; 5 data: `hs_bookmark_list` / `add` / `remove`, `hs_history`, `hs_search`) + 3 read-only resources (`hs://registry` / `hs://bookmarks` / `hs://config`). Zero external deps — pure stdlib.

### 3. One-line connect — `hs mcp --config`

```bash
hs mcp --config
```

Prints an `mcpServers` snippet ready for Claude Code / Cursor / Hermes:

```yaml
mcpServers:
  hs:
    command: hs
    args: ["mcp", "--transport", "stdio"]
    transport: stdio
```

Paste it into the AI tool's MCP config, restart, and the agent can list servers, read bookmarks/history, search running services, and manage them.

> AI agents should start with `hs prompt hs-cli` — zero-dependency usage docs, no guessing flags.

## Installation

```bash
pip install http-server-cli
# or: pip install --upgrade http-server-cli
```

Verify:
```
hs version     # → http-server v1.2.x
hs -o        # Start in current directory + open browser
```

## Usage

### Daily Workflow

```bash
# 1. Preview your project
cd ~/project-alpha
hs -o                     # Auto port + open browser

# 2. Check running servers
hs list
# ✅  http://localhost:8080   →  ~/project-alpha
# ✅  http://localhost:8081   →  ~/project-beta  (daemon)

# 3. Kill unwanted servers
hs kill 8080                # By port
hs kill ~/project-alpha     # By path
hs kill-all                 # Kill all
```

### Start

| Command | Description |
|:--------|:------------|
| `hs . [-o] [-d] [-f]` | Current directory, auto-find free port |
| `hs /path [-o] [-d] [-f]` | Specify directory |
| `hs . -i app.html [-o]` | Custom index file |
| `hs . -i './snapshots/*.html' [-o]` | Glob → most recently modified file |
| `hs /path/to/file.html [-o]` | HTML file path → auto-extract directory + set index |
| `hs /path/snapshots/*.html [-o]` | Path glob → most recent file |
| `hs start [path] [-o] [-d] [-f] [-i <file>]` | Full form of `hs .` |

### View

| Command | Description |
|:--------|:------------|
| `hs list` | List running servers (alive only) |
| `hs list --port` | Ports only |
| `hs list --path` | Paths only |
| `hs list --short` | `port:path` format |
| `hs list --json` | JSON output |
| `hs search <keyword> [--json]` | Search by port or path |
| `hs status <port\|path> [--json]` | Single server status (CPU/memory/log) |

### Kill

| Command | Description |
|:--------|:------------|
| `hs kill 8080` | By port |
| `hs kill ~/project` | By path |
| `hs kill /path/to/file.html` | HTML file → auto-resolve to parent dir |
| `hs kill /path/*.html` | Glob → most recent file |
| `hs kill-all` | Kill all user services |
| `hs kill-all --json` | JSON output |

### Bookmark

| Command | Description |
|:--------|:------------|
| `hs bookmark add <name> [path] [-i index] [--force]` | Register a bookmark (path defaults to current directory) |
| `hs bookmark update <name> [path] [-i index]` | Update bookmark path or index page |
| `hs bookmark list` | List all bookmarks |
| `hs bookmark show <name>` | Show bookmark details |
| `hs bookmark remove <name>` | Remove a bookmark |
| `hs <name> [-o]` | Start server from a bookmark |
| `hs kill <name>` | Kill service by bookmark name |

### Dashboard

| Command | Description |
|:--------|:------------|
| `hs dashboard [-p PORT] [-o] [--json]` | Web dashboard (default 8180) |
| `hs dashboard stop\|status\|restart\|help` | Subcommands |

> Managed services (dashboard, MCP SSE) are tracked in `registry-managed.json`; `hs kill-all` does NOT stop them.

### MCP (AI Agent)

| Command | Description |
|:--------|:------------|
| `hs mcp [--transport stdio\|sse] [--port PORT]` | MCP Server for AI Agent |
| `hs mcp stop\|status\|restart\|help` | Subcommands |
| `hs mcp --config` | Print `mcpServers` snippet (see AI Interchange) |
| `hs prompt [<skill>]` | Print skills/ usage docs (list / detail / --brief / --json) |

### History & Config

| Command | Description |
|:--------|:------------|
| `hs history [--json]` | Server start/stop history (excludes temp dirs) |
| `hs config [--json]` | Show configuration |
| `hs set port\|domain <value>` | Change configuration |
| `hs version [--json]` | Show version |
| `hs help` | Show help |

### Tips

- **`hs`** without args = `hs start .` (start in current directory)
- **`hs . -i app.html`**: use `app.html` as the index page

## Data Directory

```
~/.http-server.cli/
├── config.json            # Default port/domain configuration
├── registry.json          # port → {path, pid, domain, started_at, index_page}
├── registry-managed.json  # Infrastructure services (dashboard, MCP SSE)
└── logs/{port}.log        # http.server logs
```

## Local Development

```bash
git clone git@github.com:imjaden/http-server.cli.git
cd http-server.cli
pip install -e .
python3 -m pytest tests/
```

## Is This Reinventing the Wheel?

| Tool | Start Server | Auto Port | Track Project↔Port | List All | Kill by Name | Open Browser |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `python3 -m http.server` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `http-server` (npm) | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `serve` (npm) | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `live-server` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `portless` (npm) | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `kill-port-cli` (npm) | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| `lsof` / `netstat` | ❌ | ❌ | ❌ | Manual | Manual | ❌ |
| **`http-server`** | **✅** | **✅** | **✅** | **✅** | **✅** | **✅** |
