<p align="center">
  <a href="README.zh.md">🇨🇳</a> · <a href="README.md">🇬🇧</a>
</p>

<h1 align="center">
  <svg viewBox="0 0 16 16" width="28" height="28" style="vertical-align:middle;margin-right:6px;"><circle cx="8" cy="8" r="7.5" fill="#e0e0e0"/><text x="8" y="11.5" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="900" font-size="9" fill="#333">hs</text></svg>
  http-server-cli
</h1>

> Forget ports. Just preview.
>
> Based on `python3 -m http.server`, zero external dependencies. Just `hs -o` to preview your project.

- [x] **Zero External Dependencies** — Python 3.7+, macOS/Linux/Windows (`pip install http-server-cli`)
- [x] **Auto Port + Smart Index** — Default 8080, auto-increment on conflict; auto-open most-recent HTML when no index.html; specify with `-i` (`hs -o`)
- [x] **Project Management** — Track port↔path mapping, monitor CPU/memory, JSON output (`hs list`)
- [x] **Multiple Launch Modes** — Daemon or foreground (`-d`/`-f`)
- [x] **Web Dashboard** — `hs dashboard -o` GUI (CN/EN toggle, 60s countdown, Kill All, error handler)
- [x] **AI Agent Integration** — `hs mcp` MCP Server (SSE/stdio, 6 tools), managed infrastructure isolation

## Why `hs`

Multiple frontend projects → constant context switching: "Which port is A on?" "Who's occupying 8080?".

`hs` closes the loop: **Start → Track → List → Kill**.

## Comparison

| Scenario | Before | With `hs` |
|:---------|:-----|:--------|
| Start server | `python3 -m http.server 8080` + open browser manually | `hs -o` — auto-find free port, open browser |
| View servers | `lsof -i :8080`, then `ps` | `hs list` |
| Switch projects | Kill old, start new (or conflict) | `hs ../project-b` |
| Kill server | `lsof` → `kill <pid>` | `hs kill 8080` |

## Installation

```bash
pip install http-server-cli
# or: pip install --upgrade http-server-cli
```

Verify:
```
hs version     # → http-server-cli v1.0.x
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

### Dashboard

| Command | Description |
|:--------|:------------|
| `hs dashboard [-p PORT] [-o] [--json]` | Web dashboard (default 8180) |
| `hs dashboard stop\|status\|restart\|help` | Subcommands |

### MCP (AI Agent)

| Command | Description |
|:--------|:------------|
| `hs mcp [--transport stdio\|sse] [--port PORT]` | MCP Server for AI Agent |
| `hs mcp stop\|status\|restart\|help` | Subcommands |

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
~/.http-server-cli/
├── config.json            # Default port/domain configuration
├── registry.json          # port → {path, pid, domain, started_at, index_page}
├── registry-managed.json  # Infrastructure services (dashboard, MCP SSE)
└── logs/{port}.log        # http.server logs
```

## Local Development

```bash
git clone git@github.com:imjaden/http-server-cli.git
cd http-server-cli
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
| **`http-server-cli`** | **✅** | **✅** | **✅** | **✅** | **✅** | **✅** |
