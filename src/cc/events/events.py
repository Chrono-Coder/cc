"""Event payloads — the stable contract handlers receive.

Each event is a frozen dataclass. Like ``CcState`` for IDE writers, these are
**additive-only** across minor versions: fields may be added, never removed or
renamed, so plugin handlers aren't broken.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SwitchEvent:
    """Fired by ``cc switch`` around the active-environment change.

    ``switch.before`` fires while the *previous* env is still active — handlers
    may prompt and may abort the switch by raising
    :class:`cc.events.bus.EventCancelled`. ``switch.after`` fires once the new
    env is live.
    """

    prev_env_id: int | None = None
    prev_env_name: str = ""
    new_env_id: int | None = None
    new_env_name: str = ""
    silent: bool = False


@dataclass(frozen=True)
class SwitchCheckoutEvent:
    """Fired by ``cc switch`` during the checkout phase, via ``bus.collect`` —
    handlers return a list of repo labels where the env's branch existed but
    checkout failed, which the switch aggregates into its checkout-failure
    summary. cc-rnd's handler uses this to check out + rebase the env's branch
    across the shared Odoo repos (self-gating: a no-op for non-R&D workspaces).
    """

    env_id: int | None = None
    version_id: int | None = None
    no_pull: bool = False
