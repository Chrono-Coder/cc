import logging
import logging.handlers
import os

from rich.logging import RichHandler

from cc.utils.console import get_console, get_error_console
from cc.utils.constants import Constants


class LevelFilter(logging.Filter):
    """Filters log records to those with a level in the specified list."""

    def __init__(self, levels):
        super().__init__()
        self.levels = set(levels)

    def filter(self, record):
        return record.levelno in self.levels


class _CCConsoleHandler(logging.Handler):
    """Themed console handler for normal-mode cc output.

    INFO  → stdout, plain message body, no prefix (keeps `cc switch` output clean)
    WARN+ → stderr, styled `LEVEL:` prefix + plain message body

    Diagnostics go to stderr so a command's stdout stays a clean, pipeable
    data stream. Message bodies are printed with markup=False so log strings
    containing `[401]`, `[args]`, etc. don't collide with rich's markup parser.
    """

    _LEVEL_STYLE = {
        logging.WARNING:  "warning",
        logging.ERROR:    "error",
        logging.CRITICAL: "bold error",
    }

    def emit(self, record):
        try:
            msg = record.getMessage()
            if record.levelno >= logging.WARNING:
                console = get_error_console()
                style = self._LEVEL_STYLE.get(record.levelno, "error")
                console.print(f"[{style}]{record.levelname}:[/]", end=" ")
            else:
                console = get_console()
            console.print(msg, markup=False, highlight=False)
        except Exception:
            self.handleError(record)


def setup_logging(debug_mode=False):
    """Set up the 'CC' logger.

    File handler stays plain text (RotatingFileHandler) so `cc daemon logs` and
    external tailers can parse it. Console handler is RichHandler in
    debug mode (timestamp + level + path, themed) and the lightweight
    _CCConsoleHandler in normal mode (clean INFO, prefixed WARN+).
    """
    logger = logging.getLogger("CC")
    logger.setLevel(logging.DEBUG)

    os.makedirs(Constants.PATH_LOGS, exist_ok=True)
    log_file = Constants.PATH_LOG_FILE

    if logger.hasHandlers():
        logger.handlers.clear()

    # Include filename:lineno so `cc daemon logs` can render the same path column
    # RichHandler shows in `cc -d` debug mode.
    verbose_file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1 * 1024 * 1024, backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(verbose_file_formatter)
    logger.addHandler(file_handler)

    if debug_mode:
        # Debug: RichHandler with full metadata + pretty tracebacks.
        # markup=False protects against user-content bracket collisions.
        console_handler = RichHandler(
            console=get_console(),
            show_time=True,
            show_level=True,
            show_path=True,
            markup=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            omit_repeated_times=False,
            log_time_format="%H:%M:%S",
        )
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)
        logger.debug("Debug mode activated. Console logging is verbose and colored.")
    else:
        console_handler = _CCConsoleHandler()
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    logger.propagate = False


def setup_rpc_logging():
    """
    Sets up the dedicated 'RPC' logger.

    Writes sanitized RPC call logs to ~/.cc-cli/logs/rpc.log.
    Separate from the main CC logger so RPC traffic can be tailed independently.
    """
    rpc_logger = logging.getLogger("RPC")
    rpc_logger.setLevel(logging.DEBUG)

    if rpc_logger.hasHandlers():
        rpc_logger.handlers.clear()

    os.makedirs(Constants.PATH_LOGS, exist_ok=True)

    rpc_formatter = logging.Formatter("%(asctime)s  %(message)s")

    max_bytes = 2 * 1024 * 1024  # 2 MB
    backup_count = 3
    rpc_handler = logging.handlers.RotatingFileHandler(
        Constants.PATH_RPC_LOG_FILE, maxBytes=max_bytes, backupCount=backup_count
    )
    rpc_handler.setLevel(logging.DEBUG)
    rpc_handler.setFormatter(rpc_formatter)
    rpc_logger.addHandler(rpc_handler)

    rpc_logger.propagate = False
