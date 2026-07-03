"""
`cc switch -` (3.8): jump back to the env you were on before the current one,
resolved from the switch log (most recent distinct env, skipping the active one).
"""
from cc.services import environment, project, version


def _mk_env(name, project_id):
    return environment.create(
        name=name, project_id=project_id, version_name="17.0", version_path="/opt/v17",
        project_path=f"/tmp/{name}", github_url="", branch_name="main",
        database_name=f"db_{name}", module_names=[],
    )["id"]


def test_previous_env_is_the_prior_distinct_one(_db):
    version.create("17.0", "/opt/v17", branch="17.0")
    p = project.create("proj")
    e1, e2 = _mk_env("e1", p["id"]), _mk_env("e2", p["id"])

    environment.switch(e1)
    environment.switch(e2)
    assert environment.get_previous_env().id == e1  # before e2 was e1

    environment.switch(e1)
    assert environment.get_previous_env().id == e2  # now before e1 is e2


def test_previous_env_none_after_single_switch(_db):
    version.create("17.0", "/opt/v17", branch="17.0")
    p = project.create("proj")
    e1 = _mk_env("e1", p["id"])
    environment.switch(e1)
    assert environment.get_previous_env() is None  # nowhere to go back to


def test_previous_env_none_with_no_history(_db):
    assert environment.get_previous_env() is None
