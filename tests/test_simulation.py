"""Tests for simulation, portfolio, analytics, and challenges."""

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.simulation.market_replay import MarketReplayEngine
from src.simulation.paper_portfolio import PaperPortfolio
from src.analytics.performance import TradingPerformanceAnalytics
from src.learning.challenges import ChallengeTracker
from src.ai_agent.agent import TradingCoachAgent


def _sample_ohlcv(n=10):
    return pd.DataFrame(
        {
            "Open": [180 + i for i in range(n)],
            "High": [185 + i for i in range(n)],
            "Low": [178 + i for i in range(n)],
            "Close": [183 + i for i in range(n)],
            "Volume": [1000000] * n,
        },
        index=pd.date_range("2024-06-01", periods=n, freq="1min"),
    )


class TestMarketReplay(unittest.TestCase):
    def setUp(self):
        self.engine = MarketReplayEngine()

    def test_load_and_step(self):
        data = _sample_ohlcv(5)
        count = self.engine.load(data, "AAPL")
        self.assertEqual(count, 5)

        candle = self.engine.step()
        self.assertIsNotNone(candle)
        self.assertEqual(candle.index, 0)
        self.assertEqual(candle.open, 180)

    def test_step_to_end(self):
        self.engine.load(_sample_ohlcv(3), "AAPL")
        self.engine.step()
        self.engine.step()
        self.engine.step()
        self.assertIsNone(self.engine.step())

    def test_pause_play_speed(self):
        self.engine.load(_sample_ohlcv(5), "AAPL")
        self.engine.set_speed(2)
        self.assertEqual(self.engine.get_status()["speed"], 2)
        self.engine.play()
        self.assertTrue(self.engine.get_status()["is_playing"])
        self.engine.pause()
        self.assertFalse(self.engine.get_status()["is_playing"])

    def test_reset_and_seek(self):
        self.engine.load(_sample_ohlcv(5), "AAPL")
        self.engine.step()
        self.engine.step()
        self.engine.reset()
        self.assertEqual(self.engine.get_status()["current_index"], -1)
        candle = self.engine.seek(2)
        self.assertEqual(candle.index, 2)

    def test_load_empty_raises_nothing(self):
        self.assertEqual(self.engine.load(pd.DataFrame(), "AAPL"), 0)

    def test_invalid_columns_raises(self):
        bad = pd.DataFrame({"Close": [1, 2, 3]})
        with self.assertRaises(ValueError):
            self.engine.load(bad, "AAPL")


class TestPaperPortfolio(unittest.TestCase):
    def setUp(self):
        self.portfolio = PaperPortfolio(initial_cash=10000)

    def test_buy_with_commission_and_slippage(self):
        result = self.portfolio.buy("AAPL", 100.0, 10)
        self.assertTrue(result["success"])
        self.assertLess(self.portfolio.cash, 10000)
        self.assertGreater(result["commission"], 0)
        self.assertGreater(result["fill_price"], 100)

    def test_sell_realized_pnl(self):
        self.portfolio.buy("AAPL", 100.0, 10)
        result = self.portfolio.sell("AAPL", 110.0, 10)
        self.assertTrue(result["success"])
        self.assertGreater(self.portfolio.realized_pnl, 0)

    def test_insufficient_cash(self):
        result = self.portfolio.buy("AAPL", 10000.0, 100)
        self.assertFalse(result["success"])

    def test_unrealized_pnl(self):
        self.portfolio.buy("AAPL", 100.0, 10)
        pnl = self.portfolio.get_unrealized_pnl("AAPL", 110.0)
        self.assertGreater(pnl, 0)

    def test_hold(self):
        result = self.portfolio.hold("AAPL", "Waiting for signal")
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "hold")

    def test_portfolio_to_dict(self):
        self.portfolio.buy("AAPL", 100.0, 5)
        data = self.portfolio.to_dict({"AAPL": 105.0})
        self.assertIn("total_value", data)
        self.assertIn("unrealized_pnl", data)
        self.assertEqual(len(data["position_history"]), 1)


class TestTradingAnalytics(unittest.TestCase):
    def setUp(self):
        self.analytics = TradingPerformanceAnalytics()

    def test_basic_metrics(self):
        trades = [
            {"type": "buy", "price": 100, "quantity": 10},
            {"type": "sell", "price": 110, "quantity": 10},
            {"type": "buy", "price": 100, "quantity": 10},
            {"type": "sell", "price": 95, "quantity": 10},
        ]
        result = self.analytics.calculate(trades, [10000, 10100, 10050], 10000)
        self.assertEqual(result["total_trades"], 2)
        self.assertEqual(result["win_rate"], 50.0)
        self.assertIn("sharpe_ratio", result)
        self.assertIn("lessons", result)

    def test_empty_trades(self):
        result = self.analytics.calculate([], [], 10000)
        self.assertEqual(result["total_trades"], 0)
        self.assertGreater(len(result["lessons"]), 0)

    def test_profit_factor(self):
        trades = [
            {"type": "buy", "price": 100, "quantity": 10},
            {"type": "sell", "price": 120, "quantity": 10},
        ]
        result = self.analytics.calculate(trades, [10000, 10200], 10000)
        self.assertTrue(result["profit_factor"] is None or result["profit_factor"] > 0)
        self.assertGreater(result["gross_profit"], 0)

    def test_drawdown(self):
        result = self.analytics.calculate([], [10000, 9000, 8500], 10000)
        self.assertGreater(result["drawdown"], 0)


