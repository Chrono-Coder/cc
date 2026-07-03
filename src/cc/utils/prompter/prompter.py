import logging
import os
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional

from prompt_toolkit import prompt
from prompt_toolkit.completion import FuzzyWordCompleter, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style

from .confirm import ConfirmationPrompt
from .multiselect import CheckboxPrompt
from .select import RadioListPrompt

log = logging.getLogger("CC")

# ─────────────────────────────────────────────────────────────
# 1. Generic Configuration & Styles
# ─────────────────────────────────────────────────────────────


def build_prompter_style(
    primary: str = "ansicyan",
    accent: str = "ansiyellow",
    branch: str = "ansiyellow",
    db: str = "#F4845F",
    slider: str = "ansiyellow",
) -> Style:
    return Style.from_dict(
        {
            # --- Basic UI ---
            "pointer": f"{slider} bold",
            "message": f"fg:{primary} bold",
            "label": "noinherit",
            "question": f"fg:{primary} bold",
            "selected-option": "underline",
            # --- Row Content Styles ---
            "key": f"fg:{primary} bold",
            "value": "",
            # --- Data Columns ---
            "col.main": f"fg:{primary} bold",
            "col.accent": f"fg:{accent}",
            "col.secondary": "fg:ansired",
            "col.success": "fg:ansigreen",
            "col.branch": f"fg:{branch}",
            "col.db": f"fg:{db}",
            "col.label": f"fg:{primary}",
            # --- Autocomplete Menu ---
            "completion-menu": "bg:ansibrightblack fg:white",
            "completion-menu.completion.current": f"bg:{primary} fg:black bold",
            # --- Checkbox / Radio UI ---
            "checkbox.square": f"fg:{primary}",
            "checkbox.check": f"fg:{primary} bold",
            "checkbox.checked-text": "bold ",
            # Highlight Bar
            "checkbox-selected": f"bg:{primary} fg:black bold",
            "scrollbar.background": "bg:ansibrightblack",
            "scrollbar.button": f"bg:{primary}",
            "frame.border": f"fg:{primary}",
            "frame.label": f"fg:{primary} bold",
        }
    )


PROMPTER_STYLE = build_prompter_style()


def update_prompter_style(theme_name: str) -> None:
    from cc.utils.colors import THEMES
    global PROMPTER_STYLE
    palette = THEMES.get(theme_name, THEMES["default"])
    PROMPTER_STYLE = build_prompter_style(
        primary=palette.get("PT_PRIMARY", "ansicyan"),
        accent=palette.get("PT_BRANCH", "ansiyellow"),
        branch=palette.get("PT_BRANCH", "ansiyellow"),
        db=palette.get("PT_DB", "#F4845F"),
        slider=palette.get("PT_SLIDER", palette.get("PT_BRANCH", "ansiyellow")),
    )

# ─────────────────────────────────────────────────────────────
# 2. Prompter Class
# ─────────────────────────────────────────────────────────────


class _PathCompleter(PathCompleter):
    """PathCompleter that also expands ``$VAR`` before matching.

    The base completer handles ``~`` (expanduser) and absolute / CWD-relative
    paths, but not env vars — so ``$HOME/...`` completed to nothing. Expanding
    vars here makes them navigable; expansion only changes the directory prefix,
    never the basename being completed, so completion offsets stay valid against
    the user's raw (unexpanded) text.
    """

    def get_completions(self, document, complete_event):
        expanded = os.path.expandvars(document.text_before_cursor)
        if expanded != document.text_before_cursor:
            document = Document(expanded, len(expanded))
        yield from super().get_completions(document, complete_event)


