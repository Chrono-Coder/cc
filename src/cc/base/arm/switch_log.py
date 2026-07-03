from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class SwitchLog(BaseEntity):
    """
    Records timesheet spans. Auto rows come from `cc switch` (gap-based: an open
    row's duration runs to the next switch); manual rows (3.11) carry an explicit
    start+end+note. Spans over the configured threshold are flagged for review.
    """

    _name = "switch_log"

    environment_id = Property(relation="environment")  # NULL = stop/punch-out entry
    switched_at = Property(type=str, required=True, semantic="datetime")  # span start
    flagged = Property(type=bool)  # True if previous span exceeded threshold
    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")

    # 3.11 explicit-span fields (additive — new Property = auto column via
    # sync_schema, no migration). An auto row left open (ended_at NULL) still
    # reads gap-based to the next switch, so legacy rows keep working.
    ended_at = Property(type=str, semantic="datetime")  # span end; NULL = open/gap-derived
    note = Property(type=str)                            # freeform "what happened"
    source = Property(type=str)                          # "auto"(switch) | "manual"; NULL = legacy auto
    edited = Property(type=bool)                         # an auto span the user adjusted → authoritative
