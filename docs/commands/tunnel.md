# cc tunnel

> **Hidden command (as of 3.8).** `cc tunnel` is no longer registered with the CLI —
> it doesn't appear in `cc help` and isn't tab-completed. The implementation is kept on
> disk (unimported) and still works if invoked, but it's effectively retired: it saw no
> real use. To bring it back, re-add its import in
> `src/cc/commands/system/__init__.py`. This page documents the behaviour for anyone who
> re-enables it.

Open an SSH tunnel to a remote Odoo.sh PostgreSQL database for the active environment.

## Usage

```bash
cc tunnel                 # start a tunnel for the active environment
cc tunnel myenv           # start a tunnel for a specific environment
cc tunnel --stop          # stop the active tunnel
cc tunnel --status        # list all active tunnels
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Environment name (tab-completable). Defaults to the active environment. |

## Flags

| Flag | Description |
|------|-------------|
| `--stop` | Stop the active tunnel for the environment |
| `--status` | List all active tunnels with PIDs |

## What It Does

Forwards the remote Odoo.sh PostgreSQL port to local port `5433` over SSH. Once running, you can connect to the SH database from your local machine as if it were local.

On first use per environment, CC prompts for:

- **SSH host** (e.g. `project-31002026.dev.odoo.com`)
- **SSH user** (e.g. `31002026`)
- **SSH key path** (stored in CC settings)

Subsequent runs use the saved values.

## Files

| Path | Purpose |
|------|---------|
| `~/.cc-cli/tunnels/<env>.pid` | PID file for the active tunnel |

## Examples

```bash
cc tunnel
# → Starts tunnel to active env's SH database on localhost:5433

cc tunnel staging
# → Starts tunnel for the 'staging' environment

cc tunnel --status
# → Lists active tunnels and their PIDs

cc tunnel --stop
# → Stops the active env's tunnel
```

## Related

- `cc db` — manage the local database linked to an environment
- `cc sh` — open the Odoo.sh project page in the browser
