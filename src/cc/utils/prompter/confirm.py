from prompt_toolkit.application import Application
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style


class ConfirmationControl(FormattedTextControl):
    def __init__(self, message: str, default: bool = True, **kwargs):
        self.message = message
        self.selected_val = default
        self.box_width = max(len(message) + 8, 30)
        super().__init__(self._get_formatted_text, **kwargs)

    def _get_formatted_text(self):
        w = self.box_width
        title = f" {self.message} "
        inner = w - 2  # width between corner chars

        # Center the title on the top border
        pad = inner - len(title)
        left_pad = pad // 2
        right_pad = pad - left_pad

        b = "class:frame.border"
        q = "class:question"

        tokens = []

        # Top border with title
        tokens.append((b, "╭" + "─" * left_pad))
        tokens.append((q, title))
        tokens.append((b, "─" * right_pad + "╮\n"))

        # Content row
        tokens.append((b, "│"))
        tokens.append(("", "  "))
        if self.selected_val:
            tokens.append(("class:checkbox-selected", " Yes "))
        else:
            tokens.append(("", " Yes "))
        tokens.append(("", "   "))
        if not self.selected_val:
            tokens.append(("class:checkbox-selected", " No "))
        else:
            tokens.append(("", " No "))
        # Pad remainder
        content_used = 2 + 5 + 3 + 4  # "  " + " Yes " + "   " + " No "
        tokens.append(("", " " * max(0, inner - content_used)))
        tokens.append((b, "│\n"))

        # Bottom border
        tokens.append((b, "╰" + "─" * inner + "╯"))

        return FormattedText(tokens)

    def toggle(self):
        self.selected_val = not self.selected_val


class ConfirmationPrompt:
    def __init__(self, message: str, default: bool = False, style: Style = None):
        self.message = message
        self.default = default
        self.style = style
        self.control = None

    def prompt(self) -> bool:
        self.control = ConfirmationControl(self.message, self.default)

        layout = HSplit([
            Window(height=3, content=self.control),
        ])

        kb = KeyBindings()

        @kb.add("left")
        @kb.add("right")
        @kb.add("tab")
        def _(event):
            self.control.toggle()

        @kb.add("enter")
        @kb.add("space")
        def _(event):
            event.app.exit(result=self.control.selected_val)

        @kb.add("c-c")
        def _(event):
            event.app.exit(result=None)

        app = Application(
            layout=Layout(layout), key_bindings=kb, style=self.style, full_screen=False,
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
