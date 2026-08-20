"""18A.3 — production product coherence (P1) regression tests."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _ohlcv(n=12, base=180.0):
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


def _plan_payload(**overrides):
    base = {
        "symbol": "AAPL",
        "direction": "LONG",
        "thesis": "18A.3 coherence",
        "entry": {"price": 185},
        "stop_loss": {"price": 180},
        "target": {"price": 195},
        "quantity": 2,
    }
    base.update(overrides)
    return base


class TestReplayRouteCanonical(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_replay_redirects_to_terminal(self):
        resp = self.client.get("/replay", follow_redirects=False)
        self.assertIn(resp.status_code, (301, 302))
        loc = resp.headers.get("Location", "")
        self.assertIn("/terminal", loc)
        self.assertNotIn("index.html", loc)

    def test_replay_does_not_serve_legacy_simulator(self):
        resp = self.client.get("/replay", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertNotIn("Start Simulator", html)
        self.assertIn("Start Replay", html)


class TestJournalUsesLearningAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_journal_page_uses_learning_journal(self):
        html = self.client.get("/journal").get_data(as_text=True)
        self.assertIn("/api/learning/journal", html)
        self.assertNotIn("/api/ai/journal", html)
        self.assertIn("/api/learning/journal/profile", html)
        self.assertIn("/api/learning/journal/search", html)
        self.assertIn("/api/learning/journal/improvements", html)


class TestTradePlanCollection(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_memory import reset_replay_memory
        from src.trading.trade_plan import get_trade_plan_manager

        reset_replay_memory()
        get_trade_plan_manager().reset()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_get_trade_plan_collection_empty_200(self):
        resp = self.client.get("/api/trade-plan")
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True)[:300])
        self.assertEqual(resp.content_type.startswith("application/json"), True)
        body = resp.get_json()
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["plans"], [])

    def test_get_trade_plan_collection_lists_plans(self):
        self.client.post("/api/trade-plan", json=_plan_payload())
        self.client.post(
            "/api/trade-plan",
            json=_plan_payload(
                symbol="MSFT",
                entry={"price": 400},
                stop_loss={"price": 390},
                target={"price": 420},
            ),
        )
        resp = self.client.get("/api/trade-plan")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["count"], 2)
        symbols = {p["symbol"] for p in body["plans"]}
        self.assertEqual(symbols, {"AAPL", "MSFT"})

    def test_get_by_symbol_still_works(self):
        self.client.post("/api/trade-plan", json=_plan_payload())
        resp = self.client.get("/api/trade-plan/AAPL")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()["plans"]), 1)


class TestPlanOrderReplayJournalLinkage(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.learning.journal_service import reset_learning_journal_service
        from src.replay.replay_memory import reset_replay_memory
        from src.replay.replay_session import get_replay_session
        from src.simulation.paper_portfolio import get_paper_portfolio
        from src.simulation.session import get_market_session
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        reset_learning_journal_service()
        reset_replay_memory()
        get_trade_plan_manager().reset()
        get_order_engine().clear()
        get_paper_portfolio().reset(10000.0)
        get_replay_session().reset()
        get_market_session().release()
        self.app = create_app()
        self.client = self.app.test_client()

    @mock.patch("src.api.execution_routes._current_prices", return_value={"AAPL": 185.0})
    def test_live_plan_create_order_fills_and_links_record(self, _ep):
        from src.replay.replay_memory import get_replay_memory
        from src.replay.replay_session import get_replay_session

        get_replay_session().set_mode("live_paper")
        plan = self.client.post("/api/trade-plan", json=_plan_payload()).get_json()["plan"]
        resp = self.client.post(f"/api/trade-plan/{plan['id']}/create-order")
        self.assertEqual(resp.status_code, 201, resp.get_json())
        limit_order = resp.get_json()["order"]
        self.assertEqual((limit_order.get("trade_plan") or {}).get("plan_id"), plan["id"])

        # LIVE PAPER ticket market fill with plan_id (Terminal getOrderPayload behavior).
        market = self.client.post(
            "/api/orders",
            json={
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 2,
                "order_type": "market",
                "trade_plan": {"plan_id": plan["id"]},
            },
        )
        self.assertEqual(market.status_code, 200, market.get_json())
        self.assertEqual(market.get_json()["order"]["status"], "FILLED")

        record = get_replay_memory().get_by_plan_id(plan["id"])
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "filled")
        self.assertIsNotNone((record.get("execution") or {}).get("entry"))

        close = self.client.post("/api/orders/close-position", json={"symbol": "AAPL"})
        self.assertEqual(close.status_code, 200, close.get_json())

        final = self.client.get(f"/api/replay/records/{plan['id']}").get_json()
        self.assertEqual(final["record"]["status"], "closed")
        self.assertIsNotNone(final["record"].get("scoring"))
        self.assertIsNotNone(final.get("journal_entry"))

        journal = self.client.get(f"/api/learning/journal/plan/{plan['id']}")
        self.assertEqual(journal.status_code, 200)
        # Idempotent backfill
        again = self.client.post(f"/api/learning/journal/generate/{plan['id']}")
        self.assertEqual(again.status_code, 201)
        self.assertEqual(again.get_json()["entry"]["id"], journal.get_json()["entry"]["id"])

    @mock.patch("src.api.execution_routes._current_prices", return_value={"AAPL": 185.0})
    def test_casual_market_without_plan_does_not_fabricate_journal(self, _ep):
        from src.learning.journal_service import get_learning_journal_service
        from src.market.watchlist import get_watchlist
        from src.replay.replay_session import get_replay_session

        get_replay_session().set_mode("live_paper")
        get_watchlist().add("AAPL", 185.0, 184.0)
        before = len(get_learning_journal_service().list_entries())
        buy = self.client.post(
            "/api/orders",
            json={"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
        )
        self.assertEqual(buy.status_code, 200)
        self.client.post("/api/orders/close-position", json={"symbol": "AAPL"})
        after = len(get_learning_journal_service().list_entries())
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
