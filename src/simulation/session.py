"""Market session simulator — open, trade, close lifecycle."""

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from ..market.instrument import resolve_instrument


class MarketSession:
    """Simulate a trading session with market open, steps, and close."""

    STATES = ("idle", "pre_market", "open", "paused", "closed")

    def __init__(self):
        self._lock = threading.RLock()
        self._state = "idle"
        self._symbols: List[str] = []
        self._data: Dict[str, pd.DataFrame] = {}
        self._instruments: Dict[str, Dict[str, Any]] = {}
        self._index = -1
        self._max_length = 0
        self._prices: Dict[str, float] = {}
        self._prev_closes: Dict[str, float] = {}
        self._started_at: Optional[str] = None
        self._initial_cash = 10000.0
        self._interval = "1d"
        self._period = "5d"

    def start(
        self,
        symbols: List[str],
        initial_cash: float = 10000.0,
        period: str = "5d",
        interval: str = "1d",
    ) -> Dict[str, Any]:
        if not symbols:
            raise ValueError("At least one symbol required")

        from ..market.data_provider import get_market_data_provider

        provider = get_market_data_provider()

        with self._lock:
            self._symbols = []
            self._data = {}
            self._instruments = {}
            self._prices = {}
            self._prev_closes = {}
            self._max_length = 0
            self._interval = interval
            self._period = period

            for raw in symbols:
                instrument = resolve_instrument(raw)
                session_key = instrument.symbol.upper()
                df = provider.candles(instrument.instrument_id, interval, period=period)
                if df.empty:
                    continue

                self._data[session_key] = df
                self._instruments[session_key] = instrument.to_dict()
                if session_key not in self._symbols:
                    self._symbols.append(session_key)
                self._max_length = max(self._max_length, len(df))
                self._prev_closes[session_key] = float(df["Close"].iloc[0])

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

    def release(self) -> None:
        """Clear replay clock/price context so it cannot influence LIVE PAPER execution."""
        with self._lock:
            self._state = "idle"
            self._symbols = []
            self._data = {}
            self._instruments = {}
            self._index = -1
            self._max_length = 0
            self._prices = {}
            self._prev_closes = {}
            self._started_at = None

    def _resolve_session_key(self, raw: str) -> Optional[str]:
        text = (raw or "").upper()
        if text in self._data:
            return text
        try:
            instrument = resolve_instrument(text)
            key = instrument.symbol.upper()
            if key in self._data:
                return key
        except ValueError:
            return None
        return None

    def get_instrument(self, raw: str) -> Optional[Dict[str, Any]]:
        key = self._resolve_session_key(raw)
        if not key:
            return None
        with self._lock:
            payload = self._instruments.get(key)
            return dict(payload) if payload else None

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
                "symbols": list(self._symbols),
                "current_index": self._index,
                "max_index": self._max_length - 1,
                "progress_pct": progress,
                "prices": dict(self._prices),
                "prev_closes": dict(self._prev_closes),
                "candles": candles,
                "started_at": self._started_at,
                "initial_cash": self._initial_cash,
                "at_end": self._index >= self._max_length - 1 if self._max_length > 0 else False,
                "interval": self._interval,
                "period": self._period,
                "instruments": {k: dict(v) for k, v in self._instruments.items()},
            }

    def get_chart_data(self, symbol: str) -> Dict[str, Any]:
        with self._lock:
            key = self._resolve_session_key(symbol)
            if not key:
                return {"timestamps": [], "prices": []}
            df = self._data.get(key)
            if df is None or self._index < 0:
                return {"timestamps": [], "prices": []}

            subset = df.iloc[: self._index + 1]
            timestamps = [t.isoformat() if hasattr(t, "isoformat") else str(t) for t in subset.index]
            prices = subset["Close"].tolist()
            return {"timestamps": timestamps, "prices": [float(p) for p in prices]}

    def is_active(self) -> bool:
        with self._lock:
            return self._state not in ("idle", "closed")

    def has_symbol(self, symbol: str) -> bool:
        with self._lock:
            key = self._resolve_session_key(symbol)
            if not key:
                return False
            df = self._data.get(key)
            return df is not None and not df.empty

    def get_ohlcv_frame(self, symbol: str) -> Optional[pd.DataFrame]:
        with self._lock:
            key = self._resolve_session_key(symbol)
            if not key:
                return None
            df = self._data.get(key)
            if df is None or df.empty:
                return None
            return df.copy()

    def get_session_index(self) -> int:
        with self._lock:
            return self._index

    def resolve_key(self, raw: str) -> Optional[str]:
        with self._lock:
            return self._resolve_session_key(raw)


_session_instance: Optional[MarketSession] = None


def get_market_session() -> MarketSession:
    global _session_instance
    if _session_instance is None:
        _session_instance = MarketSession()
    return _session_instance
