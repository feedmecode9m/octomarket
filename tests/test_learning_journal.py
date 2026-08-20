"""Tests for Gate 17A — Automated Learning Journal."""

import os
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _ohlcv(n=20, base=180.0, step=1.0):
    closes = [base + step * i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 0.5 for c in closes],
            "High": [c + 2 for c in closes],
            "Low": [c - 2 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * n,
        },
        index=pd.date_range("2024-06-01", periods=n, freq="1D"),
    )


def _closed_record(**overrides):
    base = {
        "id": "rec-journal-1",
        "status": "closed",
        "mode": "live_paper",
        "plan_id": "plan-1",
        "market": {
            "instrument_id": "AAPL",
            "asset_class": "STOCK",
            "symbol": "AAPL",
        },
        "decision_context": {
            "market_snapshot": {
                "price": {"current": 185, "volatility": {"last_bar_range": 2}},
                "indicators": {"latest": {"SMA20": 180, "RSI": 55}},
            }
        },
        "trade_intent": {
            "direction": "LONG",
            "strategy_id": "manual",
            "strategy_name": "Manual",
            "thesis": "Breakout",
            "entry": {"price": 185},
            "stop_loss": {"price": 180},
            "target": {"price": 195},
            "risk_reward": 2.0,
        },
        "execution": {
            "entry": {"price": 185, "quantity": 10},
            "exit": {"price": 182, "reason": "stop_loss"},
        },
        "outcome": {"pnl": -30, "r_multiple": -0.6, "win_loss": "loss", "exit_reason": "stop_loss"},
        "scoring": {
            "decision_score": 82,
            "outcome_score": 40,
            "decision_grade": "B",
            "decision_quality_note": "High-quality decision process; loss may reflect normal variance.",
            "dimensions": {
                "trend_alignment": {"score": 80, "reasons_positive": ["Price aligned above SMA20"]},
                "volatility_context": {"score": 70, "reasons_positive": ["Stop distance respected recent bar volatility."]},
            },
        },
        "metadata": {"finalized_at": "2026-08-20T12:00:00"},
    }
    base.update(overrides)
    return base


class TestLearningJournalEntryBuilder(unittest.TestCase):
    def test_build_entry_references_record_not_copy(self):
        from src.learning.journal_service import LearningJournalService
        from src.learning.journal_store import LearningJournalStore

        temp = tempfile.TemporaryDirectory()
        service = LearningJournalService(
            store=LearningJournalStore(path=Path(temp.name) / "j.jsonl"),
        )
        entry = service.build_entry(_closed_record())
        self.assertEqual(entry["entry_type"], "learning_journal")
        self.assertEqual(entry["record_id"], "rec-journal-1")
        self.assertIn("lesson", entry)
        self.assertTrue(entry["repeat"])
        self.assertTrue(entry["avoid"])
        self.assertIn("decision_summary", entry)
        self.assertIn("outcome_summary", entry)
        self.assertIn("market_regime", entry)
        # Snapshot only — not a full ReplayRecord clone
        self.assertNotIn("trade_intent", entry)
        self.assertNotIn("execution", entry)
        temp.cleanup()


