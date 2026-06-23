# http-server-cli

> Forget ports. Just preview.
>
> Based on `python3 -m http.server`, zero external dependencies. Just `hs . -o` to preview your project.

- [x] **Zero External Dependencies** — Only requires macOS (lsof/open) and Python 3.7+ (`pip install http-server-cli`)
- [x] **Auto Port Allocation + Preview** — Default 8080, auto-increment on conflict (`hs . -o`)
- [x] **Smart Homepage** — Auto-redirect to most recently modified HTML file when no index.html
- [x] **Project Tracking** — Persistent project path ↔ port mapping (`hs list`)
- [x] **Process Resource Monitoring** — Real-time CPU, memory usage and runtime (`hs list`)
- [x] **Multiple Launch Modes** — Daemon background or foreground (`-d` daemon / `-f` foreground)
- [x] **JSON Output** — All commands support `--json` for API/MCP consumption
- [x] **Custom Index Page** — Specify default HTML file with `-i`/`--index`

## Why `hs`

When developing multiple frontend projects, you constantly switch between "Which port did A use?" and "Who's occupying 8080?".

`hs` closes the loop: **Start → Track → List → Kill** — auto-find free ports, remember which project uses which port, view and close anytime.

## Comparison

| Scenario | Before | With `hs` |
|:---------|:-----|:--------|
| Start server | `python3 -m http.server 8080` + manually open browser | `hs . -o` — auto-find free port, open browser |
| View servers | `lsof -i :8080`, then `ps` to see path | `hs list` |
| Switch projects | Kill old one, start new (or conflict) | `hs ../project-b` |
| Kill server | `lsof` to find PID → `kill` | `hs kill 8080` |

## Installation

```bash
pip install http-server-cli

# Upgrade to latest version
pip install --upgrade http-server-cli
```

Verify:
```
hs version     # → http-server-cli v1.0.5
hs . -o        # Start in current directory + open browser
```

## Usage

### Daily Workflow

```bash
# 1. Preview your project
cd ~/project-alpha
hs . -o                     # Auto-find free port, open browser

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
| `hs . [-o] [-d] [-f]` | **Shortcut**, equivalent to `hs start .` |
| `hs start [path] [-o] [-d] [-f] [-i <file>]` | Start server (path defaults to `.`; `-o` open browser; `-d` daemon; `-f` foreground; `-i` custom index) |
| `hs list` | List all running servers |
| `hs list --json` | JSON format list |
| `hs status [port\|path]` | Query single server status |
| `hs status --json [port\|path]` | JSON format status |
| `hs kill <port\|path>` | Kill specified server |
| `hs kill-all` | Kill all servers |
| `hs config` | Show configuration |
| `hs config --json` | JSON format configuration |
| `hs set port <num>` | Set default port (default 8080) |
| `hs set domain <str>` | Set bind domain (default localhost) |

### Tips

- **`hs . -o`** = `hs start . -o`, faster to type
- **`hs . -d`**: daemon mode, runs in background, check with `hs list`
- **`hs . -f`**: foreground mode, Ctrl+C to stop
- **`hs`** without args = `hs start .` (start in current directory)
- **`hs . -i app.html`**: use `app.html` as the index page

## Data Directory

```
~/.http-server-cli/
├── config.json       # Default port/domain configuration
├── registry.json     # port → {path, pid, domain, daemon, foreground, started_at}
└── logs/{port}.log   # http.server logs
```

## Platform Requirements

Currently only supports **macOS** (requires `lsof` command). Linux/Windows support in development.

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