class Prompter:

    @staticmethod
    def _is_interactive(interactive_mode: bool = True) -> bool:
        return interactive_mode and sys.stdin.isatty()

    @staticmethod
    def _format_row(data_dict: Dict[str, str], columns: List[Dict[str, Any]]) -> FormattedText:
        """
        Internal helper: Paints a single row with split styling for Key and Value.
        """
        formatted_parts = []

        for col in columns:
            key = col["key"]
            width = col.get("width", 0)

            key_text = key.capitalize() + ": "
            val_text = str(data_dict.get(key, ""))

            if width > 0:
                remaining_width = max(0, width - len(key_text))
                val_block = f"{val_text:<{remaining_width}}"
            else:
                val_block = f"{val_text} "
            is_name_key = key_text.strip() == "Name:"
            if not is_name_key:
                formatted_parts.append(("class:key", key_text))
                formatted_parts.append(("class:value", val_block))
            else:
                formatted_parts.append(("class:key", val_block))

        return FormattedText(formatted_parts)

    @staticmethod
    def _formatted_to_plain(ft: FormattedText) -> str:
        """
        Converts FormattedText tuples back to a plain string
        so the Autocompleter can use it for matching.
        """
        return "".join(item[1] for item in ft)

    @staticmethod
    def prompt_input_multi(
        options: Iterable[Any],
        label: str,
        columns: Optional[List[Dict[str, Any]]] = None,
        format_func: Optional[Callable[[Any], Dict[str, str]]] = None,
        interactive_mode: bool = True,
    ):
        """
        Generic multi-choice selector (Single Select).
        Uses RadioListPrompt for styling.
        """
        if not Prompter._is_interactive(interactive_mode):
            # Never guess in scripts/CI: auto-picking the first option turned
            # `echo | cc db drop -y` into "drop the first database".
            log.error(f"Interactive selection required ('{label}') but stdin is not a TTY.")
            return False

        options_list = list(options)
        if not options_list:
            log.warning("prompt_input_multi called with no options.")
            return False

        if columns is None:
            columns = [{"key": "name"}]

        prompt_options = []
        for opt in options_list:
            raw_data = format_func(opt) if format_func else {"name": str(opt)}
            formatted_row = Prompter._format_row(raw_data, columns)
            prompt_options.append((formatted_row, opt))

        full_message = FormattedText([("class:message", f" {label} ")])
        p = RadioListPrompt(message=full_message, options=prompt_options, style=PROMPTER_STYLE)

        return p.prompt()

    @staticmethod
    def prompt_autocomplete(
        options: Iterable[Any],
        label: str,
        columns: Optional[List[Dict[str, Any]]] = None,
        format_func: Optional[Callable[[Any], Dict[str, str]]] = None,
        interactive_mode: bool = True,
        default: Optional[str] = None,
    ):
        """
        Autocomplete selection (Type to filter).
        Supports both simple string lists AND structured objects.
        """
        if not Prompter._is_interactive(interactive_mode):
            # Never guess in scripts/CI (see prompt_input_multi).
            log.error(f"Interactive selection required ('{label}') but stdin is not a TTY.")
            return False

        options_list = list(options)
        if not options_list:
            log.warning("prompt_autocomplete called with no options.")
            return False

        choice_map = {}
        completer_words = []

        for opt in options_list:
            if columns:
                raw_data = format_func(opt) if format_func else {"name": str(opt)}
                formatted_row = Prompter._format_row(raw_data, columns)
                display_str = Prompter._formatted_to_plain(formatted_row)
            else:
                display_str = str(opt)

            choice_map[display_str] = opt
            completer_words.append(display_str)

        # WORD=True so the whole space-free token counts as one word. With the
        # default (False), prompt_toolkit treats "-" (and other symbols) as a word
        # boundary, so typing past a dash (e.g. "master-l10n…") only matches the
        # fragment after it and completion appears to break.
        completer = FuzzyWordCompleter(completer_words, WORD=True)

        try:
            result_text = prompt(
                FormattedText([("class:message", f"{label}\n> ")]),
                completer=completer,
                complete_style=CompleteStyle.MULTI_COLUMN,
                style=PROMPTER_STYLE,
                default=str(default) if default else "",
            )
            return choice_map.get(result_text, result_text)
        except (KeyboardInterrupt, EOFError):
            return False

    @staticmethod
    def prompt_input_single(label: str, default: Optional[str] = None, interactive_mode: bool = True):
        if not Prompter._is_interactive(interactive_mode):
            return default
        try:
            result = prompt(
                message=FormattedText([("class:message", f"{label}: ")]),
                default=str(default) if default else "",
                style=PROMPTER_STYLE,
            )
        except (KeyboardInterrupt, EOFError):
            return False
        return result.strip() if result else default

    @staticmethod
    def prompt_input_path(
        label: str,
        default: Optional[str] = None,
        *,
        must_exist: bool = False,
        kind: str = "dir",
        allow_empty: bool = False,
        interactive_mode: bool = True,
    ):
        """Prompt for a filesystem path with Tab-completion and ~/$VAR expansion.

        `kind` ("dir" | "file" | "any") drives both completion and validation.
        With `must_exist`, a path that doesn't exist is rejected and re-prompted
        (up to 3 tries, then returns the default). `allow_empty` lets the user
        skip with an empty entry (returns ""). Returns False on Ctrl+C.
        """
        if not Prompter._is_interactive(interactive_mode):
            return default

        completer = _PathCompleter(expanduser=True, only_directories=(kind == "dir"))

        for _ in range(3):
            try:
                result = prompt(
                    message=FormattedText([("class:message", f"{label}: ")]),
                    default=str(default) if default else "",
                    completer=completer,
                    complete_while_typing=False,
                    style=PROMPTER_STYLE,
                )
            except (KeyboardInterrupt, EOFError):
                return False

            raw = result.strip() if result else ""
            if not raw:
                return "" if allow_empty else default

            expanded = os.path.expandvars(os.path.expanduser(raw))
            if not must_exist:
                return expanded

            ok = (
                os.path.isdir(expanded) if kind == "dir"
                else os.path.isfile(expanded) if kind == "file"
                else os.path.exists(expanded)
            )
            if ok:
                return expanded

            from cc.utils.console import get_console
            what = "directory" if kind == "dir" else "file" if kind == "file" else "path"
            get_console().print(f"  [error]No such {what}:[/] {expanded}")

        return default

    @staticmethod
    def prompt_confirm(message: str, default: bool = False, interactive_mode: bool = True) -> bool:
        if not Prompter._is_interactive(interactive_mode):
            return default

        # Use new Horizontal ConfirmationPrompt
        p = ConfirmationPrompt(message, default, style=PROMPTER_STYLE)
        result = p.prompt()

        # If user aborts (ctrl-c), result is None.
        # We return the default value to be safe, or you can handle differently.
        if result is None:
            return default

        return result

    @staticmethod
    def prompt_checkbox(
        options: Iterable[Any],
        label: str,
        columns: Optional[List[Dict[str, Any]]] = None,
        format_func: Optional[Callable[[Any], Dict[str, str]]] = None,
        interactive_mode: bool = True,
    ) -> List[Any]:

        if not Prompter._is_interactive(interactive_mode):
            # Never guess in scripts/CI (see prompt_input_multi).
            log.error(f"Interactive selection required ('{label}') but stdin is not a TTY.")
            return []

        options_list = list(options)
        if not options_list:
            return []

        if columns is None:
            columns = [{"key": "name"}]

        prompt_options = []
        for opt in options_list:
            raw_data = format_func(opt) if format_func else {"name": str(opt)}
            formatted_row = Prompter._format_row(raw_data, columns)
            prompt_options.append((formatted_row, opt))

        full_message = FormattedText(
            [("class:message", f"{label} "), ("class:col.label", "(Space to toggle, Enter to confirm)")]
        )

        p = CheckboxPrompt(message=full_message, options=prompt_options, style=PROMPTER_STYLE)

        result = p.prompt()
        return result if result is not None else []
