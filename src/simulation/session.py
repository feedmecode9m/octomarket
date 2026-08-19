"""Market session simulator — open, trade, close lifecycle."""

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from ..core.data_fetcher import DataFetcher


class MarketSession:
    """Simulate a trading session with market open, steps, and close."""

    STATES = ("idle", "pre_market", "open", "paused", "closed")

    def __init__(self):
        self._lock = threading.RLock()
        self._state = "idle"
        self._symbols: List[str] = []
        self._data: Dict[str, pd.DataFrame] = {}
        self._index = -1
        self._max_length = 0
        self._prices: Dict[str, float] = {}
        self._prev_closes: Dict[str, float] = {}
        self._started_at: Optional[str] = None
        self._initial_cash = 10000.0

    def start(self, symbols: List[str], initial_cash: float = 10000.0, period: str = "5d", interval: str = "1d") -> Dict[str, Any]:
        if not symbols:
            raise ValueError("At least one symbol required")

        with self._lock:
            self._symbols = [s.upper() for s in symbols]
            self._data = {}
            self._prices = {}
            self._prev_closes = {}
            self._max_length = 0

            for symbol in self._symbols:
                fetcher = DataFetcher(symbol=symbol, interval=interval, period=period)
                df = fetcher.get_real_time_data()
                if not df.empty:
                    self._data[symbol] = df
                    self._max_length = max(self._max_length, len(df))
                    self._prev_closes[symbol] = float(df["Close"].iloc[0])

            if not self._data:
                raise ValueError("Could not load data for any symbol")

            self._index = -1
            self._state = "pre_market"
            self._started_at = datetime.now().isoformat()
            self._initial_cash = initial_cash

            return self.get_state()

    def step(self) -> Dict[str, Any]:
        with self._lock:
            if self._state not in ("pre_market", "open", "paused"):
                return {"error": "Session not active", "state": self.get_state()}

            self._index += 1
            if self._index >= self._max_length:
                self._state = "closed"
                return self.get_state()

            if self._state == "pre_market":
                self._state = "open"

            for symbol, df in self._data.items():
                if self._index < len(df):
                    self._prices[symbol] = float(df["Close"].iloc[self._index])

            return self.get_state()

    def pause(self):
        with self._lock:
            if self._state == "open":
                self._state = "paused"

    def resume(self):
        with self._lock:
            if self._state == "paused":
                self._state = "open"

    def close(self):
        with self._lock:
            self._state = "closed"

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            progress = round((self._index + 1) / self._max_length * 100, 1) if self._max_length > 0 else 0
            candles = {}
            for symbol, df in self._data.items():
                if 0 <= self._index < len(df):
                    row = df.iloc[self._index]
                    ts = df.index[self._index]
                    candles[symbol] = {
                        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row["Volume"]),
                    }

            return {
                "state": self._state,
                "symbols": self._symbols,
                "current_index": self._index,
                "max_index": self._max_length - 1,
                "progress_pct": progress,
                "prices": dict(self._prices),
                "prev_closes": dict(self._prev_closes),
                "candles": candles,
                "started_at": self._started_at,
                "initial_cash": self._initial_cash,
                "at_end": self._index >= self._max_length - 1 if self._max_length > 0 else False,
            }

    def get_chart_data(self, symbol: str) -> Dict[str, Any]:
        with self._lock:
            df = self._data.get(symbol.upper())
            if df is None or self._index < 0:
                return {"timestamps": [], "prices": []}

            subset = df.iloc[: self._index + 1]
            timestamps = [t.isoformat() if hasattr(t, "isoformat") else str(t) for t in subset.index]
            prices = subset["Close"].tolist()
            return {"timestamps": timestamps, "prices": [float(p) for p in prices]}


_session_instance: Optional[MarketSession] = None


def get_market_session() -> MarketSession:
    global _session_instance
    if _session_instance is None:
        _session_instance = MarketSession()
    return _session_instance
