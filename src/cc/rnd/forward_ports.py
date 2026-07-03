"""
Forward-port discovery for R&D tickets.

An Odoo ticket starts on a main branch (e.g. ``19.0-fix-issue``) and is
forward-ported to later versions. The fork branches follow
``{target-version}-{main-branch}-fw`` — so the port of ``19.0-fix-issue`` to
19.1 is ``19.1-19.0-fix-issue-fw`` and to master is ``master-19.0-fix-issue-fw``.

Because the main branch is known, ports are matched by stripping the
``-{main}-fw`` suffix; the remainder is the *target* version token, resolved
against cc's registered version names (so ``saas-17.4`` and friends work without
a fragile regex). The anchor's own version is the longest registered version
name that prefixes the main branch.
"""


def resolve_version(token, version_names):
    """Return the registered version name matching `token` exactly, or None."""
    return token if token in version_names else None


def _anchor_version(main_branch, version_names):
    """The registered version name that prefixes the main branch (longest wins)."""
    best = None
    for v in version_names:
        if main_branch == v or main_branch.startswith(f"{v}-"):
            if best is None or len(v) > len(best):
                best = v
    return best


def match_ports(main_branch, branches, version_names):
    """Resolve a ticket's branch chain.

    Returns an ordered list of {"branch", "version", "is_anchor"} — the anchor
    (the main branch itself) first if present, then each forward-port. `version`
    is the resolved registered version name, or None when the target version
    isn't registered (caller decides whether to skip/warn).
    """
    version_names = set(version_names or [])
    suffix = f"-{main_branch}-fw"
    out = []
    seen = set()

    # Anchor first.
    if main_branch in branches:
        out.append({
            "branch": main_branch,
            "version": _anchor_version(main_branch, version_names),
            "is_anchor": True,
        })
        seen.add(main_branch)

    for b in branches:
        if b in seen or b == main_branch:
            continue
        if b.endswith(suffix) and len(b) > len(suffix):
            token = b[: -len(suffix)]
            out.append({
                "branch": b,
                "version": resolve_version(token, version_names),
                "is_anchor": False,
            })
            seen.add(b)
    return out
