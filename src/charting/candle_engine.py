"""OHLCV candle loading with session-aware future-leak prevention."""

import threading
from typing import Any, Dict, Optional

import pandas as pd

from ..market.data_provider import MarketDataProvider, get_market_data_provider
from ..simulation.session import MarketSession, get_market_session
from .timeframe import validate_timeframe


REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


class CandleEngine:
    """Load and slice OHLCV candles for the chart workspace."""

    def __init__(
        self,
        session: Optional[MarketSession] = None,
        provider: Optional[MarketDataProvider] = None,
    ):
        self._lock = threading.RLock()
        self._session_override = session
        self._provider = provider or get_market_data_provider()
        self._cache: Dict[str, pd.DataFrame] = {}

    @property
    def _session(self) -> MarketSession:
        return self._session_override if self._session_override is not None else get_market_session()

    def get_candles(
        self,
        symbol: str,
        interval: Optional[str] = None,
        period: Optional[str] = None,
        max_index: Optional[int] = None,
        respect_session: bool = True,
    ) -> Dict[str, Any]:
        """
        Return OHLCV series for chart rendering.

        When respect_session is True and replay mode is active for the symbol,
        candles are capped at the session current_index (no future leakage).
        In LIVE mode the provider returns the full series regardless of session state.
        """
        symbol = symbol.upper()
        interval, period = validate_timeframe(
            interval or "1d",
            period,
        )

        df = self._load_ohlcv(symbol, interval, period, respect_session)

        cap_index = self._resolve_cap_index(symbol, max_index, respect_session)
        if cap_index is not None and not df.empty:
            cap_index = min(cap_index, len(df) - 1)
            if cap_index < 0:
                return self._empty_payload(symbol, interval, period, cap_index=-1)
            df = df.iloc[: cap_index + 1]

        return self._serialize(symbol, interval, period, df, cap_index)

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

    def _load_ohlcv(
        self,
        symbol: str,
        interval: str,
        period: str,
        respect_session: bool,
    ) -> pd.DataFrame:
        session_df = self._session_data_if_active(symbol, interval, period, respect_session)
        if session_df is not None:
            return session_df

        cache_key = f"{symbol}_{interval}_{period}"
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key].copy()

        df = self._provider.candles(symbol, interval, period=period)
        if df.empty:
            return pd.DataFrame()

        with self._lock:
            self._cache[cache_key] = df.copy()
        return df

    def _session_data_if_active(
        self,
        symbol: str,
        interval: str,
        period: str,
        respect_session: bool,
    ) -> Optional[pd.DataFrame]:
        if not respect_session or not self._replay_cap_active(symbol):
            return None
        return self._session.get_ohlcv_frame(symbol)

    def _replay_cap_active(self, symbol: str) -> bool:
        """Only cap candles during REPLAY — not in LIVE browsing."""
        from ..replay.replay_session import is_replay_mode

        return (
            is_replay_mode()
            and self._session.is_active()
            and self._session.has_symbol(symbol)
        )

    def _resolve_cap_index(
        self,
        symbol: str,
        max_index: Optional[int],
        respect_session: bool,
    ) -> Optional[int]:
        if max_index is not None:
            return max_index
        if not respect_session or not self._replay_cap_active(symbol):
            return None
        idx = self._session.get_session_index()
        return idx if idx >= 0 else None

    def _serialize(
        self,
        symbol: str,
        interval: str,
        period: str,
        df: pd.DataFrame,
        cap_index: Optional[int],
    ) -> Dict[str, Any]:
        if df.empty:
            return self._empty_payload(symbol, interval, period, cap_index)

        timestamps = [
            t.isoformat() if hasattr(t, "isoformat") else str(t) for t in df.index
        ]
        return {
            "symbol": symbol,
            "timeframe": interval,
            "period": period,
            "count": len(df),
            "session_capped": cap_index is not None and cap_index >= 0,
            "cap_index": cap_index,
            "timestamps": timestamps,
            "open": [float(x) for x in df["Open"]],
            "high": [float(x) for x in df["High"]],
            "low": [float(x) for x in df["Low"]],
            "close": [float(x) for x in df["Close"]],
            "volume": [float(x) for x in df["Volume"]],
        }

    def _empty_payload(
        self,
        symbol: str,
        interval: str,
        period: str,
        cap_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "timeframe": interval,
            "period": period,
            "count": 0,
            "session_capped": cap_index is not None and cap_index >= 0,
            "cap_index": cap_index,
            "timestamps": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }

    def _valid_ohlcv(self, df: pd.DataFrame) -> bool:
        return all(col in df.columns for col in REQUIRED_COLUMNS)


_engine_instance: Optional[CandleEngine] = None


def get_candle_engine() -> CandleEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CandleEngine()
    return _engine_instance
