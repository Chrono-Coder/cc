"""
Verb consistency + env-name collisions (3.8 wave 4b).

- Canonical verbs (create/delete) are the only ones completion offers; the old
  add/remove still work as silent aliases (mapped in the command dispatch).
- Env names are non-unique, so a by-name lookup that hits >1 project must be
  disambiguable — env.find_all_by_name returns every match with its project.
"""
def _mk_env(name, project_id):
    from cc.services import environment
    return environment.create(
        name=name, project_id=project_id, version_name="17.0", version_path="/opt/v17",
        project_path=f"/tmp/{name}", github_url="", branch_name="main",
        database_name=f"db_{name}", module_names=[],
    )["id"]


def _arg(command_cls, name):
    args = command_cls(skip_add_parser=True).arguments()
    return next(a for a in args if a.names == [name])


# ── completion: only canonical verbs offered (old add/remove hidden) ─────

def test_env_action_offers_only_canonical_verbs():
    from cc.commands.project.environment_command import EnvironmentCommand
    verbs = _arg(EnvironmentCommand, "action").complete
    assert {"create", "delete", "pin", "unpin"} <= set(verbs)
    assert "add" not in verbs and "remove" not in verbs


def test_project_action_offers_only_canonical_verbs():
    from cc.commands.project.project_command import ProjectCommand
    verbs = _arg(ProjectCommand, "action").complete
    assert {"create", "delete", "list"} <= set(verbs)
    assert "add" not in verbs and "remove" not in verbs


def test_env_target_uses_env_target_kind():
    from cc.commands.project.environment_command import EnvironmentCommand
    from cc.completion.kinds import CompleteKind
    assert _arg(EnvironmentCommand, "target").complete is CompleteKind.ENV_TARGET


# ── aliases route to the canonical handler ──────────────────────────────

def test_dispatch_aliases():
    from cc.commands.project.environment_command import _ENV_ALIASES
    from cc.commands.project.project_command import _PROJECT_ALIASES
    assert _ENV_ALIASES == {"add": "create", "remove": "delete"}
    assert _PROJECT_ALIASES == {"add": "create", "remove": "delete"}


# ── collision resolution data ───────────────────────────────────────────

def test_find_all_by_name_returns_every_project_match(_db):
    from cc.services import environment, project, version
    version.create("17.0", "/opt/v17", branch="17.0")
    p1, p2 = project.create("acme"), project.create("globex")
    _mk_env("staging", p1["id"])
    _mk_env("staging", p2["id"])
    _mk_env("prod", p1["id"])

    staging = environment.find_all_by_name("staging")
    assert len(staging) == 2
    assert {e.project_name for e in staging} == {"acme", "globex"}

    assert len(environment.find_all_by_name("prod")) == 1
    assert environment.find_all_by_name("nope") == []
