"""Market data provider contract for OHLCV retrieval."""

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


class MarketDataProvider(ABC):
    """Abstract OHLCV data source for chart and replay engines."""

    @abstractmethod
    def candles(
        self,
        instrument_id: str,
        timeframe: str,
        *,
        period: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles for an instrument.

        Args:
            instrument_id: Canonical or workspace symbol (e.g. AAPL, EURUSD, ESZ26).
            timeframe: Chart interval (e.g. 1d, 5m, 1h).
            period: Lookback period when start/end not set (yfinance-style).
            start: Optional start date (ISO string) for historical range.
            end: Optional end date (reserved for future providers).

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns, or empty.
        """
        raise NotImplementedError


_default_provider: Optional[MarketDataProvider] = None


def get_market_data_provider() -> MarketDataProvider:
    """Return the default market data provider (Yahoo)."""
    global _default_provider
    if _default_provider is None:
        from .yahoo_provider import YahooProvider
        _default_provider = YahooProvider()
    return _default_provider
