import os
from pathlib import Path

# THE version — single source of truth. pyproject.toml reads it statically
# (setuptools dynamic attr), cc --version and the daemon's system.health
# serve it from here. Bump this one line only.
CC_VERSION = "4.0.0"


class Constants:
    def __new__(cls):
        raise TypeError("Constants Class Cannot be Instantiated")

    CC_VERSION = CC_VERSION  # class alias — call sites use Constants.CC_VERSION

    # =========================================================
    # 1. Internal Package Paths (Code, SQL, Templates)
    # =========================================================
    # This file is in: src/cc/utils/constants.py

    # .../src/cc/utils
    PATH_UTILS = os.path.dirname(os.path.abspath(__file__))

    # .../src/cc (The Package Root)
    # We go up ONE level from utils to get to 'cc'
    PATH_PACKAGE_ROOT = os.path.abspath(os.path.join(PATH_UTILS, ".."))

    # Assets inside the package
    # (Ensure you moved these folders into src/cc/)
    PATH_SQL = os.path.join(PATH_PACKAGE_ROOT, "sql")
    PATH_TEMPLATES = os.path.join(PATH_PACKAGE_ROOT, "templates")

    # Shell scripts (If you want them bundled, move 'shell' folder to src/cc/shell)
    # Otherwise, we assume they are installed in a specific system path.
    # For simplicity, let's assume you moved the 'shell' folder into 'src/cc/shell'
    PATH_SHELL = os.path.join(PATH_PACKAGE_ROOT, "shell")
    SHELL_INITDB_PATH = os.path.join(PATH_SHELL, "init-db.sh")

    # =========================================================
    # 2. User Data Paths (Database, Storage)
    # =========================================================
    # We store data in ~/.cc-cli so it survives updates/reinstalls.

    USER_HOME = Path.home()
    PATH_USER_DATA = os.path.join(USER_HOME, ".cc-cli")

    PATH_LOGS = os.path.join(PATH_USER_DATA, "logs")

    # Create the folder if it doesn't exist
    if not os.path.exists(PATH_USER_DATA):
        os.makedirs(PATH_USER_DATA)

    PATH_LOG_FILE = os.path.join(PATH_LOGS, "cc.log")
    PATH_RPC_LOG_FILE = os.path.join(PATH_LOGS, "rpc.log")
    if not os.path.exists(PATH_LOGS):
        os.makedirs(PATH_LOGS)

    # Database & Storage now live in the user's home folder
    CC_DB_NAME = "cc_cli.db"
    SQLITE_DB_PATH = os.path.join(PATH_USER_DATA, CC_DB_NAME)

    # Shell integration
    SHELL_INTEGRATION_PATH = os.path.join(PATH_USER_DATA, "shell", "cc.zsh")
    FISH_INTEGRATION_PATH = os.path.join(PATH_USER_DATA, "shell", "cc.fish")
    SHELL_SOURCE_LINE = f'source "{os.path.join(PATH_USER_DATA, "shell", "cc.zsh")}"  # cc shell integration'
    FISH_SOURCE_LINE = f'source "{os.path.join(PATH_USER_DATA, "shell", "cc.fish")}"  # cc shell integration'

    # Appearance
    SETTING_THEME = "theme"
    SETTING_THEME_PRIMARY = "theme_custom_primary"
    SETTING_THEME_BRANCH = "theme_custom_branch"
    SETTING_THEME_DB = "theme_custom_db"
    SETTING_THEME_SLIDER = "theme_custom_slider"

    # Daemon
    SOCKET_PATH = os.path.join(PATH_USER_DATA, "cc.sock")
    DAEMON_PID_FILE = os.path.join(PATH_USER_DATA, "cc-daemon.pid")

    # SSH Tunnel
    SETTING_SSH_KEY_PATH = "ssh_key_path"
    PATH_TUNNELS = os.path.join(PATH_USER_DATA, "tunnels")

    # Backups
    PATH_BACKUPS = os.path.join(PATH_USER_DATA, "backups")

    # Switch hooks
    PATH_HOOKS = os.path.join(PATH_USER_DATA, "hooks")

    # =========================================================
    # 3. Templates & Configs
    # =========================================================
    TEMPLATE_LAUNCH_JSON_PATH = os.path.join(PATH_TEMPLATES, "launch_template.json")
    SQL_CLEANDB_PATH = os.path.join(PATH_SQL, "clean_database.sql")

    # =========================================================
    # 4. Constants & Strings
    # =========================================================
    # Odoo Terms
    ODOO_ODOO = "odoo"
    ODOO_SH_URL = "https://www.odoo.sh/project"
    ODOO_SH_DOMAIN = ".odoo.sh"
    ODOO_LAUNCH_JSON = "launch.json"
    ODOO_ADDONS = "addons"
    ODOO_ENTERPRISE = "enterprise"
    ODOO_DESIGN_THEMES = "design-themes"
    ODOO_CONFIGURATIONS = "configurations"
    ODOO_NAME = "name"
    ODOO_PROGRAM = "program"
    ODOO_ODOOBIN = "odoo-bin"
    ODOO_ARGS = "args"
    ODOO_ARG_MODULE_UPDATE = "-u"
    ODOO_ARG_MODULE_INSTALL = "-i"
    ODOO_ARG_DATABASE = "-d"
    ODOO_UPGRADE_UTIL = "upgrade-util"  # odoo/upgrade-util — provides src/ for --upgrade-path
    ODOO_UPGRADE = "upgrade"            # odoo/upgrade — provides migrations/ for --upgrade-path
    ODOO_MIGRATIONS = "migrations"
    ODOO_SRC = "src"
    ODOO_MANIFEST = "__manifest__.py"
    ODOO_INIT = "__init__.py"

    # Config Terms
    CONFIG_VERSIONS = "versions"
    CONFIG_DOWNLOAD = "download"
    CONFIG_PATH = "path"

    # Setting Keys
    SETTING_MULTI_VERSION = "multi_version_mode"
    SETTING_RND_AUTO_REBASE = "rnd.auto_rebase"  # rebase R&D branches on switch
    SETTING_TIMESHEET_MODE = "timesheet_mode"  # "auto" (log on switch) | "manual"
    SETTING_TIMESHEET_THRESHOLD = "timesheet_flag_threshold"
    SETTING_TIMESHEET_PROMPT = "timesheet_flag_prompt"
    SETTING_TIMESHEET_EOD = "timesheet_eod"
    SETTING_TIMESHEET_RETENTION_DAYS = "timesheet_retention_days"
    SETTING_AUTO_FETCH = "auto_fetch"
    SETTING_AUTO_FETCH_INTERVAL = "auto_fetch_interval"
    SETTING_ENV_AUTO_STALE_DAYS = "env.auto_stale_days"
    SETTING_ENV_AUTO_STALE_STATUS = "env.auto_stale_status"
    # Odoo layout / integrations (all optional, empty = disabled/default)
    SETTING_INTERNAL_ADDONS = "odoo.internal_addons_dir"  # shared-addons dir probed inside projects
    SETTING_CLEAN_WORDS = "search.clean_words"  # extra comma-separated words stripped in fuzzy matching
    SETTING_TICKET_URL = "ticket.url_template"  # {ticket} placeholder
    SETTING_RUNBOT_URL = "psx.url_template"  # {branch} placeholder

    # IDE Map
    IDE_MAP = {
        "Visual Studio Code": "code",
        "Cursor": "cursor",
    }
