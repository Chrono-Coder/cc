import zipfile
from types import SimpleNamespace

from cc.commands.database.create_command import CreateDatabaseCommand


class _Helpers:
    @staticmethod
    def get_all_project_modules(path):
        return {"module_a", "module_b"}, {"internal_module"}


class _Prompter:
    def prompt_checkbox(self, **kwargs):
        assert kwargs["options"] == ["Select all", "internal_module", "module_a", "module_b"]
        return ["module_a", "internal_module"]

    def prompt_input_multi(self, options, label):
        return {
            "Action for internal_module": "Draft",
            "Action for module_a": "Install",
        }[label]


def _command(modules=None, no_picker=False):
    command = object.__new__(CreateDatabaseCommand)
    command.args = SimpleNamespace(
        modules=modules, no_module_picker=no_picker, fresh=False, dump=None,
    )
    command.Helpers = _Helpers
    command.prompter = _Prompter()
    command.__dict__["active_environment"] = SimpleNamespace(project_path="/project")
    return command


def test_picker_assigns_per_module_actions():
    assert _command()._select_module_actions() == {
        "internal_module": "draft",
        "module_a": "install",
    }


def test_modules_flag_is_non_interactive_install_list():
    assert _command("base,module_a,module_b")._select_module_actions() == {
        "module_a": "install",
        "module_b": "install",
    }


def test_no_picker_initializes_base_only():
    assert _command(no_picker=True)._select_module_actions() == {}


def _dump(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("dump.sql", "-- dump")


def test_database_source_ranks_project_dumps_first(tmp_path):
    unrelated = tmp_path / "other-new.zip"
    project_old = tmp_path / "acme-old.zip"
    project_new = tmp_path / "acme-new.zip"
    for path in (unrelated, project_old, project_new):
        _dump(path)
    unrelated.touch()
    project_old.touch()
    project_new.touch()

    command = _command()
    command.__dict__["active_project"] = SimpleNamespace(name="acme")
    command.setting = SimpleNamespace(
        find_by=lambda **kwargs: SimpleNamespace(value=str(tmp_path))
    )
    seen = {}

    def choose(options, label):
        seen["options"] = options
        return options[1]

    command.prompter.prompt_input_multi = choose

    assert command._select_database_source() == seen["options"][1]
    assert seen["options"][0] == "Fresh database"
    assert "acme" in seen["options"][1]
    assert "acme" in seen["options"][2]
    assert seen["options"][3].endswith("other-new.zip")


def test_fresh_flag_skips_dump_picker():
    command = _command()
    command.args.fresh = True
    assert command._select_database_source() is None


def test_explicit_valid_dump_skips_picker(tmp_path):
    path = tmp_path / "acme.zip"
    _dump(path)
    command = _command()
    command.args.dump = str(path)
    assert command._select_database_source() == str(path)
