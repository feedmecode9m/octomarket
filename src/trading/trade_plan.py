"""Trade plan model — thesis, levels, risk, and lifecycle before order execution."""

import threading
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..market.asset_class import AssetClass
from ..market.forex import lot_to_units, pip_distance, pip_value
from ..market.futures import calculate_futures_size, risk_amount as futures_risk_amount, tick_distance
from ..market.instrument import resolve_instrument
from .position_sizing import calculate_forex_size
from .risk import account_risk_percent, reward_ratio

PLAN_STATUSES = ("DRAFT", "REVIEWED", "APPROVED", "ORDER_CREATED", "COMPLETED")
DIRECTIONS = ("LONG", "SHORT")

STATUS_TRANSITIONS = {
    "DRAFT": ("REVIEWED",),
    "REVIEWED": ("APPROVED", "DRAFT"),
    "APPROVED": ("ORDER_CREATED", "DRAFT"),
    "ORDER_CREATED": ("COMPLETED",),
    "COMPLETED": (),
}


def calculate_risk_reward(
    direction: str,
    entry: float,
    stop: float,
    target: float,
    quantity: int = 1,
) -> Dict[str, Any]:
    """Compute point and dollar risk/reward and R:R ratio."""
    direction = direction.upper()
    if direction not in DIRECTIONS:
        raise ValueError(f"Direction must be LONG or SHORT, got '{direction}'")
    if entry <= 0 or stop <= 0 or target <= 0:
        raise ValueError("Entry, stop, and target must be positive prices")
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    if direction == "LONG":
        risk_points = entry - stop
        reward_points = target - entry
    else:
        risk_points = stop - entry
        reward_points = entry - target

    if risk_points <= 0:
        raise ValueError("Stop loss must be on the correct side of entry for direction")
    if reward_points <= 0:
        raise ValueError("Target must be on the correct side of entry for direction")

    rr = round(reward_points / risk_points, 2)
    dollar_risk = round(risk_points * quantity, 2)
    dollar_reward = round(reward_points * quantity, 2)

    return {
        "risk_points": round(risk_points, 4),
        "reward_points": round(reward_points, 4),
        "risk_reward": rr,
        "dollar_risk": dollar_risk,
        "dollar_reward": dollar_reward,
    }


def normalize_plan_metrics(
    plan: Dict[str, Any],
    account_balance: Optional[float] = None,
    risk_percent: Optional[float] = None,
) -> Dict[str, Any]:
    """Enrich plan with instrument-aware risk metrics."""
    raw_id = plan.get("instrument_id") or plan.get("symbol", "")
    instrument = resolve_instrument(raw_id)
    plan["symbol"] = instrument.symbol
    plan["instrument_id"] = instrument.instrument_id
    plan["asset_class"] = (
        plan.get("asset_class") or instrument.asset_class.value
    )
    if isinstance(plan["asset_class"], AssetClass):
        plan["asset_class"] = plan["asset_class"].value

    direction = (plan.get("direction") or "LONG").upper()
    entry = _price_from_level(plan.get("entry"))
    stop = _price_from_level(plan.get("stop_loss"))
    target = _price_from_level(plan.get("target"))

    if instrument.asset_class == AssetClass.FOREX:
        return _apply_forex_metrics(plan, instrument.symbol, direction, entry, stop, target, account_balance, risk_percent)

    if instrument.asset_class == AssetClass.FUTURES:
        return _apply_futures_metrics(plan, instrument.instrument_id, direction, entry, stop, target, account_balance, risk_percent)

    quantity = int(plan.get("quantity") or 10)
    metrics = calculate_risk_reward(direction, entry, stop, target, quantity)
    plan.update(metrics)
    plan["quantity_unit"] = "shares"
    return plan


