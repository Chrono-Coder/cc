from cc.base.command import Command
from cc.completion.kinds import CompleteKind


class HelpCommand(Command):
    name = "help"
    description = "Show cc usage and the command list, or help for one command: cc help switch"

    def arguments(self):
        return [
            self.Argument(
                ["topic"],
                type=str,
                nargs="?",
                help="Command to show detailed help for (e.g. cc help switch).",
                complete=CompleteKind.COMMAND,
            ),
        ]

    def execute(self):
        # `cc help` was advertised in the welcome banner but never existed —
        # it errored out as an invalid choice. This makes it real.
        topic = getattr(self.args, "topic", None)
        if topic:
            sub = Command.subparsers.choices.get(topic)
            if sub is not None:
                sub.print_help()
                return True
            from cc.utils.console import get_error_console
            get_error_console().print(f"[warning]Unknown command '{topic}'.[/]")
            return False
        Command.parser.print_help()
        return True