class TestChallenges(unittest.TestCase):
    def setUp(self):
        self.tracker = ChallengeTracker()

    def test_evaluate_capital_preservation_pass(self):
        metrics = {"drawdown": 5, "pnl": 500, "total_return_pct": 5}
        result = self.tracker.evaluate(1, metrics)
        self.assertTrue(result["completed"])
        self.assertEqual(result["score"], 100)

    def test_evaluate_capital_preservation_fail_drawdown(self):
        metrics = {"drawdown": 15, "pnl": 100}
        result = self.tracker.evaluate(1, metrics)
        self.assertFalse(result["completed"])
        self.assertGreater(len(result["mistakes"]), 0)

    def test_evaluate_risk_management(self):
        metrics = {"total_trades": 20, "drawdown": 3}
        result = self.tracker.evaluate(2, metrics)
        self.assertTrue(result["completed"])

    def test_evaluate_beat_benchmark(self):
        metrics = {"beat_benchmark": True, "total_return_pct": 10, "benchmark_return_pct": 5}
        result = self.tracker.evaluate(3, metrics)
        self.assertTrue(result["completed"])
        self.assertEqual(result["score"], 100)

    def test_get_all_challenges(self):
        from src.learning.challenges import get_all_challenges
        challenges = get_all_challenges()
        self.assertEqual(len(challenges), 3)


class TestCoachUpgrade(unittest.TestCase):
    def setUp(self):
        self.coach = TradingCoachAgent()

    def test_pre_trade_review_buy(self):
        result = self.coach.pre_trade_review(
            "BUY", "AAPL",
            {"indicators": {"rsi": 55, "short_ma": 155, "long_ma": 150, "current_price": 156}},
            {"cash": 10000, "shares_held": 0},
            reason="Golden cross",
        )
        self.assertIn("trade_confidence_score", result)
        self.assertIn("questions", result)

    def test_post_trade_review(self):
        result = self.coach.post_trade_review(
            {"action": "sell", "fill_price": 110, "realized_pnl": 50, "symbol": "AAPL", "commission": 1.1},
        )
        self.assertEqual(result["prompt"], "What happened?")
        self.assertGreater(len(result["reflection"]), 0)

    def test_confidence_score_range(self):
        score = self.coach.trade_confidence_score(
            {"rsi": 50, "short_ma": 155, "long_ma": 150, "current_price": 156},
            {},
            "low",
        )
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class TestSimulationAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_performance_endpoint(self):
        resp = self.client.get("/api/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("sharpe_ratio", data)
        self.assertIn("lessons", data)

    def test_challenges_list(self):
        resp = self.client.get("/api/challenges")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()["challenges"]), 3)

    def test_replay_load_and_step(self):
        import unittest.mock as mock
        with mock.patch("src.api.simulation_routes.DataFetcher") as MockFetcher:
            MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
            load = self.client.post("/api/simulation/replay/load", json={"symbol": "AAPL", "initial_cash": 10000})
            self.assertEqual(load.status_code, 200)

        step = self.client.post("/api/simulation/replay/step")
        self.assertEqual(step.status_code, 200)
        self.assertIn("candle", step.get_json())

    def test_manual_trade_hold(self):
        import unittest.mock as mock
        with mock.patch("src.api.simulation_routes.DataFetcher") as MockFetcher:
            MockFetcher.return_value.get_real_time_data.return_value = _sample_ohlcv(5)
            self.client.post("/api/simulation/replay/load", json={"symbol": "AAPL"})
            self.client.post("/api/simulation/replay/step")

        resp = self.client.post("/api/simulation/trade", json={"action": "HOLD", "symbol": "AAPL"})
        self.assertEqual(resp.status_code, 200)

    def test_pre_trade_review_api(self):
        resp = self.client.post("/api/ai/pre-trade-review", json={"action": "BUY", "symbol": "AAPL", "reason": "Test"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("trade_confidence_score", resp.get_json())

    def test_journal_timeline(self):
        resp = self.client.get("/api/simulation/journal-timeline")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("timeline", resp.get_json())


if __name__ == "__main__":
    unittest.main()
