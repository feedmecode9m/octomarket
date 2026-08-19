"""Tests for MarketDataProvider contract and Yahoo adapter."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.data_provider import MarketDataProvider, get_market_data_provider
from src.market.symbol_map import data_feed_symbol
from src.market.yahoo_provider import YahooProvider


def _sample_ohlcv(n=5, base=100.0):
    return pd.DataFrame(
        {
            "Open": [base + i for i in range(n)],
            "High": [base + i + 2 for i in range(n)],
            "Low": [base + i - 1 for i in range(n)],
            "Close": [base + i + 1 for i in range(n)],
            "Volume": [1_000_000 + i * 1000 for i in range(n)],
        },
        index=pd.date_range("2024-06-01", periods=n, freq="1D"),
    )


class TestProviderContract(unittest.TestCase):
    def test_default_provider_exposes_candles(self):
        provider = get_market_data_provider()
        self.assertIsInstance(provider, MarketDataProvider)
        self.assertTrue(callable(provider.candles))

    def test_subclass_must_implement_candles(self):
        class BrokenProvider(MarketDataProvider):
            pass

        with self.assertRaises(TypeError):
            BrokenProvider()

    def test_empty_instrument_id_rejected(self):
        provider = YahooProvider()
        with self.assertRaises(ValueError):
            provider.candles("", "1d", period="5d")


class TestYahooSymbolMapping(unittest.TestCase):
    def test_symbol_map_resolutions(self):
        self.assertEqual(data_feed_symbol("EURUSD"), "EURUSD=X")
        self.assertEqual(data_feed_symbol("ESZ26"), "ES=F")
        self.assertEqual(data_feed_symbol("MSFT"), "MSFT")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_yahoo_passes_resolved_symbol(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(3)
        provider = YahooProvider()

        provider.candles("EURUSD", "1d", period="5d")
        MockFetcher.assert_called_once()
        self.assertEqual(MockFetcher.call_args.kwargs["symbol"], "EURUSD=X")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_yahoo_futures_contract_symbol(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(3)
        provider = YahooProvider()

        provider.candles("ESZ26", "1d", period="5d")
        self.assertEqual(MockFetcher.call_args.kwargs["symbol"], "ES=F")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_timeframe_and_period_passed_to_fetcher(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(2)
        provider = YahooProvider()

        provider.candles("MSFT", "5m", period="1mo")
        kwargs = MockFetcher.call_args.kwargs
        self.assertEqual(kwargs["symbol"], "MSFT")
        self.assertEqual(kwargs["interval"], "5m")
        self.assertEqual(kwargs["period"], "1mo")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_invalid_instrument_returns_empty(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = pd.DataFrame()
        provider = YahooProvider()

        df = provider.candles("NOTAREALSYMBOL", "1d", period="5d")
        self.assertTrue(df.empty)


if __name__ == "__main__":
    unittest.main()
