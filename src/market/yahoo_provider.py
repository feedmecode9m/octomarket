"""Yahoo Finance market data provider via existing DataFetcher."""

from typing import Optional

import pandas as pd

from ..charting.timeframe import get_default_period, normalize_interval
from ..core.data_fetcher import DataFetcher
from .data_provider import MarketDataProvider
from .symbol_map import data_feed_symbol

REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


class YahooProvider(MarketDataProvider):
    """Fetch OHLCV using yfinance through the legacy DataFetcher."""

    def candles(
        self,
        instrument_id: str,
        timeframe: str,
        *,
        period: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        if not instrument_id:
            raise ValueError("instrument_id is required")

        interval = normalize_interval(timeframe)
        feed_symbol = data_feed_symbol(instrument_id)

        if start:
            fetcher = DataFetcher(
                symbol=feed_symbol,
                interval=interval,
                period=period or get_default_period(interval),
                start_date=start,
            )
        else:
            fetcher = DataFetcher(
                symbol=feed_symbol,
                interval=interval,
                period=period or get_default_period(interval),
            )

        df = fetcher.get_real_time_data()
        if df.empty or not self._valid_ohlcv(df):
            return pd.DataFrame()

        if end is not None and not df.empty:
            end_ts = pd.Timestamp(end)
            df = df[df.index <= end_ts]

        return df.copy()

    def _valid_ohlcv(self, df: pd.DataFrame) -> bool:
        return all(col in df.columns for col in REQUIRED_COLUMNS)
