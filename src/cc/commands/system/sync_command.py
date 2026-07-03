import logging
import os
import platform
import subprocess

from cc.base.command import Command
from cc.daemon.client import call

log = logging.getLogger("CC")

try:
    import Cryptodome  # noqa: F401
    _SYNC_AVAILABLE = True
except ImportError:
    _SYNC_AVAILABLE = False


class SyncCommand(Command):
    name = "sync"
    description = "Synchronize local data with the CC server."

    def arguments(self):
        return [
            self.Argument(
                names=["action"],
                type=str,
                nargs="?",
                choices=["push", "pull", "status", "setup", "register", "link", "stamp", "resolve", "enable", "server"],
                default="status",
                help="Sync action: enable, setup, push, pull, status, register, link, stamp, resolve, server.",
            ),
            self.Argument(
                names=["--name"],
                type=str,
                default=None,
                help="Device name for register, or project name for link.",
            ),
            self.Argument(
                names=["--path"],
                type=str,
                default=None,
                help="Local project path for link.",
            ),
            self.Argument(
                names=["--project"],
                type=str,
                default=None,
                help="Project name for link.",
            ),
            self.Argument(
                names=["--since"],
                type=str,
                default=None,
                help="ISO timestamp for pull (e.g. 2026-01-01T00:00:00).",
            ),
            self.Argument(
                names=["--port"],
                type=int,
                default=9100,
                help="Port for sync server (default: 9100).",
            ),
        ]

    def execute(self):
        action = self.args.action

        if action == "enable":
            return self._enable()

        if not _SYNC_AVAILABLE:
            from cc.utils.console import get_console
            console = get_console()
            console.print("\n[warning]Sync plugin is not installed.[/]")
            console.print("  Install it with: [primary]cc sync enable[/]")
            console.print()
            return False

        actions = {
            "status": self._status,
            "setup": self._setup,
            "register": self._register,
            "link": self._link,
            "push": self._push,
            "pull": self._pull,
            "stamp": self._stamp,
            "resolve": self._resolve,
            "server": self._server,
        }

        handler = actions.get(action, self._status)
        return handler()

    def _status(self):
        from cc.utils.console import get_console
        console = get_console()

        result = call("sync.status")
        console.print("\n[bold]Sync Status (local)[/]")
        for table, count in result.get("pending", {}).items():
            style = "error" if count > 0 else "success"
            console.print(f"  {table}: [{style}]{count} pending[/]")

        from cc.sync.http_client import health, is_configured
        if is_configured():
            h = health()
            if h:
                console.print("\n  Server: [success]connected[/]")
            else:
                console.print("\n  Server: [error]unreachable[/]")
        else:
            console.print("\n  Server: [muted]not configured[/]")

        console.print()
        return True

    def _setup(self):
        """Interactively configure this device's sync credentials.

        Prompts for the server URL + API key, verifies them against the
        server, then writes them to ~/.cc-cli/.env (chmod 600). The key is
        never synced, so it has to be planted on each device by hand — this
        is that step.
        """
        from cc.sync import http_client
        from cc.utils.console import get_console
        console = get_console()

        console.print("\n[heading]Sync setup[/]")
        console.print(
            "[muted]Point this device at a cc sync server. Credentials are written "
            "to ~/.cc-cli/.env and are never synced between devices.[/]\n"
        )

        # Pre-fill from current env, then fall back to stored settings.
        cur_server = os.environ.get("CC_SERVER")
        cur_key = os.environ.get("CC_API_KEY")
        if not cur_server:
            s = self.setting.find_by(name="sync.server_url", limit=1)
            cur_server = s.value if s else None
        if not cur_key:
            s = self.setting.find_by(name="sync.api_key", limit=1)
            cur_key = s.value if s else None

        server_prompt = f"Server URL{f' [{cur_server}]' if cur_server else ''}: "
        server = input(server_prompt).strip() or (cur_server or "")
        if not server:
            console.print("[error]Server URL is required.[/]\n")
            return False

        key_default = f" [{cur_key[:8]}…]" if cur_key else ""
        api_key = input(f"API key{key_default}: ").strip() or (cur_key or "")
        if not api_key:
            console.print("[error]API key is required.[/]\n")
            return False

        console.print()
        from cc.utils.ui import Spinner
        with Spinner("Verifying credentials"):
            ok, message = http_client.verify(server, api_key)

        if not ok:
            console.print(f"[error]✗ {message}[/]")
            console.print(
                "[muted]Nothing written. If the key was rejected, register this "
                "device ON THE SERVER (`cc sync register --name <device>` run there), "
                "then re-run `cc sync setup` with the key it prints.[/]\n"
            )
            return False

        console.print(f"[success]✓ {message}[/]")
        env_path = self._write_env({"CC_SERVER": server.rstrip("/"), "CC_API_KEY": api_key})
        console.print(f"[success]✓ Wrote[/] [primary]{env_path}[/] [muted](permissions 600)[/]")
        console.print("\nStart auto-sync now: [primary]cc daemon restart[/]\n")
        return True

    def _write_env(self, updates: dict) -> str:
        """Merge key=value pairs into ~/.cc-cli/.env, preserving other lines."""
        from cc.utils.constants import Constants
        env_path = os.path.join(Constants.PATH_USER_DATA, ".env")
        lines = []
        seen = set()
        if os.path.isfile(env_path):
            with open(env_path) as f:
                for raw in f:
                    stripped = raw.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        key = stripped.split("=", 1)[0].strip()
                        if key in updates:
                            lines.append(f"{key}={updates[key]}")
                            seen.add(key)
                            continue
                    lines.append(raw.rstrip("\n"))
        for key, value in updates.items():
            if key not in seen:
                lines.append(f"{key}={value}")
        with open(env_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(env_path, 0o600)
        return env_path

    def _register(self):
        from cc.utils.console import get_console
        console = get_console()
        name = self.args.name or platform.node() or "unnamed"
        result = call("sync.register_device", name=name)
        console.print(f"\n[bold]Device registered:[/] {result['name']}")
        console.print(f"[bold]API key:[/] {result['api_key']}")
        console.print("\nStore this key — you'll need it to configure sync on remote devices.")
        console.print(
            "[warning]Note:[/] this registered the device in [bold]this machine's[/] database. "
            "It is only valid as a client key if [bold]this machine is the sync server[/]. "
            "To enroll a different laptop, run this on the server, then put the key in that "
            "laptop's ~/.cc-cli/.env via [primary]cc sync setup[/].\n"
        )
        return True

    def _link(self):
        from cc.utils.console import get_console
        console = get_console()
        device_name = self.args.name or platform.node()
        project_name = self.args.project
        local_path = self.args.path

        if not project_name or not local_path:
            console.print("[error]Usage: cc sync link --name DEVICE --project PROJECT --path /local/path[/]")
            return False

        result = call("sync.link_project", device_name=device_name, project_name=project_name, local_path=local_path)
        verb = "Updated" if result.get("updated") else "Linked"
        console.print(f"\n{verb}: [bold]{result['project']}[/] → {result['local_path']} (on {result['device']})\n")
        return True

    def _push(self):
        from cc.sync.http_client import is_configured
        from cc.utils.console import get_console
        console = get_console()

        # Pull local pending data
        result = call("sync.pull")
        changes = {t: rows for t, rows in result.items() if t != "server_time"}
        total = sum(len(rows) for rows in changes.values())

        if total == 0:
            console.print("\n[muted]Nothing to push — no synced rows locally.[/]\n")
            return True

        if is_configured():
            from cc.sync import http_client
            from cc.utils.ui import Spinner
            try:
                with Spinner("Pushing to server"):
                    remote_result = http_client.call("sync.push", changes=changes)
            except RuntimeError as e:
                console.print(f"\n[error]✗ Push failed.[/]\n[warning]{e}[/]\n")
                return False
            # Everything we sent is now on the server (accepted or already there),
            # so mark it synced locally — otherwise `sync status` shows it forever.
            marked = call("sync.mark_synced", timestamp=remote_result.get("server_time"))
            console.print(
                f"\n[bold]Pushed to server:[/] "
                f"[success]{remote_result['accepted']} accepted[/], "
                f"[muted]{remote_result['skipped']} skipped[/]"
                f"  [muted]({marked['marked']} marked synced)[/]\n"
            )
        else:
            console.print(f"\n[warning]Server not configured.[/] {total} rows ready to push.")
            console.print("Set CC_SERVER and CC_API_KEY, or use 'cc config' to configure.\n")

        return True

    def _pull(self):
        from cc.sync.http_client import is_configured
        from cc.utils.console import get_console
        console = get_console()

        if not is_configured():
            console.print("\n[warning]Server not configured.[/] Set CC_SERVER and CC_API_KEY.\n")
            return False

        from cc.sync import http_client
        since = self.args.since
        kwargs = {}
        if since:
            kwargs["since"] = since

        from cc.utils.ui import Spinner
        try:
            with Spinner("Pulling from server"):
                remote_data = http_client.call("sync.pull", **kwargs)
        except RuntimeError as e:
            console.print(f"\n[error]✗ Pull failed.[/]\n[warning]{e}[/]\n")
            return False
        changes = {t: rows for t, rows in remote_data.items() if t != "server_time"}
        total = sum(len(rows) for rows in changes.values())

        if total == 0:
            console.print("\n[muted]Nothing new from server.[/]\n")
            return True

        result = call("sync.push", changes=changes)
        console.print(
            f"\n[bold]Pulled from server:[/] "
            f"[success]{result['accepted']} new[/], "
            f"[muted]{result['skipped']} already synced[/]\n"
        )
        return True

    def _enable(self):
        from cc.utils.console import get_console
        console = get_console()

        if _SYNC_AVAILABLE:
            console.print("\n[success]✓ Sync plugin is already installed.[/]\n")
            return True

        venv_pip = os.path.join(os.path.expanduser("~"), ".cc-cli", "venv", "bin", "pip")
        if not os.path.isfile(venv_pip):
            console.print("[error]cc venv not found.[/] Reinstall cc with [primary]./install.sh[/]")
            return False

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        if not os.path.isfile(os.path.join(repo_root, "pyproject.toml")):
            console.print("[error]cc source not found.[/] Run this from the cc repo directory.")
            return False

        from cc.utils.ui import Spinner
        with Spinner("Installing sync plugin"):
            result = subprocess.run(
                [venv_pip, "install", "-e", f"{repo_root}[sync]", "-q"],
                capture_output=True, text=True,
            )

        if result.returncode != 0:
            console.print(f"[error]Install failed:[/] {result.stderr.strip()}")
            return False

        console.print("\n[success]✓ Sync plugin installed.[/]")
        console.print("  Restart your terminal, then configure with:")
        console.print("    [primary]CC_SERVER[/]=https://your-server  → add to [primary]~/.cc-cli/.env[/]")
        console.print("    [primary]CC_API_KEY[/]=your-key            → add to [primary]~/.cc-cli/.env[/]")
        console.print("  Then [primary]cc daemon restart[/]\n")
        return True

    def _stamp(self):
        from cc.utils.console import get_console
        console = get_console()
        result = call("sync.stamp_sync_ids")
        console.print(f"\n[bold]Stamped {result['stamped']} rows[/] with sync IDs.\n")
        return True

    def _resolve(self):
        """Resolve synced paths to local equivalents, clone missing repos."""
        import os
        import re
        import subprocess

        from cc.base.db import get_db_connection
        from cc.utils.console import get_console
        console = get_console()

        local_versions = {}
        for v in self.version.search([]):
            if v.path and os.path.isdir(v.path):
                local_versions[v.name] = v

        conn = get_db_connection()
        fixed_versions = 0
        fixed_paths = 0
        cleared_paths = 0
        cloned = 0

        # Phase 1: remap versions
        for env in self.environment.search([]):
            ver = env.version_id
            if ver and ver.path and not os.path.isdir(ver.path):
                digits = re.sub(r"[^0-9.]", "", ver.name)
                local_ver = local_versions.get(digits) or local_versions.get(ver.name)
                if local_ver and local_ver.id != ver.id:
                    conn.execute(
                        "UPDATE environment SET version_id = ? WHERE id = ?",
                        (local_ver.id, env.id),
                    )
                    fixed_versions += 1

        # Phase 2: resolve or clone project paths
        clone_dir = self._detect_clone_dir(local_versions)
        for env in self.environment.search([]):
            ver = env.version_id
            if not ver or not ver.path or not os.path.isdir(ver.path):
                if env.project_path:
                    conn.execute("UPDATE environment SET project_path = NULL WHERE id = ?", (env.id,))
                    cleared_paths += 1
                continue

            if env.project_path and os.path.isdir(env.project_path):
                continue

            paths, _ = self.Helpers._get_project_paths(env.name, ver.name)
            if paths:
                conn.execute(
                    "UPDATE environment SET project_path = ? WHERE id = ?",
                    (list(paths.keys())[0], env.id),
                )
                fixed_paths += 1
                continue

            if env.github_url and clone_dir:
                repo_name = env.github_url.rstrip("/").split("/")[-1]
                clone_url = self._to_ssh_url(env.github_url)
                target = os.path.join(ver.path, clone_dir, repo_name)
                if not os.path.isdir(target):
                    from cc.utils.ui import Spinner
                    # Non-interactive: if the SSH key isn't loaded, fail fast with
                    # "Permission denied (publickey)" instead of hanging on a hidden
                    # passphrase prompt behind the spinner until the timeout fires.
                    clone_env = {
                        **os.environ,
                        "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8",
                        "GIT_TERMINAL_PROMPT": "0",
                    }
                    with Spinner(f"Cloning {repo_name}"):
                        result = subprocess.run(
                            ["git", "clone", clone_url, target],
                            capture_output=True, text=True, timeout=120,
                            stdin=subprocess.DEVNULL, env=clone_env,
                        )
                    if result.returncode != 0:
                        console.print(f"  [error]Failed to clone {repo_name}:[/] {result.stderr.strip()}")
                        conn.execute("UPDATE environment SET project_path = NULL WHERE id = ?", (env.id,))
                        cleared_paths += 1
                        continue
                conn.execute(
                    "UPDATE environment SET project_path = ? WHERE id = ?",
                    (target, env.id),
                )
                cloned += 1
                fixed_paths += 1
            else:
                conn.execute("UPDATE environment SET project_path = NULL WHERE id = ?", (env.id,))
                cleared_paths += 1

        for ver in self.version.search([]):
            if ver.path and not os.path.isdir(ver.path):
                digits = re.sub(r"[^0-9.]", "", ver.name)
                local = local_versions.get(digits)
                if local and local.id != ver.id:
                    console.print(f"  [muted]Duplicate version '{ver.name}' → merged into '{local.name}'[/]")

        console.print("\n[bold]Resolved paths:[/]")
        console.print(f"  Versions remapped: [success]{fixed_versions}[/]")
        console.print(f"  Paths found:       [success]{fixed_paths}[/]")
        if cloned:
            console.print(f"  Repos cloned:      [success]{cloned}[/]")
        console.print(f"  Paths cleared:     [muted]{cleared_paths}[/]")
        console.print()
        return True

    def _detect_clone_dir(self, local_versions):
        """Detect where projects live relative to version root.

        Scans existing project paths to infer the pattern. Falls back to
        the sync.clone_dir setting, or prompts the user.
        """
        import os

        for env in self.environment.search([]):
            if not env.project_path or not os.path.isdir(env.project_path):
                continue
            ver = env.version_id
            if not ver or not ver.path:
                continue
            rel = os.path.relpath(env.project_path, ver.path)
            parts = rel.split(os.sep)
            if len(parts) >= 2:
                return os.path.join(*parts[:-1])

        setting = self.setting.find_by(name="sync.clone_dir", limit=1)
        if setting and setting.value:
            return setting.value

        from cc.utils.console import get_console
        console = get_console()
        console.print("\n[warning]No existing projects found to detect clone directory.[/]")
        console.print("[muted]Enter the path relative to the version root (e.g. stack/addons, custom):[/]")
        clone_dir = input("> ").strip()
        if clone_dir:
            call("setting.upsert", key="sync.clone_dir", value=clone_dir)
            return clone_dir
        return None

    @staticmethod
    def _to_ssh_url(https_url):
        """Convert https://github.com/org/repo to git@github.com:org/repo.git"""
        if https_url.startswith("git@"):
            return https_url
        url = https_url.rstrip("/")
        if "github.com/" in url:
            path = url.split("github.com/", 1)[1]
            if not path.endswith(".git"):
                path += ".git"
            return f"git@github.com:{path}"
        return https_url

    def _server(self):
        from cc.utils.console import get_console
        console = get_console()
        port = self.args.port
        console.print(f"\n[bold]Starting CC Sync server on port {port}...[/]\n")
        from cc.sync.http_server import run
        run(port=port)
        return True
