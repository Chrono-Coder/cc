# Settings Guide

All CC settings are stored in the SQLite database at `~/.cc-cli/cc_cli.db`. The schema lives in [`cc.config.schema`](https://github.com/Chrono-Coder/cc/blob/main/src/cc/config/schema.py).

## How to change a setting

Three entry points, all writing through the same daemon RPC:

- **Single change:** `cc config` — picks the setting from a list, prompts for the new value.
- **First-time walkthrough:** `cc setup` — walks the full sequence (settings + versions + pyenv + shell + theme).
- **Web dashboard:** the `/settings` page in `cc web` — as of 3.8 it renders from the **same** `cc.config.schema` registry the CLI uses (via the `setting.schema` RPC), so CLI and web expose the same keys. The one web-only extra is the Odoo.sh session ID (`sh_session_id`), stored masked. (GitHub auth is no longer a setting — it comes from `gh auth login` / the OS keyring as of 3.6.)

## IDE

Drives both `cc open` (the launcher) and `cc switch` (the [IDE writer plugins](../concepts/ide-writers.md) that update editor config on each switch).

| Value | Behavior |
|-------|----------|
| `auto` (default) | Auto-detect — run every writer whose filesystem check matches |
| `code` | Visual Studio Code (legacy alias; maps to the `vscode` writer) |
| `cursor` | Cursor |
| `none` | No editor integration — terminal-only setup |
| Comma-separated writer names | Explicit selection: `vscode,my-plugin` |

Out of the box cc ships with `vscode` and `cursor` writers. Other editors can be added as plugins — see [IDE Writers](../concepts/ide-writers.md).

## Downloads path

The directory CC scans when looking for dump files to restore with `cc db init`.

Default: `~/Downloads`

## Multi-version mode

Key: `multi_version_mode`.

**Off by default** — cc tracks exactly one active environment (the one you last
switched to). When `true`, cc keeps **one active environment per Odoo version**,
resolved from the version of your current directory, so v17 and v18 stay
independently active in parallel terminals. Enable it if you run multiple versions
side by side. See [Multi-Version Mode](../concepts/multi-version-mode.md) for details.

Default: `false`

## Auto-fetch

When `true`, CC spawns a background `git fetch origin` across all Odoo repos after each switch, if the fetch interval has elapsed. This keeps the local object store current so that branch checkouts at switch time are near-instant.

Default: `false`

## Auto-fetch interval

How many hours between background fetches.

Default: `24`

## Auto-rebase R&D branches on switch

Key: `rnd.auto_rebase`.

In an R&D workspace, `cc switch` checks out **and rebases** the env's branch
across the shared Odoo repos (odoo, enterprise, design-themes, upgrade,
upgrade-util) on every switch. Turn it **off** to switch without cc touching git —
useful when you want to manage checkouts yourself or have work in progress you
don't want rebased. Has no effect outside R&D workspaces.

Default: `true`

## Auto-stale envs after (days)

On switch, automatically mark active environments unused for this many days as merged/archived, so the switch picker stays short. **Pinned envs are never touched.** `0` disables.

Default: `0`

## Auto-stale status

Which status to apply when auto-staling: `archived` (hidden until you reactivate) or `merged` (soft — reappears if used again within the grace window).

Default: `archived`

## Timesheet tracking mode

Key: `timesheet_mode` (referred to in prose as `timesheet.mode`). One of:

- **`auto`** (default) — cc logs a time entry on every `cc switch`. Manual entries
  (`cc time start/end`) layer on top.
- **`manual`** — switches aren't tracked; only `cc time start` / `cc time end`
  entries count toward your totals.

See [Timesheet](../concepts/timesheet.md) for the full model.

Default: `auto`

## Timesheet flag threshold

Number of minutes a session must exceed before it is flagged with ⚑.

Default: `60` (1 hour)

Set to a higher value if you prefer less frequent prompts, or lower if you want tighter timesheet discipline.

## Prompt on flagged switch

When `true`, CC shows a confirmation prompt when switching away from a flagged (long) session.

When `false`, the summary is printed but CC doesn't wait for confirmation.

## EOD auto-stop time

`HH:MM` time-of-day at which CC auto-punches-out if you forget. Blank disables.

Example: `18:30` will close out any open timesheet entry at 6:30 PM the next time you switch.

## Switch-log retention (days)

On switch, CC prunes switch-log (timesheet) entries older than this many days. `0` keeps history forever.

Default: `90`

## Auto-reindex on switch (Intel)

When `true`, `cc switch` background-reindexes the project's git repo if it's a registered [Intel](../commands/intel.md) repo and was last indexed more than an hour ago.

Default: `true`

## Color theme

The cc color palette. One of `default`, `purple`, `chronocoder`, `custom`.

Use [`cc config theme`](../commands/config/theme.md) for the dedicated picker (with live preview), or change it via `cc config` like any other setting.
