"""18A.2 — LIVE PAPER must not consume REPLAY price/portfolio state."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _ohlcv(n=8, base=180.0):
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


class TestLiveReplayIsolation(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.ai_agent.trade_journal import get_trade_journal
        from src.market.watchlist import get_watchlist
        from src.replay.replay_memory import reset_replay_memory
        from src.replay.replay_session import get_replay_session
        from src.simulation.paper_portfolio import get_paper_portfolio
        from src.simulation.session import get_market_session
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        reset_replay_memory()
        get_trade_plan_manager().reset()
        get_order_engine().clear()
        get_trade_journal().clear()
        get_paper_portfolio().reset(10000.0)
        get_watchlist().clear() if hasattr(get_watchlist(), "clear") else None
        # Best-effort watchlist wipe
        wl = get_watchlist()
        for entry in list(wl.get_all()):
            wl.remove(entry["symbol"])

        self.app = create_app()
        self.client = self.app.test_client()
        get_replay_session().reset()
        get_market_session().release()

    @mock.patch("src.market.live_price.fetch_live_quote", return_value=316.7)
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_live_fill_ignores_replay_close_after_reset(self, MockFetcher, _mock_live):
        """After REPLAY, LIVE market fills must use LIVE price — never last replay close."""
        from src.simulation.paper_portfolio import get_paper_portfolio
        from src.simulation.session import get_market_session

        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(10, base=270.0)

        self.client.post("/api/session/start", json={"instrument_id": "AAPL", "initial_cash": 10000})
        step = self.client.post("/api/session/step").get_json()
        replay_close = float(step["current_candle"]["close"])
        self.assertAlmostEqual(replay_close, 273.0, places=1)

        self.client.post("/api/session/reset")
        state = self.client.get("/api/session/state").get_json()
        self.assertEqual(state["mode"], "live_paper")
        self.assertEqual(state["status"], "idle")
        self.assertFalse(state.get("session_capped", False))

        # Plant residual session price as the pre-fix contamination vector.
        session = get_market_session()
        with session._lock:
            session._prices["AAPL"] = replay_close
            session._state = "closed"

        self.client.post("/api/watchlist", json={"symbol": "AAPL"})
        # Force watchlist to the LIVE quote under test (ignore fetcher used by add).
        from src.market.watchlist import get_watchlist

        get_watchlist().update_price("AAPL", 316.7, 316.0)

        before_cash = get_paper_portfolio().cash
        resp = self.client.post(
            "/api/orders",
            json={"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        order = resp.get_json()["order"]
        self.assertEqual(order["status"], "FILLED")
        fill = float(order["fill_price"])
        self.assertNotAlmostEqual(fill, replay_close, places=1)
        self.assertGreater(fill, 310.0)
        self.assertLess(get_paper_portfolio().cash, before_cash)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_replay_does_not_overwrite_live_cash(self, MockFetcher):
        from src.simulation.paper_portfolio import get_paper_portfolio

        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(6, base=180.0)
        portfolio = get_paper_portfolio()
        portfolio.reset(10000.0)
        portfolio.cash = 8123.45
        live_cash = portfolio.cash

        self.client.post("/api/session/start", json={"instrument_id": "AAPL", "initial_cash": 10000})
        # During replay the sandbox may use initial_cash, but LIVE backup must stay intact.
        self.client.post("/api/session/step")
        self.client.post("/api/session/reset")

        self.assertAlmostEqual(get_paper_portfolio().cash, live_cash, places=2)

    @mock.patch("src.market.live_price.fetch_live_quote", return_value=200.0)
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_replay_does_not_overwrite_live_positions(self, MockFetcher, _mock_live):
        from src.market.watchlist import get_watchlist
        from src.simulation.paper_portfolio import get_paper_portfolio

        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(6, base=180.0)
        get_watchlist().add("AAPL", 200.0, 199.0)
        buy = get_paper_portfolio().buy("AAPL", 200.0, 3, reason="seed live position")
        self.assertTrue(buy["success"])
        live_qty = get_paper_portfolio().positions["AAPL"].quantity
        live_cash = get_paper_portfolio().cash

        self.client.post("/api/session/start", json={"instrument_id": "AAPL", "initial_cash": 10000})
        self.client.post("/api/session/step")
        # Execute a replay market fill against session prices (sandbox only).
        self.client.post(
            "/api/orders",
            json={"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
        )
        self.client.post("/api/session/reset")

        portfolio = get_paper_portfolio()
        self.assertIn("AAPL", portfolio.positions)
        self.assertEqual(portfolio.positions["AAPL"].quantity, live_qty)
        self.assertAlmostEqual(portfolio.cash, live_cash, places=2)

    @mock.patch("src.market.live_price.fetch_live_quote", return_value=0.0)
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_live_market_rejects_stale_replay_price(self, MockFetcher, _mock_fetch):
        """Missing LIVE price must reject — never silently fill at residual replay close."""
        from src.simulation.session import get_market_session

        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(6, base=270.0)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/session/step")
        self.client.post("/api/session/reset")

        session = get_market_session()
        with session._lock:
            session._prices["AAPL"] = 272.6
            session._state = "closed"

        resp = self.client.post(
            "/api/orders",
            json={"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertIn("LIVE price", body.get("error", ""))
        order = body.get("order") or {}
        self.assertEqual(order.get("status"), "REJECTED")
        self.assertIsNone(order.get("fill_price"))

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_mode_transition_live_replay_live(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(8, base=180.0)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/session/step")
        mid = self.client.get("/api/session/state").get_json()
        self.assertEqual(mid["mode"], "replay")
        self.assertTrue(mid.get("replay_mode") or mid["mode"] == "replay")

        self.client.post("/api/session/close")
        state = self.client.get("/api/session/state").get_json()
        self.assertEqual(state["mode"], "live_paper")
        self.assertEqual(state["status"], "idle")
        self.assertFalse(state.get("session_capped", False))
        # Residual session prices must be cleared from the authoritative session map.
        from src.simulation.session import get_market_session

        self.assertEqual(get_market_session().get_state().get("prices"), {})

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_replay_future_candles_still_hidden(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(8, base=180.0)
        self.client.post("/api/session/start", json={"instrument_id": "AAPL"})
        self.client.post("/api/session/step")
        chart = self.client.get("/api/chart/AAPL?timeframe=1d&period=1mo").get_json()
        self.assertTrue(chart["session_capped"])
        self.assertEqual(chart["count"], 1)
        self.assertLess(chart["count"], 8)


if __name__ == "__main__":
    unittest.main()
