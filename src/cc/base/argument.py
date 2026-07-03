class Argument:
    def __init__(
        self,
        names,
        type=str,
        help=None,
        default=None,
        required=False,
        action=None,
        nargs=None,
        choices=None,
        complete=None,
        autocompletions=None,
        metavar=None,
    ):
        """
        A simple class to encapsulate the properties of an argument.

        Parameters
        ----------
        - name: the name or flag for the argument (e.g., '--verbose' or 'message').
        - type: the expected type of the argument (e.g., str, int).
        - help: the help text to describe the argument.
        - default: the default value if the argument is not provided.
        - required: whether the argument is mandatory (for optional arguments).
        - action: special actions such as 'store_true' for flags.

        """
        self.names = names
        self.type = type
        self.help = help
        self.default = default
        self.required = required
        self.action = action
        self.nargs = nargs
        self.choices = choices
        # What this arg completes to (ORM entity class, literal tuple, or CompleteKind); read by cc.completion.spec, stored as `cc_complete`.
        self.complete = complete
        self.autocompletions = autocompletions or []
        self.metavar = metavar

    def add_to_parser(self, parser):
        """Adds this argument to the given parser."""
        kwargs = {
            "type": self.type,
            "help": self.help,
            "default": self.default,
            "required": self.required,
            "action": self.action,
            "nargs": self.nargs,
            "choices": self.choices,
        }
        if self.metavar is not None:
            kwargs["metavar"] = self.metavar

        if any(name.startswith("--") or name.startswith("-") for name in self.names):
            # Optional argument (flag)
            if self.action == "store_true":
                kwargs.pop("type", None)
                kwargs.pop("nargs", None)
                kwargs.pop("choices", None)
                parser.add_argument(
                    *self.names,
                    **kwargs,
                )
            else:
                action = parser.add_argument(
                    *self.names,
                    **kwargs,
                )
                action.cc_complete = self.complete

        else:
            # Positional argument — keep `default` (a nargs="?" positional like the
            # workspace/env/project `action` arg relies on it, e.g. default="list").
            action = parser.add_argument(
                self.names[0], type=self.type, help=self.help,
                nargs=self.nargs, choices=self.choices, default=self.default,
            )
            action.cc_complete = self.complete
