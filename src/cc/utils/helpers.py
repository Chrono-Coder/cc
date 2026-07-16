import fnmatch
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict, deque
from typing import List, Optional

from .constants import Constants

log = logging.getLogger("CC")

PROJECT_SEARCH_CUTOFF = 0.6

# Set once we've kicked a cold-cache reconcile, so the fallback fires at most once per process.
_db_cache_reconciled = False


class Helpers:
    def __new__(cls):
        raise TypeError("Helpers Class Cannot be Instantiated")

    @staticmethod
    def parse_github_remote(url: str) -> Optional[str]:
        """Parse a git remote URL and return 'owner/repo', or None."""
        match = re.match(
            r"^(?:https://|git@)([^/:]+)(?:-[^/:]+)?[:/]([^/]+)/(.+?)(?:\.git)?$",
            url,
        )
        if not match:
            return None
        domain = re.sub(r"github\.com-.*", "github.com", match.group(1).split(":")[0])
        if "github" not in domain:
            return None
        return f"{match.group(2)}/{match.group(3)}"

    @staticmethod
    def search_str(search_space: list, pattern: str, n: int = 5) -> list:
        """
        Finds strings in a search space that match a given glob pattern.
        The pattern supports wildcards, e.g., 'proj*' matches 'project1'.

        :param search_space: A list of strings to search within.
        :param pattern: The glob pattern to match against.
        :param n: The maximum number of matches to return.
        :return: A list of matching strings.
        """
        pattern = f"*{pattern}*"
        if not pattern or not search_space:
            return []

        matches = []
        # Use fnmatch to find all items that match the glob-style pattern
        for item in search_space:
            if fnmatch.fnmatch(item.lower(), pattern.lower()):
                matches.append(item)
        return matches[:n] if n else matches

    @staticmethod
    def clean_word(word, clean=None, alpha_numeric=True, alphabetic=False):
        clean = clean or {}
        cleaned_word = word
        for clean_item in clean:
            cleaned_word = cleaned_word.replace(clean_item, "")

        if alphabetic:
            cleaned_word = re.sub(r"[^a-zA-Z]", "", cleaned_word)
        elif alpha_numeric:
            cleaned_word = re.sub(r"[^a-zA-Z]", "", cleaned_word)

        return cleaned_word

    @staticmethod
    def listdir(path):
        try:
            return [dir.name for dir in os.scandir(path) if dir.is_dir() and not dir.name.startswith(".")]
        except FileNotFoundError:
            log.warning(f"listdir failed: Path not found {path}")
            return []

    @staticmethod
    def search_subdir_file(
        parent_dir,
        name,
        is_file,
        max_depth=3,
        banned_dirs=False,
        ignore_words=False,
        file_type=False,
        n=1,
        strict=True,
        skips=0,
        cutoff=0.6,
        total_cutoff=1,
        clean=False,
    ):
        """
        parent_dir: dir to search inside
        ... (rest of docstring) ...
        """

        # === Methods === #
        def _ensure_file_type(val, type):
            if type and not type.startswith("."):
                type = f".{type}"

            name_without_ext, ext = os.path.splitext(val)
            if type and ext != type:
                val = f"{name_without_ext}{type}"
            return val

        # === Checks === #
        if isinstance(parent_dir, list):
            parent_dir = parent_dir and parent_dir[0]

        if not parent_dir or not os.path.isdir(parent_dir) or not name:
            log.debug(f"search_subdir_file: Invalid input. parent_dir: {parent_dir}, name: {name}")
            return []

        if is_file:
            name = _ensure_file_type(name, file_type)

        banned_dirs = banned_dirs or set()
        ignore_words = ignore_words or set()
        clean = clean or set()

        log.debug(
            f"Starting search for {'file' if is_file else 'dir'} '{name}' in '{parent_dir}'"
            f" (depth: {max_depth}, strict: {strict})"
        )

        # === Data Preparation === #
        data = []
        queue = deque([(parent_dir, 0)])

        while queue:
            current_dir, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue

            try:
                files = (
                    [
                        entry.name
                        for entry in os.scandir(current_dir)
                        if entry.is_file() and (not file_type or os.path.splitext(entry.name)[1] == file_type)
                    ]
                    if is_file
                    else []
                )
                subdirs = [
                    entry.name for entry in os.scandir(current_dir) if entry.is_dir() and entry.name not in banned_dirs
                ]
            except PermissionError:
                log.debug(f"Permission denied while scanning: {current_dir}")
                continue  # Skip directories without permission
            except FileNotFoundError:
                log.debug(f"Directory not found during scan (possibly a broken symlink): {current_dir}")
                continue

            data.append((current_dir, files if is_file else subdirs))
            if subdirs:
                queue.extend((os.path.join(current_dir, d), depth + 1) for d in subdirs)  # Append next level

        # === Not Strict === #
        if not strict:
            names_path_dict = defaultdict(list)
            for dirpath, names in data:
                for entry in names:
                    names_path_dict[entry].append(dirpath)

            matches = Helpers.search_str(names_path_dict.keys(), os.path.splitext(name)[0])
            res = []
            for match in matches:
                for path in names_path_dict[match]:
                    if len(res) > n:
                        log.debug(f"Found non-strict matches: {res}")
                        return res
                    res.append(os.path.join(path, match))

            log.debug(f"Found non-strict matches: {res}")
            return res

        # === Strict === #
        count_skip = 0
        paths = []
        for dirpath, names in data:
            if name in names:
                if count_skip < skips:
                    count_skip += 1
                    continue
                paths.append(os.path.join(dirpath, name))
            if len(paths) >= n:
                log.debug(f"Found strict matches: {paths}")
                return paths

        log.debug(f"Found strict matches: {paths}")
        return paths

    @staticmethod
    def parse_odoo_remotes(remote_v_output: str) -> tuple:
        """Parse `git remote -v` text into (fork, upstream) remote names.

        fork → a URL under the odoo-dev org (push target); upstream → a URL under
        the canonical odoo org. Resolution is by URL, not remote name, because
        names are inconsistent across repos. Either side may be None.
        """
        fork = upstream = None
        for line in remote_v_output.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name, url = parts[0], parts[1]
            if "odoo-dev/" in url:
                fork = fork or name
            elif ":odoo/" in url or "/odoo/" in url:
                upstream = upstream or name
        return fork, upstream

    @staticmethod
    def list_fork_branches(repo_path: str) -> list:
        """Branch names on the repo's odoo-dev fork, most-recently-committed first.

        Returns [] if the repo has no fork remote (so callers can fall back to a
        manual prompt). Scoping to the fork keeps the list to the user's own dev
        branches instead of the upstream's thousands.
        """
        import subprocess
        remotes = subprocess.run(
            ["git", "-C", repo_path, "remote", "-v"], capture_output=True, text=True
        )
        if remotes.returncode != 0:
            return []
        fork, _ = Helpers.parse_odoo_remotes(remotes.stdout)
        if not fork:
            return []
        out = subprocess.run(
            ["git", "-C", repo_path, "for-each-ref", "--sort=-committerdate",
             "--format=%(refname:short)", f"refs/remotes/{fork}/"],
            capture_output=True, text=True,
        )
        prefix = f"{fork}/"
        branches = []
        for line in out.stdout.splitlines():
            name = line[len(prefix):] if line.startswith(prefix) else line
            if name and name != "HEAD":
                branches.append(name)
        return branches

    @staticmethod
    def repo_github_url(repo_path: str) -> str:
        """https://github.com/<owner>/<repo> for a repo's origin remote, or ''."""
        import subprocess
        url = subprocess.run(
            ["git", "-C", repo_path, "config", "--get", "remote.origin.url"],
            capture_output=True, text=True,
        ).stdout.strip()
        owner_repo = Helpers.parse_github_remote(url)
        return f"https://github.com/{owner_repo}" if owner_repo else ""

    @staticmethod
    def detect_workspace_for_cwd():
        """Return the Workspace whose path (or its version's path) contains the
        current directory, most-specific match wins. None if cwd is outside any."""
        from cc.base.arm.workspace import Workspace
        from cc.base.db import database_connection_manager
        cwd = os.path.realpath(os.getcwd())
        best, best_len = None, -1
        with database_connection_manager():
            for w in Workspace.find_by():
                candidates = []
                if w.path:
                    candidates.append(w.path)
                if w.version_id and w.version_id.path:
                    candidates.append(w.version_id.path)
                for p in candidates:
                    rp = os.path.realpath(p)
                    if (cwd == rp or cwd.startswith(rp + os.sep)) and len(rp) > best_len:
                        best, best_len = w, len(rp)
        return best

    @staticmethod
    def sort_files_by_mtime(files):
        """
        Sort files by modified time in descending order.
        """
        # Filter files that exist, and sort by modification time
        if any(not os.path.exists(file) for file in files):
            return files
        sorted_files = sorted(
            files,
            key=lambda file: os.path.getmtime(file),
            reverse=True,
        )
        return sorted_files

    @staticmethod
    def vs_code(
        path,
        subdir_to_focus=False,
        file_to_focus=False,
        continue_if_focus_fail=True,
        new_window=False,
        focus_path=False,
        ide="code",
    ):
        failed = False
        if not os.path.isdir(path):
            log.error(f"Failed to open VS Code, Path {path} is not a valid directory")
            return False

        subdir = False
        focus_path = focus_path or path
        if subdir_to_focus:
            subdir = Helpers.search_subdir_file(focus_path, subdir_to_focus, False)
            if not subdir:
                failed = True
            else:
                for _, _, files in os.walk(subdir[0]):
                    if files:
                        file_to_focus = files[0]
                        break
                else:
                    failed = True

            if failed and not continue_if_focus_fail:
                log.warning(f"Failed to Focus on File {subdir_to_focus} since it does not exist under {focus_path}")
                return False

        if file_to_focus:
            file_path = Helpers.search_subdir_file(subdir or focus_path, file_to_focus, True)
            if not file_path:
                failed = True

            if failed and not continue_if_focus_fail:
                log.warning(f"Failed to Focus on File {file_to_focus} since it does not exist under {focus_path}")
                return False

        vscode_dir = os.path.join(path, ".vscode")
        settings_file = os.path.join(vscode_dir, "settings.json")
        os.makedirs(vscode_dir, exist_ok=True)
        terminal_cwd = focus_path
        settings = {}
        if os.path.exists(settings_file):
            with open(settings_file) as f:
                try:
                    settings = json.load(f)
                except json.JSONDecodeError:
                    log.warning(f"Could not parse {settings_file}. It will be overwritten.")
        settings["terminal.integrated.cwd"] = terminal_cwd
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=4)

        command = [ide]
        command.append("-n" if new_window else "--reuse-window")
        command.append(path)
        if file_to_focus and not failed:  # Focus file in the same command
            command.append(file_path[0])

        # Helpers._copy_to_clipboard(f"cd {focus_path}")

        log.debug(f"Running VS Code command: {' '.join(command)}")
        subprocess.run(" ".join(command), shell=True, capture_output=True, check=False)
        return True

    # === DB Methods === #
    @staticmethod
    def get_all_tracked_db_names() -> list[str]:
        """Return all database names tracked in the CC SQLite DB."""
        from cc.utils.constants import Constants
        try:
            conn = sqlite3.connect(Constants.SQLITE_DB_PATH)
            cursor = conn.execute("SELECT name FROM database ORDER BY name")
            names = [row[0] for row in cursor.fetchall()]
            conn.close()
            return names
        except Exception:
            return []

    @staticmethod
    def search_db(db_name, banned_words=False, banned_dbs=False):
        log.debug(f"Searching for DB name like '{db_name}'")
        dbs = Helpers.get_all_db_names(banned_dbs=banned_dbs, banned_words=banned_words)
        matches = Helpers.search_str(dbs, db_name, n=0)
        return sorted(matches)

    @staticmethod
    def get_all_db_names(banned_dbs: set = False, banned_words: set = False):
        """Database names present in Postgres, read from cc's metadata cache.

        The cache (the `database` table, in_pg=1) is maintained by the daemon's
        background reconcile, so this is instant and works regardless of how PG
        runs (native or dockerized) — no `psql` subprocess.
        """
        banned_dbs = (banned_dbs or set()) | {"odoo", "postgres"}
        banned_words = banned_words or {"CC-COPY"}

        from cc.base.arm.database import Database
        from cc.base.db import database_connection_manager

        def _read_cache():
            with database_connection_manager():
                return {d.name for d in Database.find_by() if d.in_pg}

        try:
            names = _read_cache()
        except Exception as e:
            log.debug(f"get_all_db_names: cache read failed: {e}")
            names = set()

        # Cold cache (fresh install, pre-3.8 rows with NULL in_pg, or daemon
        # never reconciled): ask the daemon to reconcile once, then re-read.
        global _db_cache_reconciled
        if not names and not _db_cache_reconciled:
            _db_cache_reconciled = True
            try:
                from cc.daemon.client import call
                call("database.reconcile")
                names = _read_cache()
            except Exception as e:
                log.debug(f"get_all_db_names: reconcile fallback failed: {e}")

        names -= banned_dbs
        names = {db for db in names if not any(word in db for word in banned_words)}
        return names

    # === Git Methods === #
    @staticmethod
    def git_is_repo(path):
        return os.path.exists(os.path.join(path, ".git"))

    @staticmethod
    def git_get_branch_name():
        if not Helpers.git_is_repo(os.getcwd()):
            log.debug("git_get_branch_name: Not a git repo.")
            return False
        try:
            name = subprocess.check_output(
                ["git", "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except subprocess.CalledProcessError as e:
            log.error(f"Error getting branch name: {e}")
            return False
        except FileNotFoundError:
            log.error("Error: 'git' command not found.")
            return False

        return name

    @staticmethod
    def git_get_latest_uncommitted_files(path):
        if not Helpers.git_is_repo(path):
            return []

        try:
            result = subprocess.run(
                ["git", "-C", path, "status", "--porcelain"],
                cwd=path,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            log.error(f"Error getting git status: {e.stderr.strip()}")
            return []
        except FileNotFoundError:
            log.error("Error: 'git' command not found.")
            return []

        changes = result.stdout and result.stdout.strip().split("\n")
        changed_files = []

        if changes:
            for line in changes:
                changed_files.append(line.strip().split()[-1])

        paths_dict = {os.path.join(path, file): file for file in changed_files}
        sorted_paths = Helpers.sort_files_by_mtime(paths_dict.keys())

        res = []
        [res.append(paths_dict[val]) for val in sorted_paths]
        return res

    @staticmethod
    def git_get_latest_commit_files(path):
        if not Helpers.git_is_repo(path):
            return []

        try:
            result = subprocess.run(
                ["git", "-C", path, "diff", "--name-only", "HEAD~1", "HEAD"],
                cwd=path,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            error = e.stderr.strip()
            if "unknown revision or path not in the working tree" not in error:
                log.error(f"Error getting git diff: {e.stderr.strip()}")
            return []
        except FileNotFoundError:
            log.error("Error: 'git' command not found.")
            return []

        changed_files = result.stdout and result.stdout.strip().split("\n")

        paths_dict = {os.path.join(path, file): file for file in changed_files}
        sorted_paths = Helpers.sort_files_by_mtime(paths_dict.keys())

        res = []
        [res.append(paths_dict[val]) for val in sorted_paths]
        return res

    @staticmethod
    def git_get_latest_changed_files(path):
        """
        path: path of git repo

        returns untracked + tracked files changed. if there are none returns the files changed in the latest commit.
        """
        if files := Helpers.git_get_latest_uncommitted_files(path):
            return files

        return Helpers.git_get_latest_commit_files(path)

    @staticmethod
    def get_all_project_modules(project_path: str) -> (set, set):
        """
        Lists all subdirectories (modules) in a given project path.

        Args:
        ----
            project_path: The absolute path to the project's modules directory.

        """
        if not project_path or not os.path.isdir(project_path):
            log.warning(f"get_all_project_modules: project_path is invalid: {project_path}")
            return set(), set()

        def is_odoo_module(path: str) -> bool:
            return any(
                os.path.isfile(os.path.join(path, manifest))
                for manifest in ("__manifest__.py", "__openerp__.py")
            )

        submodules = set()
        main_modules = sorted(
            name for name in Helpers.listdir(project_path)
            if is_odoo_module(os.path.join(project_path, name))
        )
        internal = Helpers.get_internal_addons_dir()
        internal_path = os.path.join(project_path, internal) if internal else ""
        if internal_path and os.path.isdir(internal_path):
            submodules = {
                name for name in Helpers.listdir(internal_path)
                if is_odoo_module(os.path.join(internal_path, name))
            }
        return set(main_modules), submodules

    @staticmethod
    def get_internal_addons_dir() -> str:
        """Name of the shared internal-addons directory probed inside project
        roots (setting `odoo.internal_addons_dir`). Empty = feature disabled."""
        from cc.base.arm.setting import Setting

        s = Setting.find_by(name=Constants.SETTING_INTERNAL_ADDONS, limit=1)
        return (s.value or "").strip() if s else ""

    @staticmethod
    def setting_clean_words() -> set:
        """User-configured extra words stripped during fuzzy name matching
        (setting `search.clean_words`, comma-separated)."""
        from cc.base.arm.setting import Setting

        s = Setting.find_by(name=Constants.SETTING_CLEAN_WORDS, limit=1)
        if not s or not s.value:
            return set()
        return {w.strip().lower() for w in s.value.split(",") if w.strip()}

    @staticmethod
    def get_relevant_project_db_names(project_name: str):
        return Helpers.search_db(project_name)

    @staticmethod
    def format_list_str(lst):
        """
        Formats a list as string with proper indentation.
        e.g. given [1, 2, 3] outputs:
        [
            1,
            2,
            3
        ]
        for empty list:
        [

        ]
        """
        list_str = json.dumps(lst, indent=4)[1:-1]  # Remove outer brackets
        if lst:
            return "[" + list_str.replace("    ", "        ") + "    ]"
        else:
            return "[\n\n    ]"

    @staticmethod
    def replace_in_file(file_path: str, replacement_dict: dict):
        try:
            # Read, replace, and write the file
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            for key, value in replacement_dict.items():
                content = content.replace(key, value)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except FileNotFoundError:
            log.error(f"replace_in_file: File not found at {file_path}")
        except Exception as e:
            log.error(f"replace_in_file: Error processing file {file_path}: {e}")

    # ==== GENERAL DATABASE UTILS ==== #
    @staticmethod
    def get_active_project_for_completion() -> Optional[sqlite3.Row]:
        """
        A self-contained function to get the active project, safe for use in
        contexts like argcomplete where a shared connection isn't available.
        """
        from cc.base.db import database_connection_manager

        with database_connection_manager():
            from cc.base.arm.app_state import AppState
            state = AppState.search([("version_id", "IS", None)], limit=1)
            return state.environment_id.project_id if state else None

    @staticmethod
    def get_all_project_names_for_completion() -> List[str]:
        """
        Retrieves only the names of all projects for fast autocompletion.
        This function is self-contained and safe to call from argcomplete.
        """
        from cc.base.arm.project import Project
        from cc.base.db import database_connection_manager

        with database_connection_manager():
            projects = Project.find_by(orderby="name ASC")
            return [project.name for project in projects]

    @staticmethod
    def get_all_version_names_for_completion() -> List[str]:
        """
        Retrieves only the names of all versions for fast autocompletion.
        This function is self-contained and safe to call from argcomplete.
        """
        from cc.base.arm.version import Version
        from cc.base.db import database_connection_manager

        with database_connection_manager():
            versions = Version.find_by(orderby="name ASC")
            return [version.name for version in versions]

    @staticmethod
    def get_active_environment() -> Optional[str]:
        from cc.base.db import database_connection_manager

        with database_connection_manager():
            from cc.base.arm.app_state import AppState
            state = AppState.search([("version_id", "IS", None)], limit=1)
            return state.environment_id if state else None

    @staticmethod
    def get_all_environments() -> Optional[str]:
        from cc.base.arm.environment import Environment
        from cc.base.db import database_connection_manager

        with database_connection_manager():
            envs = Environment.find_by()
            return envs

    @staticmethod
    def _get_project_paths(project_name: str, version_name: str):
        versions_search = Helpers._get_versions_search(version_name)
        projects = {}
        max_depth = 3
        try:
            max_depth = int(os.getenv("CC_PROJECT_SEARCH_DEPTH", "3"))
        except (ValueError, TypeError):
            log.warning("Invalid value for CC_PROJECT_SEARCH_DEPTH. Using default of 3.")

        search_kwargs = dict(
            banned_dirs=Helpers._get_banned_dirs(),
            ignore_words=Helpers._get_ignore_words(),
            strict=False,
            cutoff=PROJECT_SEARCH_CUTOFF,
            n=5,
            clean=Helpers._get_clean_words(),
        )

        searched_paths = set()
        for version in (versions_search or []):
            if not version.path or version.path in searched_paths:
                continue
            searched_paths.add(version.path)
            project_paths = Helpers.search_subdir_file(
                version.path, project_name, False, max_depth=max_depth, **search_kwargs,
            )
            if project_paths:
                for path in project_paths:
                    projects[path] = (version.path, version.name)

        if not projects:
            from cc.base.arm.workspace import Workspace
            for ws in Workspace.find_by():
                if not ws.path or ws.path in searched_paths:
                    continue
                searched_paths.add(ws.path)
                v_name = ""
                v_path = ws.path
                if ws.version_id:
                    from cc.base.arm.version import Version
                    v = Version.find_by(id=ws.version_id, limit=1)
                    if v:
                        v_name = v.name
                        v_path = v.path or ws.path
                project_paths = Helpers.search_subdir_file(
                    ws.path, project_name, False, max_depth=max_depth, **search_kwargs,
                )
                if project_paths:
                    for path in project_paths:
                        projects[path] = (v_path, v_name)

        if not projects and not versions_search:
            log.warning("_get_project_paths: No versions or workspaces found to search in.")

        return projects, versions_search

    @staticmethod
    def _get_versions_search(version_name: str):
        from cc.base.arm.version import Version
        from cc.base.db import database_connection_manager

        with database_connection_manager():
            versions_search = Version.find_by(name=version_name)
            if not versions_search:
                return Version.find_by()
            return versions_search

    @staticmethod
    def _get_clean_words():
        return Helpers.setting_clean_words()

    @staticmethod
    def _get_ignore_words():
        return {"_account", "_stock", "_hr", "_report", "_inventory", "cache"}

    @staticmethod
    def _get_banned_dirs():
        return {"odoo", "enterprise", "design-themes", "config_files", ".git", "logs", "views", ".vscode", "trash",
                # macOS standard home subdirs that don't contain code — keeps the
                # scanner out of TCC-protected app containers.
                "Library", "Applications", "Music", "Pictures", "Movies", "Public", ".Trash"}

    # =========================================================
    # Pyenv Helpers
    # =========================================================

    @staticmethod
    def pyenv_is_installed() -> bool:
        """Returns True if pyenv is available in PATH."""
        import shutil
        return shutil.which("pyenv") is not None

    @staticmethod
    def pyenv_list_versions() -> list:
        """Returns a list of installed pyenv Python versions (excludes virtualenvs)."""
        try:
            result = subprocess.run(
                ["pyenv", "versions", "--bare", "--skip-aliases"],
                capture_output=True, text=True, check=True,
            )
            versions = [
                v.strip() for v in result.stdout.splitlines()
                if v.strip() and "/" not in v and not v.strip().startswith("cc-")
            ]
            return versions
        except Exception as e:
            log.debug(f"pyenv_list_versions failed: {e}")
            return []

    @staticmethod
    def pyenv_list_all_virtualenvs() -> list:
        """Returns all pyenv virtualenvs (excludes bare Python versions)."""
        try:
            result = subprocess.run(
                ["pyenv", "virtualenvs", "--bare", "--skip-aliases"],
                capture_output=True, text=True, check=True,
            )
            return [v.strip() for v in result.stdout.splitlines() if v.strip()]
        except Exception as e:
            log.debug(f"pyenv_list_all_virtualenvs failed: {e}")
            return []

    @staticmethod
    def pyenv_virtualenv_exists(name: str) -> bool:
        """Returns True if a pyenv virtualenv with the given name exists."""
        try:
            result = subprocess.run(
                ["pyenv", "versions", "--bare"],
                capture_output=True, text=True, check=True,
            )
            return name in [v.strip() for v in result.stdout.splitlines()]
        except Exception:
            return False

    @staticmethod
    def pyenv_has_virtualenv_plugin() -> bool:
        """True if the pyenv-virtualenv plugin is available."""
        try:
            result = subprocess.run(
                ["pyenv", "commands"], capture_output=True, text=True, check=False,
            )
            return "virtualenv" in result.stdout.split()
        except FileNotFoundError:
            return False

    @staticmethod
    def pyenv_create_virtualenv(base_version: str, name: str) -> bool:
        """Creates a pyenv virtualenv. Returns True on success."""
        if not Helpers.pyenv_has_virtualenv_plugin():
            if sys.platform == "darwin":
                install_cmd = "`brew install pyenv-virtualenv`"
            else:
                install_cmd = ("`git clone https://github.com/pyenv/pyenv-virtualenv "
                               "$(pyenv root)/plugins/pyenv-virtualenv`")
            log.error(
                f"pyenv-virtualenv plugin not installed. Install with "
                f"{install_cmd}, then add "
                f"`eval \"$(pyenv virtualenv-init -)\"` to your shell rc "
                f"and restart your shell."
            )
            return False
        try:
            subprocess.run(
                ["pyenv", "virtualenv", base_version, name],
                check=True,
            )
            log.debug(f"Created pyenv virtualenv '{name}' from Python {base_version}.")
            return True
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to create pyenv virtualenv '{name}': {e}")
            return False

    @staticmethod
    def pyenv_get_python_path(virtualenv_name: str) -> str:
        """Returns the full path to the Python binary for a pyenv virtualenv."""
        home = os.path.expanduser("~")
        return os.path.join(home, ".pyenv", "versions", virtualenv_name, "bin", "python")

    @staticmethod
    def pyenv_detect_version_from_path(path: str) -> str:
        """Reads .python-version file from the given path if it exists."""
        pv_file = os.path.join(path, ".python-version")
        if os.path.exists(pv_file):
            with open(pv_file) as f:
                return f.read().strip()
        return None
