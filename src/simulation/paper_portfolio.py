"""Realistic paper trading portfolio with commissions and slippage."""

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..market.watchlist import get_sector


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_cost: float
    opened_at: str


@dataclass
class TradeRecord:
    id: str
    timestamp: str
    symbol: str
    action: str
    quantity: int
    requested_price: float
    fill_price: float
    commission: float
    slippage_cost: float
    total_cost: float
    cash_after: float
    reason: str = ""


class PaperPortfolio:
    """Paper portfolio with commissions, slippage, and P/L tracking."""

    DEFAULT_COMMISSION_RATE = 0.001
    DEFAULT_SLIPPAGE_RATE = 0.0005

    def __init__(
        self,
        initial_cash: float = 10000.0,
        commission_rate: float = DEFAULT_COMMISSION_RATE,
        slippage_rate: float = DEFAULT_SLIPPAGE_RATE,
    ):
        self._lock = threading.RLock()
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.reset(initial_cash)

    def reset(self, initial_cash: Optional[float] = None):
        with self._lock:
            if initial_cash is not None:
                self.initial_cash = initial_cash
            self.cash = self.initial_cash
            self.positions: Dict[str, Position] = {}
            self.trade_history: List[TradeRecord] = []
            self.position_history: List[Dict[str, Any]] = []
            self.realized_pnl = 0.0
            self.total_commissions = 0.0
            self.total_slippage = 0.0

    def buy(
        self,
        symbol: str,
        price: float,
        quantity: int,
        timestamp: Optional[str] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        return self._execute("buy", symbol, price, quantity, timestamp, reason)

    def sell(
        self,
        symbol: str,
        price: float,
        quantity: Optional[int] = None,
        timestamp: Optional[str] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        symbol = symbol.upper()
        with self._lock:
            pos = self.positions.get(symbol)
            if not pos:
                return {"success": False, "error": f"No position in {symbol}"}
            qty = quantity if quantity is not None else pos.quantity
            qty = min(qty, pos.quantity)
        return self._execute("sell", symbol, price, qty, timestamp, reason)

    def hold(self, symbol: str = "", reason: str = "") -> Dict[str, Any]:
        return {
            "success": True,
            "action": "hold",
            "symbol": symbol.upper(),
            "message": "Held position — no trade executed.",
            "reason": reason,
        }

    def get_unrealized_pnl(self, symbol: str, current_price: float) -> float:
        with self._lock:
            pos = self.positions.get(symbol.upper())
            if not pos or current_price <= 0:
                return 0.0
            market_value = pos.quantity * current_price
            cost_basis = pos.quantity * pos.avg_cost
            return round(market_value - cost_basis, 2)

    def get_total_unrealized_pnl(self, prices: Dict[str, float]) -> float:
        total = 0.0
        with self._lock:
            for symbol, pos in self.positions.items():
                price = prices.get(symbol, 0)
                if price > 0:
                    total += pos.quantity * price - pos.quantity * pos.avg_cost
        return round(total, 2)

    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        with self._lock:
            value = self.cash
            for symbol, pos in self.positions.items():
                price = prices.get(symbol, prices.get(symbol.upper(), 0))
                if price > 0:
                    value += pos.quantity * price
            return round(value, 2)

    def get_allocation(self, prices: Dict[str, float]) -> Dict[str, float]:
        total = self.get_portfolio_value(prices)
        if total <= 0:
            return {}
        with self._lock:
            allocation = {"cash": round(self.cash / total * 100, 1)}
            for symbol, pos in self.positions.items():
                price = prices.get(symbol, 0)
                if price > 0:
                    allocation[symbol] = round(pos.quantity * price / total * 100, 1)
            return allocation

    def get_sector_exposure(self, prices: Dict[str, float]) -> Dict[str, float]:
        total = self.get_portfolio_value(prices)
        if total <= 0:
            return {}
        sectors: Dict[str, float] = {}
        with self._lock:
            for symbol, pos in self.positions.items():
                price = prices.get(symbol, 0)
                if price > 0:
                    sector = get_sector(symbol)
                    sectors[sector] = sectors.get(sector, 0) + pos.quantity * price
        return {s: round(v / total * 100, 1) for s, v in sectors.items()}

    def get_risk_score(self, prices: Dict[str, float]) -> float:
        """0-100 risk score based on concentration, cash reserves, and position count."""
        total = self.get_portfolio_value(prices)
        if total <= 0:
            return 0.0

        score = 0.0
        allocation = self.get_allocation(prices)
        cash_pct = allocation.get("cash", 0)

        max_position = max(
            (v for k, v in allocation.items() if k != "cash"),
            default=0,
        )
        if max_position > 50:
            score += 40
        elif max_position > 30:
            score += 25
        elif max_position > 20:
            score += 10

        sector_exp = self.get_sector_exposure(prices)
        max_sector = max(sector_exp.values(), default=0)
        if max_sector > 70:
            score += 30
        elif max_sector > 50:
            score += 15

        if cash_pct < 5:
            score += 20
        elif cash_pct < 10:
            score += 10

        with self._lock:
            if len(self.positions) >= 8:
                score += 10
            elif len(self.positions) >= 5:
                score += 5

        return min(round(score, 1), 100.0)

    def to_dict(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        current_prices = current_prices or {}
        with self._lock:
            positions = {}
            for sym, pos in self.positions.items():
                cp = current_prices.get(sym, 0)
                positions[sym] = {
                    "quantity": pos.quantity,
                    "avg_cost": round(pos.avg_cost, 4),
                    "current_price": cp,
                    "market_value": round(pos.quantity * cp, 2) if cp else 0,
                    "unrealized_pnl": self.get_unrealized_pnl(sym, cp),
                    "opened_at": pos.opened_at,
                }

            total_value = self.get_portfolio_value(current_prices)
            unrealized = self.get_total_unrealized_pnl(current_prices)

            return {
                "initial_cash": self.initial_cash,
                "cash": round(self.cash, 2),
                "positions": positions,
                "total_value": total_value,
                "realized_pnl": round(self.realized_pnl, 2),
                "unrealized_pnl": unrealized,
                "total_pnl": round(self.realized_pnl + unrealized, 2),
                "total_return_pct": round((total_value - self.initial_cash) / self.initial_cash * 100, 2)
                if self.initial_cash > 0
                else 0,
                "total_commissions": round(self.total_commissions, 2),
                "total_slippage": round(self.total_slippage, 2),
                "trade_count": len(self.trade_history),
                "position_history": list(self.position_history),
                "allocation": self.get_allocation(current_prices),
                "sector_exposure": self.get_sector_exposure(current_prices),
                "risk_score": self.get_risk_score(current_prices),
            }

    def _execute(
        self,
        action: str,
        symbol: str,
        price: float,
        quantity: int,
        timestamp: Optional[str],
        reason: str,
    ) -> Dict[str, Any]:
        symbol = symbol.upper()
        ts = timestamp or datetime.now().isoformat()

        if price <= 0 or quantity <= 0:
            return {"success": False, "error": "Price and quantity must be positive"}

        with self._lock:
            if action == "buy":
                fill_price = price * (1 + self.slippage_rate)
                gross = fill_price * quantity
                commission = gross * self.commission_rate
                total_cost = gross + commission
                if total_cost > self.cash:
                    max_qty = int(self.cash / (fill_price * (1 + self.commission_rate)))
                    if max_qty <= 0:
                        return {"success": False, "error": "Insufficient cash"}
                    quantity = max_qty
                    gross = fill_price * quantity
                    commission = gross * self.commission_rate
                    total_cost = gross + commission

                self.cash -= total_cost
                slippage_cost = (fill_price - price) * quantity

                if symbol in self.positions:
                    pos = self.positions[symbol]
                    total_qty = pos.quantity + quantity
                    pos.avg_cost = (pos.quantity * pos.avg_cost + quantity * fill_price) / total_qty
                    pos.quantity = total_qty
                else:
                    self.positions[symbol] = Position(symbol, quantity, fill_price, ts)

            else:  # sell
                pos = self.positions.get(symbol)
                if not pos or pos.quantity < quantity:
                    return {"success": False, "error": f"Insufficient shares of {symbol}"}

                fill_price = price * (1 - self.slippage_rate)
                gross = fill_price * quantity
                commission = gross * self.commission_rate
                proceeds = gross - commission
                slippage_cost = (price - fill_price) * quantity

                pnl = (fill_price - pos.avg_cost) * quantity - commission
                self.realized_pnl += pnl
                self.cash += proceeds

                pos.quantity -= quantity
                if pos.quantity == 0:
                    del self.positions[symbol]

            self.total_commissions += commission
            self.total_slippage += slippage_cost

            record = TradeRecord(
                id=str(uuid.uuid4()),
                timestamp=ts,
                symbol=symbol,
                action=action,
                quantity=quantity,
                requested_price=price,
                fill_price=round(fill_price, 4),
                commission=round(commission, 4),
                slippage_cost=round(slippage_cost, 4),
                total_cost=round(total_cost if action == "buy" else -proceeds, 4),
                cash_after=round(self.cash, 2),
                reason=reason,
            )
            self.trade_history.append(record)
            self.position_history.append({
                "timestamp": ts,
                "action": action,
                "symbol": symbol,
                "quantity": quantity,
                "fill_price": record.fill_price,
                "realized_pnl": round(pnl, 2) if action == "sell" else 0,
                "cash_after": record.cash_after,
            })

            return {
                "success": True,
                "action": action,
                "symbol": symbol,
                "quantity": quantity,
                "fill_price": record.fill_price,
                "commission": record.commission,
                "slippage_cost": record.slippage_cost,
                "cash_after": record.cash_after,
                "realized_pnl": round(self.realized_pnl, 2),
            }


_portfolio_instance: Optional[PaperPortfolio] = None


def get_paper_portfolio() -> PaperPortfolio:
    global _portfolio_instance
    if _portfolio_instance is None:
        _portfolio_instance = PaperPortfolio()
    return _portfolio_instance
