"""
Guard: every command must build its argparse parser cleanly.

Instantiating a command runs add_arguments() → Argument.add_to_parser() for all
its args — the same path `cc` / the daemon hit on startup. A bad Argument kwarg
(e.g. an unsupported `dest=`) breaks *every* cc invocation but is invisible to
the service-layer tests, so we assert registration here.
"""
import cc.commands  # noqa: F401 — populates Command subclasses
from cc.base.command import Command


def test_all_commands_register():
    classes = Command.build_classes()
    assert classes, "no commands discovered"

    failures = []
    for hc in classes:
        try:
            hc()
        except Exception as e:  # noqa: BLE001 — surface any registration error
            failures.append(f"{hc.__name__}: {e}")

    assert not failures, "commands failed to register:\n" + "\n".join(failures)
