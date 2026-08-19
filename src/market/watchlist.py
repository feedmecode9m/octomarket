"""Watchlist — track symbols, prices, and daily movement."""

import threading
from typing import Any, Dict, List, Optional

SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "AMZN": "Technology", "TSLA": "Technology", "META": "Technology",
    "NVDA": "Technology", "NFLX": "Technology", "AMD": "Technology",
    "JPM": "Finance", "BAC": "Finance", "GS": "Finance", "MS": "Finance",
    "JNJ": "Healthcare", "PFE": "Healthcare", "UNH": "Healthcare",
    "XOM": "Energy", "CVX": "Energy",
    "SPY": "ETF", "QQQ": "ETF", "IWM": "ETF",
}


class Watchlist:
    """Manage a list of symbols with price tracking."""

    MAX_SYMBOLS = 20

    def __init__(self):
        self._lock = threading.RLock()
        self._symbols: Dict[str, Dict[str, Any]] = {}

    def add(self, symbol: str, price: float = 0.0, prev_close: float = 0.0) -> Dict[str, Any]:
        symbol = symbol.upper()
        with self._lock:
            if len(self._symbols) >= self.MAX_SYMBOLS and symbol not in self._symbols:
                raise ValueError(f"Watchlist full (max {self.MAX_SYMBOLS} symbols)")
            entry = self._symbols.get(symbol, {})
            self._symbols[symbol] = {
                "symbol": symbol,
                "price": price or entry.get("price", 0),
                "prev_close": prev_close or entry.get("prev_close", price),
                "sector": SECTOR_MAP.get(symbol, "Other"),
                "added_at": entry.get("added_at") or __import__("datetime").datetime.now().isoformat(),
            }
            return self._update_entry(symbol)

    def remove(self, symbol: str) -> bool:
        symbol = symbol.upper()
        with self._lock:
            if symbol in self._symbols:
                del self._symbols[symbol]
                return True
            return False

    def update_price(self, symbol: str, price: float, prev_close: Optional[float] = None):
        symbol = symbol.upper()
        with self._lock:
            if symbol not in self._symbols:
                return
            if prev_close is not None:
                self._symbols[symbol]["prev_close"] = prev_close
            self._symbols[symbol]["price"] = price

    def get_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [self._update_entry(s) for s in self._symbols]

    def get_symbols(self) -> List[str]:
        with self._lock:
            return list(self._symbols.keys())

    def _update_entry(self, symbol: str) -> Dict[str, Any]:
        entry = self._symbols[symbol]
        price = entry["price"]
        prev = entry.get("prev_close", price)
        change_pct = ((price - prev) / prev * 100) if prev > 0 else 0
        trend = "bullish" if change_pct > 0.5 else "bearish" if change_pct < -0.5 else "neutral"
        return {
            "symbol": symbol,
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "change_percent": round(change_pct, 2),
            "trend": trend,
            "sector": entry.get("sector", "Other"),
        }


_watchlist_instance: Optional[Watchlist] = None


def get_watchlist() -> Watchlist:
    global _watchlist_instance
    if _watchlist_instance is None:
        _watchlist_instance = Watchlist()
    return _watchlist_instance


def get_sector(symbol: str) -> str:
    return SECTOR_MAP.get(symbol.upper(), "Other")
