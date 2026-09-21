"""
Convert legacy trade lifecycle archived entries (scalar buy_order / sell_order)
to dict-keyed buy_orders / sell_orders. Used by the one-off migration script and tests.
"""
from __future__ import annotations

from typing import Any, Dict


def migrate_legacy_archived_entry_in_place(entry: Dict[str, Any]) -> None:
    """
    Mutate a single archived_entries item from legacy layout to dict layout.
    No-op if ``buy_orders`` is already present.
    """
    if "buy_orders" in entry:
        return

    bo = entry.pop("buy_order", None)
    so = entry.pop("sell_order", None)
    bot_scalar = entry.pop("buy_order_terminal", True)
    sot_scalar = entry.pop("sell_order_terminal", True)

    if bo is not None:
        sym = bo.symbol
        entry["buy_orders"] = {sym: bo}
        entry["sell_orders"] = {sym: so}
        entry["buy_order_terminal"] = {sym: bot_scalar}
        entry["sell_order_terminal"] = {sym: sot_scalar}
    else:
        entry["buy_orders"] = {}
        entry["sell_orders"] = {}
        entry["buy_order_terminal"] = {}
        entry["sell_order_terminal"] = {}
