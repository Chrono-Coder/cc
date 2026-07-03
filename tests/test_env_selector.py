"""
Env picker (3.8): type-to-filter searches the full set, the scroll window keeps
long lists calm, and the cursor opens on the active env. These exercise the pure
logic (no TUI run / no DB).
"""
from cc.utils.prompter.env_selector import EnvSelectorTUI


class _E:
    def __init__(self, id, name, status="active", pinned=False):
        self.id = id
        self.name = name
        self.status = status
        self.pinned = pinned


def _envs(n):
    return [_E(i, f"env{i:02d}") for i in range(n)]


def test_filter_is_case_insensitive_substring_over_full_set():
    envs = [_E(1, "acme_staging"), _E(2, "acme_prod"), _E(3, "globex_dev")]
    tui = EnvSelectorTUI(envs)
    assert len(tui._filtered()) == 3  # empty filter → all

    tui.filter = "PROD"
    assert [e.name for e in tui._filtered()] == ["acme_prod"]

    tui.filter = "acme"
    assert {e.name for e in tui._filtered()} == {"acme_staging", "acme_prod"}

    tui.filter = "zzz"
    assert tui._filtered() == []


def test_window_caps_to_viewport_and_centers_on_cursor():
    tui = EnvSelectorTUI(_envs(20), viewport=5)

    tui.cursor = 0
    assert tui._window(20) == (0, 5)

    tui.cursor = 10
    start, end = tui._window(20)
    assert end - start == 5 and start <= 10 < end

    tui.cursor = 19
    assert tui._window(20) == (15, 20)


def test_window_shows_all_when_under_viewport():
    tui = EnvSelectorTUI(_envs(3), viewport=10)
    assert tui._window(3) == (0, 3)


def test_cursor_opens_on_active_env():
    envs = [_E(1, "a"), _E(2, "b"), _E(3, "c")]
    assert EnvSelectorTUI(envs, active_env_id=3).cursor == 2
    assert EnvSelectorTUI(envs).cursor == 0  # no active → top
