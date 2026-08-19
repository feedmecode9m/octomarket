"""Bracket order helpers — entry with linked stop-loss and take-profit."""

from typing import Any, Dict, List, Optional


def create_bracket_exits(
    engine,
    symbol: str,
    quantity: int,
    entry_id: str,
    group_id: str,
    stop_loss: Optional[float],
    take_profit: Optional[float],
) -> List[Dict[str, Any]]:
    """Create stop-loss and take-profit child orders for a bracket entry."""
    children = []
    if stop_loss:
        children.append(engine.create_order(
            symbol=symbol, side="sell", quantity=quantity,
            order_type="stop_market", stop_price=stop_loss,
            parent_id=entry_id, bracket_group_id=group_id, role="stop_loss",
        ))
    if take_profit:
        children.append(engine.create_order(
            symbol=symbol, side="sell", quantity=quantity,
            order_type="limit", limit_price=take_profit,
            parent_id=entry_id, bracket_group_id=group_id, role="take_profit",
        ))
    return children
