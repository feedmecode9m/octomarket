"""Tests for Phase 10 live market practice features."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.market.watchlist import Watchlist, get_sector
from src.market.alerts import AlertManager
from src.simulation.session import MarketSession
from src.simulation.events import MarketEventEngine
from src.simulation.paper_portfolio import PaperPortfolio
from src.ai_agent.market_commentator import MarketCommentator


def _sample_ohlcv(n=10, base=180):
    return pd.DataFrame(
        {
            "Open": [base + i for i in range(n)],
            "High": [base + 5 + i for i in range(n)],
            "Low": [base - 2 + i for i in range(n)],
            "Close": [base + 3 + i for i in range(n)],
            "Volume": [1000000] * n,
        },
        index=pd.date_range("2024-06-01", periods=n, freq="1D"),
    )


class TestWatchlist(unittest.TestCase):
    def setUp(self):
        self.wl = Watchlist()

    def test_add_and_get(self):
        entry = self.wl.add("AAPL", price=220, prev_close=217)
        self.assertEqual(entry["symbol"], "AAPL")
        self.assertEqual(entry["price"], 220)
        self.assertAlmostEqual(entry["change_percent"], 1.38, places=1)
        self.assertEqual(entry["trend"], "bullish")

    def test_remove(self):
        self.wl.add("AAPL", 220, 217)
        self.assertTrue(self.wl.remove("AAPL"))
        self.assertFalse(self.wl.remove("AAPL"))
        self.assertEqual(self.wl.get_all(), [])

    def test_bearish_trend(self):
        entry = self.wl.add("TSLA", 200, 210)
        self.assertEqual(entry["trend"], "bearish")
        self.assertLess(entry["change_percent"], 0)

    def test_max_symbols(self):
        for i in range(20):
            self.wl.add(f"S{i}", 100, 100)
        with self.assertRaises(ValueError):
            self.wl.add("EXTRA", 100, 100)

    def test_get_sector(self):
        self.assertEqual(get_sector("AAPL"), "Technology")
        self.assertEqual(get_sector("UNKNOWN"), "Other")


class TestAlertManager(unittest.TestCase):
    def setUp(self):
        self.alerts = AlertManager()

    def test_create_price_alert(self):
        alert = self.alerts.create("TSLA", "price", "drops", 5)
        self.assertTrue(alert["active"])
        self.assertEqual(len(self.alerts.get_all()), 1)

    def test_price_drop_triggers(self):
        self.alerts.create("TSLA", "price", "drops", 5)
        triggered = self.alerts.check_price_alerts("TSLA", 190, 200)
        self.assertEqual(len(triggered), 1)
        self.assertEqual(triggered[0]["change_percent"], -5.0)

    def test_indicator_rsi_triggers(self):
        self.alerts.create("AAPL", "indicator", "below", 30)
        triggered = self.alerts.check_indicator_alerts("AAPL", rsi=25)
        self.assertEqual(len(triggered), 1)

    def test_portfolio_risk_alert(self):
        event = self.alerts.check_portfolio_risk(75)
        self.assertIsNotNone(event)
        self.assertEqual(event["type"], "portfolio_risk")

    def test_delete_alert(self):
        alert = self.alerts.create("AAPL", "price", "above", 200)
        self.assertTrue(self.alerts.delete(alert["id"]))
        self.assertFalse(self.alerts.delete("nonexistent"))


class TestMarketSession(unittest.TestCase):
    def setUp(self):
        self.session = MarketSession()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_start_and_step(self, MockFetcher):
        mock_fetcher = MockFetcher.return_value
        mock_fetcher.get_real_time_data.return_value = _sample_ohlcv(5)

        state = self.session.start(["AAPL"])
        self.assertEqual(state["state"], "pre_market")

        state = self.session.step()
        self.assertEqual(state["state"], "open")
        self.assertIn("AAPL", state["prices"])

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_pause_and_resume(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
        self.session.start(["AAPL"])
        self.session.step()
        self.session.pause()
        self.assertEqual(self.session.get_state()["state"], "paused")
        self.session.resume()
        self.assertEqual(self.session.get_state()["state"], "open")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_close_session(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(3)
        self.session.start(["AAPL"])
        self.session.close()
        self.assertEqual(self.session.get_state()["state"], "closed")

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_chart_data(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
        self.session.start(["AAPL"])
        self.session.step()
        chart = self.session.get_chart_data("AAPL")
        self.assertEqual(len(chart["prices"]), 1)

    def test_start_empty_raises(self):
        with self.assertRaises(ValueError):
            self.session.start([])


class TestMarketEvents(unittest.TestCase):
    def setUp(self):
        self.engine = MarketEventEngine(trigger_probability=1.0)

    def test_generate_event(self):
        event = self.engine.maybe_generate("AAPL", session_index=2)
        self.assertIsNotNone(event)
        self.assertIn("what_happened", event)
        self.assertIn("possible_responses", event)
        self.assertIn("risk_considerations", event)

    def test_no_event_at_index_zero(self):
        event = self.engine.maybe_generate("AAPL", session_index=0)
        self.assertIsNone(event)

    def test_get_recent(self):
        self.engine.maybe_generate("AAPL", 1)
        self.engine.maybe_generate("TSLA", 2)
        recent = self.engine.get_recent()
        self.assertEqual(len(recent), 2)


class TestPortfolioUpgrade(unittest.TestCase):
    def setUp(self):
        self.portfolio = PaperPortfolio(initial_cash=10000)

    def test_multi_position(self):
        self.portfolio.buy("AAPL", 100, 10)
        self.portfolio.buy("MSFT", 200, 5)
        prices = {"AAPL": 105, "MSFT": 210}
        data = self.portfolio.to_dict(prices)
        self.assertEqual(len(data["positions"]), 2)

    def test_partial_exit(self):
        self.portfolio.buy("AAPL", 100, 20)
        result = self.portfolio.sell("AAPL", 110, 10)
        self.assertTrue(result["success"])
        self.assertEqual(self.portfolio.positions["AAPL"].quantity, 10)

    def test_allocation(self):
        self.portfolio.buy("AAPL", 100, 50)
        allocation = self.portfolio.get_allocation({"AAPL": 100})
        self.assertIn("AAPL", allocation)
        self.assertIn("cash", allocation)

    def test_sector_exposure(self):
        self.portfolio.buy("AAPL", 100, 10)
        self.portfolio.buy("MSFT", 200, 5)
        sectors = self.portfolio.get_sector_exposure({"AAPL": 100, "MSFT": 200})
        self.assertIn("Technology", sectors)

    def test_risk_score_concentrated(self):
        self.portfolio.buy("AAPL", 100, 80)
        risk = self.portfolio.get_risk_score({"AAPL": 100})
        self.assertGreater(risk, 30)

    def test_risk_score_in_to_dict(self):
        self.portfolio.buy("AAPL", 100, 10)
        data = self.portfolio.to_dict({"AAPL": 100})
        self.assertIn("risk_score", data)
        self.assertIn("allocation", data)
        self.assertIn("sector_exposure", data)


class TestMarketCommentator(unittest.TestCase):
    def setUp(self):
        self.commentator = MarketCommentator()

    def test_concentration_comment(self):
        portfolio = {
            "positions": {
                "AAPL": {"market_value": 7000, "avg_cost": 100, "current_price": 140, "quantity": 50},
            },
            "total_value": 10000,
            "cash": 3000,
            "risk_score": 50,
        }
        result = self.commentator.commentate(portfolio, [])
        self.assertTrue(any("concentrated" in c.lower() for c in result["commentary"]))

    def test_empty_portfolio(self):
        portfolio = {"positions": {}, "total_value": 10000, "cash": 10000, "risk_score": 0}
        result = self.commentator.commentate(portfolio, [])
        self.assertTrue(len(result["commentary"]) > 0)

    def test_high_risk_warning(self):
        portfolio = {"positions": {}, "total_value": 10000, "cash": 10000, "risk_score": 80}
        result = self.commentator.commentate(portfolio, [])
        self.assertTrue(any("risk" in w.lower() for w in result["warnings"]))


class TestTerminalAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    @mock.patch("src.api.terminal_routes.DataFetcher")
    def test_watchlist_add_and_get(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(3, 220)
        resp = self.client.post("/api/watchlist", json={"symbol": "AAPL"})
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/api/watchlist")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(any(w["symbol"] == "AAPL" for w in data))

    @mock.patch("src.api.terminal_routes.DataFetcher")
    def test_watchlist_delete(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(3)
        self.client.post("/api/watchlist", json={"symbol": "AAPL"})
        resp = self.client.delete("/api/watchlist/AAPL")
        self.assertEqual(resp.status_code, 200)

    @mock.patch("src.api.terminal_routes._fetch_price")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_session_lifecycle(self, MockSessionFetcher, mock_fetch_price):
        MockSessionFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
        mock_fetch_price.return_value = (183, 180)

        resp = self.client.post("/api/session/start", json={"symbols": ["AAPL"], "initial_cash": 10000})
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post("/api/session/step")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("prices", resp.get_json())

        resp = self.client.get("/api/session/state")
        self.assertEqual(resp.status_code, 200)

    @mock.patch("src.api.terminal_routes._fetch_price")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_terminal_trade(self, MockSessionFetcher, mock_fetch_price):
        MockSessionFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
        mock_fetch_price.return_value = (183, 180)

        self.client.post("/api/session/start", json={"symbols": ["AAPL"]})
        self.client.post("/api/session/step")

        resp = self.client.post("/api/terminal/trade", json={"action": "buy", "symbol": "AAPL", "quantity": 5})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json().get("success"))

    def test_commentary_endpoint(self):
        resp = self.client.get("/api/commentary")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("commentary", data)

    def test_events_endpoint(self):
        resp = self.client.get("/api/events")
        self.assertEqual(resp.status_code, 200)

    def test_alerts_crud(self):
        resp = self.client.post("/api/alerts", json={
            "symbol": "TSLA", "type": "price", "condition": "drops", "threshold": 5
        })
        self.assertEqual(resp.status_code, 200)
        alert_id = resp.get_json()["alert"]["id"]
        resp = self.client.get("/api/alerts")
        self.assertEqual(len(resp.get_json()["alerts"]), 1)
        resp = self.client.delete(f"/api/alerts/{alert_id}")
        self.assertEqual(resp.status_code, 200)

    def test_terminal_page(self):
        resp = self.client.get("/terminal")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
