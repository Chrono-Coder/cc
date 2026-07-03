import logging

from cc.utils.console import get_console

log = logging.getLogger("CC")


class Spinner:
    """
    Context manager that displays a rich spinner for long operations.

    In debug mode, prints plain log messages instead of animating.

    Usage:
        with Spinner("Processing...", "Success!", "Failed!"):
            # long-running work — on exception, fail_text is shown
    """

    def __init__(
        self,
        text="Loading...",
        success_text="Success!",
        fail_text="Failed.",
        spinner_type="dots",
        debug_mode=False,
    ):
        self.text = text
        self.success_text = success_text
        self.fail_text = fail_text
        self.spinner_type = spinner_type
        self.use_spinner = not debug_mode
        self._status = None
        self._console = get_console()

    def __enter__(self):
        if self.use_spinner:
            self._status = self._console.status(
                f"[primary]{self.text}[/]", spinner=self.spinner_type
            )
            self._status.__enter__()
            log.debug(f"Spinner started: {self.text}")
        else:
            self._console.print(f"[muted]{self.text}[/]")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._status:
            self._status.__exit__(exc_type, exc_value, traceback)
            if exc_type:
                log.debug(f"Spinner failing due to exception: {exc_value}")
                self._console.print(f"[error]✗[/] {self.fail_text}")
            elif self.success_text:
                self._console.print(f"[success]✓[/] {self.success_text}")
        elif not self.use_spinner:
            if exc_type:
                self._console.print(f"[error]✗ {self.fail_text}[/]")
            elif self.success_text:
                self._console.print(f"[success]✓ {self.success_text}[/]")

        return False
