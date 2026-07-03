# cc time

View your timesheet and manage time entries. cc tracks an **automatic span on
every `cc switch`**, and you can layer **explicit manual entries** on top — start
and stop them yourself, with notes — then edit or delete anything that's off.

## Usage

```bash
cc time [action] [target] [flags]
```

`action` is one of `start` · `end` · `edit` · `delete` · `review`. With no
action, `cc time` prints today's log.

## Actions

| Action | Description |
|--------|-------------|
| `start [env]` | Open a manual entry on `env` (defaults to the active env). Prompts for a note if `--note` isn't given. |
| `end` | Close the most recent open manual entry. |
| `edit` | Interactively pick an entry and change its start, end, or note. |
| `delete` | Interactively pick an entry and delete it. |
| `review` | Pick an entry, then choose: edit start / edit end / edit note / delete. |

Editing or noting an **automatic** (switch-logged) entry promotes it to
*authoritative* — your edit is treated as the source of truth and overrides the
auto baseline for that window.

## Flags

| Flag | Description |
|------|-------------|
| `--note`, `-m` | Note for `start` / `end` (what you're working on). |
| `-d YYYY-MM-DD` | Show the log for a specific date |
| `--week` | Per-day summary for the last 7 days |
| `--csv` | Output as CSV (with `-d`, `--week`, or default) |
| `--json` | Output as JSON |
| `--stop` | Punch out — ends the current session |
| `--clear-flags` | Remove flags from all flagged entries |

Days bucket by your **local** calendar day. A day's total sums the resolved
worked spans; manual and auto entries can overlap freely, and totals never
double-count (see [Day Bucketing & Totals](#day-bucketing--totals) below).

## Manual entries

```bash
cc time start                       # open a manual entry on the active env
cc time start acme -m "QA review"   # open one on 'acme' with a note
cc time end -m "shipped the fix"    # close the open manual entry
```

A manual entry is an explicit span. Leaving it open means it runs until you
`cc time end` it (shown as `→ now` in the log). Manual entries are
**authoritative** in their window — they win over the auto baseline so the same
minutes aren't counted twice.

## Editing

```bash
cc time edit     # pick an entry → change its start, end, or note
cc time delete   # pick an entry → delete it
cc time review   # pick an entry → choose the action
```

These are interactive: cc lists your recent entries (with source + id), you pick
one, and adjust it. Times are entered as `HH:MM` in your local timezone.

## Examples

```bash
cc time                     # today's log
cc time -d 2026-03-25       # specific date
cc time --week              # last 7 days, per-day totals
cc time --week --csv        # export the week as CSV
cc time --json              # today's segments as JSON
cc time --stop              # punch out
cc time --clear-flags       # clear flags after reviewing
```

## Output

```
  Today

  09:12 → 10:45   [1h 33m]   acme_memberships2
  10:45 → 12:00   [1h 15m]   globex_v18         ✎ manual   — QA review
  12:00 → 14:30   [2h 30m]   acme_approvals     ⚑
  14:30 → now     [1h 12m]   initech_trips      ✎ edited

  Total: 6h 30m
```

Badges next to a segment:

| Badge | Meaning |
|-------|---------|
| `✎ manual` | An explicit `cc time start/end` entry |
| `✎ edited` | An auto entry you edited (now authoritative) |
| `⚑` | A session longer than your flag threshold (default 60 min) |
| `— <note>` | The entry's note |

Use `--clear-flags` once you've reviewed the flagged sessions.

## Tracking mode

The `timesheet.mode` setting controls whether switches are tracked:

- **`auto`** (default) — every `cc switch` logs an automatic span; manual entries
  layer on top.
- **`manual`** — switches log nothing; only `cc time start` / `cc time end`
  entries count toward your totals.

Change it via `cc config` (the *Timesheet → Tracking mode* setting) or the web
`/settings` page.

→ See [Timesheet](../concepts/timesheet.md) for the full model.
