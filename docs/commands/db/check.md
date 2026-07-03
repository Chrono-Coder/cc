# cc db check

Diagnose the Postgres connection — show how cc connects to Postgres (or why it
can't).

## Usage

```bash
cc db check
```

## What it does

cc reads Postgres through a **self-discovering connector**: it probes a configured
DSN (the `pg.connection` setting), then libpq defaults, then common local socket
dirs, then `localhost` TCP — and, for a **dockerized Postgres** whose port isn't
published, it reaches the container via `docker exec` (no password needed).

`cc db check` runs every probe and prints a table of each method and its result. A
● marks the first one that connects — the method cc actually uses. This is handy
when you don't know how your Postgres runs.

If nothing connects (e.g. Docker with a password), the command exits non-zero and
points you at setting a DSN with `cc config` → `pg.connection`
(e.g. `host=localhost port=5432 user=postgres password=…`).

## Related

- [`cc db`](README.md) — database group overview
- [`cc config`](../config/README.md) — set `pg.connection`
