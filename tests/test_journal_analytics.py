"""Tests for Gate 17B — Journal Analytics & Memory Layer."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _entry(
    *,
    entry_id="e1",
    record_id="r1",
    date="2026-01-15",
    instrument_id="ESZ26",
    strategy_id="futures_trend",
    regime="trending",
    trend_state="aligned",
    win_loss="win",
    r_multiple=1.4,
    decision_score=86,
    outcome_score=70,
):
    return {
        "id": entry_id,
        "record_id": record_id,
        "entry_type": "learning_journal",
        "date": date,
        "instrument_id": instrument_id,
        "continuous_id": "ES",
        "strategy_id": strategy_id,
        "mode": "live_paper",
        "market_regime": {
            "trend_state": trend_state,
            "volatility_state": "normal",
            "active_regimes": [regime],
        },
        "scoring_snapshot": {
            "decision_score": decision_score,
            "outcome_score": outcome_score,
        },
        "outcome_snapshot": {
            "pnl": 50 if win_loss == "win" else -40,
            "r_multiple": r_multiple,
            "win_loss": win_loss,
        },
        "lesson": "test",
        "repeat": [],
        "avoid": [],
        "confidence": "moderate",
    }


class TestTraderProfile(unittest.TestCase):
    def test_profile_strengths_and_weaknesses_from_evidence(self):
        from src.learning.journal_profile import JournalTraderProfileService

        entries = []
        for i in range(8):
            entries.append(
                _entry(
                    entry_id=f"s{i}",
                    record_id=f"rs{i}",
                    strategy_id="futures_trend",
                    win_loss="win" if i % 2 == 0 else "loss",
                    r_multiple=1.5 if i % 2 == 0 else 0.8,
                    decision_score=85,
                    date=f"2026-01-{10 + i:02d}",
                )
            )
        for i in range(8):
            entries.append(
                _entry(
                    entry_id=f"w{i}",
                    record_id=f"rw{i}",
                    strategy_id="fx_mean_reversion",
                    regime="ranging",
                    trend_state="counter",
                    win_loss="loss" if i % 2 == 0 else "win",
                    r_multiple=-0.9 if i % 2 == 0 else -0.2,
                    decision_score=60,
                    date=f"2026-02-{10 + i:02d}",
                )
            )

        profile = JournalTraderProfileService().build_profile(entries, min_trades=5)
        self.assertEqual(profile["profile_type"], "historical_performance_pattern")
        self.assertTrue(profile["strengths"] or profile["weaknesses"] or profile["observed_areas"])
        self.assertIn("disclaimer", profile)
        # No identity insults
        blob = str(profile).lower()
        self.assertNotIn("bad trader", blob)


class TestJournalSearch(unittest.TestCase):
    def test_filters_by_instrument_result_and_score(self):
        from src.learning.journal_query import JournalQueryService

        entries = [
            _entry(entry_id="a", instrument_id="ESZ26", win_loss="loss", decision_score=65, r_multiple=-0.5),
            _entry(entry_id="b", instrument_id="ESZ26", win_loss="win", decision_score=90, r_multiple=1.2),
            _entry(entry_id="c", instrument_id="EURUSD", win_loss="loss", decision_score=50, r_multiple=-1.0),
        ]
        result = JournalQueryService().search(
            entries,
            instrument_id="ESZ26",
            result="loss",
            decision_score_max=70,
        )
        self.assertEqual(result["total_matched"], 1)
        self.assertEqual(result["entries"][0]["id"], "a")
        self.assertEqual(result["common_factors"]["sample_size"], 1)


class TestImprovementTracking(unittest.TestCase):
    def test_detects_improvement_across_periods(self):
        from src.learning.improvement_tracker import ImprovementTracker

        entries = []
        for i in range(6):
            entries.append(
                _entry(
                    entry_id=f"b{i}",
                    record_id=f"rb{i}",
                    date=f"2026-01-{10 + i:02d}",
                    win_loss="loss",
                    r_multiple=-0.8,
                    regime="trending",
                )
            )
        for i in range(6):
            entries.append(
                _entry(
                    entry_id=f"a{i}",
                    record_id=f"ra{i}",
                    date=f"2026-04-{10 + i:02d}",
                    win_loss="win" if i % 2 == 0 else "loss",
                    r_multiple=1.0 if i % 2 == 0 else 0.5,
                    regime="trending",
                )
            )
        findings = ImprovementTracker().track(entries, min_trades_per_period=5)
        self.assertTrue(findings)
        self.assertEqual(findings[0]["status"], "improvement_detected")
        self.assertTrue(findings[0]["evidence_only"])


class TestRecommendationContextReadOnly(unittest.TestCase):
    def test_context_is_read_only_and_does_not_create_plans(self):
        from src.learning.journal_analytics import JournalAnalyticsService
        from src.learning.journal_service import LearningJournalService
        from src.learning.journal_store import LearningJournalStore
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        temp = tempfile.TemporaryDirectory()
        store = LearningJournalStore(path=Path(temp.name) / "j.jsonl")
        journal = LearningJournalService(store=store)
        for i in range(6):
            store.save(
                _entry(
                    entry_id=f"e{i}",
                    record_id=f"r{i}",
                    strategy_id="futures_trend",
                    date=f"2026-03-{10 + i:02d}",
                    r_multiple=1.2,
                    win_loss="win",
                )
            )
        analytics = JournalAnalyticsService(journal=journal)
        manager = get_trade_plan_manager()
        engine = get_order_engine()
        plans_before = len(manager.get_plans_for_symbol("ESZ26"))
        orders_before = len(engine.get_all())

        ctx = analytics.recommendation_context(
            instrument_id="ESZ26",
            strategy_family="trend_following",
            min_trades=5,
        )
        self.assertTrue(ctx["decision_support_only"])
        self.assertTrue(ctx["read_only"])
        self.assertTrue(ctx["does_not_create_plans"])
        self.assertTrue(ctx["does_not_create_orders"])
        self.assertTrue(ctx["does_not_alter_execution"])
        self.assertIn(ctx["trader_history"]["alignment"], ("positive", "negative", "neutral", "insufficient"))

        self.assertEqual(len(manager.get_plans_for_symbol("ESZ26")), plans_before)
        self.assertEqual(len(engine.get_all()), orders_before)
        temp.cleanup()


class TestJournalAnalyticsAPIAndUI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from src.learning.journal_service import reset_learning_journal_service

        reset_learning_journal_service()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_profile_search_improvements_endpoints(self):
        from src.learning.journal_service import get_learning_journal_service

        service = get_learning_journal_service()
        for i in range(6):
            service._store.save(
                _entry(
                    entry_id=f"api{i}",
                    record_id=f"rapi{i}",
                    date=f"2026-01-{10 + i:02d}",
                    win_loss="win" if i % 2 == 0 else "loss",
                    r_multiple=1.0 if i % 2 == 0 else -0.5,
                )
            )
        profile = self.client.get("/api/learning/journal/profile?min_trades=3")
        self.assertEqual(profile.status_code, 200)
        self.assertIn("profile", profile.get_json())

        search = self.client.get("/api/learning/journal/search?instrument_id=ESZ26&result=loss")
        self.assertEqual(search.status_code, 200)
        self.assertGreaterEqual(search.get_json()["total_matched"], 1)

        improvements = self.client.get("/api/learning/journal/improvements?min_trades=2")
        self.assertEqual(improvements.status_code, 200)
        self.assertIn("findings", improvements.get_json())

        ctx = self.client.get(
            "/api/learning/journal/recommendation-context?instrument_id=ESZ26&strategy_family=trend_following"
        )
        self.assertEqual(ctx.status_code, 200)
        body = ctx.get_json()["context"]
        self.assertTrue(body["does_not_create_orders"])

    def test_terminal_exposes_journal_memory_ui(self):
        html = self.client.get("/terminal").get_data(as_text=True)
        self.assertIn("loadJournalTraderProfile", html)
        self.assertIn("/api/learning/journal/profile", html)
        self.assertIn("/api/learning/journal/search", html)
        self.assertIn("trader_history_context", html)

    def test_recommend_attaches_trader_history_without_side_effects(self):
        from src.trading.order_engine import get_order_engine
        from src.trading.trade_plan import get_trade_plan_manager

        get_trade_plan_manager().reset()
        get_order_engine().clear()
        plans_before = len(get_trade_plan_manager().get_plans_for_symbol("ESZ26"))
        orders_before = len(get_order_engine().get_all())

        with mock.patch("src.api.research_routes._selector") as selector:
            selector.recommend.return_value = {
                "instrument_id": "ESZ26",
                "recommendation": {"strategy_family": "trend_following", "confidence": "moderate", "narrative": "x"},
                "decision_support_only": True,
            }
            resp = self.client.post(
                "/api/research/recommend",
                json={"instrument_id": "ESZ26"},
            )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()["recommendation"]
        self.assertIn("trader_history_context", payload)
        self.assertTrue(payload["trader_history_context"]["read_only"])
        self.assertEqual(len(get_trade_plan_manager().get_plans_for_symbol("ESZ26")), plans_before)
        self.assertEqual(len(get_order_engine().get_all()), orders_before)


if __name__ == "__main__":
    unittest.main()
