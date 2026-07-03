# cc daemon

Manage the cc daemon — the background process that owns all database writes, exposed as JSON-RPC 2.0 over a Unix socket at `~/.cc-cli/cc.sock`.

## Usage

```bash
cc daemon start              # start in the background (no-op if already running)
cc daemon stop               # stop the running daemon
cc daemon restart            # stop then start (pick up new service code)
cc daemon status             # running state, PID, uptime, RPC count, DB size
cc daemon status -q          # quiet probe: exit 0 if running, 1 if not
cc daemon start --foreground # run in this terminal (debugging)
```

## Verbs

| Verb | Description |
| --- | --- |
| `start` | Start the daemon in the background. No-op if already running. |
| `stop` | Send `SIGTERM` to the running daemon and wait for it to exit. |
| `restart` | `stop` then `start`. Use after updating cc to pick up new service functions. |
| `status` | Show running state, PID, socket health, uptime, RPC count, DB size, and last error. |
| [`logs`](logs.md) | Tail the daemon and RPC log files. |

## Flags

These flags are shared across the lifecycle verbs above (`logs` has its own — see its page).

| Flag | Verbs | Description |
| --- | --- | --- |
| `-q`, `--quiet` | all | Suppress output. For `status`, **exit 0 if the daemon is running, exit 1 if not** — nothing is printed. This is the contract the shell integration uses to decide whether to auto-launch (see below). |
| `-f`, `--foreground` | `start`, `restart` | Run in the foreground, logging to this terminal (`Ctrl+C` to stop). Useful for debugging. |

## Why a daemon?

The CLI, web companion, and VSCode extension can all run at the same time. SQLite only supports one writer at a time — without coordination, concurrent writes corrupt data.

The daemon is the **single writer**. All writes go through it via the Unix socket at `~/.cc-cli/cc.sock`. Reads still go directly to the database (safe — SQLite supports unlimited concurrent readers).

## Auto-start

The daemon starts automatically when any cc command needs to write — you don't normally run `cc daemon start` yourself. The shell integration probes it on each prompt and launches it on demand using the quiet status contract:

```bash
cc daemon status -q || cc daemon start
```

`cc daemon status -q` exits `0` when the daemon is running and `1` when it isn't, so the `start` only fires when nothing is listening. Use the lifecycle verbs explicitly to restart after an update or to check health.

## Files

| Path | Description |
| --- | --- |
| `~/.cc-cli/cc.sock` | Unix socket — active while the daemon is running |
| `~/.cc-cli/cc-daemon.pid` | PID file |
| `~/.cc-cli/logs/cc.log` | Daemon log (rotating) |
| `~/.cc-cli/logs/rpc.log` | RPC log (rotating) |

## Related

- [`cc daemon logs`](logs.md) — tail the daemon and RPC logs
- [`cc web`](../web.md) — companion app; all its writes go through the daemon
- [Command Reference](../README.md)
