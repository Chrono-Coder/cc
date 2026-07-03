from typing import Any, List, Tuple, Union

from prompt_toolkit.application import Application
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.scrollable_pane import ScrollOffsets
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame

# Type definitions
OptionValue = Any
Option = Union[AnyFormattedText, Tuple[AnyFormattedText, OptionValue]]
IndexedOption = Tuple[int, AnyFormattedText, OptionValue]


class RadioListControl(FormattedTextControl):
    def __init__(self, options: List[Option], **kwargs) -> None:
        # Original full list of options
        self.all_options = self._index_options(options)

        # Filter string
        self.filter_text = ""

        # Cursor is relative to the FILTERED list
        self.cursor_index = 0

        self.answered = False

        super().__init__(self._get_formatted_text, get_cursor_position=self._get_cursor_position, **kwargs)

    @property
    def filtered_options(self) -> List[IndexedOption]:
        """Returns the list of options matching the filter text."""
        if not self.filter_text:
            return self.all_options

        # Simple case-insensitive match on the display text
        return [opt for opt in self.all_options if self.filter_text.lower() in str(opt[1]).lower()]  # opt[1] is name

    @property
    def options_count(self) -> int:
        return len(self.filtered_options)

    def _index_options(self, options) -> List[IndexedOption]:
        """Normalize options into (index, name, value) tuples."""
        indexed_options = []
        for idx, opt in enumerate(options):
            if isinstance(opt, (str, int, float)):
                indexed_options.append((idx, str(opt), opt))
            elif isinstance(opt, tuple) and len(opt) == 2:
                indexed_options.append((idx, opt[0], opt[1]))
            else:
                indexed_options.append((idx, opt, opt))
        return indexed_options

    def _get_formatted_text(self):
        result = []

        # Show Filter Status
        if self.filter_text:
            result.append(("class:col.accent", f"Filter: {self.filter_text}\n"))
            result.append(("", "----------------\n"))

        visible_options = self.filtered_options

        # Safety check for cursor
        if self.cursor_index >= len(visible_options):
            self.cursor_index = max(0, len(visible_options) - 1)

        for i, (original_idx, name, value) in enumerate(visible_options):
            is_cursor = i == self.cursor_index

            def mouse_handler(mouse_event, visual_idx=i):
                if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
                    self.cursor_index = visual_idx

            # Text style: bold primary when hovered, plain white otherwise
            # — matches env_selector's pattern.
            text_style = "class:col.main" if is_cursor else "fg:ansiwhite"

            # 1. Pointer
            if is_cursor:
                row_fragments = [("class:pointer", " ❯ ")]
            else:
                row_fragments = [("", "   ")]

            # Spacer
            row_fragments.append(("", " "))

            # 2. Content
            if isinstance(name, list):
                for col_style, col_text, *rest in name:
                    combined_style = f"{col_style} {text_style}".strip()
                    row_fragments.append((combined_style, col_text))
            else:
                row_fragments.append((text_style, str(name)))

            result.extend((s, t, mouse_handler) for s, t, *rest in row_fragments)
            result.append(("", "\n"))

        if not visible_options:
            result.append(("class:col.label", "  No matches found.\n"))

        return result

    def _get_cursor_position(self, document=None) -> Point:
        # ENABLE SCROLLING
        # Account for filter header offset
        offset = 2 if self.filter_text else 0
        return Point(x=0, y=self.cursor_index + offset)


class RadioListPrompt:
    def __init__(self, message: AnyFormattedText = "", options: List[Option] = None, style: Style = None) -> None:
        self.message = message
        self.options = options
        self.style = style
        self.control = None

    def _create_layout(self) -> Layout:
        layout = HSplit(
            [
                Frame(
                    Window(
                        content=self.control,
                        height=Dimension(min=1, max=5),
                        scroll_offsets=ScrollOffsets(top=1, bottom=1),
                    ),
                    title=self.message,
                ),
            ]
        )
        return Layout(layout)

    def _create_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()
        control = self.control

        @kb.add("c-c", eager=True)
        def _(event):
            event.app.exit(result=None)

        @kb.add("up", eager=True)
        def _(event):
            count = len(control.filtered_options)
            if count > 0:
                control.cursor_index = (control.cursor_index - 1) % count

        @kb.add("down", eager=True)
        def _(event):
            count = len(control.filtered_options)
            if count > 0:
                control.cursor_index = (control.cursor_index + 1) % count

        @kb.add("enter", eager=True)
        @kb.add("space", eager=True)
        def _(event):
            visible_options = control.filtered_options
            if visible_options:
                selected_option = visible_options[control.cursor_index]
                event.app.exit(result=selected_option[2])

        @kb.add("backspace")
        def _(event):
            control.filter_text = control.filter_text[:-1]
            control.cursor_index = 0

        # Catch-all for typing characters to filter
        @kb.add("<any>")
        def _(event):
            char = event.data
            if char and len(char) == 1 and char.isprintable():
                control.filter_text += char
                control.cursor_index = 0

        return kb

    def prompt(self) -> Any:
        self.control = RadioListControl(self.options)
        app = Application(
            layout=self._create_layout(),
            key_bindings=self._create_key_bindings(),
            style=self.style,
            full_screen=False,
            mouse_support=True,
            cursor=CursorShape._NEVER_CHANGE,
        )
        import sys
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()
        app.output.show_cursor = lambda: None
        try:
            result = app.run()
        finally:
            app.renderer.erase()
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()
        return result
