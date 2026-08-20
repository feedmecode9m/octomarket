"""Tests for Gate 16C — Research Reliability Layer."""

import os
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _ohlcv(n=120, base=5000.0, step=1.5):
    closes = [base + step * i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 1 for c in closes],
            "High": [c + 4 for c in closes],
            "Low": [c - 3 for c in closes],
            "Close": closes,
            "Volume": [50000] * n,
        },
        index=pd.date_range("2020-01-01", periods=n, freq="1D"),
    )


class TestTransactionCostModel(unittest.TestCase):
    def test_forex_preset_includes_spread(self):
        from src.research.costs import TransactionCostModel

        model = TransactionCostModel.for_asset_class("FOREX")
        self.assertGreater(model.spread_bps, 0)
        self.assertGreater(model.effective_slippage_rate(), model.slippage_rate)

    def test_gross_metrics_restore_costs(self):
        from src.research.costs import gross_profit_metrics

        records = [
            {"outcome": {"pnl": 50}},
            {"outcome": {"pnl": -30}},
            {"outcome": {"pnl": 20}},
        ]
        gross = gross_profit_metrics(records, total_costs=30)
        self.assertIsNotNone(gross["profit_factor_gross"])
        self.assertGreater(gross["profit_factor_gross"], 1.0)


class TestConfidenceMetadata(unittest.TestCase):
    def test_low_sample_warning(self):
        from src.research.confidence import assess_sample_confidence

        meta = assess_sample_confidence(8)
        self.assertEqual(meta["confidence_level"], "low")
        self.assertTrue(meta["warnings"])

    def test_adequate_sample(self):
        from src.research.confidence import assess_sample_confidence

        meta = assess_sample_confidence(45)
        self.assertEqual(meta["confidence_level"], "high")
        self.assertTrue(meta["sample_adequate"])


class TestBenchmarkComparison(unittest.TestCase):
    def test_buy_and_hold_vs_strategy(self):
        from src.research.benchmark import compute_benchmark_comparison

        df = _ohlcv(40)
        equity = [{"equity": 10000}, {"equity": 10500}, {"equity": 11000}]
        result = compute_benchmark_comparison(
            ohlcv=df,
            equity_curve=equity,
            initial_cash=10000,
            asset_class="FUTURES",
        )
        self.assertIsNotNone(result["buy_and_hold_return_pct"])
        self.assertIsNotNone(result["strategy_return_pct"])
        self.assertIn("alpha", result)
        self.assertIn("interpretation", result)


class TestDateWindows(unittest.TestCase):
    def test_split_walk_forward_windows(self):
        from src.research.dates import split_date_range

        index = pd.date_range("2018-01-01", periods=100, freq="1D")
        windows = split_date_range(index)
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0]["name"], "research")
        self.assertEqual(windows[2]["name"], "out_of_sample")

    def test_apply_session_date_window(self):
        from src.research.dates import apply_session_date_window
        from src.simulation.session import MarketSession

        session = MarketSession()
        session._data["ES"] = _ohlcv(60)
        session._symbols = ["ES"]
        session._max_length = 60

        result = apply_session_date_window(
            session,
            start_date="2020-01-15",
            end_date="2020-02-15",
        )
        self.assertIsNotNone(result["start"])
        self.assertLess(len(session._data["ES"]), 60)

    def test_overlapping_walk_forward_windows_rejected(self):
        from src.research.dates import validate_non_overlapping_windows

        with self.assertRaises(ValueError):
            validate_non_overlapping_windows(
                [
                    {"name": "research", "start": "2020-01-01", "end": "2022-12-31"},
                    {"name": "validation", "start": "2022-06-01", "end": "2023-12-31"},
                    {"name": "out_of_sample", "start": "2024-01-01", "end": "2025-12-31"},
                ]
            )


class TestStrategyReportReliability(unittest.TestCase):
    def test_report_schema_v3_fields(self):
        from src.research.report import build_strategy_report

        report = build_strategy_report(
            strategy_id="futures_trend",
            strategy_name="Trend Following",
            instrument_id="ESZ26",
            asset_class="FUTURES",
            continuous_id="ES",
            timeframe="1d",
            period="6mo",
            date_range={"start": "2024-01-01", "end": "2024-06-01"},
            records=[],
            equity_curve=[{"equity": 10000}, {"equity": 10100}],
            benchmark_comparison={"alpha": 1.2, "beat_benchmark": True},
            transaction_costs={"total_costs": 12.5, "cost_model": {"label": "futures_retail"}},
            initial_cash=10000,
        )
        self.assertEqual(report["schema_version"], 3)
        self.assertIn("benchmark_comparison", report)
        self.assertIn("confidence", report)
        self.assertIn("transaction_costs", report)
        self.assertIn("gross_metrics", report)
        self.assertEqual(report["confidence"]["confidence_level"], "none")


class TestWalkForwardService(unittest.TestCase):
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_walk_forward_produces_three_windows(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(120)
        from src.research.store import ResearchReportStore
        from src.research.walkforward import WalkForwardService

        temp = tempfile.TemporaryDirectory()
        service = WalkForwardService(
            report_store=ResearchReportStore(path=Path(temp.name) / "wf.jsonl"),
        )
        report = service.run(
            "futures_trend",
            "ESZ26",
            period="2y",
            max_trades=2,
        )
        self.assertEqual(report["report_type"], "walk_forward")
        self.assertEqual(len(report["windows"]), 3)
        self.assertIn("stability", report)
        self.assertIn("characteristics", report)
        self.assertNotIn("winner", str(report).lower())
        temp.cleanup()


if __name__ == "__main__":
    unittest.main()
