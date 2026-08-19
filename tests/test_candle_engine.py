"""Tests for OHLCV candle engine and future-leak prevention."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.charting.candle_engine import CandleEngine
from src.simulation.session import MarketSession


def _sample_ohlcv(n=10, base=100):
    return pd.DataFrame(
        {
            "Open": [base + i for i in range(n)],
            "High": [base + i + 2 for i in range(n)],
            "Low": [base + i - 1 for i in range(n)],
            "Close": [base + i + 1 for i in range(n)],
            "Volume": [1000000 + i * 1000 for i in range(n)],
        },
        index=pd.date_range("2024-06-01", periods=n, freq="1D"),
    )


class TestCandleEngine(unittest.TestCase):
    def setUp(self):
        self.session = MarketSession()
        self.engine = CandleEngine(self.session)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_ohlcv_retrieval(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
        result = self.engine.get_candles("AAPL", interval="1d", period="5d", respect_session=False)
        self.assertEqual(result["count"], 5)
        self.assertEqual(len(result["open"]), 5)
        self.assertEqual(len(result["volume"]), 5)
        self.assertEqual(result["close"][-1], 105.0)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_empty_data(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = pd.DataFrame()
        result = self.engine.get_candles("AAPL", respect_session=False)
        self.assertEqual(result["count"], 0)

    @mock.patch("src.replay.replay_session.is_replay_mode", return_value=True)
    def test_session_caps_future_candles(self, _mock_replay):
        df = _sample_ohlcv(10)
        self.session._data["AAPL"] = df
        self.session._symbols = ["AAPL"]
        self.session._state = "open"
        self.session._index = 2
        self.session._max_length = 10

        result = self.engine.get_candles("AAPL", respect_session=True)
        self.assertTrue(result["session_capped"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["cap_index"], 2)
        self.assertEqual(result["close"][-1], 103.0)

    @mock.patch("src.replay.replay_session.is_replay_mode", return_value=True)
    def test_no_future_leak_full_series_unavailable(self, _mock_replay):
        df = _sample_ohlcv(10)
        self.session._data["AAPL"] = df
        self.session._symbols = ["AAPL"]
        self.session._state = "open"
        self.session._index = 0
        self.session._max_length = 10

        result = self.engine.get_candles("AAPL", respect_session=True)
        self.assertEqual(result["count"], 1)
        self.assertNotEqual(result["count"], 10)

    @mock.patch("src.replay.replay_session.is_replay_mode", return_value=False)
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_live_mode_ignores_active_session_index(self, MockFetcher, _mock_replay):
        """LIVE browsing must not cap candles even if MarketSession has stale state."""
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(10)
        df = _sample_ohlcv(10)
        self.session._data["AAPL"] = df
        self.session._symbols = ["AAPL"]
        self.session._state = "open"
        self.session._index = 2
        self.session._max_length = 10

        result = self.engine.get_candles("AAPL", respect_session=True)
        self.assertFalse(result["session_capped"])
        self.assertEqual(result["count"], 10)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_explicit_max_index(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8)
        result = self.engine.get_candles("AAPL", max_index=3, respect_session=False)
        self.assertEqual(result["count"], 4)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_chart_api_candles(self, MockFetcher):
        from app import create_app
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6)
        app = create_app()
        client = app.test_client()
        resp = client.get("/api/chart/AAPL")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["symbol"], "AAPL")
        self.assertIn("open", data)
        self.assertIn("high", data)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_chart_api_404_no_data(self, MockFetcher):
        from app import create_app
        MockFetcher.return_value.get_real_time_data.return_value = pd.DataFrame()
        app = create_app()
        client = app.test_client()
        resp = client.get("/api/chart/INVALID")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
