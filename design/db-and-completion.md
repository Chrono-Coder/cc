# cc — DB cache, lifecycle & native completion

Status: **locked**, building P0. Working doc (not committed, not user-facing).

## North star

cc becomes the **fast cache + lifecycle hub** for the developer's Postgres
databases, and that cache feeds **native shell completion**. Reads never block
on `psql`; writes are consistent across PG + cache + env links; destroying real
data is always an explicit, separately-confirmed act.

## Safety invariants (non-negotiable)

1. **Removing a cc record never destroys Postgres data by surprise.**
   `cc env remove` / `cc project remove` touch cc bookkeeping + links only.
2. `cc env remove` (plain) **interactively offers** to also drop the linked PG
   database: quiet confirm for the record, then a **distinct, louder** data-loss
   warning for the DB (default **No**), and it **skips any DB still linked to a
   surviving env**. Dropping is via `pg.drop_db` + cache reconcile.
3. Dropping a PG database is otherwise exclusively `cc db drop` / `cc dropdb`.
4. No raw `dropdb`/`psql` subprocess in the CLI — all PG mutations go through the
   daemon/pg service (CQRS-lite).

## P0-prereq — a proper PG connector (self-discovering)

The cache is useless until reads work on the user's primary machine (macOS), and
they fail there today: `psycopg2.connect(dbname=...)` relies on the bundled
libpq's compiled-in socket dir, which doesn't match where a local PG listens
(Homebrew `/tmp` or `/opt/homebrew/var/...`, Postgres.app `~/Library/...`, Linux
`/var/run/postgresql`). The user doesn't know their own setup → the connector
must **probe**, not require config.

- `cc.services.pg_connect.connect(db)` tries candidates in order — **configured
  DSN** (`pg.connection` setting) → libpq default → common socket dirs (mac
  Homebrew / Postgres.app) → localhost TCP (current user, `postgres`) — first
  success wins and is cached for the daemon's life.
- On total failure: one `CCError` listing every attempt + how to set
  `pg.connection`.
- `pg.check()` / `cc db check`: probe all candidates and print a table so a user
  who doesn't know how PG runs can see exactly how cc connects.
- Per-DB probes (`get_last_login[s]`) reuse the resolved method and stay
  best-effort (a bad DB → "no data", never errors the whole list).

## P0 — PG metadata cache (foundation)

- `Database` gains cached PG metadata (new `Property`s → `sync_schema`
  auto-adds columns, no migration): `in_pg` (bool), `size_bytes` (int),
  `last_login` (datetime str), `is_odoo` (bool), `last_synced_at` (datetime str).
- `database.reconcile()` (daemon write): pull `pg.list_databases` +
  `get_db_stats` + `get_last_logins`; upsert rows with metadata + `in_pg=true`;
  set `in_pg=false` (keep row) for tracked names absent from PG.
- Kept fresh: reconcile on **daemon startup** + a **background loop**
  (`cc.daemon.db_sync`, mirrors `sync/auto.py`), plus targeted updates on
  mutations (P1). Interval a constant now, a setting later.
- **All readers become pure SQLite**: web `/databases` drops its per-request
  live merge; `cc db -l` and completion read the cache.

## P1 — DB lifecycle

- Route **drop + rename** through `pg.drop_db` / `pg.rename_db` via the daemon
  (they exist; the CLI just isn't using them). Each updates cache + env links.
- `cc db drop <name>` (canonical) + `cc dropdb` (thin top-level alias).
- `cc env remove` cascade per invariant #2; record removal becomes **unlink-only**
  (the reconciler owns Database rows now, so the old "delete orphan record"
  cascade is removed — it also fixes the bug where the orphan check ignored the
  M2M pool).
- `copy`/`restore`/`initdb` keep mechanics, gain cache updates. `--extend` left
  as-is.

## P2 — native completion (entity-based)

- Declarative `complete=` on each `Argument`: an **ORM entity class**
  (`Project`/`Environment`/`Version`/`Workspace`/`Database`), a **literal tuple**
  (curated verb sets), or a small **`CompleteKind`** enum (`MODULE`, `PATH`,
  `ENV_TARGET`). Fixed `choices=` read off the arg. `help` topic → command names.
- **Neutral spec** (introspect parser) → **per-shell emitters** (zsh/bash/fish).
  Entity completion = `SELECT name FROM "<entity._name>"`; `Database` reads the
  P0 cache (`WHERE in_pg`). Generation bakes the query; TAB asks the live source.
- Delete `utils/completers.py` + the `_KIND_BY_COMPLETER` name-matching dict.
- `cc completion <shell>` stays a Command; `cc shell install` writes the script.

## Sequencing

P0 → P1 → P2. P2's db part depends on P0; the rest of P2 is independent.

## Phase A — SHIPPED (commits `30aee87`, `f935cf1`)

Every DB op now works on dockerized PG:
- `pg.run_sql(sql, db)` — direct psycopg2 / `docker exec psql`, backend cached
  (`pg.backend()` exposes which); `pg.load_dump(db, path)` — `psql -f` /
  `docker exec -i psql` (streams the dump over stdin, no docker cp).
- `database.copy`/`restore`/`extend`/`init_from_dump` via run_sql/load_dump;
  `cc copy`/`restore`/`db --extend`/`initdb` rewired off raw subprocess.
- The `cc db` picker (`get_all_db_names`, `_get_cc_copied_names`) reads the cache.
- **initdb filestore:** copied for native Odoo, skipped for dockerized (the
  filestore lives in the container/volume; the DB restores either way). "fuck
  filestore" — founder, 2026-06-14.

## Open / deferred

- Two-tier sync (cheap sizes frequent, expensive last_login rarer) — optimization.
- Sync interval as a `cc config` setting.
- Live-PG completion fallback (decided against: cache is source for completion).
