"""Tests for trade plan API and order conversion."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _plan_payload(**overrides):
    base = {
        "symbol": "AAPL",
        "direction": "LONG",
        "thesis": "Breakout above resistance",
        "entry": {"price": 185, "source": {"type": "drawing", "id": "abc-123", "label": "Resistance"}},
        "stop_loss": {"price": 180},
        "target": {"price": 195},
        "quantity": 10,
        "setup": {
            "indicators": [{"key": "SMA20", "summary": "Above price"}, {"key": "RSI", "summary": "62"}],
            "drawings": [{"id": "abc-123", "type": "horizontal", "label": "Resistance"}],
        },
    }
    base.update(overrides)
    return base


class TestTradePlanAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_memory import reset_replay_memory
        from src.trading.trade_plan import get_trade_plan_manager

        reset_replay_memory()
        self.app = create_app()
        self.client = self.app.test_client()
        get_trade_plan_manager().reset()

    def test_create_plan(self):
        resp = self.client.post("/api/trade-plan", json=_plan_payload())
        self.assertEqual(resp.status_code, 201)
        plan = resp.get_json()["plan"]
        self.assertEqual(plan["symbol"], "AAPL")
        self.assertEqual(plan["risk_reward"], 2.0)
        self.assertEqual(plan["entry"]["source"]["id"], "abc-123")

    def test_create_invalid_stop(self):
        resp = self.client.post("/api/trade-plan", json=_plan_payload(stop_loss={"price": 190}))
        self.assertEqual(resp.status_code, 400)

    def test_get_plans_by_symbol(self):
        self.client.post("/api/trade-plan", json=_plan_payload())
        resp = self.client.get("/api/trade-plan/AAPL")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["symbol"], "AAPL")
        self.assertEqual(len(data["plans"]), 1)
        self.assertIsNotNone(data["active"])

    def test_get_plan_by_id(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        resp = self.client.get(f"/api/trade-plan/id/{plan_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["id"], plan_id)

    def test_update_plan(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        resp = self.client.put(
            f"/api/trade-plan/{plan_id}",
            json={"thesis": "Updated thesis", "target": {"price": 200}},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["plan"]["thesis"], "Updated thesis")

    def test_review_plan(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        resp = self.client.post(f"/api/trade-plan/{plan_id}/review", json={"setup": _plan_payload()["setup"]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["plan"]["status"], "REVIEWED")

    def test_approve_plan(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        self.client.post(f"/api/trade-plan/{plan_id}/review")
        resp = self.client.post(f"/api/trade-plan/{plan_id}/approve")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["plan"]["status"], "APPROVED")

    def test_approve_without_review_fails(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        resp = self.client.post(f"/api/trade-plan/{plan_id}/approve")
        self.assertEqual(resp.status_code, 400)

    def test_create_order_from_plan(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        resp = self.client.post(f"/api/trade-plan/{plan_id}/create-order")
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data["plan"]["status"], "ORDER_CREATED")
        self.assertIsNotNone(data["order"]["id"])
        self.assertEqual(data["order"]["symbol"], "AAPL")
        self.assertIn("plan_id", data["order"].get("trade_plan", {}))

    def test_create_order_includes_trade_plan_context(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        resp = self.client.post(f"/api/trade-plan/{plan_id}/create-order")
        order = resp.get_json()["order"]
        tp = order.get("trade_plan", {})
        self.assertEqual(tp.get("thesis"), "Breakout above resistance")
        self.assertEqual(tp.get("entry_source", {}).get("id"), "abc-123")

    def test_symbol_isolation(self):
        self.client.post("/api/trade-plan", json=_plan_payload())
        self.client.post("/api/trade-plan", json=_plan_payload(
            symbol="MSFT",
            entry={"price": 400},
            stop_loss={"price": 390},
            target={"price": 420},
        ))
        aapl = self.client.get("/api/trade-plan/AAPL").get_json()["plans"]
        msft = self.client.get("/api/trade-plan/MSFT").get_json()["plans"]
        self.assertEqual(len(aapl), 1)
        self.assertEqual(aapl[0]["symbol"], "AAPL")
        self.assertEqual(msft[0]["symbol"], "MSFT")


    def test_update_not_found(self):
        resp = self.client.put("/api/trade-plan/missing-id", json={"thesis": "x"})
        self.assertEqual(resp.status_code, 404)

    def test_get_plan_by_id_not_found(self):
        resp = self.client.get("/api/trade-plan/id/missing-id")
        self.assertEqual(resp.status_code, 404)

    def test_create_order_twice_fails(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        self.client.post(f"/api/trade-plan/{plan_id}/create-order")
        resp = self.client.post(f"/api/trade-plan/{plan_id}/create-order")
        self.assertEqual(resp.status_code, 400)

    def test_review_attaches_indicator_snapshot(self):
        create = self.client.post("/api/trade-plan", json=_plan_payload())
        plan_id = create.get_json()["plan"]["id"]
        setup = _plan_payload()["setup"]
        self.client.post(f"/api/trade-plan/{plan_id}/review", json={"setup": setup})
        plan = self.client.get(f"/api/trade-plan/id/{plan_id}").get_json()
        self.assertEqual(len(plan["setup"]["indicators"]), 2)


class TestTerminalTradePlanIntegration(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def test_terminal_has_trade_plan_panel(self):
        resp = self.client.get("/terminal")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn('id="planThesis"', html)
        self.assertIn('id="reviewPlanBtn"', html)
        self.assertIn('id="createOrderFromPlanBtn"', html)
        self.assertIn('name="planDirection"', html)


if __name__ == "__main__":
    unittest.main()
