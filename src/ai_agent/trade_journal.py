"""Trade journal for recording and reviewing trading decisions."""

import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class TradeJournal:
    """Record trades with rationale, entry/exit, result, and lessons learned."""

    def __init__(self):
        self._entries: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def record(
        self,
        symbol: str,
        trade_type: str,
        entry_price: float,
        quantity: int,
        reason: str,
        exit_price: Optional[float] = None,
        lesson_learned: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a new journal entry."""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol.upper(),
            "type": trade_type.lower(),
            "entry_price": float(entry_price),
            "exit_price": float(exit_price) if exit_price is not None else None,
            "quantity": int(quantity),
            "reason": reason,
            "lesson_learned": lesson_learned,
            "strategy": strategy,
            "result": self._calculate_result(trade_type, entry_price, exit_price, quantity),
            "status": "closed" if exit_price is not None else "open",
        }

        with self._lock:
            self._entries.append(entry)

        return entry.copy()

    def update_exit(self, entry_id: str, exit_price: float, lesson_learned: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Close an open journal entry with exit details."""
        with self._lock:
            for entry in self._entries:
                if entry["id"] == entry_id:
                    entry["exit_price"] = float(exit_price)
                    entry["status"] = "closed"
                    entry["result"] = self._calculate_result(
                        entry["type"], entry["entry_price"], exit_price, entry["quantity"]
                    )
                    if lesson_learned:
                        entry["lesson_learned"] = lesson_learned
                    return entry.copy()
        return None

    def get_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.copy() for e in self._entries]

    def get_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        symbol = symbol.upper()
        with self._lock:
            return [e.copy() for e in self._entries if e["symbol"] == symbol]

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for entry in self._entries:
                if entry["id"] == entry_id:
                    return entry.copy()
        return None

    def clear(self):
        with self._lock:
            self._entries.clear()

    def sync_from_trades(self, trades: List[Dict[str, Any]], strategy_name: str = "MA Crossover + RSI") -> int:
        """Sync journal from simulator trade list. Returns number of new entries."""
        added = 0

        with self._lock:
            existing_keys = {
                (e.get("trade_time") or e["timestamp"], e["symbol"], e["type"], e["entry_price"])
                for e in self._entries
            }

            for trade in trades:
                trade_time = trade.get("time", "")
                key = (
                    trade_time,
                    trade.get("symbol", "").upper(),
                    trade.get("type", "").lower(),
                    float(trade.get("price", 0)),
                )
                if key in existing_keys:
                    continue

                entry = {
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat(),
                    "trade_time": trade_time,
                    "symbol": trade.get("symbol", "UNKNOWN").upper(),
                    "type": trade.get("type", "buy").lower(),
                    "entry_price": float(trade.get("price", 0)),
                    "exit_price": None,
                    "quantity": int(trade.get("quantity", 0)),
                    "reason": self._infer_reason(trade.get("type", "buy"), strategy_name),
                    "lesson_learned": None,
                    "strategy": strategy_name,
                    "result": None,
                    "status": "open",
                }
                self._entries.append(entry)
                existing_keys.add(key)
                added += 1

        return added

    def get_summary(self) -> Dict[str, Any]:
        """Summarize journal performance."""
        entries = self.get_all()
        closed = [e for e in entries if e["status"] == "closed" and e["result"]]

        wins = sum(1 for e in closed if e["result"].get("pnl", 0) > 0)
        losses = sum(1 for e in closed if e["result"].get("pnl", 0) <= 0)
        total_pnl = sum(e["result"].get("pnl", 0) for e in closed)

        lessons = [e["lesson_learned"] for e in closed if e.get("lesson_learned")]

        return {
            "total_entries": len(entries),
            "closed_trades": len(closed),
            "open_trades": len(entries) - len(closed),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(closed) * 100, 1) if closed else 0,
            "total_pnl": round(total_pnl, 2),
            "recent_lessons": lessons[-5:],
        }

    def _calculate_result(
        self,
        trade_type: str,
        entry_price: float,
        exit_price: Optional[float],
        quantity: int,
    ) -> Optional[Dict[str, Any]]:
        if exit_price is None:
            return None

        if trade_type == "buy":
            pnl = (exit_price - entry_price) * quantity
            pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        else:
            pnl = (entry_price - exit_price) * quantity
            pnl_pct = ((entry_price - exit_price) / entry_price * 100) if entry_price > 0 else 0

        return {
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "outcome": "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven",
        }

    def _infer_reason(self, trade_type: str, strategy: str) -> str:
        if trade_type == "buy":
            return f"Buy signal triggered by {strategy} — short MA crossed above long MA with confirming RSI/momentum."
        return f"Sell signal triggered by {strategy} — death cross, profit target, or stop loss hit."


# Global journal instance
_journal_instance: Optional[TradeJournal] = None


def get_trade_journal() -> TradeJournal:
    global _journal_instance
    if _journal_instance is None:
        _journal_instance = TradeJournal()
    return _journal_instance
