import logging
import subprocess
from typing import Tuple

from cc.base.arm import Project
from cc.base.command import Command
from cc.utils.helpers import Helpers

log = logging.getLogger("CC")


class BranchCommand(Command):
    group = "git"
    name = "branch"
    description = "Change the branch attribute of active/chosen environment."

    def arguments(self):
        arguments = [
            self.Argument(
                ["name"],
                type=str,
                help="Name of the project for which to update the branch for",
                nargs="?",
                complete=Project,
            ),
            self.Argument(
                ["-c", "--checkout"],
                action="store_true",
                help="Checkout the branch in the working directory after updating the record.",
            ),
        ]
        return arguments

    def execute(self):
        log.debug(f"Executing branch command with args: {self.args}")
        name = self.args.name
        project = None

        if name:
            project = self.project.find_by(name=name)
            if not project:
                log.error(f"Cannot find specified project with name: '{name}'")
                return False

        active_proj = project or self.active_project
        if not active_proj:
            log.error("There is no active project.")
            from cc.utils.console import get_console
            get_console().print("[warning]No active project.[/] Run [primary]cc switch <project_alias>[/] first.")
            return False

        log.debug(f"Using project: {active_proj.name}")

        environment = self.project_environment_selector(active_proj)
        if not environment:
            log.error(f"No environment selected for project '{active_proj.name}'. Aborting.")
            return False

        log.debug(f"Selected environment: {environment.name}")

        github_url, branch_name = self._get_branch_details(environment.project_path)

        if not branch_name:
            log.warning("No branch was selected. Aborting update.")
            return False

        from cc.daemon.client import call
        call("env.update_branch", env_id=environment.id, github_url=github_url, branch_name=branch_name)
        from cc.utils.console import get_console
        console = get_console()
        console.print(f"[success]✓ Updated environment '{environment.name}':[/]")
        console.print(f"  [muted]Branch → {branch_name}[/]")
        console.print(f"  [muted]GitHub URL → {github_url or 'N/A'}[/]")

        active_env = self.active_environment
        is_active_in_cwd = active_env and active_env.id == environment.id
        if (self.args.checkout or is_active_in_cwd) and branch_name:
            project_path = environment.project_path
            if project_path:
                console.print(f"[muted]Checking out '{branch_name}' in {project_path}[/]")
                self.run_command(["git", "-C", project_path, "checkout", branch_name])
            else:
                log.warning("No project path — cannot checkout.")

    @staticmethod
    def _get_branch_details(directory: str) -> Tuple[str, str]:
        log.debug(f"Getting git remote URL from: {directory}")
        url = subprocess.run(
            ["git", "-C", directory, "config", "--get", "remote.origin.url"],
            capture_output=True, text=True
        ).stdout.strip()
        log.debug(f"Found remote URL: {url}")

        owner_repo = Helpers.parse_github_remote(url)
        github_url = ""
        if owner_repo:
            github_url = f"https://github.com/{owner_repo}"
            log.debug(f"Parsed GitHub URL: {github_url}")
        else:
            log.warning(f"Could not detect GitHub repository path from URL: {url}")

        branch_name = BranchCommand._branch_selector(directory)
        return github_url, branch_name

    @staticmethod
    def _branch_selector(directory: str) -> str:
        log.debug(f"Fetching remote branches from: {directory}")
        branches_remote = (
            subprocess.run(
                ["git", "-C", directory, "branch", "-r", "--format=%(refname:short)"],
                capture_output=True, text=True
            ).stdout.replace("origin/", "").splitlines()
        )
        log.debug(f"Fetching local branches from: {directory}")
        branches_local = subprocess.run(
            ["git", "-C", directory, "branch", "--format=%(refname:short)"],
            capture_output=True, text=True
        ).stdout.splitlines()

        branches = list(set(branches_local + branches_remote))
        log.debug(f"Found {len(branches)} unique branches. Prompting user.")

        branch_name = BranchCommand.prompter.prompt_autocomplete(
            options=sorted(branches),
            label="Choose a Branch",
        )
        log.debug(f"User selected branch: {branch_name}")
        return branch_name or ""
