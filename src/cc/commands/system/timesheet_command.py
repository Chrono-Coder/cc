import logging
from datetime import date, datetime, time, timedelta, timezone

from cc.base.arm import Environment
from cc.base.command import Command
from cc.utils.console import get_console

log = logging.getLogger("CC")

_ACTIONS = ("start", "end", "edit", "delete", "review")


class TimesheetCommand(Command):
    name = "time"
    description = "View and manage your timesheet (start/end manual entries, edit, review)."

    def arguments(self):
        return [
            self.Argument(
                ["action"],
                type=str,
                nargs="?",
                choices=list(_ACTIONS),
                help="start | end (manual entry) · edit | delete | review (interactive).",
            ),
            self.Argument(
                ["target"],
                type=str,
                nargs="?",
                help="Env name for `start` (defaults to the active env).",
                complete=Environment,
            ),
            self.Argument(["--note", "-m"], type=str, help="Note for start/end."),
            self.Argument(["-d", "--date"], type=str, help="Show a specific date (YYYY-MM-DD)."),
            self.Argument(["--week"], action="store_true", help="Per-day summary for the last 7 days."),
            self.Argument(["--csv"], action="store_true", help="Output as CSV."),
            self.Argument(["--json"], action="store_true", help="Output as JSON."),
            self.Argument(["--clear-flags"], action="store_true", help="Clear all flagged entries."),
            self.Argument(["--stop"], action="store_true", help="Punch out — end the current session."),
        ]

    def execute(self):
        action = self.args.action
        if action == "start":
            return self._start()
        if action == "end":
            return self._end()
        if action in ("edit", "delete", "review"):
            return self._review(default_action=action)
        if self.args.clear_flags:
            return self._clear_flags()
        if self.args.stop:
            return self._stop()
        if self.args.week:
            return self._show_week()

        target_date = date.today()
        if self.args.date:
            try:
                target_date = date.fromisoformat(self.args.date)
            except ValueError:
                log.error(f"Invalid date format '{self.args.date}'. Use YYYY-MM-DD.")
                return False
        return self._show_day(target_date)

    # ── shared helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _local_day_bounds(target_date: date) -> tuple:
        """(start, end) UTC-ISO bounds for the LOCAL calendar day — switched_at is
        UTC, but days must bucket by the user's local midnight."""
        local_start = datetime.combine(target_date, time.min).astimezone()
        local_end = local_start + timedelta(days=1)
        return (
            local_start.astimezone(timezone.utc).isoformat(),
            local_end.astimezone(timezone.utc).isoformat(),
        )

    def _day_segments(self, target_date: date) -> list:
        """Resolved segments for the day, via the shared service resolution
        (same logic the web uses — human-touched wins, no double-count)."""
        from cc.services import timesheet
        start, end = self._local_day_bounds(target_date)
        return timesheet.entries(start, end)

    @staticmethod
    def _day_total(segments) -> float:
        return sum(s["seconds"] for s in segments)

    @staticmethod
    def _hm(seconds) -> str:
        return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60):02d}m"

    @staticmethod
    def _local(iso: str) -> datetime:
        return datetime.fromisoformat(iso).astimezone()

    # ── single day ──────────────────────────────────────────────────────────

    def _show_day(self, target_date: date):
        segments = self._day_segments(target_date)
        total_seconds = self._day_total(segments)

        if self.args.csv:
            return self._emit_csv([(target_date, segments)])
        if self.args.json:
            return self._emit_json(target_date, segments, total_seconds)

        console = get_console()
        date_label = "Today" if target_date == date.today() else target_date.strftime("%a %d %b %Y")
        console.print()
        console.print(f"  [heading]{date_label}[/]")
        console.print(f"  [primary]{'─' * 60}[/]")
        console.print()

        if not segments:
            console.print("  [warning]No time recorded.[/]\n")
            return True

        for s in segments:
            start_dt, end_dt = self._local(s["start"]), self._local(s["end"])
            # a manual entry still open ends at "now" — mark it
            tag = ""
            if s["source"] == "manual":
                tag = "  [info]✎ manual[/]" if not s["edited"] else "  [info]✎[/]"
            elif s["edited"]:
                tag = "  [info]✎ edited[/]"
            flag_marker = "  [error]⚑[/]" if s["flagged"] else ""
            note = f"  [muted]— {s['note']}[/]" if s["note"] else ""
            console.print(
                f"  [muted]{start_dt.strftime('%H:%M')} → {end_dt.strftime('%H:%M')}[/]"
                f"  \\[[bold]{self._hm(s['seconds'])}[/]]"
                f"  [bold]{s['env_name']}[/]{tag}{flag_marker}{note}"
            )

        flagged_count = sum(1 for s in segments if s["flagged"])
        console.print()
        console.print(f"  [primary]{'─' * 60}[/]")
        summary = f"  Total: [bold]{self._hm(total_seconds)}[/]"
        if flagged_count:
            summary += f"  [error]({flagged_count} flagged — clear with cc time --clear-flags)[/]"
        console.print(summary)
        console.print()
        return True

    # ── week ────────────────────────────────────────────────────────────────

    def _show_week(self):
        today = date.today()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        if self.args.csv:
            return self._emit_csv([(d, self._day_segments(d)) for d in days])

        console = get_console()
        console.print()
        console.print("  [heading]Last 7 days[/]")
        console.print(f"  [primary]{'─' * 60}[/]")
        console.print()
        grand = 0.0
        for d in days:
            secs = self._day_total(self._day_segments(d))
            grand += secs
            label = "Today" if d == today else d.strftime("%a %d %b")
            value = f"[bold]{self._hm(secs)}[/]" if secs else "[muted]—[/]"
            console.print(f"  [muted]{label:<12}[/]  {value}")
        console.print()
        console.print(f"  [primary]{'─' * 60}[/]")
        console.print(f"  Total: [bold]{self._hm(grand)}[/]")
        console.print()
        return True

    # ── output formats ──────────────────────────────────────────────────────

    def _emit_json(self, target_date, segments, total_seconds):
        import json
        out = {
            "date": target_date.isoformat(),
            "total_seconds": int(total_seconds),
            "segments": segments,
        }
        print(json.dumps(out, indent=2))
        return True

    def _emit_csv(self, day_segments):
        import csv
        import sys
        writer = csv.writer(sys.stdout)
        writer.writerow(["date", "start", "end", "duration_seconds", "env", "source", "note", "flagged"])
        for target_date, segments in day_segments:
            for s in segments:
                writer.writerow([
                    target_date.isoformat(), s["start"], s["end"], int(s["seconds"]),
                    s["env_name"], s["source"], s["note"], int(s["flagged"]),
                ])
        return True

    # ── manual start / end ───────────────────────────────────────────────────

    def _start(self):
        """Open a manual entry on an env (defaults to the active env)."""
        from cc.daemon.client import call
        console = get_console()

        env = None
        if self.args.target:
            env = self.environment.find_by(name=self.args.target, limit=1)
            if not env:
                log.error(f"Environment '{self.args.target}' not found.")
                return False
        else:
            env = self.active_environment
        if not env:
            console.print("[error]No env given and none active.[/] Use [primary]cc time start <env>[/].")
            return False

        note = self.args.note or self.prompter.prompt_input_single("Note (what are you working on?)", default="") or ""
        now = datetime.now(timezone.utc).isoformat()
        call("timesheet.create_entry", env_id=env.id, started_at=now, note=note)
        console.print(f"[success]✓ Started manual entry on [primary]{env.name}[/].[/] End it with [primary]cc time end[/].")
        return True

    def _end(self):
        """Close the most recent open manual entry."""
        from cc.daemon.client import call
        console = get_console()

        open_manual = self.switch_log.search(
            [("source", "=", "manual"), ("ended_at", "IS", None)], orderby="id DESC", limit=1,
        )
        if not open_manual:
            console.print("[muted]No open manual entry to end.[/]")
            return True

        note = self.args.note
        if note is None:
            existing = open_manual.note or ""
            note = self.prompter.prompt_input_single("Note (what happened?)", default=existing) or existing
        now = datetime.now(timezone.utc).isoformat()
        call("timesheet.update_entry", entry_id=open_manual.id, ended_at=now, note=note)
        env = open_manual.environment_id
        console.print(f"[success]✓ Ended entry on [primary]{env.name if env else '?'}[/].[/]")
        return self._show_day(date.today())

    # ── review (edit / delete) ───────────────────────────────────────────────

    def _review(self, default_action="review"):
        from cc.daemon.client import call
        console = get_console()
        logs = self.switch_log.search([], orderby="id DESC", limit=20)
        if not logs:
            console.print("[muted]No timesheet entries to review.[/]")
            return True

        labels = {}
        for e in logs:
            when = self._local(e.switched_at).strftime("%a %d %b %H:%M")
            who = f"{e.environment_id.project_id.name}/{e.environment_id.name}" if e.environment_id else "— punch-out"
            src = e.source or "auto"
            labels[f"{when}  {who}  [{src}, id {e.id}]"] = e

        choice = self.prompter.prompt_input_multi(list(labels), "Select an entry")
        if not choice:
            return True
        entry = labels[choice]

        if default_action == "delete":
            what = "Delete"
        else:
            what = self.prompter.prompt_input_multi(
                ["Edit start", "Edit end", "Edit note", "Delete"], "Action"
            )

        if what == "Delete":
            if self.prompter.prompt_confirm("Delete this entry?", default=False):
                call("timesheet.delete_entry", entry_id=entry.id)
                console.print("[success]✓ Entry deleted.[/]")
            return True
        if what == "Edit note":
            note = self.prompter.prompt_input_single("Note", default=entry.note or "")
            call("timesheet.update_entry", entry_id=entry.id, note=note or "")
            console.print("[success]✓ Note updated.[/]")
            return True
        # Edit start / Edit end → adjust HH:MM
        is_end = what == "Edit end"
        cur_iso = entry.ended_at if is_end else entry.switched_at
        if is_end and not cur_iso:
            cur = self._local(entry.switched_at)
        else:
            cur = self._local(cur_iso)
        new = self.prompter.prompt_input_single(f"New {'end' if is_end else 'start'} time (HH:MM)", default=cur.strftime("%H:%M"))
        if not new:
            return True
        try:
            hh, mm = new.strip().split(":")[:2]
            updated = cur.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        except (ValueError, IndexError):
            log.error("Invalid time. Use HH:MM.")
            return False
        iso = updated.astimezone(timezone.utc).isoformat()
        kwargs = {"ended_at": iso} if is_end else {"switched_at": iso}
        call("timesheet.update_entry", entry_id=entry.id, **kwargs)
        console.print(f"[success]✓ {'End' if is_end else 'Start'} set to {updated.strftime('%H:%M')}.[/]")
        return True

    # ── stop / flags ─────────────────────────────────────────────────────────

    def _stop(self):
        from cc.daemon.client import call
        from cc.utils.errors import CCError
        console = get_console()
        try:
            ts = call("timesheet.punch_out")
        except CCError as e:
            console.print(f"[muted]{e}[/]")
            return True
        now = self._local(ts)
        console.print(f"[success]✓ Punched out at {now.strftime('%H:%M')}.[/]")
        return self._show_day(date.today())

    def _clear_flags(self):
        from cc.daemon.client import call
        count = call("timesheet.clear_flags")
        console = get_console()
        console.print(
            f"[success]✓ Cleared {count} flagged entries.[/]" if count else "[muted]No flagged entries.[/]"
        )
        return True
