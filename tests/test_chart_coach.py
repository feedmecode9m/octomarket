"""Tests for chart coach, market context, and plan review."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ai_agent.chart_coach import ChartCoach
from src.ai_agent.market_context import (
    build_indicator_summary,
    build_market_context,
    normalize_drawings,
    normalize_trade_plan,
)
from src.ai_agent.plan_review import review_post_trade, review_pre_trade


def _sample_plan():
    return {
        "id": "plan-1",
        "symbol": "AAPL",
        "direction": "LONG",
        "thesis": "Breakout above resistance",
        "entry": {"price": 185, "source": {"type": "drawing", "id": "draw-12"}},
        "stop_loss": {"price": 180},
        "target": {"price": 195},
        "risk_reward": 2.0,
        "risk_points": 5,
        "reward_points": 10,
        "setup": {"indicators": [{"key": "SMA20"}], "drawings": []},
    }


class TestMarketContext(unittest.TestCase):
    def test_build_context(self):
        ctx = build_market_context(
            symbol="AAPL",
            price=185.2,
            indicator_payload={"indicators": {"RSI": {"values": [None, 62]}, "SMA20": {"values": [None, 182]}}},
            drawings=[{"type": "horizontal", "price": 185, "label": "Resistance", "id": "d1"}],
            trade_plan=_sample_plan(),
        )
        self.assertEqual(ctx["symbol"], "AAPL")
        self.assertEqual(ctx["indicators"]["RSI"], 62)
        self.assertEqual(ctx["trade_plan"]["entry"], 185)

    def test_normalize_drawings_horizontal(self):
        norm = normalize_drawings([{"type": "horizontal", "price": 185, "label": "Resistance"}])
        self.assertEqual(norm[0]["role"], "resistance")

    def test_normalize_drawings_zone(self):
        norm = normalize_drawings([{"type": "zone", "top": 190, "bottom": 185, "label": "Demand Zone"}])
        self.assertEqual(norm[0]["role"], "demand")

    def test_normalize_trade_plan(self):
        norm = normalize_trade_plan(_sample_plan())
        self.assertEqual(norm["rr"], 2.0)
        self.assertEqual(norm["stop"], 180)

    def test_indicator_summary_macd(self):
        summary = build_indicator_summary({
            "indicators": {
                "MACD": {"macd": [0, 1], "signal": [0, 0.5]},
            }
        })
        self.assertEqual(summary["MACD"], "bullish crossover")


    def test_macd_bearish_summary(self):
        summary = build_indicator_summary({
            "indicators": {"MACD": {"macd": [1, 0], "signal": [0.5, 1]}},
        })
        self.assertEqual(summary["MACD"], "bearish crossover")

    def test_context_without_plan(self):
        ctx = build_market_context(symbol="AAPL", price=100)
        self.assertIsNone(ctx["trade_plan"])


class TestPlanReview(unittest.TestCase):
    def test_pre_trade_with_thesis_and_rr(self):
        ctx = build_market_context(
            symbol="AAPL",
            price=185,
            indicator_payload={"indicators": {"RSI": {"values": [64]}}},
            drawings=[{"type": "horizontal", "price": 185, "label": "Resistance"}],
            trade_plan=_sample_plan(),
        )
        review = review_pre_trade(ctx)
        self.assertIn(review["grade"], ("A", "B", "C", "D", "F"))
        self.assertTrue(review["observations"])
        self.assertTrue(review["risk_notes"])
        self.assertEqual(review["review_type"], "pre_trade")

    def test_pre_trade_no_plan(self):
        review = review_pre_trade({"symbol": "AAPL"})
        self.assertEqual(review["grade"], "F")
        self.assertTrue(review["warnings"])

    def test_pre_trade_high_rsi_warning(self):
        ctx = build_market_context(
            symbol="AAPL",
            trade_plan=_sample_plan(),
            indicator_payload={"indicators": {"RSI": {"values": [75]}}},
        )
        review = review_pre_trade(ctx)
        self.assertTrue(any("RSI" in w for w in review["warnings"]))

    def test_pre_trade_low_rr_warning(self):
        plan = _sample_plan()
        plan["risk_reward"] = 1.0
        ctx = build_market_context(symbol="AAPL", trade_plan=plan)
        review = review_pre_trade(ctx)
        self.assertTrue(any("Risk/reward" in w for w in review["warnings"]))

    def test_no_buy_sell_recommendation(self):
        review = review_pre_trade(build_market_context(symbol="AAPL", trade_plan=_sample_plan()))
        text = str(review).lower()
        self.assertNotIn("buy aapl", text)
        self.assertNotIn("sell aapl", text)

    def test_post_trade_plan_followed(self):
        ctx = build_market_context(symbol="AAPL", trade_plan=_sample_plan())
        review = review_post_trade(ctx, {"fill_price": 185.1, "exit_price": 194, "pnl": 90})
        self.assertEqual(review["review_type"], "post_trade")
        self.assertTrue(review.get("followed_plan"))
        self.assertTrue(review["observations"])

    def test_post_trade_slippage_warning(self):
        ctx = build_market_context(symbol="AAPL", trade_plan=_sample_plan())
        review = review_post_trade(ctx, {"fill_price": 187, "exit_price": 190, "pnl": 30})
        self.assertTrue(any("Filled above" in w for w in review["warnings"]))


    def test_missing_thesis_question(self):
        plan = _sample_plan()
        plan["thesis"] = ""
        ctx = build_market_context(symbol="AAPL", trade_plan=plan)
        review = review_pre_trade(ctx)
        self.assertTrue(any("thesis" in q.lower() or "structure" in q.lower() for q in review["questions"]))

    def test_macd_conflict_warning(self):
        ctx = build_market_context(
            symbol="AAPL",
            trade_plan=_sample_plan(),
            indicator_payload={"indicators": {"MACD": {"macd": [1, 0], "signal": [0.5, 1]}}},
        )
        review = review_pre_trade(ctx)
        self.assertTrue(any("MACD" in w for w in review["warnings"]))


class TestChartCoach(unittest.TestCase):
    def setUp(self):
        self.coach = ChartCoach()

    def test_review_chart_stores_history(self):
        result = self.coach.review_chart(
            symbol="AAPL",
            trade_plan=_sample_plan(),
            drawings=[{"type": "horizontal", "price": 185, "label": "Resistance"}],
        )
        self.assertIn("grade", result)
        history = self.coach.get_history("AAPL")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], result["id"])

    def test_review_trade_plan_post(self):
        result = self.coach.review_trade_plan(
            _sample_plan(),
            execution={"fill_price": 185.2, "exit_price": 192, "pnl": 68},
        )
        self.assertEqual(result["review_type"], "post_trade")

    def test_history_limit(self):
        for _ in range(5):
            self.coach.review_chart("MSFT", trade_plan={**_sample_plan(), "symbol": "MSFT"})
        self.assertEqual(len(self.coach.get_history("MSFT", limit=3)), 3)

    def test_reset_clears_history(self):
        self.coach.review_chart("AAPL", trade_plan=_sample_plan())
        self.coach.reset()
        self.assertEqual(self.coach.get_history("AAPL"), [])


if __name__ == "__main__":
    unittest.main()
