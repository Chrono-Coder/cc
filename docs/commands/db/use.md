# cc db use

Set the active database for the current environment. Writes `cc.database` into the
editor's `settings.json` (picked up by `launch.json`'s `-d` arg via
`${config:cc.database}`) and links the database to the active environment in cc's
records.

## Usage

```bash
cc db use <name>
cc db use                   # pick from a list of matching databases
cc db use -p                # pick from the environment's pool only
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Database to set active (tab-completable). Omit to pick from a list. |

## Flags

| Flag | Description |
|------|-------------|
| `-p`, `--pool` | When prompting, show only databases linked to the current environment's pool |

## What it does

1. Requires an active project — switch to one first with [`cc switch`](../switch.md).
2. With no `name`, shows a picker: by default, PostgreSQL databases matching the active project name; with `-p`, only the current environment's pool. Databases with a live `-CC-COPY` are marked with a ✓.
3. Writes the chosen database to `cc.database` in the version's `settings.json`.
4. Links it as the active database for the current environment.

## Related

- [`cc db`](README.md) — database group overview
- [`cc db list`](list.md) — show the environment's databases
- [`cc db link`](link.md) / [`cc db unlink`](unlink.md) — manage the pool
- [`cc switch`](../switch.md) — switch the active environment
