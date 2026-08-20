"""Tests for Gate 16B — Strategy Validation & Ranking Layer."""

import os
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _trending_ohlcv(n=80, base=5000.0, step=2.0):
    closes = [base + step * i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 1 for c in closes],
            "High": [c + 4 for c in closes],
            "Low": [c - 3 for c in closes],
            "Close": closes,
            "Volume": [50000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="1D"),
    )


def _trending_forex(n=80, base=1.0850):
    closes = [base + 0.0004 * i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 0.0002 for c in closes],
            "High": [c + 0.0005 for c in closes],
            "Low": [c - 0.0005 for c in closes],
            "Close": closes,
            "Volume": [0] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="1D"),
    )


def _sample_closed_record(**overrides):
    base = {
        "id": "rec-1",
        "status": "closed",
        "market": {"instrument_id": "ESZ26", "asset_class": "FUTURES"},
        "decision_context": {
            "market_snapshot": {
                "price": {"current": 5000, "volatility": {"last_bar_range": 5}},
                "indicators": {"latest": {"SMA20": 4990, "RSI": 58}},
            }
        },
        "trade_intent": {
            "direction": "LONG",
            "entry": {"price": 5000},
            "stop_loss": {"price": 4990},
            "target": {"price": 5020},
            "risk_reward": 2.0,
            "thesis": "Test",
        },
        "execution": {"entry": {"price": 5000}, "exit": {"price": 5010}},
        "outcome": {"pnl": 100, "win_loss": "win", "r_multiple": 1.5},
        "scoring": {
            "decision_score": 82,
            "outcome_score": 70,
            "total_score": 78,
            "dimensions": {
                "trend_alignment": {"score": 80, "reasons_positive": ["Price aligned above SMA20"]},
                "volatility_context": {"score": 75, "reasons_positive": ["Stop distance respected recent bar volatility."]},
            },
        },
    }
    base.update(overrides)
    return base


class TestRegimeAnalysis(unittest.TestCase):
    def test_classify_trending_regime(self):
        from src.research.regime import aggregate_regime_performance, classify_trade_regimes

        record = _sample_closed_record()
        flags = classify_trade_regimes(record)
        self.assertTrue(flags["trending"])
        perf = aggregate_regime_performance([record])
        self.assertIn("trending", perf)
        self.assertEqual(perf["trending"]["trade_count"], 1)

    def test_regime_performance_metrics(self):
        from src.research.regime import aggregate_regime_performance

        perf = aggregate_regime_performance([_sample_closed_record(), _sample_closed_record(id="rec-2")])
        self.assertGreaterEqual(len(perf), 1)
        bucket = perf[list(perf.keys())[0]]
        self.assertIn("average_decision_score", bucket)
        self.assertIn("profit_factor", bucket)


class TestComparisonReport(unittest.TestCase):
    def test_build_comparison_includes_all_strategies(self):
        from src.research.comparison import build_comparison_report

        reports = [
            {
                "report_id": "r1",
                "strategy_id": "futures_trend",
                "strategy_name": "Trend Following",
                "trade_count": 10,
                "win_rate": 0.4,
                "profit_factor": 1.5,
                "average_decision_score": 82,
                "average_outcome_score": 70,
                "max_drawdown_pct": 8.0,
                "regime_performance": {"trending": {"trade_count": 8, "average_decision_score": 85}},
                "date_range": {"start": "2024-01-01", "end": "2024-06-01"},
            },
            {
                "report_id": "r2",
                "strategy_id": "futures_breakout",
                "strategy_name": "Breakout",
                "trade_count": 7,
                "win_rate": 0.35,
                "profit_factor": 1.3,
                "average_decision_score": 79,
                "average_outcome_score": 68,
                "max_drawdown_pct": 10.0,
                "regime_performance": {},
                "date_range": {"start": "2024-01-01", "end": "2024-06-01"},
            },
        ]
        comparison = build_comparison_report(
            instrument_id="ESZ26",
            asset_class="FUTURES",
            timeframe="1d",
            period="6mo",
            strategy_reports=reports,
            continuous_id="ES",
        )
        self.assertEqual(comparison["strategy_count"], 2)
        self.assertEqual(comparison["report_type"], "comparison")
        self.assertIn("regime_analysis", comparison)
        self.assertIn("characteristics", comparison)
        self.assertTrue(comparison["characteristics"])
        self.assertNotIn("winner", str(comparison).lower())

    def test_characteristics_are_neutral(self):
        from src.research.comparison import build_comparison_report

        comparison = build_comparison_report(
            instrument_id="ESZ26",
            asset_class="FUTURES",
            timeframe="1d",
            period="6mo",
            strategy_reports=[
                {
                    "report_id": "a",
                    "strategy_id": "futures_trend",
                    "strategy_name": "Trend Following",
                    "trade_count": 5,
                    "profit_factor": 1.2,
                    "win_rate": 0.4,
                    "average_decision_score": 80,
                    "average_outcome_score": 65,
                    "date_range": {},
                }
            ],
        )
        text = " ".join(comparison["characteristics"]).lower()
        self.assertIn("tested conditions", text)
        self.assertNotIn("winner", text)


