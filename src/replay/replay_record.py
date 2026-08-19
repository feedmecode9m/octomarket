"""Durable replay record model — decision, execution, and outcome."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

from ..market.asset_class import AssetClass
from ..market.continuous_contract import continuous_id_for
from ..market.futures import pnl as futures_pnl
from ..market.instrument import resolve_instrument

SCHEMA_VERSION = 2
RECORD_STATUSES = ("planned", "submitted", "filled", "closed")


def new_record_id() -> str:
    return str(uuid.uuid4())


def capture_decision_context(
    plan: Dict[str, Any],
    chart_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Capture chart workspace and market snapshot at decision time."""
    from .market_snapshot import capture_market_snapshot

    instrument_id = plan.get("instrument_id") or plan.get("symbol", "")
    snapshot = capture_market_snapshot(instrument_id, chart_state=chart_state)
    return {
        "timeframe": snapshot["chart"]["timeframe"],
        "period": snapshot["chart"]["period"],
        "captured_at": snapshot["captured_at"],
        "market_snapshot": snapshot,
    }


def build_market_identity(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Build market identity block from a normalized trade plan."""
    raw_id = plan.get("instrument_id") or plan.get("symbol", "")
    instrument = resolve_instrument(raw_id)
    market: Dict[str, Any] = {
        "instrument_id": instrument.instrument_id,
        "asset_class": instrument.asset_class.value,
        "symbol": instrument.symbol,
        "session": instrument.session.to_dict() if instrument.session else None,
    }
    if instrument.asset_class == AssetClass.FUTURES:
        market["continuous_id"] = instrument.continuous_id or continuous_id_for(instrument.instrument_id)
        if instrument.contract:
            market["contract"] = instrument.contract
        if instrument.contract_month:
            market["contract_month"] = instrument.contract_month
    return market


def build_replay_record_from_plan(
    plan: Dict[str, Any],
    *,
    chart_state: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Initialize a replay record when a trade plan is created."""
    if mode is None:
        from .replay_session import is_replay_mode

        mode = "replay" if is_replay_mode() else "live_paper"
    now = datetime.now().isoformat()
    return {
        "id": new_record_id(),
        "status": "planned",
        "mode": mode,
        "plan_id": plan["id"],
        "market": build_market_identity(plan),
        "decision_context": capture_decision_context(plan, chart_state),
        "trade_intent": deepcopy(plan),
        "execution": {
            "status": "pending",
            "order_id": None,
            "entry": None,
            "exit": None,
            "fills": [],
        },
        "outcome": {
            "pnl": None,
            "r_multiple": None,
            "win_loss": None,
            "exit_reason": None,
        },
        "scoring": None,
        "metadata": {
            "created_at": now,
            "updated_at": now,
            "finalized_at": None,
            "schema_version": SCHEMA_VERSION,
        },
    }


def update_record_timestamp(record: Dict[str, Any]) -> None:
    record["metadata"]["updated_at"] = datetime.now().isoformat()


def apply_order_submitted(record: Dict[str, Any], order_id: str, order: Dict[str, Any]) -> Dict[str, Any]:
    record["status"] = "submitted"
    record["execution"]["status"] = "submitted"
    record["execution"]["order_id"] = order_id
    record["execution"]["submitted_at"] = order.get("created_at") or datetime.now().isoformat()
    update_record_timestamp(record)
    return record


def apply_entry_fill(record: Dict[str, Any], order: Dict[str, Any], fill: Dict[str, Any]) -> Dict[str, Any]:
    fill_price = float(fill.get("fill_price") or order.get("fill_price") or 0)
    quantity = float(fill.get("quantity") or order.get("filled_quantity") or order.get("quantity") or 0)
    entry = {
        "order_id": order["id"],
        "price": fill_price,
        "quantity": quantity,
        "filled_at": order.get("filled_at") or datetime.now().isoformat(),
        "side": order.get("side"),
    }
    record["status"] = "filled"
    record["execution"]["status"] = "filled"
    record["execution"]["entry"] = entry
    record["execution"]["fills"].append({"role": "entry", **entry})
    update_record_timestamp(record)
    return record


def apply_exit_fill(
    record: Dict[str, Any],
    order: Dict[str, Any],
    fill: Dict[str, Any],
    *,
    exit_reason: str,
) -> Dict[str, Any]:
    fill_price = float(fill.get("fill_price") or order.get("fill_price") or 0)
    quantity = float(fill.get("quantity") or order.get("filled_quantity") or order.get("quantity") or 0)
    exit_payload = {
        "order_id": order["id"],
        "price": fill_price,
        "quantity": quantity,
        "filled_at": order.get("filled_at") or datetime.now().isoformat(),
        "side": order.get("side"),
        "reason": exit_reason,
    }
    record["status"] = "closed"
    record["execution"]["status"] = "closed"
    record["execution"]["exit"] = exit_payload
    record["execution"]["fills"].append({"role": exit_reason, **exit_payload})
    record["outcome"] = calculate_outcome(record, exit_price=fill_price, exit_reason=exit_reason)
    record["metadata"]["finalized_at"] = datetime.now().isoformat()
    from .replay_scoring import apply_scoring

    record = apply_scoring(record)
    update_record_timestamp(record)
    return record


def calculate_outcome(
    record: Dict[str, Any],
    *,
    exit_price: float,
    exit_reason: str,
) -> Dict[str, Any]:
    """Compute P/L, R-multiple, and win/loss from plan + execution."""
    plan = record.get("trade_intent") or {}
    entry = (record.get("execution") or {}).get("entry") or {}
    entry_price = float(entry.get("price") or _price_from_level(plan.get("entry")) or 0)
    if entry_price <= 0 or exit_price <= 0:
        return {
            "pnl": None,
            "r_multiple": None,
            "win_loss": None,
            "exit_reason": exit_reason,
        }

    asset_class = record.get("market", {}).get("asset_class", AssetClass.STOCK.value)
    instrument_id = record.get("market", {}).get("instrument_id") or plan.get("instrument_id") or plan.get("symbol")
    direction = (plan.get("direction") or "LONG").upper()
    quantity = int(entry.get("quantity") or plan.get("quantity") or plan.get("contracts") or 1)

    pnl_value = _calculate_pnl(asset_class, instrument_id, direction, entry_price, exit_price, quantity, plan)
    risk_amount = float(plan.get("risk_amount") or plan.get("dollar_risk") or 0)
    r_multiple = round(pnl_value / risk_amount, 2) if risk_amount > 0 else None

    if pnl_value > 0:
        win_loss = "win"
    elif pnl_value < 0:
        win_loss = "loss"
    else:
        win_loss = "breakeven"

    return {
        "pnl": round(pnl_value, 2),
        "r_multiple": r_multiple,
        "win_loss": win_loss,
        "exit_reason": exit_reason,
    }


def _calculate_pnl(
    asset_class: str,
    instrument_id: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    quantity: int,
    plan: Dict[str, Any],
) -> float:
    if asset_class == AssetClass.FUTURES.value:
        raw = futures_pnl(entry_price, exit_price, quantity, instrument_id)
        if direction == "SHORT":
            raw = -raw
        return raw

    if asset_class == AssetClass.FOREX.value:
        symbol = plan.get("symbol") or instrument_id
        from ..market.forex import pip_size as get_pip_size, pip_value

        ps = get_pip_size(symbol)
        if direction == "LONG":
            pips = (exit_price - entry_price) / ps
        else:
            pips = (entry_price - exit_price) / ps
        lots = float(plan.get("position_lots") or (quantity / 100_000))
        per_lot = pip_value(symbol, entry_price, lots=1.0)
        return round(pips * per_lot * lots, 2)

    if direction == "LONG":
        return round((exit_price - entry_price) * quantity, 2)
    return round((entry_price - exit_price) * quantity, 2)


def _price_from_level(level: Any) -> Optional[float]:
    if isinstance(level, dict):
        price = level.get("price")
    else:
        price = level
    if price is None:
        return None
    return float(price)
