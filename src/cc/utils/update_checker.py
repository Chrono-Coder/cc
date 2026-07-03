import logging
import os
import subprocess
import threading
from datetime import datetime, timezone

log = logging.getLogger("CC")

_CHECK_INTERVAL_HOURS = 24
_PROMPT_COOLDOWN_HOURS = 6
_NO_PROMPT_COMMANDS = {"switch", "stat"}
_REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
_REMOTE = "origin"
_BRANCH = "main"

# Clear the credential-helper chain so the background fetch can never invoke the
# OS keychain helper (which pops a GUI dialog on macOS even with no terminal).
_NOPROMPT = ["-c", "credential.helper=", "-c", "credential.interactive=false"]


def _git_env() -> dict:
    """Force git fully non-interactive — a private/auth'd remote must fail fast,
    never prompt the terminal, keychain, or SSH passphrase, in the update check."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"            # no HTTP user/pass prompt
    env["GIT_ASKPASS"] = "echo"                 # askpass yields nothing → no GUI prompt
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes")
    return env


def _user_data_path() -> str:
    from cc.utils.constants import Constants
    return Constants.PATH_USER_DATA


def _last_check_file() -> str:
    return os.path.join(_user_data_path(), "last_update_check")


def _update_available_file() -> str:
    return os.path.join(_user_data_path(), "update_available")


def _is_git_repo() -> bool:
    return os.path.isdir(os.path.join(_REPO_PATH, ".git"))


def _run_git(*args) -> str:
    result = subprocess.run(
        ["git", "-C", _REPO_PATH, *_NOPROMPT, *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=_git_env(),
    )
    return result.stdout.strip()


def _fetch_and_compare():
    """Runs in background thread — fetches remote and writes flag if behind.

    "Behind" means ``origin/main`` contains commits that are NOT reachable
    from the current ``HEAD``. This is the only case worth telling the user
    to ``git pull`` for. A feature branch sitting *ahead* of main (or
    diverged but already containing every main commit as ancestors) will
    NOT trigger the flag — the user has nothing to pull there.
    """
    try:
        log.debug("UpdateChecker: fetching remote...")
        subprocess.run(
            ["git", "-C", _REPO_PATH, *_NOPROMPT, "fetch", _REMOTE, _BRANCH, "--quiet"],
            capture_output=True,
            timeout=15,
            env=_git_env(),
        )

        remote_sha = _run_git("rev-parse", f"{_REMOTE}/{_BRANCH}")
        # Commits in origin/main NOT reachable from HEAD = how many we're missing.
        # 0 → up to date (we're on main at HEAD, or on a feature branch that
        # already includes every main commit as ancestor).
        behind_raw = _run_git("rev-list", "--count", f"HEAD..{_REMOTE}/{_BRANCH}")
        try:
            behind = int(behind_raw)
        except (TypeError, ValueError):
            behind = 0
        log.debug(f"UpdateChecker: behind={behind} commits, remote={remote_sha[:8]}")

        flag_file = _update_available_file()
        if behind > 0 and remote_sha:
            log.debug("UpdateChecker: update available, writing flag.")
            with open(flag_file, "w") as f:
                f.write(remote_sha)
        else:
            log.debug("UpdateChecker: up to date.")
            if os.path.exists(flag_file):
                os.remove(flag_file)

        # Record check time
        with open(_last_check_file(), "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())

    except Exception as e:
        log.debug(f"UpdateChecker: background check failed: {e}")


def _should_check() -> bool:
    last_check_file = _last_check_file()
    if not os.path.exists(last_check_file):
        return True
    try:
        with open(last_check_file) as f:
            last_check = datetime.fromisoformat(f.read().strip())
        hours_since = (datetime.now(timezone.utc) - last_check).total_seconds() / 3600
        return hours_since >= _CHECK_INTERVAL_HOURS
    except Exception:
        return True


def trigger_background_check():
    """Kick off a background fetch if enough time has passed. Non-blocking."""
    if not _is_git_repo():
        return
    if not _should_check():
        log.debug("UpdateChecker: skipping check, checked recently.")
        return
    thread = threading.Thread(target=_fetch_and_compare, daemon=True)
    thread.start()


def _last_prompt_file() -> str:
    return os.path.join(_user_data_path(), "last_update_prompt")


def should_prompt_user(command_name: str | None = None) -> bool:
    """Returns True if we should show the interactive update prompt."""
    if command_name in _NO_PROMPT_COMMANDS:
        return False
    path = _last_prompt_file()
    if not os.path.exists(path):
        return True
    try:
        with open(path) as f:
            last = datetime.fromisoformat(f.read().strip())
        return (datetime.now(timezone.utc) - last).total_seconds() / 3600 >= _PROMPT_COOLDOWN_HOURS
    except Exception:
        return True


def record_prompt():
    """Record that we just showed the update prompt."""
    try:
        with open(_last_prompt_file(), "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())
    except Exception:
        pass


def clear_update_flag():
    flag_file = _update_available_file()
    if os.path.exists(flag_file):
        os.remove(flag_file)


def get_notification() -> str | None:
    """Render the update notification via the themed console.

    Returns the remote SHA so callers can also display version info, or
    None if no update is pending. Side-effect: prints the notification.
    """
    flag_file = _update_available_file()
    if not os.path.exists(flag_file):
        return None
    try:
        with open(flag_file) as f:
            remote_sha = f.read().strip()[:8]
        from cc.utils.console import get_console
        get_console().print(
            f"  [warning]↑ Update available[/]  "
            f"[muted]({remote_sha}) — cd {_REPO_PATH} && git pull[/]"
        )
        return remote_sha
    except Exception:
        return None
