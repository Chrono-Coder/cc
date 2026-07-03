import logging
import os
import subprocess
import sys

log = logging.getLogger("CC")

_DEBUG_MODE = False


def set_debug_mode(is_debug: bool):
    global _DEBUG_MODE
    _DEBUG_MODE = is_debug
    log.debug(f"Shell utility debug mode set to: {_DEBUG_MODE}")


class ShellCommandException(Exception):
    def __init__(self, message, *args):
        log.error(message)
        super().__init__(message, *args)


class PythonShellCommandException(ShellCommandException): ...


def _copy_to_clipboard(text: str):
    # (Keep your existing implementation - omitted here for brevity, assume it's unchanged)
    import platform

    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True, stderr=subprocess.DEVNULL)
        elif system == "Linux":
            # Try xclip, fallback to xsel
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode("utf-8"),
                    check=True,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=text.encode("utf-8"),
                    check=True,
                    stderr=subprocess.DEVNULL,
                )
        return True
    except Exception as e:
        log.warning(f"Clipboard failed: {e}")
        return False


def run_command(args: list, **kwargs) -> subprocess.CompletedProcess:
    """Run a command safely without shell interpolation. Returns CompletedProcess."""
    log.debug(f"Running command: {args}")
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def exec_sh_command(command: str):
    """
    Executes a command.
    - If it is 'cd', it schedules it for the parent shell via CC_RUN_FILE.
    - Otherwise, it runs it immediately via subprocess.
    """
    command = command.strip()

    # 1. Handle Environment Changes (cd, export)
    if command.startswith("cd ") or command.startswith("export "):
        run_file = os.environ.get("CC_RUN_FILE")
        if run_file:
            # The run file is eval'd by the parent shell and callers pass raw
            # filesystem values: quote them. A path with a space breaks the
            # eval; one containing $(...) or ; would execute. shlex.quote
            # output parses identically in zsh/bash and fish.
            import shlex

            is_fish = os.environ.get("CC_FISH") or os.environ.get("FISH_VERSION")
            if command.startswith("cd "):
                command = f"cd {shlex.quote(command[3:].strip())}"
            else:  # export VAR=val — fish spells it "set -x VAR val"
                var, sep, val = command[len("export "):].partition("=")
                if sep:
                    quoted = shlex.quote(val)
                    command = f"set -x {var} {quoted}" if is_fish else f"export {var}={quoted}"
                elif is_fish:
                    command = f"set -x {var}"
            log.debug(f"Queueing shell instruction: {command}")
            try:
                with open(run_file, "a") as f:
                    f.write(command + "\n")
                return ""
            except Exception as e:
                log.error(f"Failed to write to run file: {e}")
                return False
        else:
            log.warning("CC_RUN_FILE not set. Cannot execute parent shell command.")
            return False

    # 2. Handle Standard Commands (dropdb, cloc, etc.)
    log.debug(f"Executing shell command: {command}")
    try:
        # shell=True allows using pipes and wildcards if your commands use them
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        # If there was output, return it (to match old API behavior)
        if result.stdout:
            print(result.stdout, end="")  # Mimic old behavior of printing
            return result.stdout.strip()

        if result.returncode != 0 and result.stderr:
            log.error(f"Command failed: {result.stderr.strip()}")
            return False

        return result.stdout.strip()

    except Exception as e:
        log.error(f"Error executing command '{command}': {e}")
        return False


def shell_exit(clean_files=False):
    log.debug("CC Aborted.")
    sys.exit(0)