class TestJournalAutoGenerateOnClose(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.learning.journal_service import reset_learning_journal_service
        from src.replay.replay_memory import reset_replay_memory
        from src.replay.replay_session import get_replay_session
        from src.simulation.session import get_market_session
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        reset_learning_journal_service()
        reset_replay_memory()
        get_trade_plan_manager().reset()
        get_order_engine().clear()
        get_replay_session().reset()
        get_market_session().close()
        self.app = create_app()
        self.client = self.app.test_client()

    @mock.patch("src.api.execution_routes._current_prices")
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_close_creates_journal_entry(self, MockFetcher, mock_prices):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(12)
        mock_prices.return_value = {"AAPL": 185.0}

        from src.replay.replay_session import get_replay_session

        get_replay_session().set_mode("live_paper")
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
                "thesis": "Journal auto-generate",
            },
        ).get_json()["plan"]
        self.client.post(f"/api/trade-plan/{plan['id']}/approve")
        self.client.post(f"/api/trade-plan/{plan['id']}/create-order")

        from src.api.execution_routes import process_session_fills

        process_session_fills(
            {"AAPL": {"open": 185, "high": 186, "low": 184, "close": 185, "volume": 0}}
        )
        close = self.client.post("/api/orders/close-position", json={"symbol": "AAPL"})
        self.assertIn(close.status_code, (200, 201), close.get_json())

        journal = self.client.get(f"/api/learning/journal/plan/{plan['id']}")
        self.assertEqual(journal.status_code, 200, journal.get_json())
        entry = journal.get_json()["entry"]
        self.assertEqual(entry["entry_type"], "learning_journal")
        self.assertTrue(entry["lesson"])
        self.assertIn("confidence", entry)

        # Replay record endpoint surfaces journal for review UI
        review = self.client.get(f"/api/replay/records/{plan['id']}").get_json()
        self.assertIsNotNone(review.get("journal_entry"))
        self.assertEqual(review["journal_entry"]["record_id"], review["record"]["id"])


class TestResearchDoesNotPolluteJournal(unittest.TestCase):
    @mock.patch("src.market.yahoo_provider.DataFetcher")
    def test_research_run_skips_live_journal(self, MockFetcher):
        MockFetcher.return_value.get_real_time_data.return_value = _ohlcv(80, base=5000, step=2)
        from src.learning.journal_service import get_learning_journal_service, reset_learning_journal_service
        from src.research.runner import StrategyBacktestRunner
        from src.research.store import ResearchReportStore

        reset_learning_journal_service()
        before = len(get_learning_journal_service().list_entries())
        temp = tempfile.TemporaryDirectory()
        StrategyBacktestRunner(
            report_store=ResearchReportStore(path=Path(temp.name) / "r.jsonl")
        ).run("futures_trend", "ESZ26", max_trades=3, persist_report=False)
        after = len(get_learning_journal_service().list_entries())
        self.assertEqual(before, after)
        temp.cleanup()


class TestRecurringPatterns(unittest.TestCase):
    def test_scan_finds_regime_strategy_buckets(self):
        from src.learning.journal_patterns import scan_recurring_patterns

        records = []
        for i in range(8):
            records.append(
                _closed_record(
                    id=f"r{i}",
                    trade_intent={
                        "direction": "LONG",
                        "strategy_id": "futures_trend",
                        "strategy_name": "Trend Following",
                        "entry": {"price": 5000},
                        "stop_loss": {"price": 4990},
                        "target": {"price": 5020},
                        "risk_reward": 2.0,
                    },
                    market={"instrument_id": "ESZ26", "asset_class": "FUTURES", "symbol": "ES"},
                    outcome={
                        "pnl": 50 if i % 2 == 0 else -40,
                        "r_multiple": 1.0 if i % 2 == 0 else -0.8,
                        "win_loss": "win" if i % 2 == 0 else "loss",
                    },
                )
            )
        findings = scan_recurring_patterns(records, min_trades=5)
        self.assertTrue(findings)
        self.assertEqual(findings[0]["strategy_id"], "futures_trend")
        self.assertIn("finding", findings[0])
        self.assertIn("recommendation", findings[0])


class TestJournalAPIAndUI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.learning.journal_service import reset_learning_journal_service

        reset_learning_journal_service()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_list_and_patterns_endpoints(self):
        from src.learning.journal_service import get_learning_journal_service

        service = get_learning_journal_service()
        entry = service.build_entry(_closed_record())
        service._store.save(entry)
        listed = self.client.get("/api/learning/journal")
        self.assertEqual(listed.status_code, 200)
        self.assertGreaterEqual(listed.get_json()["count"], 1)
        patterns = self.client.get("/api/learning/journal/patterns?min_trades=2")
        self.assertEqual(patterns.status_code, 200)
        self.assertIn("patterns", patterns.get_json())

    def test_terminal_loads_journal_block(self):
        html = self.client.get("/terminal").get_data(as_text=True)
        self.assertIn("loadLearningJournal", html)
        self.assertIn("/api/learning/journal/plan/", html)


if __name__ == "__main__":
    unittest.main()
