"""Trade plan model — thesis, levels, risk, and lifecycle before order execution."""

import threading
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

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


def validate_plan_levels(plan: Dict[str, Any]) -> None:
    """Validate entry/stop/target for direction."""
    direction = (plan.get("direction") or "LONG").upper()
    entry = _price_from_level(plan.get("entry"))
    stop = _price_from_level(plan.get("stop_loss"))
    target = _price_from_level(plan.get("target"))
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

    def __init__(self):
        self._lock = threading.RLock()
        self._plans: Dict[str, Dict[str, Any]] = {}

    def create_plan(self, data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = str(data.get("symbol", "")).upper()
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

        metrics = calculate_risk_reward(
            direction,
            entry["price"],
            stop["price"],
            target["price"],
            quantity,
        )
        plan.update(metrics)
        validate_plan_levels(plan)

        with self._lock:
            self._plans[plan["id"]] = deepcopy(plan)
            return deepcopy(plan)

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            plan = self._plans.get(plan_id)
            return deepcopy(plan) if plan else None

    def get_plans_for_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        symbol = symbol.upper()
        with self._lock:
            items = [p for p in self._plans.values() if p["symbol"] == symbol]
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

            metrics = calculate_risk_reward(
                plan["direction"],
                plan["entry"]["price"],
                plan["stop_loss"]["price"],
                plan["target"]["price"],
                plan["quantity"],
            )
            plan.update(metrics)
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
            return deepcopy(plan)

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
                "setup": plan.get("setup", {}),
                "entry_source": plan["entry"].get("source"),
                "risk_reward": plan.get("risk_reward"),
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
        return {
            "indicators": indicators if isinstance(indicators, list) else [],
            "drawings": drawings if isinstance(drawings, list) else [],
        }

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


_manager_instance: Optional[TradePlanManager] = None


def get_trade_plan_manager() -> TradePlanManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = TradePlanManager()
    return _manager_instance
