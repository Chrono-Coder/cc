import logging
import os
import subprocess
import webbrowser

from cc.base.arm import Project
from cc.base.command import Command

log = logging.getLogger("CC")


class GithubCommand(Command):
    group = "git"
    name = "github"
    description = "Open the active environment's GitHub repo in a browser."

    def arguments(self):
        arguments = [
            self.Argument(
                ["name"],
                type=str,
                help="Open project GitHub page: cc git github PROJECT_NAME",
                nargs="?",
                complete=Project,
            ),
            self.Argument(
                ["-p", "--path"],
                action="store_true",
                help="Open GitHub page for current path: cc git github -p",
            ),
        ]
        return arguments

    def execute(self):
        log.debug(f"Executing github command with args: {self.args}")
        path = os.getcwd()
        is_active = False

        if project_alias := self.args.name:
            log.debug(f"Project name '{project_alias}' provided. Searching for project.")
            project_id = self.project.find_by(name=project_alias, limit=1)
            if not project_id:
                log.error(f"Project '{project_alias}' not found.")
                return False

            environment = self.project_environment_selector(project_id)
            if not environment:
                log.error(f"No environment selected for project '{project_alias}'.")
                return False

            path = environment.project_path
            log.debug(f"Using path from selected environment: {path}")

        elif self.active_project_path and not self.args.path:
            log.debug("No project name provided, using active project path.")
            path = self.active_project_path
            is_active = True
        else:
            log.debug("No project name and no active project, using current working directory.")

        return self._open_github_for_path(path, is_active)

    def _open_github_for_path(self, path: str, is_active: bool = False) -> bool:
        """
        Gets the GitHub remote URL for a given path, parses it, and opens it.
        """
        parsed_url = None
        if is_active:
            parsed_url = f"{self.active_environment.github_url}/tree/{self.active_environment.branch_name}"
        else:
            parsed_url = self._parse_github_url_from_path(path)
        if not parsed_url:
            from cc.utils.console import get_console
            get_console().print("[warning]Failed to parse path for GitHub URL.[/]")
            return False

        from cc.utils.console import get_console
        get_console().print(f"[muted]Opening URL in browser: {parsed_url}[/]")
        try:
            if not webbrowser.open(parsed_url):
                log.warning("webbrowser.open() returned False. Could not determine how to open the URL.")
                return False
            return True
        except Exception as e:
            log.error(f"Failed to open web browser: {e}")
            return False

    def _parse_github_url_from_path(self, path: str) -> str:
        log.debug(f"Attempting to open GitHub page for path: {path}")

        if not self.Helpers.git_is_repo(path):
            log.error(f"The path '{path}' is not a valid git repository.")
            return False

        try:
            log.debug("Running 'git remote get-url origin'")
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
            )
            raw_url = result.stdout.strip()
            log.debug(f"Raw remote URL: {raw_url}")
        except FileNotFoundError:
            log.error("Error: 'git' command not found. Is git installed and in PATH?")
            return False
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to get remote URL for 'origin' in '{path}'.")
            error_message = e.stderr.strip()
            if error_message:
                log.error(f"Git error: {error_message}")
            else:
                log.error("Does the 'origin' remote exist?")
            return False
        except Exception as e:
            log.error(f"An unexpected error occurred while getting git remote: {e}")
            return False

        owner_repo = self.Helpers.parse_github_remote(raw_url)
        if not owner_repo:
            log.error(f"Failed to parse GitHub URL from remote: {raw_url}")
            return False
        parsed_url = f"https://github.com/{owner_repo}"
        log.debug(f"Parsed GitHub URL: {parsed_url}")
        return parsed_url
