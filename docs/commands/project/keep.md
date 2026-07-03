# cc project keep

Exempt a project from auto-archiving. Its environments are then never swept to
`merged`/`archived` by the auto-stale sweep, no matter how long they sit unused.

`cc project keep` is a **toggle**: run it once to protect a project, run it again
to lift the exemption.

## Usage

```bash
cc project keep [name]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Project to keep / un-keep. Omit to be prompted with a picker. |

## What It Does

When [`env.auto_stale_days`](../../configuration/settings.md) is set, every
`cc switch` retires active environments that haven't been used in that many days
(see [Auto-stale](../../configuration/settings.md)). `cc project keep` flags a
project so the sweep **skips all of its environments** — useful for a long-running
client or a presales project you check in on infrequently and don't want to
disappear from the switch picker.

The flag toggles:

- First run: `✓ '<name>' is now kept — exempt from auto-archiving.`
- Second run: `'<name>' is no longer exempt — auto-archiving applies again.`

Pinned environments are already exempt from auto-staling on their own; `cc project
keep` exempts the **whole project** at once.

## Examples

```bash
cc project keep acme        # protect 'acme' — its envs never auto-archive
cc project keep acme        # run again to remove the exemption
cc project keep             # pick a project from a list
```

## Related

- [`cc project create`](create.md) — create a project
- [`cc project delete`](delete.md) — delete a project
- [`cc project env`](env.md) — manage a project's environments (archive/activate)
- [Auto-stale settings](../../configuration/settings.md) — `env.auto_stale_days` / `env.auto_stale_status`
- [Command Reference](../README.md)
