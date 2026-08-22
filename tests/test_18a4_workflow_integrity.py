"""18A.4 — user workflow integrity regression tests."""

import os
import sys
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _plan_payload(**overrides):
    base = {
        "symbol": "AAPL",
        "direction": "LONG",
        "thesis": "18A.4 workflow",
        "entry": {"price": 185},
        "stop_loss": {"price": 180},
        "target": {"price": 195},
        "quantity": 1,
    }
    base.update(overrides)
    return base


class TestTerminalWorkflowUI(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_terminal_has_close_position_button(self):
        html = self.client.get("/terminal").get_data(as_text=True)
        self.assertIn('id="closePositionBtn"', html)
        self.assertIn("CLOSE POSITION", html)

    def test_terminal_shows_plan_link_indicator(self):
        html = self.client.get("/terminal").get_data(as_text=True)
        self.assertIn("planLinkIndicator", html)
        self.assertIn("Decision Review", html)

    def test_terminal_exit_replay_not_duplicate_close(self):
        html = self.client.get("/terminal").get_data(as_text=True)
        self.assertIn("Exit Replay", html)
        self.assertNotIn('id="closeSessionBtn"', html)

    def test_journal_deep_links_to_plan_review(self):
        html = self.client.get("/journal").get_data(as_text=True)
        self.assertIn("/terminal?plan_id=", html)


class TestJournalConsistency(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.ai_agent.trade_journal import get_trade_journal
        from src.learning.journal_service import reset_learning_journal_service
        from src.replay.replay_memory import reset_replay_memory
        from src.simulation.paper_portfolio import get_paper_portfolio
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        reset_learning_journal_service()
        reset_replay_memory()
        get_trade_plan_manager().reset()
        get_order_engine().clear()
        get_paper_portfolio().reset(10000.0)
        get_trade_journal().clear()
        self.app = create_app()
        self.client = self.app.test_client()

    @mock.patch("src.api.execution_routes._current_prices", return_value={"AAPL": 185.0})
    def test_history_matches_learning_journal_after_close(self, _ep):
        from src.replay.replay_session import get_replay_session

        get_replay_session().set_mode("live_paper")
        plan = self.client.post("/api/trade-plan", json=_plan_payload()).get_json()["plan"]
        self.client.post(
            "/api/orders",
            json={
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
                "trade_plan": {"plan_id": plan["id"]},
            },
        )
        self.client.post("/api/orders/close-position", json={"symbol": "AAPL"})

        history = self.client.get("/api/terminal/history").get_json()
        journal = self.client.get("/api/learning/journal").get_json()

        self.assertEqual(history.get("source"), "learning_journal")
        self.assertEqual(len(history["history"]), len(journal["entries"]))
        if history["history"]:
            self.assertEqual(history["history"][0]["plan_id"], plan["id"])

    @mock.patch("src.api.execution_routes._current_prices", return_value={"AAPL": 185.0})
    def test_execution_does_not_populate_legacy_ai_journal(self, _ep):
        from src.ai_agent.trade_journal import get_trade_journal
        from src.replay.replay_session import get_replay_session

        get_replay_session().set_mode("live_paper")
        before = len(get_trade_journal().get_all())
        plan = self.client.post("/api/trade-plan", json=_plan_payload()).get_json()["plan"]
        self.client.post(
            "/api/orders",
            json={
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
                "trade_plan": {"plan_id": plan["id"]},
            },
        )
        self.client.post("/api/orders/close-position", json={"symbol": "AAPL"})
        after = len(get_trade_journal().get_all())
        self.assertEqual(after, before)


class TestWorkflowLifecycleStillGreen(unittest.TestCase):
    """Ensure 18A.3 lifecycle behavior remains intact."""

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
    def test_plan_linked_close_surfaces_review_data(self, _ep):
        from src.replay.replay_session import get_replay_session

        get_replay_session().set_mode("live_paper")
        plan = self.client.post("/api/trade-plan", json=_plan_payload()).get_json()["plan"]
        self.client.post(
            "/api/orders",
            json={
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
                "trade_plan": {"plan_id": plan["id"]},
            },
        )
        self.client.post("/api/orders/close-position", json={"symbol": "AAPL"})

        review = self.client.get(f"/api/replay/records/{plan['id']}").get_json()
        self.assertEqual(review["record"]["status"], "closed")
        self.assertIsNotNone(review.get("journal_entry"))


if __name__ == "__main__":
    unittest.main()
