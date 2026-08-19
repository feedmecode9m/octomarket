"""Tests for Strategy Lab — builder, backtester, comparator, coach, skill score."""

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.strategy_lab.strategy_builder import StrategyBuilder
from src.strategy_lab.backtester import StrategyBacktester
from src.strategy_lab.comparator import StrategyComparator
from src.strategy_lab.library import get_strategy_library, get_strategy_by_id
from src.ai_agent.agent import TradingCoachAgent
from src.learning.skill_score import SkillScoreCalculator


def _ohlcv(n=60):
    import numpy as np
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": [1000000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="1D"),
    )


class TestStrategyBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = StrategyBuilder()

    def test_ma_crossover_buy(self):
        desc = "Buy when the 20 day moving average crosses above the 50 day moving average"
        result = self.builder.parse(desc)
        self.assertEqual(len(result["rules"]), 1)
        rule = result["rules"][0]
        self.assertEqual(rule["indicator"], "SMA")
        self.assertEqual(rule["fast_period"], 20)
        self.assertEqual(rule["slow_period"], 50)
        self.assertEqual(rule["action"], "BUY")

    def test_rsi_sell(self):
        desc = "Sell when RSI goes above 70"
        result = self.builder.parse(desc)
        rule = result["rules"][0]
        self.assertEqual(rule["indicator"], "RSI")
        self.assertEqual(rule["threshold"], 70)
        self.assertEqual(rule["action"], "SELL")

    def test_rsi_buy_below(self):
        desc = "Buy when RSI goes below 30"
        result = self.builder.parse(desc)
        self.assertEqual(result["rules"][0]["action"], "BUY")
        self.assertEqual(result["rules"][0]["condition"], "below")

    def test_empty_description_raises(self):
        with self.assertRaises(ValueError):
            self.builder.parse("")

    def test_parse_rules_directly(self):
        rules = [{"indicator": "RSI", "period": 14, "threshold": 70, "condition": "above", "action": "SELL"}]
        result = self.builder.parse_rules(rules, "Test")
        self.assertEqual(len(result["rules"]), 1)


class TestBacktester(unittest.TestCase):
    def setUp(self):
        self.backtester = StrategyBacktester()
        self.data = _ohlcv(60)
        self.strategy = get_strategy_by_id("ma_crossover")

    def test_run_backtest_returns_metrics(self):
        result = self.backtester.run(self.strategy, self.data, "TEST", 10000)
        self.assertIn("total_return_pct", result)
        self.assertIn("win_rate", result)
        self.assertIn("max_drawdown", result)
        self.assertIn("sharpe_ratio", result)
        self.assertIn("benchmark_comparison", result)
        self.assertIn("trades", result)

    def test_commissions_applied(self):
        result = self.backtester.run(self.strategy, self.data, "TEST", 10000)
        if result["total_trades"] > 0:
            self.assertGreater(result["commissions_paid"], 0)

    def test_empty_data_raises(self):
        with self.assertRaises(ValueError):
            self.backtester.run(self.strategy, pd.DataFrame(), "TEST")

    def test_no_rules_raises(self):
        with self.assertRaises(ValueError):
            self.backtester.run({"name": "Empty", "rules": []}, self.data)


class TestComparator(unittest.TestCase):
    def setUp(self):
        self.comparator = StrategyComparator()
        self.data = _ohlcv(60)

    def test_compare_strategies(self):
        s1 = get_strategy_by_id("ma_crossover")
        s2 = get_strategy_by_id("rsi_reversal")
        result = self.comparator.compare([s1, s2], self.data)
        self.assertIn("best_performer", result)
        self.assertIn("rankings", result)
        self.assertGreaterEqual(len(result["rankings"]), 3)

    def test_risk_differences(self):
        s1 = get_strategy_by_id("ma_crossover")
        s2 = get_strategy_by_id("rsi_reversal")
        result = self.comparator.compare([s1, s2], self.data)
        self.assertIsInstance(result["risk_differences"], list)

    def test_empty_strategies_raises(self):
        with self.assertRaises(ValueError):
            self.comparator.compare([], self.data)


