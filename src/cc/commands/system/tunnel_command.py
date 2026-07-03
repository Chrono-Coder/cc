import logging
import os
import signal
import subprocess

from cc.base.arm import Environment
from cc.base.command import Command
from cc.daemon.client import call

log = logging.getLogger("CC")

TUNNEL_LOCAL_PORT = 5433


class TunnelCommand(Command):
    name = "tunnel"
    description = "Open an SSH tunnel to a remote Odoo.sh PostgreSQL database."

    def arguments(self):
        return [
            self.Argument(
                ["name"],
                type=str,
                nargs="?",
                help="Environment name. Defaults to the active environment.",
                complete=Environment,
            ),
            self.Argument(
                ["--stop"],
                action="store_true",
                help="Stop the active tunnel for the environment.",
            ),
            self.Argument(
                ["--status"],
                action="store_true",
                help="List all active tunnels.",
            ),
        ]

    def execute(self):
        if self.args.status:
            return self._status()

        env = self._resolve_env()
        if not env:
            return False

        if self.args.stop:
            return self._stop(env.name)

        return self._start(env)

    # ── Resolve environment ──────────────────────────────────────────────────

    def _resolve_env(self):
        if self.args.name:
            env = self.environment.find_by(name=self.args.name, limit=1)
            if not env:
                log.error(f"Environment '{self.args.name}' not found.")
            return env
        env = self.active_environment
        if not env:
            log.error("No active environment. Run 'cc switch' first or pass an environment name.")
        return env

    # ── Start ────────────────────────────────────────────────────────────────

    def _start(self, env):
        ssh_host = env.ssh_host or self._prompt_save_field(env, "ssh_host", "SSH Host (e.g. project-31002026.dev.odoo.com)")  # noqa: E501
        ssh_user = env.ssh_user or self._prompt_save_field(env, "ssh_user", "SSH User (e.g. 31002026)")
        if not ssh_host or not ssh_user:
            return False

        key_path = self._get_or_set_ssh_key()
        if not key_path:
            return False

        key_path = os.path.expanduser(key_path)
        if not os.path.exists(key_path):
            log.error(f"SSH key not found: {key_path}")
            return False

        from cc.utils.console import get_console
        console = get_console()
        console.print("[muted]Fetching PG credentials from remote server...[/]")
        creds = self._fetch_pg_creds(key_path, ssh_user, ssh_host)
        if not creds:
            return False

        self._stop_all_tunnels()

        console.print(f"[muted]Opening tunnel on 127.0.0.1:{TUNNEL_LOCAL_PORT} → {ssh_host}:5432 ...[/]")
        proc = subprocess.Popen([
            "ssh", "-N", "-i", key_path,
            "-L", f"{TUNNEL_LOCAL_PORT}:localhost:5432",
            f"{ssh_user}@{ssh_host}",
        ])

        os.makedirs(self.Constants.PATH_TUNNELS, exist_ok=True)
        pid_file = os.path.join(self.Constants.PATH_TUNNELS, f"{env.name}.pid")
        with open(pid_file, "w") as f:
            f.write(str(proc.pid))

        self._write_tunnel_settings(creds)
        console.print(f"[success]✓ Tunnel open (PID {proc.pid}).[/] Use [primary]cc tunnel --stop[/] to close it.")
        return True

    def _fetch_pg_creds(self, key_path, ssh_user, ssh_host):
        try:
            result = subprocess.run(
                ["ssh", "-i", key_path, f"{ssh_user}@{ssh_host}",
                 "env | grep -E '^(PGPASSWORD|PGUSER|PGDATABASE)'"],
                capture_output=True, text=True, check=True, timeout=15,
            )
        except subprocess.CalledProcessError as e:
            log.error(f"SSH command failed: {e.stderr.strip()}")
            return None
        except subprocess.TimeoutExpired:
            log.error("SSH connection timed out.")
            return None

        creds = {}
        for line in result.stdout.strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()

        required = {"PGDATABASE", "PGUSER", "PGPASSWORD"}
        missing = required - creds.keys()
        if missing:
            log.error(f"Missing PG environment variables from remote: {', '.join(missing)}")
            return None

        return creds

    def _write_tunnel_settings(self, creds):
        version = self.active_version
        if not version:
            log.warning("No active version — cannot update settings.json.")
            return

        import json
        vscode_dir = os.path.join(version.path, ".vscode")
        settings_path = os.path.join(vscode_dir, "settings.json")
        os.makedirs(vscode_dir, exist_ok=True)
        try:
            settings = {}
            if os.path.exists(settings_path):
                with open(settings_path) as f:
                    settings = json.load(f)

            settings["cc.tunnel.active"] = True
            settings["cc.tunnel.db"] = creds["PGDATABASE"]
            settings["cc.tunnel.user"] = creds["PGUSER"]
            settings["cc.tunnel.password"] = creds["PGPASSWORD"]
            settings["cc.tunnel.host"] = "127.0.0.1"
            settings["cc.tunnel.port"] = TUNNEL_LOCAL_PORT

            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=4)
            log.debug("Updated cc.tunnel.* in settings.json")
            log.warning("Tunnel credentials written to .vscode/settings.json — ensure this file is in .gitignore.")
        except Exception as e:
            log.warning(f"Could not update settings.json: {e}")

    # ── Stop ─────────────────────────────────────────────────────────────────

    def _stop(self, env_name):
        killed = self._stop_if_running(env_name)
        if not killed:
            from cc.utils.console import get_console
            get_console().print(f"[muted]No active tunnel found for '{env_name}'.[/]")
            return False
        self._clear_tunnel_settings()
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Tunnel for '{env_name}' stopped.[/]")
        return True

    def _stop_all_tunnels(self):
        tunnel_dir = self.Constants.PATH_TUNNELS
        if not os.path.isdir(tunnel_dir):
            return
        for pid_file in os.listdir(tunnel_dir):
            if pid_file.endswith(".pid"):
                self._stop_if_running(pid_file[:-4])

    def _stop_if_running(self, env_name):
        pid_file = os.path.join(self.Constants.PATH_TUNNELS, f"{env_name}.pid")
        if not os.path.exists(pid_file):
            return False
        try:
            pid = int(open(pid_file).read().strip())
            os.kill(pid, signal.SIGTERM)
            log.debug(f"Sent SIGTERM to PID {pid}")
        except (ValueError, ProcessLookupError):
            pass
        os.remove(pid_file)
        return True

    def _clear_tunnel_settings(self):
        version = self.active_version
        if not version:
            return

        import json
        settings_path = os.path.join(version.path, ".vscode", "settings.json")
        if not os.path.exists(settings_path):
            return
        try:
            with open(settings_path) as f:
                settings = json.load(f)
            settings["cc.tunnel.active"] = False
            for key in ("cc.tunnel.db", "cc.tunnel.user", "cc.tunnel.password"):
                settings.pop(key, None)
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            log.warning(f"Could not clear tunnel settings: {e}")

    # ── Status ───────────────────────────────────────────────────────────────

    def _status(self):
        from cc.utils.console import get_console
        from cc.utils.panels import themed_table
        console = get_console()

        tunnel_dir = self.Constants.PATH_TUNNELS
        if not os.path.isdir(tunnel_dir):
            console.print("[muted]No tunnels have been opened yet.[/]")
            return True

        pid_files = [f for f in os.listdir(tunnel_dir) if f.endswith(".pid")]
        if not pid_files:
            console.print("[muted]No active tunnels.[/]")
            return True

        table = themed_table(title="Tunnels")
        table.add_column("Environment", style="bold")
        table.add_column("PID")
        table.add_column("Status")
        for pid_file in sorted(pid_files):
            env_name = pid_file[:-4]
            try:
                pid = int(open(os.path.join(tunnel_dir, pid_file)).read().strip())
                os.kill(pid, 0)
                status = "[success]active[/]"
            except (ValueError, ProcessLookupError):
                status = "[error]dead[/] (run --stop to clean up)"
                pid = "?"
            table.add_row(env_name, str(pid), status)
        console.print()
        console.print(table)
        console.print()
        return True

    # ── Settings helpers ─────────────────────────────────────────────────────

    def _get_or_set_ssh_key(self):
        key_setting = self.setting.find_by(name=self.Constants.SETTING_SSH_KEY_PATH, limit=1)
        if key_setting:
            return key_setting.value

        key_path = self.prompter.prompt_input_path(
            "SSH Key Path", default="~/.ssh/github-second", must_exist=True, kind="file",
        )
        if not key_path:
            return None

        self._upsert_setting(self.Constants.SETTING_SSH_KEY_PATH, key_path)
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ SSH key path saved: {key_path}[/]")
        return key_path

    def _prompt_save_field(self, env, field, label):
        value = self.prompter.prompt_input_single(label)
        if not value:
            return None
        call("env.update", env_id=env.id, **{field: value})
        return value

    def _upsert_setting(self, key, value):
        call("setting.upsert", key=key, value=value)
