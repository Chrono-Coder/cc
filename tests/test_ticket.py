"""
`cc ticket` (3.8): prefer the env's explicit ticket_ids field over guessing the
number from the branch name; fall back to the branch when no ticket_ids are set.
"""
from argparse import Namespace

from cc.commands.odoo.open_ticket_command import TicketCommand


def _cmd(env):
    cmd = TicketCommand(skip_add_parser=True)
    cmd.args = Namespace(name=None)
    cmd.active_environment = env  # cached_property is a non-data descriptor → shadowed
    return cmd


class _Env:
    def __init__(self, ticket_ids="", branch_name=""):
        self.ticket_ids = ticket_ids
        self.branch_name = branch_name


def test_prefers_single_ticket_id():
    cmd = _cmd(_Env(ticket_ids="1234567", branch_name="19.0-9999999-x"))
    assert cmd.get_ticket_id() == "1234567"


def test_falls_back_to_branch_when_no_ticket_ids():
    cmd = _cmd(_Env(ticket_ids="", branch_name="19.0-7654321-feature"))
    assert cmd.get_ticket_id() == "7654321"


def test_no_ticket_ids_no_number_in_branch():
    cmd = _cmd(_Env(ticket_ids="", branch_name="just-a-name"))
    assert cmd.get_ticket_id() is False
