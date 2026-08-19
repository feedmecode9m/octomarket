"""Tests for trade plan models, risk calculation, and lifecycle."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.trading.trade_plan import (
    TradePlanManager,
    calculate_risk_reward,
    validate_plan_levels,
)


class TestRiskCalculation(unittest.TestCase):
    def test_long_risk_reward(self):
        m = calculate_risk_reward("LONG", 185, 180, 195, quantity=10)
        self.assertEqual(m["risk_points"], 5)
        self.assertEqual(m["reward_points"], 10)
        self.assertEqual(m["risk_reward"], 2.0)
        self.assertEqual(m["dollar_risk"], 50.0)
        self.assertEqual(m["dollar_reward"], 100.0)

    def test_short_risk_reward(self):
        m = calculate_risk_reward("SHORT", 185, 190, 175, quantity=5)
        self.assertEqual(m["risk_points"], 5)
        self.assertEqual(m["reward_points"], 10)
        self.assertEqual(m["risk_reward"], 2.0)

    def test_invalid_stop_long(self):
        with self.assertRaises(ValueError):
            calculate_risk_reward("LONG", 185, 190, 195)

    def test_invalid_target_long(self):
        with self.assertRaises(ValueError):
            calculate_risk_reward("LONG", 185, 180, 180)

    def test_invalid_direction(self):
        with self.assertRaises(ValueError):
            calculate_risk_reward("FLAT", 185, 180, 195)


class TestTradePlanManager(unittest.TestCase):
    def setUp(self):
        self.mgr = TradePlanManager()

    def _sample(self, **overrides):
        base = {
            "symbol": "AAPL",
            "direction": "LONG",
            "thesis": "Breakout above resistance",
            "entry": {"price": 185},
            "stop_loss": {"price": 180},
            "target": {"price": 195},
            "quantity": 10,
        }
        base.update(overrides)
        return base

    def test_create_plan(self):
        plan = self.mgr.create_plan(self._sample())
        self.assertEqual(plan["symbol"], "AAPL")
        self.assertEqual(plan["status"], "DRAFT")
        self.assertEqual(plan["risk_reward"], 2.0)

    def test_create_with_drawing_source(self):
        plan = self.mgr.create_plan(self._sample(entry={
            "price": 185,
            "source": {"type": "drawing", "id": "draw-12", "label": "Resistance"},
        }))
        self.assertEqual(plan["entry"]["source"]["id"], "draw-12")

    def test_create_with_indicator_setup(self):
        plan = self.mgr.create_plan(self._sample(setup={
            "indicators": [{"key": "SMA20", "summary": "Above price"}],
            "drawings": [{"id": "d1", "type": "horizontal"}],
        }))
        self.assertEqual(len(plan["setup"]["indicators"]), 1)

    def test_update_plan(self):
        plan = self.mgr.create_plan(self._sample())
        updated = self.mgr.update_plan(plan["id"], {"target": {"price": 200}})
        self.assertEqual(updated["target"]["price"], 200)
        self.assertGreater(updated["risk_reward"], 2.0)

    def test_review_and_approve_flow(self):
        plan = self.mgr.create_plan(self._sample())
        reviewed = self.mgr.review_plan(plan["id"])
        self.assertEqual(reviewed["status"], "REVIEWED")
        approved = self.mgr.approve_plan(plan["id"])
        self.assertEqual(approved["status"], "APPROVED")

    def test_invalid_transition(self):
        plan = self.mgr.create_plan(self._sample())
        with self.assertRaises(ValueError):
            self.mgr.approve_plan(plan["id"])

    def test_mark_order_created(self):
        plan = self.mgr.create_plan(self._sample())
        self.mgr.review_plan(plan["id"])
        self.mgr.approve_plan(plan["id"])
        updated = self.mgr.mark_order_created(plan["id"], "order-123")
        self.assertEqual(updated["status"], "ORDER_CREATED")
        self.assertEqual(updated["order_id"], "order-123")

    def test_build_order_payload(self):
        plan = self.mgr.create_plan(self._sample())
        payload = self.mgr.build_order_payload(plan)
        self.assertEqual(payload["symbol"], "AAPL")
        self.assertEqual(payload["side"], "buy")
        self.assertTrue(payload["bracket"])
        self.assertIn("plan_id", payload["trade_plan"])

    def test_short_order_side(self):
        plan = self.mgr.create_plan(self._sample(direction="SHORT", stop_loss={"price": 190}, target={"price": 175}))
        payload = self.mgr.build_order_payload(plan)
        self.assertEqual(payload["side"], "sell")

    def test_get_plans_for_symbol(self):
        self.mgr.create_plan(self._sample())
        self.mgr.create_plan(self._sample(symbol="MSFT", entry={"price": 400}, stop_loss={"price": 390}, target={"price": 420}))
        self.assertEqual(len(self.mgr.get_plans_for_symbol("AAPL")), 1)

    def test_validate_plan_levels(self):
        plan = self.mgr.create_plan(self._sample())
        validate_plan_levels(plan)

    def test_cannot_update_after_order_created(self):
        plan = self.mgr.create_plan(self._sample())
        self.mgr.review_plan(plan["id"])
        self.mgr.approve_plan(plan["id"])
        self.mgr.mark_order_created(plan["id"], "ord-1")
        with self.assertRaises(ValueError):
            self.mgr.update_plan(plan["id"], {"thesis": "late edit"})

    def test_mark_completed(self):
        plan = self.mgr.create_plan(self._sample())
        self.mgr.review_plan(plan["id"])
        self.mgr.approve_plan(plan["id"])
        self.mgr.mark_order_created(plan["id"], "ord-1")
        done = self.mgr.mark_completed(plan["id"])
        self.assertEqual(done["status"], "COMPLETED")

    def test_missing_symbol(self):
        with self.assertRaises(ValueError):
            self.mgr.create_plan({"direction": "LONG"})


if __name__ == "__main__":
    unittest.main()
