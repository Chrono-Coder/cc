"""`cc shell` — manage cc's shell integration."""
import logging
import os

from cc.base.command import Command
from cc.shell import installer
from cc.utils.console import get_console

log = logging.getLogger("CC")


class ShellCommand(Command):
    group = "config"
    name = "shell"
    description = "Manage cc shell integration (zsh / bash / fish)."

    def arguments(self):
        return [
            self.Argument(
                names=["action"],
                type=str,
                nargs="?",
                choices=["install", "status"],
                default="status",
                help="install or status (default: status)",
            ),
            self.Argument(
                names=["--shell"],
                type=str,
                choices=list(installer.SUPPORTED_SHELLS),
                default=None,
                help="Force a specific shell (auto-detects by default).",
            ),
            self.Argument(
                names=["-f", "--force"],
                action="store_true",
                help="Reinstall even if integration is already in place.",
            ),
        ]

    def execute(self):
        if self.args.action == "status":
            return self._status()
        return self._install()

    def _status(self):
        console = get_console()
        shell_type = self.args.shell or installer.detect_shell()
        if not shell_type:
            shell = os.environ.get("SHELL", "")
            console.print(
                f"[warning]Shell integration supports zsh, bash, and fish "
                f"(detected: {shell or 'unknown'}).[/]"
            )
            return False
        if installer.is_installed(shell_type):
            console.print(
                f"[success]✓ Shell integration installed[/] "
                f"[muted]for {shell_type}.[/]"
            )
        else:
            console.print(
                f"[muted]Shell integration not installed[/] "
                f"[muted]for {shell_type}.[/]  "
                f"Run [primary]cc config shell install[/]."
            )
        return True

    def _install(self):
        console = get_console()
        shell_type = self.args.shell or installer.detect_shell()
        if not shell_type:
            shell = os.environ.get("SHELL", "")
            log.error(
                f"Shell integration supports zsh, bash, and fish "
                f"(detected: {shell or 'unknown'})."
            )
            return False

        if installer.is_installed(shell_type) and not self.args.force:
            console.print(
                f"[success]✓ Already installed[/] [muted]for {shell_type}.[/]  "
                f"Pass [primary]--force[/] to reinstall."
            )
            return True

        if not installer.install(shell_type):
            return False

        if shell_type == "fish":
            rc = "~/.config/fish/config.fish"
        elif shell_type == "bash":
            rc = "~/.bashrc"
        else:
            rc = "~/.zshrc"
        console.print(f"[success]✓ Installed[/] [muted]for {shell_type}.[/]")
        console.print(f"  Run [primary]source {rc}[/] to activate now.")
        if shell_type == "zsh":
            console.print(
                "  [muted]For powerlevel10k: add [/][primary]cc_env[/]"
                "[muted] to POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS in ~/.p10k.zsh[/]"
            )
        elif shell_type == "bash":
            console.print(
                "  [muted]To show the active env in your prompt, add [/]"
                "[primary]$(__cc_env_segment)[/][muted] to your PS1.[/]"
            )
        elif shell_type == "fish":
            console.print(
                "  [muted]To show the active env in your prompt, add [/]"
                "[primary]__cc_env_segment[/][muted] to your fish_right_prompt.[/]"
            )
        return True
