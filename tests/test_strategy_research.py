"""Tests for Gate 16A — Strategy Research Evaluation Layer."""

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


class TestStrategyResearchRunner(unittest.TestCase):
    def test_report_schema_fields(self):
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
            equity_curve=[{"equity": 10000}, {"equity": 9800}, {"equity": 10100}],
        )
        self.assertEqual(report["schema_version"], 3)
        self.assertIn("regime_performance", report)
        self.assertIn("benchmark_comparison", report)
        self.assertIn("confidence", report)
        self.assertIn("transaction_costs", report)
        self.assertIn("report_id", report)
        self.assertIn("average_decision_score", report)
        self.assertIn("best_conditions", report)
        self.assertIn("weak_conditions", report)

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_es_research_produces_scored_records(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(80)
        from src.research.runner import StrategyBacktestRunner
        from src.research.store import ResearchReportStore

        temp = tempfile.TemporaryDirectory()
        runner = StrategyBacktestRunner(report_store=ResearchReportStore(path=Path(temp.name) / "r.jsonl"))
        report = runner.run(
            "futures_trend",
            "ESZ26",
            period="6mo",
            max_trades=5,
            persist_report=True,
        )

        self.assertEqual(report["instrument_id"], "ESZ26")
        self.assertEqual(report["continuous_id"], "ES")
        self.assertIn("trade_count", report)
        temp.cleanup()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_eurusd_research_run(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_forex(80)
        from src.research.runner import StrategyBacktestRunner
        from src.research.store import ResearchReportStore

        temp = tempfile.TemporaryDirectory()
        runner = StrategyBacktestRunner(report_store=ResearchReportStore(path=Path(temp.name) / "r.jsonl"))
        report = runner.run(
            "forex_momentum",
            "EURUSD",
            period="6mo",
            max_trades=5,
        )
        self.assertEqual(report["asset_class"], "FOREX")
        temp.cleanup()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_two_strategies_same_pipeline(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(80)
        from src.research.runner import StrategyBacktestRunner
        from src.research.store import ResearchReportStore

        temp = tempfile.TemporaryDirectory()
        store = ResearchReportStore(path=Path(temp.name) / "r.jsonl")
        runner = StrategyBacktestRunner(report_store=store)

        r1 = runner.run("futures_trend", "ESZ26", max_trades=3)
        r2 = runner.run("futures_momentum", "ESZ26", max_trades=3)

        for report in (r1, r2):
            self.assertIn("average_decision_score", report)
            self.assertIn("profit_factor", report)
            self.assertEqual(report["schema_version"], 3)
        temp.cleanup()

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_replay_candle_cap_during_research(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(80)
        from src.replay.replay_session import get_replay_session
        from src.strategies.context import build_strategy_context

        replay = get_replay_session()
        replay.reset()
        replay.start(instrument_id="ESZ26", period="6mo")
        replay.step()
        replay.step()
        ctx = build_strategy_context("ESZ26")
        self.assertTrue(ctx.session_capped)
        self.assertLess(ctx.bar_count, 80)
        replay.reset()


class TestStrategyResearchAPI(unittest.TestCase):
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
    def test_research_strategies_endpoint(self, MockFetcher):
        resp = self.client.get("/api/research/strategies")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("FUTURES", data["catalog"])

    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_research_run_and_fetch_report(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(80)
        run = self.client.post(
            "/api/research/run",
            json={"strategy_id": "futures_trend", "instrument_id": "ESZ26", "max_trades": 3},
        )
        self.assertEqual(run.status_code, 201)
        report = run.get_json()["report"]
        fetch = self.client.get(f"/api/research/report/{report['report_id']}")
        self.assertEqual(fetch.status_code, 200)
        self.assertEqual(fetch.get_json()["report"]["strategy_id"], "futures_trend")

    @mock.patch("src.api.execution_routes._current_prices")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_aapl_manual_regression_unchanged(self, MockFetcher, mock_prices):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(8, base=180, step=1)
        mock_prices.return_value = {"AAPL": 185.0}
        plan = self.client.post(
            "/api/trade-plan",
            json={
                "symbol": "AAPL",
                "instrument_id": "AAPL",
                "asset_class": "STOCK",
                "direction": "LONG",
                "entry": {"price": 185},
                "stop_loss": {"price": 180},
                "target": {"price": 195},
                "quantity": 10,
                "thesis": "Manual unchanged",
            },
        ).get_json()["plan"]
        self.assertIsNone(plan.get("strategy_id"))


class TestResearchIntegrity(unittest.TestCase):
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_research_does_not_contaminate_live_state(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _trending_ohlcv(80)
        from src.ai_agent.trade_journal import get_trade_journal
        from src.charting.chart_state import get_chart_state
        from src.replay.replay_session import get_replay_session
        from src.research.runner import StrategyBacktestRunner
        from src.research.store import ResearchReportStore
        from src.simulation.session import get_market_session

        live = get_market_session()
        live.start(["AAPL"], period="1mo")
        live.step()
        live_index = live.get_session_index()
        live_max = live._max_length
        get_chart_state().update(instrument_id="AAPL", timeframe="1d", period="1mo")
        journal = get_trade_journal()
        journal.record("AAPL", "buy", 180, 1, "live note")
        journal_count = len(journal.get_all())
        get_replay_session().set_mode("live_paper")

        temp = tempfile.TemporaryDirectory()
        StrategyBacktestRunner(report_store=ResearchReportStore(path=Path(temp.name) / "r.jsonl")).run(
            "futures_trend",
            "ESZ26",
            max_trades=2,
            persist_report=False,
        )

        self.assertEqual(get_market_session().get_session_index(), live_index)
        self.assertEqual(get_market_session()._max_length, live_max)
        self.assertEqual(get_chart_state().get_state()["instrument_id"], "AAPL")
        self.assertEqual(len(get_trade_journal().get_all()), journal_count)
        self.assertFalse(get_replay_session().is_replay_mode())
        temp.cleanup()

    def test_recommendation_cannot_create_trades(self):
        from src.research.selection import AdaptiveStrategySelector
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        plans_before = len(get_trade_plan_manager()._plans)
        orders_before = len(get_order_engine().get_all())
        AdaptiveStrategySelector().recommend(
            "ESZ26",
            market_context={
                "asset_class": "FUTURES",
                "active_regimes": ["trending"],
                "trend_state": "trending",
                "volatility_state": "high",
                "data_quality": {"warnings": []},
            },
            strategy_reports=[],
            walk_forward_reports=[],
        )
        self.assertEqual(len(get_trade_plan_manager()._plans), plans_before)
        self.assertEqual(len(get_order_engine().get_all()), orders_before)


if __name__ == "__main__":
    unittest.main()
