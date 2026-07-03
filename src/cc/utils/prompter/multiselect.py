from typing import Any, List, Set, Tuple, Union

from prompt_toolkit.application import Application
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.widgets import Frame
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.scrollable_pane import ScrollOffsets
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.styles import Style

# Type definitions
OptionValue = Any
Option = Union[AnyFormattedText, Tuple[AnyFormattedText, OptionValue]]
IndexedOption = Tuple[int, AnyFormattedText, OptionValue]


class CheckboxControl(FormattedTextControl):
    def __init__(self, options: List[Option], **kwargs) -> None:
        # Original full list of options
        self.all_options = self._index_options(options)

        # Filter string
        self.filter_text = ""

        # Cursor is relative to the FILTERED list
        self.cursor_index = 0

        # Selected indices refer to the ORIGINAL list indices (option[0])
        self.selected_indices: Set[int] = set()
        self.answered = False

        # Pass _get_cursor_position to the parent constructor to handle scrolling
        super().__init__(self._get_formatted_text, get_cursor_position=self._get_cursor_position, **kwargs)

    @property
    def filtered_options(self) -> List[IndexedOption]:
        """Returns the list of options matching the filter text."""
        if not self.filter_text:
            return self.all_options

        # Simple case-insensitive match on the display text
        return [opt for opt in self.all_options if self.filter_text.lower() in str(opt[1]).lower()]  # opt[1] is name

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
            is_checked = original_idx in self.selected_indices

            # Click handler (needs to know current visual index 'i')
            def mouse_handler(mouse_event, visual_idx=i):
                if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
                    self.cursor_index = visual_idx
                    real_idx = visible_options[visual_idx][0]
                    self.toggle_selection(real_idx)

            # Text style: bold primary when hovered or checked, plain
            # white otherwise — matches env_selector's pattern.
            text_style = "class:col.main" if (is_cursor or is_checked) else "fg:ansiwhite"

            # 1. Pointer
            if is_cursor:
                row_fragments = [("class:pointer", " ❯ ")]
            else:
                row_fragments = [("", "   ")]

            # 2. Checkbox marker
            if is_checked:
                row_fragments.append(("class:checkbox.check", "● "))
            else:
                row_fragments.append(("class:checkbox.square", "○ "))

            # Spacer
            row_fragments.append(("", " "))

            # 3. Content
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
        # ENABLE SCROLLING: Report cursor position to Window
        # We need to account for the filter header lines if present
        offset = 2 if self.filter_text else 0
        return Point(x=0, y=self.cursor_index + offset)

    def toggle_selection(self, original_index=None):
        """Toggle selection. If no index provided, toggles current cursor item."""
        if original_index is not None:
            idx = original_index
        else:
            visible_options = self.filtered_options
            if not visible_options:
                return
            idx = visible_options[self.cursor_index][0]

        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
        else:
            self.selected_indices.add(idx)


class CheckboxPrompt:
    def __init__(self, message: AnyFormattedText = "", options: List[Option] = None, style: Style = None) -> None:
        self.message = message
        self.options = options
        self.style = style
        self.control = None

    def _create_layout(self) -> Layout:
        layout = HSplit(
            [
                Frame(
                    Window(content=self.control, scroll_offsets=ScrollOffsets(top=1, bottom=1)),
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
            # Move up (wrap around list)
            count = len(control.filtered_options)
            if count > 0:
                control.cursor_index = (control.cursor_index - 1) % count

        @kb.add("down", eager=True)
        def _(event):
            # Move down (wrap around list)
            count = len(control.filtered_options)
            if count > 0:
                control.cursor_index = (control.cursor_index + 1) % count

        # Space toggles selection
        @kb.add("space", eager=True)
        def _(event):
            control.toggle_selection()

        @kb.add("enter", eager=True)
        def _(event):
            # Return values of selected indices
            selected_values = [opt[2] for opt in control.all_options if opt[0] in control.selected_indices]
            event.app.exit(result=selected_values)

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

    def prompt(self) -> List[Any]:
        self.control = CheckboxControl(self.options)
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
