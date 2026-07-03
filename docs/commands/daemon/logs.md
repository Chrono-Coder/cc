# cc daemon logs

Tail the cc daemon and RPC log files from the CLI.

## Usage

```bash
cc daemon logs              # last 50 lines of cc.log (all logs)
cc daemon logs rpc          # last 50 lines of rpc.log (RPC calls only)
cc daemon logs -f           # follow mode (tail -f)
cc daemon logs -f rpc       # follow the RPC log in real time
cc daemon logs -l warning   # filter by log level
cc daemon logs -n 200       # show last 200 lines
```

## Arguments

| Argument | Description |
|----------|-------------|
| `source` | Which log to show: `all` (default) or `rpc` |

## Flags

| Flag | Description |
|------|-------------|
| `-f`, `--follow` | Follow the log in real time (like `tail -f`) |
| `-n`, `--lines` | Number of lines to show (default: 50) |
| `-l`, `--level` | Filter by level: `debug`, `info`, `warning`, `error` |

## Log files

| File | Content |
|------|---------|
| `~/.cc-cli/logs/cc.log` | All daemon output — ORM, SQL, RPC, lifecycle (1MB rotating, 5 backups) |
| `~/.cc-cli/logs/rpc.log` | RPC calls only — method, sanitized params/result, elapsed time (2MB rotating, 3 backups) |

## RPC log format

```
2026-05-03 19:34:25,598  OK  pg.list_databases({}) → list[63]  5.4ms
2026-05-03 19:34:25,861  OK  pg.get_db_stats({}) → list[63]  261.9ms
2026-05-03 19:34:26,211  OK  pg.get_last_logins({db_names: …}) → dict[63 keys]  0.0ms
```

Data is sanitized — lists show `list[N]`, dicts show `dict[N keys]` or key names, long strings are truncated. No full database lists or sensitive values are written to the log.

## Related

- [`cc daemon`](README.md) — daemon lifecycle management
- [`cc daemon status`](README.md) — daemon health (uptime, RPC count, DB size, last error)
- Web companion → `/logs` — same log data with level/source filters and live auto-refresh
- [Command Reference](../README.md)
