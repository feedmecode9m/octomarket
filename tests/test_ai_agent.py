"""Tests for the AI Trading Coach module."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ai_agent.agent import TradingCoachAgent
from src.ai_agent.market_analyzer import MarketAnalyzer
from src.ai_agent.risk_coach import RiskCoach
from src.ai_agent.trade_journal import TradeJournal


class TestMarketAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = MarketAnalyzer()

    def test_analyze_bullish_indicators(self):
        result = self.analyzer.analyze({
            "rsi": 55,
            "short_ma": 155.0,
            "long_ma": 150.0,
            "price_momentum": 0.02,
            "volatility": 2.0,
            "current_price": 156.0,
            "volume_change_pct": 15,
        })
        self.assertEqual(result["trend"], "bullish")
        self.assertEqual(result["rsi"]["zone"], "neutral")
        self.assertEqual(result["moving_averages"]["signal"], "bullish")

    def test_analyze_overbought_rsi(self):
        result = self.analyzer.analyze({"rsi": 75, "short_ma": 100, "long_ma": 99, "current_price": 101})
        self.assertEqual(result["rsi"]["zone"], "overbought")

    def test_analyze_oversold_rsi(self):
        result = self.analyzer.analyze({"rsi": 25, "short_ma": 99, "long_ma": 100, "current_price": 98})
        self.assertEqual(result["rsi"]["zone"], "oversold")

    def test_analyze_insufficient_data(self):
        result = self.analyzer.analyze({})
        self.assertEqual(result["moving_averages"]["signal"], "insufficient_data")

    def test_support_resistance(self):
        prices = [100, 102, 98, 105, 103, 99, 107]
        result = self.analyzer.analyze({"current_price": 107}, prices=prices)
        self.assertIsNotNone(result["support_resistance"]["support"])
        self.assertIsNotNone(result["support_resistance"]["resistance"])


class TestRiskCoach(unittest.TestCase):
    def setUp(self):
        self.coach = RiskCoach()

    def test_position_sizing(self):
        result = self.coach.explain_position_sizing(cash=5000, price=150, risk_per_trade=0.02, stop_loss_pct=0.01)
        self.assertGreater(result["recommended_shares"], 0)
        self.assertIn("explanation", result)

    def test_position_sizing_zero_price(self):
        result = self.coach.explain_position_sizing(cash=5000, price=0)
        self.assertEqual(result["recommended_shares"], 0)

    def test_stop_loss(self):
        result = self.coach.explain_stop_loss(entry_price=100, stop_loss_pct=0.01, shares_held=10)
        self.assertEqual(result["stop_price"], 99.0)
        self.assertAlmostEqual(result["max_loss"], 10.0)

    def test_risk_reward_favorable(self):
        result = self.coach.explain_risk_reward(entry_price=100, stop_loss_pct=0.01, profit_target_pct=0.03)
        self.assertEqual(result["quality"], "favorable")
        self.assertGreater(result["ratio"], 2)

    def test_drawdown_low(self):
        result = self.coach.explain_drawdown(initial_value=5000, current_value=5100)
        self.assertEqual(result["severity"], "low")

    def test_drawdown_high(self):
        result = self.coach.explain_drawdown(initial_value=5000, current_value=4200, portfolio_values=[5000, 4800, 4200])
        self.assertEqual(result["severity"], "high")

    def test_assess_risk(self):
        result = self.coach.assess_risk(
            portfolio={"cash": 5000, "current_value": 4800, "initial_cash": 5000, "shares_held": 5},
            indicators={"current_price": 150, "volatility": 5},
        )
        self.assertIn(result["risk_level"], ["low", "moderate", "high"])
        self.assertIn("warnings", result)


class TestTradeJournal(unittest.TestCase):
    def setUp(self):
        self.journal = TradeJournal()

    def test_record_entry(self):
        entry = self.journal.record(
            symbol="AAPL",
            trade_type="buy",
            entry_price=150.0,
            quantity=10,
            reason="Golden cross signal",
        )
        self.assertEqual(entry["symbol"], "AAPL")
        self.assertEqual(entry["status"], "open")
        self.assertIsNotNone(entry["id"])

    def test_record_and_close(self):
        entry = self.journal.record(
            symbol="AAPL", trade_type="buy", entry_price=100, quantity=5, reason="Test"
        )
        updated = self.journal.update_exit(entry["id"], exit_price=110, lesson_learned="Patience pays")
        self.assertEqual(updated["status"], "closed")
        self.assertEqual(updated["result"]["outcome"], "win")
        self.assertEqual(updated["result"]["pnl"], 50.0)

    def test_sync_from_trades(self):
        trades = [
            {"time": "2024-01-01T10:00:00", "symbol": "AAPL", "type": "buy", "price": 150, "quantity": 5},
            {"time": "2024-01-01T11:00:00", "symbol": "AAPL", "type": "sell", "price": 155, "quantity": 5},
        ]
        added = self.journal.sync_from_trades(trades)
        self.assertEqual(added, 2)
        self.assertEqual(self.journal.get_summary()["total_entries"], 2)

    def test_sync_deduplication(self):
        trades = [{"time": "2024-01-01T10:00:00", "symbol": "AAPL", "type": "buy", "price": 150, "quantity": 5}]
        self.journal.sync_from_trades(trades)
        added = self.journal.sync_from_trades(trades)
        self.assertEqual(added, 0)

    def test_get_by_symbol(self):
        self.journal.record(symbol="AAPL", trade_type="buy", entry_price=150, quantity=5, reason="Test")
        self.journal.record(symbol="MSFT", trade_type="buy", entry_price=300, quantity=2, reason="Test")
        aapl_entries = self.journal.get_by_symbol("AAPL")
        self.assertEqual(len(aapl_entries), 1)

    def test_clear(self):
        self.journal.record(symbol="AAPL", trade_type="buy", entry_price=150, quantity=5, reason="Test")
        self.journal.clear()
        self.assertEqual(len(self.journal.get_all()), 0)


class TestTradingCoachAgent(unittest.TestCase):
    def setUp(self):
        self.journal = TradeJournal()
        self.agent = TradingCoachAgent(trade_journal=self.journal)

    def test_analyze_market_requires_symbol(self):
        with self.assertRaises(ValueError):
            self.agent.analyze_market("", {}, {})

    def test_analyze_market_returns_structure(self):
        result = self.agent.analyze_market(
            symbol="AAPL",
            indicators={"rsi": 55, "short_ma": 155, "long_ma": 150, "current_price": 156, "price_momentum": 0.01},
            portfolio={"cash": 5000, "current_value": 5000, "initial_cash": 5000},
        )
        self.assertIn("market_summary", result)
        self.assertIn("possible_scenarios", result)
        self.assertIn("risk_warning", result)
        self.assertIn("learning_points", result)
        self.assertIn("current_trend", result)
        self.assertIn("risk_level", result)
        self.assertIn("strategy_explanation", result)

    def test_analyze_market_learning_points_not_empty(self):
        result = self.agent.analyze_market(
            symbol="AAPL",
            indicators={"rsi": 75, "short_ma": 155, "long_ma": 150, "current_price": 156},
            portfolio={"cash": 5000, "current_value": 5000, "initial_cash": 5000},
        )
        self.assertGreater(len(result["learning_points"]), 0)

    def test_review_trade_empty_history(self):
        result = self.agent.review_trade(trade_history=[], strategy={}, outcome={})
        self.assertIn("mistakes", result)
        self.assertIn("strengths", result)
        self.assertIn("improvement_plan", result)
        self.assertGreater(len(result["mistakes"]), 0)

    def test_review_trade_with_history(self):
        trades = [
            {"time": "2024-01-01", "symbol": "AAPL", "type": "buy", "price": 150, "quantity": 5},
            {"time": "2024-01-02", "symbol": "AAPL", "type": "sell", "price": 155, "quantity": 5},
        ]
        result = self.agent.review_trade(
            trade_history=trades,
            strategy={"short_window": 5, "long_window": 20},
            outcome={"win_rate": 100, "total_return_pct": 3.3, "max_drawdown": 1},
        )
        self.assertIn("journal_feedback", result)
        self.assertGreater(len(result["strengths"]), 0)

    def test_possible_actions_no_position_bullish(self):
        result = self.agent.analyze_market(
            symbol="AAPL",
            indicators={"rsi": 55, "short_ma": 155, "long_ma": 150, "current_price": 156, "price_momentum": 0.02},
            portfolio={"cash": 5000, "current_value": 5000, "shares_held": 0},
        )
        actions = result["possible_actions"]
        action_types = [a["action"] for a in actions]
        self.assertIn("consider_buy", action_types)


class TestLearningLessons(unittest.TestCase):
    def test_get_all_lessons(self):
        from src.learning.lessons import get_all_lessons
        lessons = get_all_lessons()
        self.assertEqual(len(lessons), 7)

    def test_get_lesson_by_id(self):
        from src.learning.lessons import get_lesson_by_id
        lesson = get_lesson_by_id(1)
        self.assertIsNotNone(lesson)
        self.assertIn("Market Orders", lesson["title"])
        self.assertIn("content", lesson)
        self.assertIn("quiz", lesson)

    def test_get_lesson_not_found(self):
        from src.learning.lessons import get_lesson_by_id
        self.assertIsNone(get_lesson_by_id(999))

    def test_lesson_categories(self):
        from src.learning.lessons import get_lessons_by_category
        ta_lessons = get_lessons_by_category("technical_analysis")
        self.assertGreaterEqual(len(ta_lessons), 2)


class TestAIApiEndpoints(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_analyze_market_missing_symbol(self):
        resp = self.client.post("/api/ai/analyze-market", json={"indicators": {}, "portfolio": {}})
        self.assertEqual(resp.status_code, 400)

    def test_analyze_market_success(self):
        resp = self.client.post("/api/ai/analyze-market", json={
            "symbol": "AAPL",
            "indicators": {"rsi": 55, "short_ma": 155, "long_ma": 150, "current_price": 156},
            "portfolio": {"cash": 5000, "current_value": 5000, "initial_cash": 5000},
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("market_summary", data)
        self.assertIn("learning_points", data)

    def test_review_trade_success(self):
        resp = self.client.post("/api/ai/review-trade", json={
            "trade_history": [],
            "strategy": {"short_window": 5},
            "outcome": {"win_rate": 0},
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("mistakes", data)
        self.assertIn("improvement_plan", data)

    def test_list_lessons(self):
        resp = self.client.get("/api/ai/lessons")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["lessons"]), 7)

    def test_get_lesson_detail(self):
        resp = self.client.get("/api/ai/lessons/3")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("RSI", resp.get_json()["title"])

    def test_get_lesson_not_found(self):
        resp = self.client.get("/api/ai/lessons/999")
        self.assertEqual(resp.status_code, 404)

    def test_journal_get(self):
        resp = self.client.get("/api/ai/journal")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("entries", data)
        self.assertIn("summary", data)

    def test_journal_post(self):
        resp = self.client.post("/api/ai/journal", json={
            "symbol": "AAPL",
            "type": "buy",
            "entry_price": 150,
            "quantity": 10,
            "reason": "Test entry for learning",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["symbol"], "AAPL")

    def test_journal_post_missing_fields(self):
        resp = self.client.post("/api/ai/journal", json={"symbol": "AAPL"})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
