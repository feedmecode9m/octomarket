"""Order management engine — TradingView-style order lifecycle."""

import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .bracket import create_bracket_exits

ORDER_STATUSES = ("CREATED", "PENDING", "TRIGGERED", "FILLED", "CANCELLED", "REJECTED")
ORDER_TYPES = ("market", "limit", "stop_market", "stop_limit")
SIDES = ("buy", "sell")


class OrderEngine:
    """Manage orders with full lifecycle and bracket support."""

    MAX_ORDERS = 200

    def __init__(self):
        self._lock = threading.RLock()
        self._orders: Dict[str, Dict[str, Any]] = {}

    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        bracket: bool = False,
        trade_plan: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        bracket_group_id: Optional[str] = None,
        role: str = "entry",
    ) -> Dict[str, Any]:
        symbol = symbol.upper()
        side = side.lower()
        order_type = order_type.lower()

        if side not in SIDES:
            raise ValueError(f"Invalid side: {side}")
        if order_type not in ORDER_TYPES:
            raise ValueError(f"Invalid order type: {order_type}")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        with self._lock:
            if len(self._orders) >= self.MAX_ORDERS:
                raise ValueError(f"Order limit reached ({self.MAX_ORDERS})")

            order_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            group_id = bracket_group_id or (str(uuid.uuid4()) if bracket else None)

            order = {
                "id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "filled_quantity": 0,
                "order_type": order_type,
                "limit_price": limit_price,
                "stop_price": stop_price,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "status": "CREATED",
                "created_at": now,
                "filled_at": None,
                "fill_price": None,
                "commission": None,
                "slippage": None,
                "bracket_group_id": group_id,
                "parent_id": parent_id,
                "role": role,
                "trade_plan": trade_plan or {},
                "reject_reason": None,
            }

            self._validate_order(order)
            if parent_id and role in ("stop_loss", "take_profit"):
                order["status"] = "CREATED"
            else:
                order["status"] = "PENDING"
            self._orders[order_id] = order

            result = order.copy()
            children = []

            if bracket and role == "entry" and side == "buy":
                children = create_bracket_exits(
                    self, symbol, quantity, order_id, group_id, stop_loss, take_profit
                )

            result["bracket_orders"] = children
            return result

    def update_order(self, order_id: str, **fields) -> Optional[Dict[str, Any]]:
        allowed = {"limit_price", "stop_price", "stop_loss", "take_profit", "quantity"}
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None
            if order["status"] not in ("PENDING", "CREATED", "TRIGGERED"):
                return None
            for key, val in fields.items():
                if key in allowed and val is not None:
                    order[key] = float(val) if key != "quantity" else int(val)
            return order.copy()

    def cancel_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None
            if order["status"] in ("FILLED", "CANCELLED", "REJECTED"):
                return order.copy()
            order["status"] = "CANCELLED"
            return order.copy()

    def cancel_bracket_siblings(self, order_id: str, exclude_roles: Optional[List[str]] = None):
        exclude_roles = exclude_roles or []
        with self._lock:
            order = self._orders.get(order_id)
            if not order or not order.get("bracket_group_id"):
                return
            group = order["bracket_group_id"]
            for o in self._orders.values():
                if (
                    o["bracket_group_id"] == group
                    and o["id"] != order_id
                    and o["role"] not in exclude_roles
                    and o["status"] in ("PENDING", "TRIGGERED", "CREATED")
                ):
                    o["status"] = "CANCELLED"

    def mark_filled(
        self,
        order_id: str,
        fill_price: float,
        filled_quantity: Optional[int] = None,
        commission: float = 0,
        slippage: float = 0,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None
            qty = filled_quantity or order["quantity"]
            order["filled_quantity"] = qty
            order["fill_price"] = round(fill_price, 4)
            order["commission"] = round(commission, 4)
            order["slippage"] = round(slippage, 4)
            order["status"] = "FILLED"
            order["filled_at"] = datetime.now().isoformat()
            return order.copy()

    def mark_rejected(self, order_id: str, reason: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None
            order["status"] = "REJECTED"
            order["reject_reason"] = reason
            return order.copy()

    def mark_triggered(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None
            if order["status"] == "PENDING":
                order["status"] = "TRIGGERED"
            return order.copy()

    def activate_bracket_exits(self, entry_order_id: str):
        """After entry fills, ensure bracket exit orders are pending."""
        with self._lock:
            entry = self._orders.get(entry_order_id)
            if not entry:
                return
            group = entry.get("bracket_group_id")
            if not group:
                return
            for o in self._orders.values():
                if o["bracket_group_id"] == group and o["role"] in ("stop_loss", "take_profit"):
                    if o["status"] == "CREATED":
                        o["status"] = "PENDING"

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            o = self._orders.get(order_id)
            return o.copy() if o else None

    def get_all(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            orders = list(self._orders.values())
            if status:
                orders = [o for o in orders if o["status"] == status.upper()]
            return [o.copy() for o in orders]

    def get_pending(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                o.copy()
                for o in self._orders.values()
                if o["status"] in ("PENDING", "TRIGGERED")
            ]

    def get_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        symbol = symbol.upper()
        with self._lock:
            return [o.copy() for o in self._orders.values() if o["symbol"] == symbol]

    def get_bracket_group(self, group_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [o.copy() for o in self._orders.values() if o.get("bracket_group_id") == group_id]

    def clear(self):
        with self._lock:
            self._orders.clear()

    def export_state(self) -> Dict[str, Any]:
        with self._lock:
            return {"orders": {oid: dict(order) for oid, order in self._orders.items()}}

    def import_state(self, state: Dict[str, Any]) -> None:
        with self._lock:
            self._orders = {
                oid: dict(order) for oid, order in (state.get("orders") or {}).items()
            }

    def _validate_order(self, order: Dict[str, Any]):
        ot = order["order_type"]
        if ot == "limit" and not order.get("limit_price"):
            raise ValueError("Limit orders require limit_price")
        if ot in ("stop_market", "stop_limit") and not order.get("stop_price"):
            raise ValueError("Stop orders require stop_price")
        if ot == "stop_limit" and not order.get("limit_price"):
            raise ValueError("Stop-limit orders require limit_price")


_engine_instance: Optional[OrderEngine] = None


def get_order_engine() -> OrderEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OrderEngine()
    return _engine_instance
