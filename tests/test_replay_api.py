"""Tests for /api/replay/* canonical replay engine."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _sample_ohlcv(n=8, base=180):
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


class TestReplayAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_memory import reset_replay_memory
        from src.replay.replay_session import get_replay_session
        from src.simulation.session import get_market_session

        reset_replay_memory()
        self.app = create_app()
        self.client = self.app.test_client()
        get_replay_session().reset()
        get_market_session().close()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_start_stock(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6)
        resp = self.client.post("/api/replay/start", json={"instrument_id": "AAPL"})
        self.assertEqual(resp.status_code, 200)
        state = resp.get_json()["state"]
        self.assertEqual(state["instrument"]["instrument_id"], "AAPL")
        self.assertEqual(state["instrument"]["asset_class"], "STOCK")
        self.assertEqual(state["mode"], "replay")
        self.assertEqual(state["status"], "running")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_start_forex(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6, base=1.08)
        resp = self.client.post("/api/replay/start", json={"instrument_id": "EURUSD"})
        self.assertEqual(resp.status_code, 200)
        state = resp.get_json()["state"]
        self.assertEqual(state["instrument"]["asset_class"], "FOREX")
        self.assertNotIn("continuous_id", state["instrument"])

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_start_futures_continuous_identity(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6, base=5000)
        resp = self.client.post("/api/replay/start", json={"instrument_id": "ESZ26"})
        self.assertEqual(resp.status_code, 200)
        state = resp.get_json()["state"]
        self.assertEqual(state["instrument"]["asset_class"], "FUTURES")
        self.assertEqual(state["instrument"]["continuous_id"], "ES")
        self.assertEqual(state["instrument_id"], "ESZ26")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_step_and_state(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
        self.client.post("/api/replay/start", json={"instrument_id": "AAPL"})
        resp = self.client.post("/api/replay/step")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["current_index"], 0)
        self.assertIn("metrics", data)

        state = self.client.get("/api/replay/state?instrument_id=AAPL").get_json()
        self.assertEqual(state["visible_candles"]["count"], 1)
        self.assertGreater(state["hidden_candles"], 0)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_future_candles_hidden(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8)
        self.client.post("/api/replay/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/replay/step")
        self.client.post("/api/replay/step")
        candles = self.client.get("/api/replay/candles/AAPL").get_json()
        self.assertEqual(candles["count"], 2)
        self.assertEqual(candles["hidden_count"], 6)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_reset_and_mode(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(4)
        self.client.post("/api/replay/start", json={"instrument_id": "AAPL"})
        reset = self.client.post("/api/replay/reset")
        self.assertEqual(reset.get_json()["status"], "idle")
        mode = self.client.post("/api/replay/mode", json={"mode": "live_paper"})
        self.assertEqual(mode.get_json()["mode"], "live_paper")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_compare_uses_plan(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6)
        self.client.post("/api/replay/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/replay/step")
        self.client.post("/api/replay/step")

        plan = {
            "symbol": "AAPL",
            "direction": "LONG",
            "thesis": "Breakout",
            "entry": {"price": 185},
            "stop_loss": {"price": 180},
            "target": {"price": 195},
            "risk_reward": 2.0,
        }
        resp = self.client.post("/api/replay/compare", json={"trade_plan": plan})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("plan_grade", body["comparison"])


if __name__ == "__main__":
    unittest.main()
