import os
import re
import time

from rich.table import Table
from rich.text import Text

from cc.base.command import Command
from cc.utils.console import get_console
from cc.utils.constants import Constants

# "2026-05-24 18:43:33,654 - CC - DEBUG - logger.py:91 - message"
# (filename:lineno is optional for backward compat with old log lines)
_STD_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (?P<name>\S+) - (?P<level>\S+) - "
    r"(?:(?P<loc>\S+:\d+) - )?(?P<msg>.*)$"
)
# "2026-05-24 18:43:33,654  any message"  (RPC log: no name/level)
_RPC_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+(?P<msg>.*)$"
)

# Use rich's built-in logging.level.* theme keys — same ones RichHandler
# uses internally, so `cc daemon logs` renders level pills identical to `cc -d`.
_LEVEL_STYLE = {
    "DEBUG":    "logging.level.debug",
    "INFO":     "logging.level.info",
    "WARNING":  "logging.level.warning",
    "ERROR":    "logging.level.error",
    "CRITICAL": "logging.level.critical",
}


def _format_line(line: str, is_rpc: bool):
    """Parse a log line and return a renderable mirroring RichHandler:
    HH:MM:SS  LEVEL    message ...                       file:lineno

    Message body is appended as plain text (markup-safe — brackets in
    payloads like `[401]` or `list[63]` render literally). The right
    column uses Table.grid so the location stays on the same line."""
    line = line.rstrip("\n")

    if is_rpc:
        m = _RPC_RE.match(line)
        text = Text()
        if not m:
            text.append(line)
            return text
        text.append(m.group("ts")[11:19], style="muted")  # HH:MM:SS
        text.append("  ")
        text.append(m.group("msg"))
        return text

    m = _STD_RE.match(line)
    if not m:
        return Text(line)

    level = m.group("level")
    loc = m.group("loc") or ""

    left = Text()
    left.append(m.group("ts")[11:19], style="muted")  # HH:MM:SS
    left.append(" ")
    left.append(f"{level:<8}", style=_LEVEL_STYLE.get(level, ""))
    left.append(m.group("msg"))

    if not loc:
        return left

    # Two-column grid: message left-side, file:lineno right-aligned.
    grid = Table.grid(expand=True)
    grid.add_column(ratio=1, overflow="fold")
    grid.add_column(justify="right", style="muted")
    grid.add_row(left, loc)
    return grid


class LogsCommand(Command):
    group = "daemon"
    name = "logs"
    description = "Tail CC log files."

    _LOG_FILES = {
        "all": Constants.PATH_LOG_FILE,      # cc.log — everything
        "rpc": Constants.PATH_RPC_LOG_FILE,   # rpc.log — RPC calls only
    }

    _VALID_LEVELS = {"debug", "info", "warning", "error"}

    def arguments(self):
        return [
            self.Argument(
                names=["source"],
                type=str,
                nargs="?",
                choices=list(self._LOG_FILES.keys()),
                default="all",
                help="Which log to show: all (default) or rpc.",
            ),
            self.Argument(
                names=["-f", "--follow"],
                action="store_true",
                help="Follow the log in real time (like tail -f).",
            ),
            self.Argument(
                names=["-n", "--lines"],
                type=int,
                default=50,
                help="Number of lines to show (default: 50).",
            ),
            self.Argument(
                names=["-l", "--level"],
                type=str,
                default=None,
                help="Filter by log level: debug, info, warning, error.",
            ),
        ]

    def execute(self):
        source = self.args.source or "all"
        log_file = self._LOG_FILES[source]
        is_rpc = source == "rpc"
        console = get_console()

        if not os.path.exists(log_file):
            console.print(f"[warning]No log file found at {log_file}[/]")
            return

        level_filter = None
        if self.args.level:
            if self.args.level.lower() not in self._VALID_LEVELS:
                console.print(
                    f"[error]Invalid level:[/] {self.args.level}. "
                    f"Choose from: {', '.join(sorted(self._VALID_LEVELS))}"
                )
                return
            level_filter = self.args.level.upper()

        if self.args.follow:
            self._follow(log_file, level_filter, is_rpc, console)
        else:
            self._tail(log_file, self.args.lines, level_filter, is_rpc, console)

    @staticmethod
    def _matches_level(line: str, level_filter):
        if level_filter is None:
            return True
        return f" - {level_filter} - " in line

    def _tail(self, log_file, n_lines, level_filter, is_rpc, console):
        with open(log_file, "r") as f:
            lines = f.readlines()

        if level_filter:
            lines = [l for l in lines if self._matches_level(l, level_filter)]

        for line in lines[-n_lines:]:
            console.print(_format_line(line, is_rpc))

    def _follow(self, log_file, level_filter, is_rpc, console):
        """Pure-Python tail -f: theme each line as it arrives."""
        try:
            with open(log_file, "r") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    if not self._matches_level(line, level_filter):
                        continue
                    console.print(_format_line(line, is_rpc))
        except KeyboardInterrupt:
            pass
