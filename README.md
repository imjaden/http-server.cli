<p align="center">
  <a href="README.zh.md">🇨🇳</a> · <a href="README.md">🇬🇧</a>
</p>

<h1 align="center">
  <svg viewBox="0 0 16 16" width="28" height="28" style="vertical-align:middle;margin-right:6px;"><circle cx="8" cy="8" r="7.5" fill="#e0e0e0"/><text x="8" y="11.5" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="900" font-size="9" fill="#333">hs</text></svg>
  http-server-cli
</h1>

> Forget ports. Just preview.
>
> Based on `python3 -m http.server`, zero external dependencies. Just `hs . -o` to preview your project.

- [x] **Zero External Dependencies** — Python 3.7+, macOS/Linux/Windows (`pip install http-server-cli`)
- [x] **Auto Port + Smart Index** — Default 8080, auto-increment on conflict; auto-open most-recent HTML when no index.html; specify with `-i` (`hs . -o`)
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
| Start server | `python3 -m http.server 8080` + open browser manually | `hs . -o` — auto-find free port, open browser |
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
hs . -o        # Start in current directory + open browser
```

## Usage

### Daily Workflow

```bash
# 1. Preview your project
cd ~/project-alpha
hs . -o                     # Auto port + open browser

# 2. Check running servers
hs list
# ✅  http://localhost:8080   →  ~/project-alpha
# ✅  http://localhost:8081   →  ~/project-beta  (daemon)

# 3. Kill unwanted servers
hs kill 8080                # By port
hs kill ~/project-alpha     # By path
hs kill-all                 # Kill all
```

### All Commands

| Command | Description |
|:-----|:------|
| `hs . [-o] [-d] [-f] [-i <file>]` | **Shortcut**, equivalent to `hs start .` |
| `hs start [path] [-o] [-d] [-f] [-i <file>]` | Start server (`-o` open browser; `-d` daemon; `-f` foreground; `-i` custom index) |
| `hs list [--port|--path|--short] [--json]` | List running servers (filter: `--port` only ports, `--path` only paths, `--short` port:path) |
| `hs status <port|path> [--json]` | Query single server status |
| `hs kill <port|path> [--json]` | Kill specified server |
| `hs kill-all [--json]` | Kill all servers |
| `hs search <keyword> [--json]` | Search servers by port or path keyword |
| `hs history [--json]` | Show server start/stop history |
| `hs dashboard [-p PORT] [-o] [--json]` | Web dashboard (default port 8180) |
| `hs dashboard stop|status|restart|help` | Dashboard management subcommands |
| `hs mcp [--transport stdio|sse] [--port PORT]` | MCP Server for AI Agent integration |
| `hs mcp stop|status|restart|help` | MCP management subcommands |
| `hs config [--json]` | Show configuration |
| `hs set port|domain <value>` | Set configuration |
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
