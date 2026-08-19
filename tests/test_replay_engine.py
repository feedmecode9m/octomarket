"""Tests for canonical replay engine — multi-asset and serialization."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.replay.replay_session import ReplaySessionManager
from src.simulation.session import MarketSession


def _sample_ohlcv(n=10, base=100.0):
    return pd.DataFrame(
        {
            "Open": [base + i for i in range(n)],
            "High": [base + i + 1 for i in range(n)],
            "Low": [base + i - 1 for i in range(n)],
            "Close": [base + i + 0.5 for i in range(n)],
            "Volume": [1000] * n,
        },
        index=pd.date_range("2026-01-01", periods=n, freq="1D"),
    )


class TestCanonicalReplayEngine(unittest.TestCase):
    def setUp(self):
        self.session = MarketSession()
        self.replay = ReplaySessionManager(session=self.session)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_create_stock_replay_session(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6, 180)
        state = self.replay.start(instrument_id="AAPL")
        self.assertEqual(state["instrument"]["asset_class"], "STOCK")
        self.assertEqual(state["mode"], "replay")
        self.assertEqual(state["total_candles"], 6)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_create_forex_replay_session(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5, 1.08)
        state = self.replay.start(instrument_id="EURUSD")
        self.assertEqual(state["instrument"]["asset_class"], "FOREX")
        self.assertNotIn("continuous_id", state["instrument"])

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_create_futures_replay_session(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5, 5000)
        state = self.replay.start(instrument_id="ESZ26")
        self.assertEqual(state["instrument"]["asset_class"], "FUTURES")
        self.assertEqual(state["instrument"]["continuous_id"], "ES")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_advance_hides_future_candles(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8, 180)
        self.replay.start(instrument_id="AAPL")
        self.replay.step()
        visible = self.replay.get_visible_candles("AAPL")
        self.assertEqual(visible["count"], 1)
        self.assertEqual(visible["hidden_count"], 7)

        self.replay.step()
        self.replay.step()
        visible = self.replay.get_visible_candles("AAPL")
        self.assertEqual(visible["count"], 3)
        self.assertLess(visible["count"], 8)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_state_serializes(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(4, 180)
        self.replay.start(instrument_id="AAPL", interval="1d", period="1mo")
        self.replay.step()
        payload = self.replay.serialize()
        self.assertEqual(payload["instrument_id"], "AAPL")
        self.assertEqual(payload["timeframe"], "1d")
        self.assertEqual(payload["period"], "1mo")
        self.assertIn("current_candle", payload)
        self.assertIn("metrics", payload)


if __name__ == "__main__":
    unittest.main()