class TestStrategyLibrary(unittest.TestCase):
    def test_library_count(self):
        lib = get_strategy_library()
        self.assertGreaterEqual(len(lib), 6)

    def test_get_by_id(self):
        s = get_strategy_by_id("ma_crossover")
        self.assertIsNotNone(s)
        self.assertGreater(len(s["rules"]), 0)

    def test_invalid_id(self):
        self.assertIsNone(get_strategy_by_id("nonexistent"))


class TestStrategyCoach(unittest.TestCase):
    def setUp(self):
        self.coach = TradingCoachAgent()

    def test_review_strategy_high_drawdown(self):
        strategy = {"name": "Test", "rules": [{"indicator": "SMA", "action": "BUY"}]}
        backtest = {
            "win_rate": 60,
            "max_drawdown": 15,
            "total_return_pct": 5,
            "sharpe_ratio": 0.3,
            "total_trades": 10,
            "benchmark_comparison": {"beat_benchmark": True, "alpha": 2},
        }
        result = self.coach.review_strategy(strategy, backtest)
        self.assertIn("strengths", result)
        self.assertIn("weaknesses", result)
        self.assertIn("improvement_suggestions", result)
        self.assertIn("difficulty_level", result)
        self.assertTrue(any("drawdown" in w.lower() for w in result["weaknesses"]))

    def test_review_underperforms_benchmark(self):
        strategy = {"name": "Test", "rules": []}
        backtest = {
            "win_rate": 30,
            "max_drawdown": 5,
            "total_return_pct": -2,
            "total_trades": 5,
            "benchmark_comparison": {"beat_benchmark": False, "alpha": -5},
        }
        result = self.coach.review_strategy(strategy, backtest)
        self.assertTrue(any("holding" in w.lower() or "worse" in w.lower() for w in result["weaknesses"]))


class TestSkillScore(unittest.TestCase):
    def setUp(self):
        self.calc = SkillScoreCalculator()

    def test_score_bounds(self):
        result = self.calc.calculate(
            performance={"drawdown": 2, "win_rate": 60, "sharpe_ratio": 1.2, "total_trades": 10},
            backtest_results={"total_return_pct": 8, "benchmark_comparison": {"beat_benchmark": True}},
        )
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)
        self.assertIn("level", result)
        self.assertIn("components", result)

    def test_novice_level(self):
        result = self.calc.calculate(
            performance={"drawdown": 20, "win_rate": 20, "sharpe_ratio": -1, "total_trades": 0},
            backtest_results={"total_return_pct": -10, "benchmark_comparison": {"beat_benchmark": False}},
        )
        self.assertLess(result["score"], 45)


class TestStrategyLabAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_parse_strategy(self):
        resp = self.client.post("/api/strategy/parse", json={
            "description": "Sell when RSI goes above 70",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["rules"][0]["indicator"], "RSI")

    def test_library_list(self):
        resp = self.client.get("/api/strategy/library")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.get_json()["strategies"]), 6)

    def test_backtest_with_mock(self):
        import unittest.mock as mock
        with mock.patch("src.api.strategy_lab_routes.DataFetcher") as MockFetcher:
            MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(60)
            resp = self.client.post("/api/strategy/backtest", json={
                "strategy": get_strategy_by_id("rsi_reversal"),
                "symbol": "AAPL",
            })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("win_rate", data)

    def test_review_strategy_api(self):
        resp = self.client.post("/api/ai/review-strategy", json={
            "strategy": get_strategy_by_id("ma_crossover"),
            "backtest_results": {
                "win_rate": 55, "max_drawdown": 8, "total_return_pct": 3,
                "sharpe_ratio": 0.8, "total_trades": 8,
                "benchmark_comparison": {"beat_benchmark": True, "alpha": 1},
            },
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("difficulty_level", resp.get_json())

    def test_skill_score_api(self):
        resp = self.client.get("/api/skill-score")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("score", resp.get_json())

    def test_strategy_lab_page(self):
        resp = self.client.get("/strategy-lab")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Strategy Lab", resp.data)


if __name__ == "__main__":
    unittest.main()
