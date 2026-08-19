"""Tests for Phase 11 execution simulator."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.trading.order_engine import OrderEngine
from src.trading.execution import ExecutionSimulator
from src.simulation.paper_portfolio import PaperPortfolio
from src.ai_agent.execution_coach import ExecutionCoach
from src.ai_agent.trade_journal import TradeJournal


class TestOrderEngine(unittest.TestCase):
    def setUp(self):
        self.engine = OrderEngine()

    def test_create_market_order(self):
        order = self.engine.create_order("AAPL", "buy", 10, "market")
        self.assertEqual(order["status"], "PENDING")
        self.assertEqual(order["symbol"], "AAPL")

    def test_create_limit_order(self):
        order = self.engine.create_order("AAPL", "buy", 10, "limit", limit_price=200)
        self.assertEqual(order["limit_price"], 200)

    def test_limit_requires_price(self):
        with self.assertRaises(ValueError):
            self.engine.create_order("AAPL", "buy", 10, "limit")

    def test_cancel_order(self):
        order = self.engine.create_order("AAPL", "buy", 10, "limit", limit_price=200)
        cancelled = self.engine.cancel_order(order["id"])
        self.assertEqual(cancelled["status"], "CANCELLED")

    def test_update_order_price(self):
        order = self.engine.create_order("AAPL", "buy", 10, "limit", limit_price=200)
        updated = self.engine.update_order(order["id"], limit_price=195)
        self.assertEqual(updated["limit_price"], 195)

    def test_mark_filled(self):
        order = self.engine.create_order("AAPL", "buy", 10, "market")
        filled = self.engine.mark_filled(order["id"], 210.5, commission=2.1, slippage=0.5)
        self.assertEqual(filled["status"], "FILLED")
        self.assertEqual(filled["fill_price"], 210.5)

    def test_bracket_creates_children(self):
        order = self.engine.create_order(
            "AAPL", "buy", 10, "limit", limit_price=220,
            stop_loss=210, take_profit=230, bracket=True,
        )
        self.assertEqual(len(order["bracket_orders"]), 2)
        group = self.engine.get_bracket_group(order["bracket_group_id"])
        self.assertEqual(len(group), 3)

    def test_bracket_sibling_cancel(self):
        entry = self.engine.create_order(
            "AAPL", "buy", 10, "limit", limit_price=220,
            stop_loss=210, take_profit=230, bracket=True,
        )
        children = entry["bracket_orders"]
        sl = self.engine.get_order(children[0]["id"])
        self.engine.mark_filled(sl["id"], 210)
        self.engine.cancel_bracket_siblings(sl["id"])
        tp = self.engine.get_order(children[1]["id"])
        self.assertEqual(tp["status"], "CANCELLED")


class TestExecutionSimulator(unittest.TestCase):
    def setUp(self):
        self.portfolio = PaperPortfolio(initial_cash=10000)
        self.engine = OrderEngine()
        self.executor = ExecutionSimulator(self.engine, self.portfolio)

    def test_market_fill_immediate(self):
        order = self.engine.create_order("AAPL", "buy", 10, "market")
        result = self.executor.process_market_order(order, 200)
        self.assertEqual(result["status"], "FILLED")
        self.assertLess(self.portfolio.cash, 10000)

    def test_market_fill_slippage(self):
        order = self.engine.create_order("AAPL", "buy", 10, "market")
        self.executor.process_market_order(order, 200)
        filled = self.engine.get_order(order["id"])
        self.assertGreater(filled["fill_price"], 200)

    def test_limit_fill_on_candle_touch(self):
        order = self.engine.create_order("AAPL", "buy", 10, "limit", limit_price=195)
        candle = {"open": 200, "high": 201, "low": 194, "close": 198}
        fills = self.executor.process_candle("AAPL", candle)
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["status"], "FILLED")

    def test_limit_no_fill_above(self):
        order = self.engine.create_order("AAPL", "buy", 10, "limit", limit_price=190)
        candle = {"open": 200, "high": 201, "low": 195, "close": 198}
        fills = self.executor.process_candle("AAPL", candle)
        self.assertEqual(len(fills), 0)

    def test_stop_market_trigger(self):
        self.portfolio.buy("AAPL", 200, 10)
        order = self.engine.create_order("AAPL", "sell", 10, "stop_market", stop_price=195)
        candle = {"open": 200, "high": 201, "low": 193, "close": 194}
        fills = self.executor.process_candle("AAPL", candle)
        self.assertEqual(len(fills), 1)

    def test_commission_applied(self):
        order = self.engine.create_order("AAPL", "buy", 10, "market")
        self.executor.process_market_order(order, 100)
        filled = self.engine.get_order(order["id"])
        self.assertGreater(filled["commission"], 0)

    def test_partial_fill_insufficient_cash(self):
        order = self.engine.create_order("AAPL", "buy", 200, "market")
        result = self.executor.process_market_order(order, 100)
        self.assertEqual(result["status"], "FILLED")
        filled = self.engine.get_order(order["id"])
        self.assertLess(filled["filled_quantity"], 200)

    def test_reject_no_price(self):
        order = self.engine.create_order("AAPL", "buy", 10, "market")
        result = self.executor.process_market_order(order, 0)
        self.assertEqual(result["status"], "REJECTED")


class TestExecutionCoach(unittest.TestCase):
    def setUp(self):
        self.coach = ExecutionCoach()

    def test_oversized_position_warning(self):
        order = {"symbol": "AAPL", "side": "buy", "quantity": 50, "order_type": "market"}
        portfolio = {"total_value": 10000, "cash": 10000}
        result = self.coach.review(order, portfolio, 200)
        self.assertGreater(result["risk_score"], 0)
        self.assertTrue(len(result["warnings"]) > 0)

    def test_stop_loss_risk_calculation(self):
        order = {
            "symbol": "AAPL", "side": "buy", "quantity": 10,
            "order_type": "limit", "limit_price": 200,
            "stop_loss": 190, "take_profit": 220,
        }
        portfolio = {"total_value": 10000, "cash": 10000}
        result = self.coach.review(order, portfolio, 200)
        self.assertEqual(result["metrics"]["dollar_risk"], 100)
        self.assertEqual(result["metrics"]["reward_risk_ratio"], 2.0)

    def test_no_stop_warning(self):
        order = {"symbol": "AAPL", "side": "buy", "quantity": 5, "order_type": "market"}
        portfolio = {"total_value": 10000, "cash": 10000}
        result = self.coach.review(order, portfolio, 200)
        self.assertTrue(any("stop" in s.lower() for s in result["suggestions"]))

    def test_lesson_on_oversized(self):
        order = {"symbol": "AAPL", "side": "buy", "quantity": 40, "order_type": "market"}
        portfolio = {"total_value": 10000, "cash": 10000}
        result = self.coach.review(order, portfolio, 200)
        self.assertIn("oversized", result["lesson"].lower())


class TestTradeJournalUpgrade(unittest.TestCase):
    def setUp(self):
        self.journal = TradeJournal()

    def test_record_execution_with_plan(self):
        entry = self.journal.record_execution(
            "AAPL", "buy", 200, 10, "order-123",
            trade_plan={"why_enter": "Breakout", "setup": "MA cross", "expected_move": "+5%"},
        )
        self.assertEqual(entry["trade_plan"]["setup"], "MA cross")
        self.assertEqual(entry["order_id"], "order-123")

    def test_execution_review(self):
        entry = self.journal.record_execution("AAPL", "buy", 200, 10, "order-1")
        reviewed = self.journal.add_execution_review(entry["id"], {
            "entry_good": True, "risk_controlled": True, "exit_disciplined": False,
        }, exit_price=210)
        self.assertIsNotNone(reviewed["execution_review"])
        self.assertEqual(reviewed["status"], "closed")

    def test_history_closed_trades(self):
        entry = self.journal.record_execution("AAPL", "buy", 200, 10, "order-1")
        self.journal.update_exit(entry["id"], 210)
        history = self.journal.get_history()
        self.assertEqual(len(history), 1)


class TestExecutionAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_place_market_order(self):
        resp = self.client.post("/api/orders", json={
            "symbol": "AAPL", "side": "buy", "quantity": 5, "order_type": "market",
        })
        self.assertEqual(resp.status_code, 200)

    def test_list_orders(self):
        self.client.post("/api/orders", json={
            "symbol": "AAPL", "side": "buy", "quantity": 5, "order_type": "limit", "limit_price": 100,
        })
        resp = self.client.get("/api/orders")
        self.assertGreater(len(resp.get_json()["orders"]), 0)

    def test_cancel_order(self):
        resp = self.client.post("/api/orders", json={
            "symbol": "AAPL", "side": "buy", "quantity": 5, "order_type": "limit", "limit_price": 50,
        })
        oid = resp.get_json()["order"]["id"]
        resp = self.client.delete(f"/api/orders/{oid}")
        self.assertEqual(resp.status_code, 200)

    def test_review_execution(self):
        resp = self.client.post("/api/ai/review-execution", json={
            "order": {"symbol": "AAPL", "side": "buy", "quantity": 10, "order_type": "market", "stop_loss": 190},
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("risk_score", data)
        self.assertIn("warnings", data)

    def test_account_endpoint(self):
        resp = self.client.get("/api/terminal/account")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("equity", resp.get_json())

    def test_history_endpoint(self):
        resp = self.client.get("/api/terminal/history")
        self.assertEqual(resp.status_code, 200)

    def test_bracket_order(self):
        resp = self.client.post("/api/orders", json={
            "symbol": "AAPL", "side": "buy", "quantity": 5, "order_type": "limit",
            "limit_price": 100, "stop_loss": 95, "take_profit": 110, "bracket": True,
        })
        self.assertEqual(resp.status_code, 200)
        orders = self.client.get("/api/orders").get_json()["orders"]
        self.assertGreaterEqual(len(orders), 3)


if __name__ == "__main__":
    unittest.main()
