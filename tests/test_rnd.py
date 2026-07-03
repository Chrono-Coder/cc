"""
R&D switch logic tests — pure helpers, no git/DB needed.

Covers per-repo remote resolution by URL (fork = odoo-dev, upstream = odoo),
including the inconsistent-remote-name and fork-less (upgrade) cases.
"""
from cc.utils.helpers import Helpers

# The remote-resolution logic lives in this core helper; cc-rnd's switch-rebase
# handler calls it. (The old SwitchCommand._parse_rnd_remotes wrapper was removed
# when the rebase moved to the plugin.)
_parse = Helpers.parse_odoo_remotes


def test_odoo_fork_and_upstream():
    # odoo repo: origin = odoo-dev fork, odoo = upstream
    out = (
        "origin\tgit@github.com:odoo-dev/odoo.git (fetch)\n"
        "origin\tgit@github.com:odoo-dev/odoo.git (push)\n"
        "odoo\tgit@github.com:odoo/odoo.git (fetch)\n"
        "odoo\tyou_should_not_push_on_this_repository (push)\n"
    )
    assert _parse(out) == ("origin", "odoo")


def test_enterprise_inconsistent_names():
    # enterprise: fork is named 'origin' (odoo-dev), upstream named 'odoo'
    out = (
        "odoo\tgit@github.com:odoo/enterprise.git (fetch)\n"
        "odoo\tyou_should_not_push_on_this_repository (push)\n"
        "origin\tgit@github.com:odoo-dev/enterprise.git (fetch)\n"
        "origin\tgit@github.com:odoo-dev/enterprise.git (push)\n"
    )
    assert _parse(out) == ("origin", "odoo")


def test_upgrade_has_no_fork():
    # upgrade: only origin = odoo/upgrade — no odoo-dev fork
    out = (
        "origin\tgit@github.com:odoo/upgrade.git (fetch)\n"
        "origin\tgit@github.com:odoo/upgrade.git (push)\n"
    )
    assert _parse(out) == (None, "origin")


def test_https_urls_resolve():
    out = (
        "origin\thttps://github.com/odoo-dev/odoo.git (fetch)\n"
        "upstream\thttps://github.com/odoo/odoo.git (fetch)\n"
    )
    assert _parse(out) == ("origin", "upstream")


def test_unrelated_remote_ignored():
    out = (
        "fork\tgit@github.com:odoo-dev/odoo.git (fetch)\n"
        "mine\tgit@github.com:someuser/odoo.git (fetch)\n"
    )
    assert _parse(out) == ("fork", None)


def test_empty_output():
    assert _parse("") == (None, None)
