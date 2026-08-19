"""Tests for Phase 13F AI chart coach API routes."""

import os
import sys
import unittest
import unittest.mock as mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _plan_payload():
    return {
        "symbol": "AAPL",
        "direction": "LONG",
        "thesis": "Breakout above resistance",
        "entry": {"price": 185, "source": {"type": "drawing", "id": "d-12"}},
        "stop_loss": {"price": 180},
        "target": {"price": 195},
        "quantity": 10,
        "risk_reward": 2.0,
    }


class TestAIChartCoachRoutes(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.ai_agent.chart_coach import get_chart_coach
        from src.charting.drawing_store import get_drawing_store
        from src.trading.trade_plan import get_trade_plan_manager

        self.app = create_app()
        self.client = self.app.test_client()
        get_chart_coach().reset()
        get_drawing_store().reset()
        get_trade_plan_manager().reset()

    def test_chart_review_requires_symbol(self):
        resp = self.client.post("/api/ai/chart-review", json={})
        self.assertEqual(resp.status_code, 400)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_chart_review_with_plan(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = pd.DataFrame()
        self.client.post("/api/chart/AAPL/drawings", json={
            "type": "horizontal", "price": 185, "label": "Resistance",
        })
        resp = self.client.post("/api/ai/chart-review", json={
            "symbol": "AAPL",
            "trade_plan": _plan_payload(),
            "price": 185.2,
            "indicator_payload": {"indicators": {"RSI": {"values": [62]}}},
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("grade", data)
        self.assertIn("observations", data)
        self.assertIn("warnings", data)
        self.assertIn("questions", data)
        self.assertEqual(data["review_type"], "pre_trade")

    def test_chart_review_no_buy_recommendation(self):
        resp = self.client.post("/api/ai/chart-review", json={
            "symbol": "AAPL",
            "trade_plan": _plan_payload(),
        })
        body = str(resp.get_json()).lower()
        self.assertNotIn("buy aapl", body)

    def test_trade_review_by_plan_id(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        resp = self.client.post(f"/api/ai/trade-review/{plan_id}", json={"price": 185})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["plan_id"], plan_id)

    def test_trade_review_not_found(self):
        resp = self.client.post("/api/ai/trade-review/missing-plan", json={})
        self.assertEqual(resp.status_code, 404)

    def test_trade_review_post_execution(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        resp = self.client.post(f"/api/ai/trade-review/{plan_id}", json={
            "execution": {"fill_price": 185.3, "exit_price": 192, "pnl": 67},
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["review_type"], "post_trade")
        self.assertIn("plan_vs_actual", resp.get_json())

    def test_coach_history(self):
        self.client.post("/api/ai/chart-review", json={
            "symbol": "AAPL",
            "trade_plan": _plan_payload(),
        })
        self.client.post("/api/ai/chart-review", json={
            "symbol": "AAPL",
            "trade_plan": _plan_payload(),
        })
        resp = self.client.get("/api/ai/coach-history/AAPL")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["symbol"], "AAPL")
        self.assertGreaterEqual(data["count"], 2)

    def test_coach_history_empty_symbol(self):
        resp = self.client.get("/api/ai/coach-history/ZZZZ")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["count"], 0)

    def test_chart_review_with_plan_id(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        resp = self.client.post("/api/ai/chart-review", json={
            "symbol": "AAPL",
            "plan_id": plan_id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("grade", resp.get_json())

    def test_terminal_has_ai_review_button(self):
        resp = self.client.get("/terminal")
        self.assertIn(b'id="aiReviewPlanBtn"', resp.data)
        self.assertIn(b'id="coachReviewBox"', resp.data)


    def test_coach_history_limit_param(self):
        for _ in range(3):
            self.client.post("/api/ai/chart-review", json={"symbol": "AAPL", "trade_plan": _plan_payload()})
        resp = self.client.get("/api/ai/coach-history/AAPL?limit=1")
        self.assertEqual(resp.get_json()["count"], 1)

    def test_review_includes_risk_notes(self):
        resp = self.client.post("/api/ai/chart-review", json={
            "symbol": "AAPL",
            "trade_plan": _plan_payload(),
        })
        self.assertTrue(resp.get_json().get("risk_notes"))


if __name__ == "__main__":
    unittest.main()
