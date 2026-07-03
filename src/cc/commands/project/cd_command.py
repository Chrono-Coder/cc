import logging

from cc.base.arm import Environment
from cc.base.command import Command

log = logging.getLogger("CC")


class CdCommand(Command):
    name = "cd"
    description = "Change directory to the active environment's project path."

    def arguments(self):
        return [
            self.Argument(
                ["name"],
                help="Environment name to cd into.",
                nargs="?",
                complete=Environment,
                type=str,
            ),
            self.Argument(
                ["-c", "--cwd"],
                help="cd to the active environment for the current working directory (old default).",
                action="store_true",
            ),
        ]

    def execute(self):
        log.debug(f"Executing cd command with args: {self.args}")

        if self.args.name:
            return self._cd_to_named(self.args.name)

        if self.args.cwd:
            return self._cd_to_active()

        return self._cd_picker()

    def _cd_to_named(self, name: str) -> bool:
        matches = self.environment.search([("name", "=", name)])
        if not matches:
            log.error(f"Environment '{name}' not found.")
            return False
        # Names are non-unique — on a collision, ask which project rather than
        # silently cd-ing into whichever the ORM returned first.
        environment = matches[0] if len(matches) == 1 else self._pick_by_project(matches)
        if not environment:
            return False
        self.exec_sh_command(f"cd {environment.project_path}")
        return True

    def _cd_to_active(self) -> bool:
        environment = self.active_environment
        path = environment.project_path if environment else self.active_project_path
        if not path:
            log.error("No active environment found.")
            return False
        self.exec_sh_command(f"cd {path}")
        return True

    def _cd_picker(self) -> bool:
        from cc.base.arm.app_state import AppState
        from cc.base.db import database_connection_manager
        from cc.services.dto import EnvDetailDTO
        from cc.utils.prompter.env_selector import EnvSelectorTUI
        from cc.utils.prompter.prompter import PROMPTER_STYLE

        # Build (EnvDetailDTO, project_path) pairs from active AppState slots
        pairs: list[tuple[EnvDetailDTO, str]] = []
        with database_connection_manager():
            for state in AppState.search([]):
                env = state.environment_id
                if not env:
                    continue
                version = env.version_id
                project = env.project_id
                db = env.database_id
                dto = EnvDetailDTO(
                    id=env.id,
                    name=env.name,
                    project_name=project.name if project else "",
                    branch_name=env.branch_name or "",
                    database=db.name if db else None,
                    last_used_at=str(env.last_used_at) if env.last_used_at else None,
                    version_id=version.id if version else None,
                    version_name=version.name if version else "",
                )
                pairs.append((dto, env.project_path or ""))

        if not pairs:
            log.error("No active environments found.")
            return False

        if len(pairs) == 1:
            self.exec_sh_command(f"cd {pairs[0][1]}")
            return True

        path_map = {dto.id: path for dto, path in pairs}
        envs = [dto for dto, _ in pairs]
        active = self.active_environment
        selected = EnvSelectorTUI(
            environments=envs,
            project_name="",
            active_env_id=active.id if active else None,
            style=PROMPTER_STYLE,
        ).run()

        if not selected:
            return False

        self.exec_sh_command(f"cd {path_map[selected.id]}")
        return True
