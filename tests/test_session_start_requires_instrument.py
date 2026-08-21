"""A1 — session/start must not silently default to AAPL."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _ohlcv(n=6, base=180.0):
    return pd.DataFrame(
        {
            "Open": [base + i for i in range(n)],
            "High": [base + 5 + i for i in range(n)],
            "Low": [base - 2 + i for i in range(n)],
            "Close": [base + 3 + i for i in range(n)],
            "Volume": [1_000_000] * n,
        },
        index=pd.date_range("2026-01-01", periods=n, freq="1D"),
    )


class TestSessionStartRequiresInstrument(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.market.watchlist import get_watchlist
        from src.replay.replay_session import get_replay_session
        from src.simulation.session import get_market_session

        get_replay_session().reset()
        get_market_session().release()
        wl = get_watchlist()
        for entry in list(wl.get_all()):
            wl.remove(entry["symbol"])

        self.app = create_app()
        self.client = self.app.test_client()
        self.client.post("/api/session/reset")
        self.client.post("/api/session/close")

    def test_empty_body_does_not_start_replay(self):
        before = self.client.get("/api/session/state").get_json()
        resp = self.client.post("/api/session/start", json={})
        self.assertEqual(resp.status_code, 400, resp.get_json())
        body = resp.get_json()
        self.assertIn("instrument_id", (body.get("error") or "").lower())

        after = self.client.get("/api/session/state").get_json()
        self.assertEqual(after.get("mode"), "live_paper")
        self.assertEqual(after.get("status"), before.get("status") or "idle")
        self.assertNotEqual(after.get("mode"), "replay")

    def test_empty_body_does_not_use_watchlist_default(self):
        from src.market.watchlist import get_watchlist

        get_watchlist().add("MSFT", 400.0, 399.0)
        resp = self.client.post("/api/session/start", json={})
        self.assertEqual(resp.status_code, 400)
        state = self.client.get("/api/session/state").get_json()
        self.assertEqual(state.get("mode"), "live_paper")
        self.assertNotEqual(state.get("instrument_id"), "MSFT")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_explicit_instrument_still_starts(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv()
        resp = self.client.post(
            "/api/session/start",
            json={"instrument_id": "MSFT", "initial_cash": 10000},
        )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        state = resp.get_json()["state"]
        self.assertEqual(state.get("mode"), "replay")
        self.assertEqual(state.get("instrument_id"), "MSFT")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_symbols_array_still_accepted(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv()
        resp = self.client.post(
            "/api/session/start",
            json={"symbols": ["AAPL"], "initial_cash": 10000},
        )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(resp.get_json()["state"].get("instrument_id"), "AAPL")
        self.assertEqual(resp.get_json()["state"].get("mode"), "replay")


if __name__ == "__main__":
    unittest.main()
