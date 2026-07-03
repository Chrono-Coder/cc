"""Forward-port branch matching (cc.rnd.forward_ports) — pure, no git/DB."""
from cc.rnd import forward_ports as fp

VERSIONS = ["17.0", "18.0", "19.0", "19.1", "saas-17.4", "master"]


def _by_branch(matches):
    return {m["branch"]: m for m in matches}


def test_anchor_and_ports_resolve():
    branches = [
        "19.0-fix-issue",
        "19.1-19.0-fix-issue-fw",
        "master-19.0-fix-issue-fw",
        "unrelated-branch",
        "19.0-other-thing",
    ]
    out = fp.match_ports("19.0-fix-issue", branches, VERSIONS)
    by = _by_branch(out)

    assert out[0]["is_anchor"] is True and out[0]["branch"] == "19.0-fix-issue"
    assert by["19.0-fix-issue"]["version"] == "19.0"
    assert by["19.1-19.0-fix-issue-fw"]["version"] == "19.1"
    assert by["master-19.0-fix-issue-fw"]["version"] == "master"
    # unrelated branches and same-prefix-different-name are excluded
    assert "unrelated-branch" not in by
    assert "19.0-other-thing" not in by


def test_saas_target_resolves():
    out = fp.match_ports("17.0-thing", ["saas-17.4-17.0-thing-fw"], VERSIONS)
    assert out[0]["version"] == "saas-17.4"
    assert out[0]["is_anchor"] is False


def test_unregistered_target_is_none():
    out = fp.match_ports("19.0-fix", ["20.0-19.0-fix-fw"], VERSIONS)
    assert out[0]["branch"] == "20.0-19.0-fix-fw"
    assert out[0]["version"] is None


def test_anchor_absent_when_main_branch_not_listed():
    out = fp.match_ports("19.0-fix-issue", ["19.1-19.0-fix-issue-fw"], VERSIONS)
    assert all(not m["is_anchor"] for m in out)
    assert len(out) == 1


def test_anchor_version_prefix_longest_match():
    # saas-17.4 must win over a hypothetical "saas-17" if both were registered
    out = fp.match_ports("saas-17.4-fix", [], ["17.0", "saas-17", "saas-17.4"])
    # no branches → empty, but the helper is exercised via a present anchor:
    out = fp.match_ports("saas-17.4-fix", ["saas-17.4-fix"], ["saas-17", "saas-17.4"])
    assert out[0]["version"] == "saas-17.4"
