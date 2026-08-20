"""Fill processing for research runs — mirrors execution_routes without globals."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..replay.replay_memory import ReplayMemory
from ..trading.execution import ExecutionSimulator
from ..trading.order_engine import OrderEngine


def process_research_fills(
    candles: Dict[str, Dict[str, float]],
    *,
    orders: OrderEngine,
    executor: ExecutionSimulator,
    memory: Optional[ReplayMemory] = None,
) -> List[Dict[str, Any]]:
    """Process pending orders and record replay lifecycle events."""
    fills = executor.process_all_symbols(candles)
    for fill in fills:
        if fill.get("status") not in ("FILLED", "PARTIAL_FILL"):
            continue
        order = orders.get_order(fill["order_id"])
        if not order or not memory:
            continue
        payload = fill.get("fill") or {}
        role = order.get("role", "entry")
        if role == "entry":
            memory.on_entry_fill(order, payload)
        elif role in ("stop_loss", "take_profit"):
            memory.on_exit_fill(order, payload, exit_reason=role)
    return fills
