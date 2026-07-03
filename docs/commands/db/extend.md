# cc db extend

Push the active database's Odoo demo expiry date to 2099 and disable the update
cron — so an enterprise/demo database stops nagging or locking you out.

## Usage

```bash
cc db extend
```

## What it does

- Requires an active environment with a linked database — run [`cc switch`](../switch.md) first.
- Runs against the active environment's database (direct connection or via `docker exec`): sets the expiry to 2099 and disables the update-notification cron.

There are no arguments — it always targets the active environment's database. To
change which database is active first, use [`cc db use`](use.md).

## Related

- [`cc db`](README.md) — database group overview
- [`cc db use`](use.md) — set the active database
