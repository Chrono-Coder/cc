import json
import logging
import shutil
import subprocess

log = logging.getLogger("CC")

_TIMEOUT = 15


class GhError(Exception):
    def __init__(self, message: str, returncode: int = 1, stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


def gh_available() -> bool:
    return shutil.which("gh") is not None


def gh_run(args: list[str], timeout: int = _TIMEOUT) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise GhError("gh CLI not found. Install from https://cli.github.com/", returncode=-1)
    except subprocess.TimeoutExpired:
        raise GhError(f"gh command timed out after {timeout}s: gh {' '.join(args)}", returncode=-1)

    if result.returncode != 0:
        raise GhError(
            result.stderr.strip() or f"gh exited with code {result.returncode}",
            returncode=result.returncode,
            stderr=result.stderr.strip(),
        )
    return result


def gh_run_json(args: list[str], timeout: int = _TIMEOUT) -> dict | list:
    result = gh_run(args, timeout=timeout)
    return json.loads(result.stdout)


def gh_authenticated() -> bool:
    try:
        subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def gh_username() -> str | None:
    try:
        result = gh_run(["api", "user", "--jq", ".login"], timeout=10)
        return result.stdout.strip() or None
    except GhError:
        return None


def gh_token() -> str | None:
    try:
        result = gh_run(["auth", "token"], timeout=5)
        return result.stdout.strip() or None
    except GhError:
        return None


# ---------------------------------------------------------------------------
# PR search / list
# ---------------------------------------------------------------------------

_SEARCH_FIELDS = "number,title,repository,author,isDraft,updatedAt,createdAt,url"


def gh_search_prs(
    author: str | None = None,
    reviewer: str | None = None,
    limit: int = 30,
) -> list[dict]:
    args = ["search", "prs", "--state", "open", "--json", _SEARCH_FIELDS, "--limit", str(limit)]
    if author:
        args += ["--author", author]
    if reviewer:
        args += ["--review-requested", reviewer]
    return gh_run_json(args, timeout=20)


_PR_LIST_FIELDS = "number,title,headRefName,url,isDraft,state,createdAt,updatedAt,author"


def gh_pr_list(repo: str, head: str | None = None, limit: int = 10) -> list[dict]:
    args = ["pr", "list", "-R", repo, "--json", _PR_LIST_FIELDS, "--limit", str(limit)]
    if head:
        args += ["--head", head]
    return gh_run_json(args)


# ---------------------------------------------------------------------------
# PR detail / actions
# ---------------------------------------------------------------------------

_PR_VIEW_FIELDS = (
    "number,title,url,state,body,isDraft,headRefName,baseRefName,"
    "author,reviewDecision,createdAt,updatedAt,additions,deletions,changedFiles"
)


def gh_pr_view(repo: str, number: int) -> dict:
    return gh_run_json(["pr", "view", str(number), "-R", repo, "--json", _PR_VIEW_FIELDS])


def find_pr_template() -> str | None:
    """Absolute path to the repo's PR template, or None.

    `gh pr create` only auto-loads the template in its interactive flow, which we
    bypass by capturing output — and passing `--body ""` actively overrides it.
    So we resolve the template ourselves and feed it via `--body-file`. Checks
    gh's standard locations relative to the git root.
    """
    import os
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    ).stdout.strip()
    if not root:
        return None
    for rel in (
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/pull_request_template.md",
        "PULL_REQUEST_TEMPLATE.md",
        "pull_request_template.md",
        "docs/PULL_REQUEST_TEMPLATE.md",
        "docs/pull_request_template.md",
    ):
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            return path
    return None


def gh_pr_create(
    base: str,
    title: str,
    body: str = "",
    draft: bool = False,
) -> str:
    args = ["pr", "create", "--base", base, "--title", title, "--fill-first"]
    if body:
        args += ["--body", body]
    else:
        template = find_pr_template()
        if template:
            args += ["--body-file", template]
    if draft:
        args.append("--draft")
    result = gh_run(args, timeout=30)
    return result.stdout.strip()


def gh_pr_merge(
    repo: str,
    number: int,
    method: str = "squash",
    delete_branch: bool = False,
) -> bool:
    args = ["pr", "merge", str(number), "-R", repo, f"--{method}"]
    if delete_branch:
        args.append("--delete-branch")
    gh_run(args, timeout=30)
    return True


def gh_pr_checkout(number: int) -> bool:
    gh_run(["pr", "checkout", str(number)])
    return True


# ---------------------------------------------------------------------------
# Commit status / checks
# ---------------------------------------------------------------------------


def gh_commit_status(repo: str, ref: str) -> dict:
    return gh_run_json(["api", f"repos/{repo}/commits/{ref}/status"])


def gh_pr_checks(repo: str, number: int) -> list[dict]:
    result = gh_run(["pr", "checks", str(number), "-R", repo, "--json", "name,state,description,detailsUrl"])
    stdout = result.stdout.strip()
    if not stdout:
        return []
    return json.loads(stdout)
