"""Tests for replay session engine and future-leak prevention."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.replay.candle_stream import (
    count_hidden_candles,
    serialize_candles,
    slice_visible_df,
    validate_visible_index,
)
from src.replay.replay_clock import map_session_state, normalize_speed
from src.replay.replay_metrics import ReplayMetrics
from src.replay.replay_session import ReplaySessionManager
from src.simulation.session import MarketSession


def _sample_ohlcv(n=10, base=180):
    return pd.DataFrame(
        {
            "Open": [base + i for i in range(n)],
            "High": [base + 5 + i for i in range(n)],
            "Low": [base - 2 + i for i in range(n)],
            "Close": [base + 3 + i for i in range(n)],
            "Volume": [1000000] * n,
        },
        index=pd.date_range("2026-01-01", periods=n, freq="1D"),
    )


class TestCandleStream(unittest.TestCase):
    def test_validate_rejects_future_index(self):
        with self.assertRaises(ValueError):
            validate_visible_index(2, 10, requested_index=5)

    def test_validate_caps_at_current(self):
        self.assertEqual(validate_visible_index(3, 10), 3)
        self.assertEqual(validate_visible_index(99, 10), 9)

    def test_slice_visible_df(self):
        df = _sample_ohlcv(8)
        visible = slice_visible_df(df, 2)
        self.assertEqual(len(visible), 3)
        self.assertEqual(float(visible.iloc[-1]["Close"]), 185.0)

    def test_no_candles_before_first_step(self):
        df = _sample_ohlcv(5)
        payload = serialize_candles(df, -1)
        self.assertEqual(payload["count"], 0)

    def test_hidden_candle_count(self):
        self.assertEqual(count_hidden_candles(10, 2), 7)
        self.assertEqual(count_hidden_candles(10, -1), 10)
        self.assertEqual(count_hidden_candles(10, 9), 0)


class TestReplayClock(unittest.TestCase):
    def test_normalize_speed(self):
        self.assertEqual(normalize_speed("2x"), "2x")
        self.assertEqual(normalize_speed(4), "4x")
        self.assertEqual(normalize_speed("bad"), "1x")

    def test_map_session_state(self):
        self.assertEqual(map_session_state("open", False), "running")
        self.assertEqual(map_session_state("paused", False), "paused")
        self.assertEqual(map_session_state("open", True), "completed")


class TestReplayMetrics(unittest.TestCase):
    def test_tracks_high_low(self):
        metrics = ReplayMetrics()
        metrics.bind_symbol("AAPL")
        metrics.on_candle({"high": 190, "low": 185})
        metrics.on_candle({"high": 195, "low": 183})
        data = metrics.to_dict()
        self.assertEqual(data["high_reached"], 195)
        self.assertEqual(data["low_reached"], 183)
        self.assertEqual(data["candle_count"], 2)


class TestReplaySessionManager(unittest.TestCase):
    def setUp(self):
        self.session = MarketSession()
        self.replay = ReplaySessionManager(session=self.session)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_start_and_state(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6)
        state = self.replay.start("AAPL")
        self.assertEqual(state["symbol"], "AAPL")
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["total_candles"], 6)
        self.assertEqual(state["current_index"], -1)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_no_future_candles_on_step(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8)
        self.replay.start("AAPL")
        self.replay.step()
        visible = self.replay.get_visible_candles("AAPL")
        self.assertEqual(visible["count"], 1)
        self.assertEqual(visible["hidden_count"], 7)
        self.assertTrue(visible["session_capped"])

        self.replay.step()
        self.replay.step()
        visible = self.replay.get_visible_candles("AAPL")
        self.assertEqual(visible["count"], 3)
        self.assertLess(visible["count"], 8)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_advance_clock(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(4)
        self.replay.start("AAPL")
        self.replay.step()
        state = self.replay.get_state()
        self.assertEqual(state["current_index"], 0)
        self.assertGreater(state["metrics"]["candle_count"], 0)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_reset_clears_session(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(4)
        self.replay.start("AAPL")
        self.replay.step()
        result = self.replay.reset()
        self.assertEqual(result["status"], "idle")
        self.assertFalse(self.replay.is_active())

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_symbol_isolation(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
        self.replay.start("AAPL")
        self.replay.step()
        msft = self.replay.get_visible_candles("MSFT")
        self.assertEqual(msft["count"], 0)


if __name__ == "__main__":
    unittest.main()