class TestStrategyValidationBatch(unittest.TestCase):
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_es_batch_runs_all_futures_strategies(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(80)
        from src.research.runner import StrategyBacktestRunner
        from src.research.store import ResearchReportStore
        from src.research.validation import StrategyValidationService

        temp = tempfile.TemporaryDirectory()
        store = ResearchReportStore(path=Path(temp.name) / "reports.jsonl")
        service = StrategyValidationService(
            runner=StrategyBacktestRunner(report_store=store),
            report_store=store,
        )
        comparison = service.run_batch("ESZ26", period="6mo", max_trades=3)
        self.assertEqual(comparison["instrument_id"], "ESZ26")
        self.assertEqual(comparison["continuous_id"], "ES")
        self.assertGreaterEqual(comparison["strategy_count"], 3)
        self.assertIn("futures_trend", comparison["regime_analysis"])
        temp.cleanup()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_eurusd_batch_validation(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_forex(80)
        from src.research.runner import StrategyBacktestRunner
        from src.research.store import ResearchReportStore
        from src.research.validation import StrategyValidationService

        temp = tempfile.TemporaryDirectory()
        store = ResearchReportStore(path=Path(temp.name) / "reports.jsonl")
        service = StrategyValidationService(
            runner=StrategyBacktestRunner(report_store=store),
            report_store=store,
        )
        comparison = service.run_batch("EURUSD", period="6mo", max_trades=3)
        self.assertEqual(comparison["asset_class"], "FOREX")
        self.assertGreaterEqual(comparison["strategy_count"], 3)
        temp.cleanup()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_strategies_use_same_pipeline_fields(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(80)
        from src.research.runner import StrategyBacktestRunner
        from src.research.store import ResearchReportStore
        from src.research.validation import StrategyValidationService

        temp = tempfile.TemporaryDirectory()
        store = ResearchReportStore(path=Path(temp.name) / "reports.jsonl")
        service = StrategyValidationService(
            runner=StrategyBacktestRunner(report_store=store),
            report_store=store,
        )
        comparison = service.run_batch(
            "ESZ26",
            max_trades=2,
            strategy_ids=["futures_trend", "futures_momentum"],
        )
        for item in comparison["strategies"]:
            self.assertIn("average_decision_score", item)
            self.assertIn("profit_factor", item)
            self.assertIn("trade_count", item)
        temp.cleanup()


class TestStrategyValidationAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.replay.replay_memory import reset_replay_memory
        from src.research.store import reset_research_report_store
        from src.trading.trade_plan import get_trade_plan_manager

        reset_replay_memory()
        reset_research_report_store()
        get_trade_plan_manager().reset()
        self.app = create_app()
        self.client = self.app.test_client()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_validate_endpoint(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(80)
        resp = self.client.post(
            "/api/research/validate",
            json={"instrument_id": "ESZ26", "max_trades": 2},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("comparison", data)
        self.assertGreaterEqual(data["comparison"]["strategy_count"], 3)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_compare_fetch_endpoint(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(80)
        run = self.client.post(
            "/api/research/validate",
            json={"instrument_id": "ESZ26", "max_trades": 2},
        )
        cid = run.get_json()["comparison"]["comparison_id"]
        fetch = self.client.get(f"/api/research/compare/{cid}")
        self.assertEqual(fetch.status_code, 200)
        self.assertEqual(fetch.get_json()["comparison"]["comparison_id"], cid)


if __name__ == "__main__":
    unittest.main()
