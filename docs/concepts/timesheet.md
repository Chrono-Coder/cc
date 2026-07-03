# Timesheet

## How It Works

cc tracks your time on two layers:

- **Automatic baseline.** Every time you run `cc switch`, cc logs the event with
  a timestamp. Strung together, these switches form a gap-based picture of how
  long you spent on each project — no timers to start or stop.
- **Explicit manual entries.** When you want a precise span — a meeting, a code
  review, focused work that didn't involve switching — you open one yourself with
  `cc time start` and close it with `cc time end`, optionally with a note.

The two layers coexist. A day's view is *resolved* from both: manual entries (and
any auto entry you've edited) are **authoritative** and kept whole; the auto
baseline fills in the gaps around them. Where they overlap, the authoritative
span wins, so the same minutes are never counted twice — **human-touched wins**.

## Viewing Today's Log

```bash
cc time
```

<!-- 📸 IMAGE: Screenshot of cc time output showing a real day's log with flags -->

```
  Today

  09:12 → 10:45   [1h 33m]   acme_memberships2
  10:45 → 12:00   [1h 15m]   globex_v18         ✎ manual   — QA review
  12:00 → 14:30   [2h 30m]   acme_approvals     ⚑
  14:30 → now     [1h 12m]   initech_trips      ✎ edited

  Total: 6h 30m
```

Badges:

- **✎ manual** — an explicit `cc time start/end` entry.
- **✎ edited** — an auto (switch-logged) entry you edited; now authoritative.
- **⚑ flag** — a session longer than your configured threshold (default 60
  minutes). A nudge to review before submitting a timesheet, not an error.
- **— note** — the entry's note.

## Manual Entries

Open an explicit span on an environment (defaults to the active one), then close
it when you're done:

```bash
cc time start                       # open on the active env, prompt for a note
cc time start acme -m "QA review"   # open on 'acme' with a note
cc time end -m "shipped the fix"    # close the open manual entry
```

An open manual entry runs until you end it — it shows as `→ now` in the log.
Manual entries can overlap auto spans freely; they're authoritative in their
window, so totals stay honest.

## Editing & Deleting

Mis-tracked time happens — a switch you forgot, a span that's a few minutes off.
Fix any entry interactively:

```bash
cc time edit     # pick an entry → change its start, end, or note
cc time delete   # pick an entry → delete it
cc time review   # pick an entry → choose: edit start / end / note / delete
```

Editing an **automatic** entry promotes it to authoritative — your correction
becomes the source of truth for that window and overrides the auto baseline.

## Punching Out

When you stop coding for the day (or take a long break), punch out so cc doesn't
count idle time toward the current span:

```bash
cc time --stop
```

This creates a stop entry; the last project's session ends at the punch-out time.

## Tracking Mode

The `timesheet.mode` setting decides whether switches are tracked at all:

| Mode | Behavior |
|------|----------|
| `auto` (default) | Every `cc switch` logs an automatic span; manual entries layer on top. |
| `manual` | Switches log nothing — only `cc time start` / `cc time end` entries count. |

Pick `manual` if you'd rather drive the timesheet entirely by hand and not have
navigation create entries.

## Specific Date & Export

```bash
cc time -d 2026-03-25       # a specific day
cc time --week              # per-day totals for the last 7 days
cc time --csv               # CSV (with -d, --week, or default)
cc time --json              # today's resolved segments as JSON
```

## Clearing Flags

Once you've reviewed flagged sessions:

```bash
cc time --clear-flags
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `timesheet.mode` | `auto` | `auto` logs a span on every switch; `manual` counts only `cc time start/end` |
| `timesheet_flag_threshold` | `60` | Minutes before a session is flagged |
| `timesheet_flag_prompt` | `true` | Prompt to review when a flagged session is detected on switch |
| `timesheet_eod` | _(blank)_ | EOD time (HH:MM) to auto-punch-out if you forget; blank disables |
| `timesheet_retention_days` | `90` | Prune switch-log entries older than this on switch; `0` keeps history forever |

Configure via `cc config` (interactive picker) or the web `/settings` page.

## Day Bucketing & Totals

Timestamps are stored in UTC but bucketed by your **local** calendar day, so a
switch at 11pm lands on the right day. A day's **Total** sums the *resolved*
worked spans: authoritative entries (manual / edited) are kept whole and the auto
baseline fills the gaps around them, so overlapping entries never double-count.
Time after a punch-out (`cc time --stop`), before the next switch, is not counted.

## The Flag Prompt

If `timesheet_flag_prompt` is enabled, switching away from a project after a long
session shows a quick inline summary and asks if you want to continue:

```
  ⏱  2h 30m on acme / acme_approvals  [flagged]

  Today so far:
    09:12 → 10:45  [1h 33m]  acme / acme_memberships2
    10:45 → now    [2h 30m]  acme / acme_approvals  ⚑

Continue switching? [Y/n]
```
