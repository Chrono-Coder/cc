import logging
import os
import secrets
import shutil
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

from cc.base.command import Command
from cc.utils.constants import Constants

log = logging.getLogger("CC")

# The Next.js companion lives at the repo root (web/) and is built + run in
# place — cc always runs from its source checkout, so there's nothing to
# materialize. node_modules/.next stay under web/ (gitignored).
WEB_DIR = str(Path(__file__).resolve().parents[4] / "web")
DEFAULT_PORT = 3000

# Auth token for the companion (checked by web/proxy.ts). Generated once,
# passed to the browser as ?token=... which the app exchanges for a cookie.
TOKEN_PATH = Path(Constants.PATH_USER_DATA) / "web.token"


def _ensure_web_token() -> str:
    try:
        token = TOKEN_PATH.read_text().strip()
        if token:
            return token
    except FileNotFoundError:
        pass
    token = secrets.token_hex(16)
    TOKEN_PATH.write_text(token + "\n")
    os.chmod(TOKEN_PATH, 0o600)
    log.debug("Generated companion auth token at %s", TOKEN_PATH)
    return token


class WebCommand(Command):
    name = "web"
    description = "Start the CC companion app"

    def arguments(self):
        return [
            self.Argument(
                ["--port", "-p"],
                type=int,
                default=DEFAULT_PORT,
                help=f"Port for the companion app (default: {DEFAULT_PORT})",
            ),
            self.Argument(
                ["--no-browser"],
                action="store_true",
                help="Start without opening the browser",
            ),
            self.Argument(
                ["--rebuild"],
                action="store_true",
                help="Force a rebuild even if a build already exists",
            ),
        ]

    def execute(self):
        if not os.path.isdir(WEB_DIR):
            log.error(f"Companion app not found at {WEB_DIR}.")
            return False

        if not shutil.which("node"):
            log.error("Node.js is required to run the companion app but was not found.")
            log.error("Install it from https://nodejs.org (LTS recommended).")
            return False

        from cc.utils.console import get_console
        console = get_console()

        # A complete production build leaves .next/BUILD_ID; run it with
        # `next start` (next.config has no output:standalone — its server.js
        # exits immediately on Next 16 + Node 26).
        build_id = os.path.join(WEB_DIR, ".next", "BUILD_ID")
        next_bin = os.path.join(WEB_DIR, "node_modules", ".bin", "next")
        needs_build = self.args.rebuild or not os.path.isfile(build_id)

        if needs_build:
            if not shutil.which("npm"):
                log.error("npm is required to build the companion app but was not found.")
                log.error("It comes bundled with Node.js — reinstall from https://nodejs.org.")
                return False

            if not os.path.isfile(build_id):
                console.print("[warning]The companion app needs to be built (one-time setup).[/]")
                console.print(f"This will run [primary]npm install[/] + [primary]npm run build[/] in [muted]{WEB_DIR}[/].")
                answer = input("Continue? [Y/n] ").strip().lower()
                if answer not in ("", "y", "yes"):
                    console.print("[muted]Aborted.[/]")
                    return False

            from cc.utils.ui import Spinner
            with Spinner("Installing dependencies"):
                r = subprocess.run(["npm", "install"], cwd=WEB_DIR, capture_output=True)
            if r.returncode != 0:
                log.error("npm install failed.")
                return False

            with Spinner("Building companion app"):
                r = subprocess.run(["npm", "run", "build"], cwd=WEB_DIR, capture_output=True)
            if r.returncode != 0:
                log.error("Build failed.")
                return False

        token = _ensure_web_token()
        entry_url = f"http://localhost:{self.args.port}?token={token}"

        if not self.args.no_browser:
            def _open():
                time.sleep(2)
                webbrowser.open(entry_url)
            threading.Thread(target=_open, daemon=True).start()

        get_console().print(f"[muted]Starting CC companion app on http://localhost:{self.args.port}[/]")
        if self.args.no_browser:
            get_console().print(f"[muted]Open it with: {entry_url}[/]")
        # 127.0.0.1 (IPv4) bind — the SSR self-fetch (lib/api.ts) targets it; PORT
        # lets those server-side fetches reach the right port.
        env = {**os.environ, "PORT": str(self.args.port), "HOSTNAME": "127.0.0.1"}
        subprocess.run([next_bin, "start", "-p", str(self.args.port), "-H", "127.0.0.1"], cwd=WEB_DIR, env=env)
        return True
