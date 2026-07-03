import logging
import os
import signal
import time

from cc.base.command import Command
from cc.utils.constants import Constants

log = logging.getLogger("CC")


class _DaemonBase(Command):
    """Shared daemon process control. Not a registered command (no ``name``);
    the `cc daemon <verb>` subcommands below extend it.
    """

    def _read_pid(self):
        try:
            with open(Constants.DAEMON_PID_FILE) as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return None

    def _is_running(self, pid):
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def _start(self):
        from cc.utils.console import get_console
        console = get_console()
        quiet = self.args.quiet
        pid = self._read_pid()
        if self._is_running(pid):
            if not quiet:
                console.print(f"[muted]Daemon already running[/] [primary](PID {pid})[/]")
            return

        if self.args.foreground:
            if not quiet:
                console.print("[primary]Starting daemon in foreground[/] [muted](Ctrl+C to stop)…[/]")
            from cc.daemon.server import run
            run()
            return

        from cc.daemon import client
        client._start_daemon()

        pid = self._read_pid()
        if self._is_running(pid):
            if not quiet:
                console.print(f"[success]✓ Daemon started[/] [muted](PID {pid})[/]")
        else:
            if not quiet:
                console.print("[error]✗ Daemon failed to start[/] — check [primary]cc daemon logs[/]")
            return False

    def _stop(self):
        from cc.utils.console import get_console
        console = get_console()
        quiet = self.args.quiet
        pid = self._read_pid()
        if not self._is_running(pid):
            if not quiet:
                console.print("[muted]Daemon is not running.[/] Start with [primary]cc daemon start[/]")
            return

        os.kill(pid, signal.SIGTERM)

        for _ in range(20):
            time.sleep(0.1)
            if not self._is_running(pid):
                if not quiet:
                    console.print("[success]✓ Daemon stopped[/]")
                return

        if not quiet:
            console.print(f"[error]Daemon (PID {pid}) did not stop cleanly[/] — try [primary]kill -9 {pid}[/]")
        return False

    def _restart(self):
        self._stop()
        time.sleep(0.2)
        self._start()

    def _status(self):
        from cc.daemon.client import call
        from cc.utils.console import get_console
        from cc.utils.errors import DaemonError
        from cc.utils.panels import themed_table

        console = get_console()
        pid = self._read_pid()
        if not self._is_running(pid):
            if not self.args.quiet:
                console.print("[muted]Stopped[/]")
            return False  # exit 1 — shell auto-start reads this to decide to launch

        if self.args.quiet:
            return True  # running; nothing more to print

        sock_exists = os.path.exists(Constants.SOCKET_PATH)
        sock_status = "[success]ok[/]" if sock_exists else "[error]missing[/]"
        header = f"[success]Running[/]  [muted]PID[/] [bold]{pid}[/]  [muted]socket[/] {sock_status}"

        try:
            h = call("system.health")
            uptime = int(h["uptime_seconds"])
            h_str = f"{uptime // 3600}h {(uptime % 3600) // 60}m {uptime % 60}s"
            db_bytes = h.get("db_size_bytes") or 0
            db_str = f"{db_bytes / 1024:.0f} KB" if db_bytes < 1024 * 1024 else f"{db_bytes / (1024 * 1024):.1f} MB"

            table = themed_table()
            table.add_column("Field", style="primary")
            table.add_column("Value", style="bold")
            table.add_row("Uptime", h_str)
            table.add_row("RPCs", str(h["rpc_count"]))
            table.add_row("DB size", db_str)
            if h.get("last_error"):
                table.add_row("Last err", f"[error]{h['last_error']}[/]")
            console.print()
            console.print(header)
            console.print(table)
            console.print()
        except DaemonError:
            console.print()
            console.print(header)
            console.print("[muted](health unavailable — daemon may be starting)[/]")
            console.print()


def _quiet_arg(self):
    return self.Argument(
        ["-q", "--quiet"], action="store_true",
        help="Suppress output. For status, exit 0 if running else 1 (how shell auto-start probes).",
    )


def _foreground_arg(self):
    return self.Argument(
        ["-f", "--foreground"], action="store_true",
        help="Run in foreground, logging to this terminal (useful for debugging).",
    )


class DaemonStartCommand(_DaemonBase):
    group = "daemon"
    name = "start"
    description = "Start the cc daemon."

    def arguments(self):
        return [_foreground_arg(self), _quiet_arg(self)]

    def execute(self):
        return self._start()


class DaemonStopCommand(_DaemonBase):
    group = "daemon"
    name = "stop"
    description = "Stop the cc daemon."

    def arguments(self):
        return [_quiet_arg(self)]

    def execute(self):
        return self._stop()


class DaemonRestartCommand(_DaemonBase):
    group = "daemon"
    name = "restart"
    description = "Restart the cc daemon."

    def arguments(self):
        return [_foreground_arg(self), _quiet_arg(self)]

    def execute(self):
        return self._restart()


class DaemonStatusCommand(_DaemonBase):
    group = "daemon"
    name = "status"
    description = "Show daemon status."

    def arguments(self):
        return [_quiet_arg(self)]

    def execute(self):
        return self._status()