def _apply_forex_metrics(
    plan: Dict[str, Any],
    symbol: str,
    direction: str,
    entry: float,
    stop: float,
    target: float,
    account_balance: Optional[float],
    risk_percent: Optional[float],
) -> Dict[str, Any]:
    pip_risk = pip_distance(entry, stop, symbol)
    reward_pips = pip_distance(entry, target, symbol)

    if account_balance and risk_percent:
        sizing = calculate_forex_size(account_balance, risk_percent, entry, stop, symbol)
        plan["position_lots"] = sizing["lots"]
        plan["quantity"] = sizing["units"]
        plan["risk_amount"] = sizing["risk_amount"]
        plan["risk_percent"] = risk_percent
    elif plan.get("position_lots") is not None:
        lots = float(plan["position_lots"])
        plan["quantity"] = lot_to_units(lots)
        per_lot = pip_value(symbol, entry, lots=1.0)
        plan["risk_amount"] = round(pip_risk * per_lot * lots, 2)
    else:
        quantity = int(plan.get("quantity") or lot_to_units(1.0))
        lots = round(quantity / 100_000, 4)
        plan["position_lots"] = lots
        per_lot = pip_value(symbol, entry, lots=1.0)
        plan["risk_amount"] = round(pip_risk * per_lot * lots, 2)

    plan["pip_risk"] = pip_risk
    plan["reward_pips"] = reward_pips
    plan["quantity_unit"] = "lots"
    plan["risk_reward"] = reward_ratio(1.0, reward_pips / pip_risk) if pip_risk > 0 else 0
    plan["dollar_risk"] = plan["risk_amount"]
    plan["dollar_reward"] = round(
        plan["risk_amount"] * plan["risk_reward"] if plan.get("risk_reward") else 0,
        2,
    )
    if account_balance and plan.get("risk_amount"):
        plan["account_risk_percent"] = account_risk_percent(plan["risk_amount"], account_balance)
    return plan


def _apply_futures_metrics(
    plan: Dict[str, Any],
    instrument_id: str,
    direction: str,
    entry: float,
    stop: float,
    target: float,
    account_balance: Optional[float],
    risk_percent: Optional[float],
) -> Dict[str, Any]:
    tick_risk = tick_distance(entry, stop, instrument_id)
    reward_ticks = tick_distance(entry, target, instrument_id)

    if account_balance and risk_percent:
        sizing = calculate_futures_size(account_balance, risk_percent, entry, stop, instrument_id)
        plan["contracts"] = sizing["contracts"]
        plan["quantity"] = sizing["contracts"]
        plan["risk_amount"] = sizing["risk_amount"]
        plan["risk_percent"] = risk_percent
        plan["margin_required"] = sizing["margin_required"]
    elif plan.get("contracts") is not None:
        contracts = int(plan["contracts"])
        plan["quantity"] = contracts
        plan["risk_amount"] = futures_risk_amount(entry, stop, contracts, instrument_id)
    else:
        contracts = int(plan.get("quantity") or 1)
        plan["contracts"] = contracts
        plan["risk_amount"] = futures_risk_amount(entry, stop, contracts, instrument_id)

    plan["tick_risk"] = tick_risk
    plan["reward_ticks"] = reward_ticks
    plan["stop_distance"] = tick_risk
    plan["stop_unit"] = "ticks"
    plan["quantity_unit"] = "contracts"
    plan["unit_type"] = "contracts"
    plan["risk_reward"] = reward_ratio(1.0, reward_ticks / tick_risk) if tick_risk > 0 else 0
    plan["dollar_risk"] = plan["risk_amount"]
    plan["dollar_reward"] = round(
        plan["risk_amount"] * plan["risk_reward"] if plan.get("risk_reward") else 0,
        2,
    )
    if account_balance and plan.get("risk_amount"):
        plan["account_risk_percent"] = account_risk_percent(plan["risk_amount"], account_balance)
    return plan


def validate_plan_levels(plan: Dict[str, Any]) -> None:
    """Validate entry/stop/target for direction."""
    asset_class = plan.get("asset_class", AssetClass.STOCK.value)
    direction = (plan.get("direction") or "LONG").upper()
    entry = _price_from_level(plan.get("entry"))
    stop = _price_from_level(plan.get("stop_loss"))
    target = _price_from_level(plan.get("target"))

    if asset_class in (AssetClass.FOREX.value, AssetClass.FUTURES.value):
        if direction == "LONG":
            if stop >= entry:
                raise ValueError("Stop loss must be below entry for LONG")
            if target <= entry:
                raise ValueError("Target must be above entry for LONG")
        else:
            if stop <= entry:
                raise ValueError("Stop loss must be above entry for SHORT")
            if target >= entry:
                raise ValueError("Target must be below entry for SHORT")
        return

    quantity = int(plan.get("quantity") or 1)
    calculate_risk_reward(direction, entry, stop, target, quantity)


def _price_from_level(level: Any) -> float:
    if isinstance(level, dict):
        price = level.get("price")
    else:
        price = level
    if price is None:
        raise ValueError("Price level is required")
    return float(price)


