"""Real-time fill simulation for paper orders."""

from typing import Any, Dict, List, Optional

from ..simulation.paper_portfolio import PaperPortfolio, get_paper_portfolio
from .order_engine import OrderEngine, get_order_engine


class ExecutionSimulator:
    """Simulate order fills against candle data with slippage and commission."""

    def __init__(
        self,
        order_engine: Optional[OrderEngine] = None,
        portfolio: Optional[PaperPortfolio] = None,
    ):
        self.orders = order_engine or get_order_engine()
        self.portfolio = portfolio or get_paper_portfolio()

    def process_market_order(
        self,
        order: Dict[str, Any],
        current_price: float,
    ) -> Dict[str, Any]:
        """Immediately fill a market order."""
        if current_price <= 0:
            return self._reject(order, "No price available")

        side = order["side"]
        qty = order["quantity"]
        if side == "buy":
            result = self.portfolio.buy(order["symbol"], current_price, qty, reason="market order")
        else:
            result = self.portfolio.sell(order["symbol"], current_price, qty, reason="market order")

        if not result.get("success"):
            return self._reject(order, result.get("error", "Fill failed"))

        fill_price = result["fill_price"]
        self.orders.mark_filled(
            order["id"],
            fill_price,
            result["quantity"],
            result.get("commission", 0),
            result.get("slippage_cost", 0),
        )
        if order.get("role") == "entry":
            self.orders.activate_bracket_exits(order["id"])
        if order.get("role") in ("stop_loss", "take_profit"):
            self.orders.cancel_bracket_siblings(order["id"])

        return {"order_id": order["id"], "status": "FILLED", "fill": result}

    def process_candle(
        self,
        symbol: str,
        candle: Dict[str, float],
        current_price: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Process all pending orders for a symbol against OHLC candle."""
        symbol = symbol.upper()
        high = candle.get("high", current_price or 0)
        low = candle.get("low", current_price or 0)
        close = candle.get("close", current_price or 0)
        fills = []

        for order in self.orders.get_pending():
            if order["symbol"] != symbol:
                continue
            if order.get("parent_id") and order["role"] in ("stop_loss", "take_profit"):
                parent = self.orders.get_order(order["parent_id"])
                if not parent or parent["status"] != "FILLED":
                    continue

            fill_result = self._try_fill(order, high, low, close)
            if fill_result:
                fills.append(fill_result)

        return fills

    def process_all_symbols(self, candles: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        all_fills = []
        for symbol, candle in candles.items():
            all_fills.extend(self.process_candle(symbol, candle))
        return all_fills

    def _try_fill(
        self,
        order: Dict[str, Any],
        high: float,
        low: float,
        close: float,
    ) -> Optional[Dict[str, Any]]:
        ot = order["order_type"]
        side = order["side"]

        if ot == "market":
            return self.process_market_order(order, close)

        if ot == "limit":
            limit = order.get("limit_price", 0)
            if side == "buy" and low <= limit:
                return self._fill_at_price(order, min(limit, close))
            if side == "sell" and high >= limit:
                return self._fill_at_price(order, max(limit, close))
            return None

        if ot == "stop_market":
            stop = order.get("stop_price", 0)
            if side == "buy" and high >= stop:
                self.orders.mark_triggered(order["id"])
                return self._fill_at_price(order, max(stop, close))
            if side == "sell" and low <= stop:
                self.orders.mark_triggered(order["id"])
                return self._fill_at_price(order, min(stop, close))
            return None

        if ot == "stop_limit":
            stop = order.get("stop_price", 0)
            limit = order.get("limit_price", 0)
            if side == "buy" and high >= stop:
                self.orders.mark_triggered(order["id"])
                if low <= limit:
                    return self._fill_at_price(order, min(limit, close))
            if side == "sell" and low <= stop:
                self.orders.mark_triggered(order["id"])
                if high >= limit:
                    return self._fill_at_price(order, max(limit, close))
            return None

        return None

    def _fill_at_price(self, order: Dict[str, Any], price: float) -> Dict[str, Any]:
        side = order["side"]
        qty = order["quantity"]

        if side == "buy":
            result = self.portfolio.buy(order["symbol"], price, qty, reason=f"{order['order_type']} order")
        else:
            result = self.portfolio.sell(order["symbol"], price, qty, reason=f"{order['order_type']} order")

        if not result.get("success"):
            self.orders.mark_rejected(order["id"], result.get("error", "Fill failed"))
            return {"order_id": order["id"], "status": "REJECTED", "error": result.get("error")}

        actual_qty = result["quantity"]
        is_partial = actual_qty < qty

        self.orders.mark_filled(
            order["id"],
            result["fill_price"],
            actual_qty,
            result.get("commission", 0),
            result.get("slippage_cost", 0),
        )

        if order.get("role") == "entry":
            self.orders.activate_bracket_exits(order["id"])
        if order.get("role") in ("stop_loss", "take_profit"):
            self.orders.cancel_bracket_siblings(order["id"])

        status = "PARTIAL_FILL" if is_partial else "FILLED"
        return {"order_id": order["id"], "status": status, "fill": result, "partial": is_partial}

    def _reject(self, order: Dict[str, Any], reason: str) -> Dict[str, Any]:
        self.orders.mark_rejected(order["id"], reason)
        return {"order_id": order["id"], "status": "REJECTED", "error": reason}


_simulator_instance: Optional[ExecutionSimulator] = None


def get_execution_simulator() -> ExecutionSimulator:
    global _simulator_instance
    if _simulator_instance is None:
        _simulator_instance = ExecutionSimulator()
    return _simulator_instance
