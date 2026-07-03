# cc db

Manage the databases linked to the active environment, plus database lifecycle
(create, copy, restore, drop) and the Postgres connection check. The active
database is written as `cc.database` into the editor's `settings.json` (picked up
by `launch.json`'s `-d` arg via `${config:cc.database}`) and linked in cc's
internal records.

## Usage

```bash
cc db <verb> [args]
```

`cc db` is a noun group — run a verb under it (e.g. `cc db use`, `cc db list`).

## Verbs

| Verb | Description |
|------|-------------|
| [`cc db use`](use.md) | Set the active database for the current environment |
| [`cc db list`](list.md) | List databases linked to the current environment |
| [`cc db drop`](drop.md) | Drop a PostgreSQL database (local or dockerized) |
| [`cc db init`](init.md) | Create a database from a zip dump file |
| [`cc db copy`](copy.md) | Quick in-place database copy (`-CC-COPY` suffix) |
| [`cc db restore`](restore.md) | Restore a database from its CC copy |
| [`cc db backup`](backup.md) | Named DB snapshots — create, list, restore, delete |
| [`cc db rename`](rename.md) | Rename a database (PostgreSQL **and** cc's record) |
| [`cc db link`](link.md) | Add a database to the environment's pool |
| [`cc db unlink`](unlink.md) | Remove a database from the environment's pool |
| [`cc db extend`](extend.md) | Push the active DB's demo expiry to 2099, disable the update cron |
| [`cc db check`](check.md) | Diagnose the Postgres connection |

## Connection & metadata cache

cc reads Postgres through a **self-discovering connector**: it probes a configured
DSN (the `pg.connection` setting), then libpq defaults, then common local socket
dirs, then `localhost` TCP — and, for a **dockerized Postgres** whose port isn't
published, it reaches the container via `docker exec` (no password needed). Run:

```bash
cc db check
```

to see exactly which method connects (a ● marks the one cc uses) — handy when you
don't know how your Postgres runs. If nothing connects (e.g. Docker with a
password), set a DSN with `cc config` → `pg.connection`.

Database metadata (name, size, last login, whether it's an Odoo DB, and whether
it still exists in Postgres) is kept in a **local cache** that the daemon refreshes
in the background — so `cc db list`, the companion's `/databases` page, and
tab-completion are instant and never block on `psql`. Tab-completion only offers
databases currently present in Postgres.

## Database pool

Each environment can have a **pool** of databases linked to it. The pool lets you
keep multiple databases associated with one environment (e.g. clean, test,
prod-copy) and switch between them easily.

- [`cc db link`](link.md) `staging_copy` — adds to the pool without changing the active database
- [`cc db unlink`](unlink.md) `old_db` — removes from the pool
- [`cc db use`](use.md) `-p` — shows a picker filtered to only pool databases

The active database (referenced by `launch.json` via `${config:cc.database}`) is
separate from the pool — linking doesn't change what runs. Use
[`cc db use`](use.md) `<name>` to make a pool database active.

## Workspaces

Databases are scoped to environments, not workspaces. However, since environments
belong to projects and projects belong to workspaces, the database pool naturally
inherits workspace/version grouping. When you [`cc switch`](../switch.md) to a
project in a workspace, the environment's active database and pool are immediately
available.

## Related

- [`cc switch`](../switch.md) — switch the active environment (loads its database + pool)
- [`cc project env`](../project/env.md) — manage an environment's databases
- [Command Reference](../README.md)
