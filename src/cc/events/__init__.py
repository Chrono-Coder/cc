"""cc event bus — the seam that lets plugins react to core actions without core
importing them. Handlers run in the CLI process in priority order, may prompt,
and write through daemon RPC.
"""

from cc.events.bus import EventBus, EventCancelled, bus, subscribe
from cc.events.events import SwitchCheckoutEvent, SwitchEvent

__all__ = ["EventBus", "EventCancelled", "bus", "subscribe", "SwitchEvent", "SwitchCheckoutEvent"]