def _normalize_level(level: Any, default_source: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if isinstance(level, dict):
        result = {"price": float(level["price"])}
        if level.get("source"):
            result["source"] = level["source"]
        elif default_source:
            result["source"] = default_source
        return result
    return {"price": float(level)}


class TradePlanManager:
    """In-memory trade plan store and lifecycle."""

    def __init__(self, record_replay: bool = False):
        self._lock = threading.RLock()
        self._plans: Dict[str, Dict[str, Any]] = {}
        self._record_replay = record_replay

    def create_plan(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raw = data.get("symbol") or data.get("instrument_id") or ""
        symbol = str(raw).upper()
        if not symbol:
            raise ValueError("Symbol is required")

        direction = str(data.get("direction", "LONG")).upper()
        if direction not in DIRECTIONS:
            raise ValueError(f"Direction must be LONG or SHORT")

        entry = _normalize_level(data.get("entry") or data.get("entry_price"))
        stop = _normalize_level(data.get("stop_loss") or data.get("stop"))
        target = _normalize_level(data.get("target") or data.get("take_profit"))
        quantity = int(data.get("quantity") or 10)

        plan = {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "instrument_id": str(data.get("instrument_id") or symbol).upper(),
            "asset_class": data.get("asset_class"),
            "direction": direction,
            "thesis": data.get("thesis") or "",
            "entry": entry,
            "stop_loss": stop,
            "target": target,
            "quantity": quantity,
            "setup": self._normalize_setup(data.get("setup") or {}),
            "status": "DRAFT",
            "order_id": None,
            "review_notes": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        if data.get("position_lots") is not None:
            plan["position_lots"] = float(data["position_lots"])
        if data.get("contracts") is not None:
            plan["contracts"] = int(data["contracts"])
        if data.get("strategy_id"):
            plan["strategy_id"] = data["strategy_id"]
        if data.get("strategy_name"):
            plan["strategy_name"] = data["strategy_name"]
        if data.get("strategy_confidence") is not None:
            plan["strategy_confidence"] = float(data["strategy_confidence"])

        normalize_plan_metrics(
            plan,
            account_balance=data.get("account_balance"),
            risk_percent=data.get("risk_percent"),
        )
        validate_plan_levels(plan)

        with self._lock:
            self._plans[plan["id"]] = deepcopy(plan)
            created = deepcopy(plan)

        if self._record_replay:
            self._record_plan_created(created)
        return created

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            plan = self._plans.get(plan_id)
            return deepcopy(plan) if plan else None

    def get_plans_for_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        symbol = symbol.upper()
        with self._lock:
            items = [p for p in self._plans.values() if p["symbol"] == symbol or p.get("instrument_id") == symbol]
            return deepcopy(sorted(items, key=lambda p: p["created_at"], reverse=True))

    def update_plan(self, plan_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                raise KeyError(f"Trade plan '{plan_id}' not found")
            if plan["status"] in ("ORDER_CREATED", "COMPLETED"):
                raise ValueError("Cannot update plan after order is created")

            if data.get("symbol"):
                plan["symbol"] = str(data["symbol"]).upper()
            if data.get("direction"):
                plan["direction"] = str(data["direction"]).upper()
            if data.get("thesis") is not None:
                plan["thesis"] = data["thesis"]
            if data.get("quantity"):
                plan["quantity"] = int(data["quantity"])
            if data.get("entry") is not None:
                plan["entry"] = _normalize_level(data["entry"])
            if data.get("stop_loss") is not None:
                plan["stop_loss"] = _normalize_level(data["stop_loss"])
            if data.get("target") is not None:
                plan["target"] = _normalize_level(data["target"])
            if data.get("setup") is not None:
                plan["setup"] = self._normalize_setup(data["setup"])
            if data.get("position_lots") is not None:
                plan["position_lots"] = float(data["position_lots"])
            if data.get("contracts") is not None:
                plan["contracts"] = int(data["contracts"])

            normalize_plan_metrics(
                plan,
                account_balance=data.get("account_balance"),
                risk_percent=data.get("risk_percent"),
            )
            validate_plan_levels(plan)
            plan["updated_at"] = datetime.now().isoformat()
            self._plans[plan_id] = plan
            return deepcopy(plan)

    def review_plan(self, plan_id: str, notes: Optional[List[str]] = None) -> Dict[str, Any]:
        return self._transition(plan_id, "REVIEWED", notes=notes)

    def approve_plan(self, plan_id: str) -> Dict[str, Any]:
        return self._transition(plan_id, "APPROVED")

    def mark_order_created(self, plan_id: str, order_id: str) -> Dict[str, Any]:
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                raise KeyError(f"Trade plan '{plan_id}' not found")
            if plan["status"] != "APPROVED":
                raise ValueError("Plan must be APPROVED before creating order")
            plan["status"] = "ORDER_CREATED"
            plan["order_id"] = order_id
            plan["updated_at"] = datetime.now().isoformat()
            updated = deepcopy(plan)

        if self._record_replay:
            self._record_order_submitted(plan_id, order_id)
        return updated

    def mark_completed(self, plan_id: str) -> Dict[str, Any]:
        return self._transition(plan_id, "COMPLETED")

    def build_order_payload(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Build order_engine payload from approved plan."""
        side = "buy" if plan["direction"] == "LONG" else "sell"
        entry_price = plan["entry"]["price"]
        return {
            "symbol": plan["symbol"],
            "side": side,
            "quantity": plan["quantity"],
            "order_type": "limit",
            "limit_price": entry_price,
            "stop_loss": plan["stop_loss"]["price"],
            "take_profit": plan["target"]["price"],
            "bracket": True,
            "trade_plan": {
                "plan_id": plan["id"],
                "thesis": plan["thesis"],
                "direction": plan["direction"],
                "asset_class": plan.get("asset_class"),
                "instrument_id": plan.get("instrument_id"),
                "setup": plan.get("setup", {}),
                "entry_source": plan["entry"].get("source"),
                "risk_reward": plan.get("risk_reward"),
                "position_lots": plan.get("position_lots"),
                "contracts": plan.get("contracts"),
                "tick_risk": plan.get("tick_risk"),
                "pip_risk": plan.get("pip_risk"),
                "risk_amount": plan.get("risk_amount"),
                "unit_type": plan.get("unit_type") or plan.get("quantity_unit"),
                "why_enter": plan["thesis"],
                "setup_type": self._setup_summary(plan),
                "invalidation": f"Stop at {plan['stop_loss']['price']}",
                "expected_move": f"Target {plan['target']['price']}",
            },
        }

    def reset(self):
        with self._lock:
            self._plans.clear()

    def _transition(
        self,
        plan_id: str,
        target_status: str,
        notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                raise KeyError(f"Trade plan '{plan_id}' not found")

            current = plan["status"]
            allowed = STATUS_TRANSITIONS.get(current, ())
            if target_status not in allowed and target_status != current:
                raise ValueError(f"Cannot transition from {current} to {target_status}")

            if target_status in ("REVIEWED", "APPROVED"):
                validate_plan_levels(plan)

            plan["status"] = target_status
            if notes:
                plan["review_notes"] = list(notes)
            plan["updated_at"] = datetime.now().isoformat()
            return deepcopy(plan)

    def _normalize_setup(self, setup: Dict[str, Any]) -> Dict[str, Any]:
        indicators = setup.get("indicators") or []
        drawings = setup.get("drawings") or []
        result = {
            "indicators": indicators if isinstance(indicators, list) else [],
            "drawings": drawings if isinstance(drawings, list) else [],
        }
        if setup.get("strategy"):
            result["strategy"] = setup["strategy"]
        return result

    def _setup_summary(self, plan: Dict[str, Any]) -> str:
        parts = []
        setup = plan.get("setup") or {}
        for ind in setup.get("indicators") or []:
            if isinstance(ind, dict):
                parts.append(ind.get("key") or ind.get("name") or str(ind))
            else:
                parts.append(str(ind))
        if parts:
            return ", ".join(parts)
        return plan.get("thesis") or "Trade plan"

    def _record_plan_created(self, plan: Dict[str, Any]) -> None:
        from ..replay.replay_memory import get_replay_memory

        get_replay_memory().on_plan_created(plan)

    def _record_order_submitted(self, plan_id: str, order_id: str) -> None:
        from ..replay.replay_memory import get_replay_memory
        from .order_engine import get_order_engine

        order = get_order_engine().get_order(order_id) or {"id": order_id}
        get_replay_memory().on_order_submitted(plan_id, order_id, order)


_manager_instance: Optional[TradePlanManager] = None


def get_trade_plan_manager() -> TradePlanManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = TradePlanManager(record_replay=True)
    return _manager_instance
