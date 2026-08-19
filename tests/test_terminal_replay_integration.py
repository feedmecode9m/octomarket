"""Gate 15E — terminal unified replay loop integration tests."""

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


class TestTerminalReplayIntegration(unittest.TestCase):
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
    def test_terminal_start_uses_selected_instrument(self, MockFetcher):
        from src.replay.replay_session import get_replay_session

        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6)
        for instrument_id in ("AAPL", "EURUSD", "ESZ26"):
            get_replay_session().reset()
            resp = self.client.post(
                "/api/session/start",
                json={"instrument_id": instrument_id, "interval": "1d", "period": "1mo"},
            )
            self.assertEqual(resp.status_code, 200, msg=instrument_id)
            state = resp.get_json()["state"]
            self.assertEqual(state["mode"], "replay")
            self.assertEqual(state["instrument_id"], instrument_id)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_step_caps_chart_candles(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/session/step")
        self.client.post("/api/session/step")

        chart = self.client.get("/api/chart/AAPL?timeframe=1d").get_json()
        self.assertTrue(chart.get("session_capped"))
        self.assertEqual(chart.get("count"), 2)

        state = self.client.get("/api/session/state").get_json()
        self.assertEqual(state["mode"], "replay")
        self.assertEqual(state["current_index"], 1)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_live_mode_full_chart_when_idle(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(6)
        chart = self.client.get("/api/chart/AAPL?timeframe=1d&period=1mo").get_json()
        self.assertFalse(chart.get("session_capped"))
        self.assertEqual(chart.get("count"), 6)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_replay_trade_lifecycle_records_and_scores(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(8)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL", "initial_cash": 10000})
        self.client.post("/api/session/step")
        self.client.post("/api/session/step")

        plan_resp = self.client.post(
            "/api/trade-plan",
            json={
                "symbol": "AAPL",
                "instrument_id": "AAPL",
                "asset_class": "STOCK",
                "direction": "LONG",
                "entry": {"price": 185},
                "stop_loss": {"price": 180},
                "target": {"price": 195},
                "quantity": 10,
                "thesis": "Breakout",
            },
        )
        self.assertEqual(plan_resp.status_code, 201)
        plan = plan_resp.get_json()["plan"]
        self.assertEqual(plan_resp.get_json()["plan"]["id"], plan["id"])

        record_resp = self.client.get(f"/api/replay/records/{plan['id']}")
        self.assertEqual(record_resp.status_code, 200)
        record = record_resp.get_json()["record"]
        self.assertEqual(record["mode"], "replay")
        self.assertEqual(record["status"], "planned")
        self.assertIn("market_snapshot", record["decision_context"])

        order_resp = self.client.post(f"/api/trade-plan/{plan['id']}/create-order")
        self.assertEqual(order_resp.status_code, 201)

        self.client.post("/api/session/step")
        close_resp = self.client.post("/api/orders/close-position", json={"symbol": "AAPL"})
        self.assertEqual(close_resp.status_code, 200)

        final = self.client.get(f"/api/replay/records/{plan['id']}").get_json()["record"]
        self.assertEqual(final["status"], "closed")
        self.assertIsNotNone(final.get("scoring"))
        self.assertIsNotNone(final["outcome"].get("pnl"))

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_close_session_returns_live_mode(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/session/close")
        state = self.client.get("/api/session/state").get_json()
        self.assertEqual(state["mode"], "live_paper")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_chart_state_includes_replay_metadata(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        workspace = self.client.get("/api/chart/state").get_json()
        self.assertEqual(workspace["replay"]["mode"], "replay")
        self.assertTrue(workspace["replay"]["session_capped"])
