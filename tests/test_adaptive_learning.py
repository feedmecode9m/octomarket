"""Tests for Phase 9 adaptive learning — profile, mistakes, mentor, scenarios."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.learning.trader_profile import TraderProfile
from src.learning.mistake_detector import MistakeDetector
from src.learning.recommendations import AdaptiveRecommendations
from src.learning.progress import ProgressTracker
from src.simulation.scenarios import ScenarioTrainer, get_scenario_trainer
from src.ai_agent.mentor import TradingMentor


class TestTraderProfile(unittest.TestCase):
    def setUp(self):
        self.profile = TraderProfile()

    def test_default_profile(self):
        p = self.profile.get()
        self.assertEqual(p["level"], "beginner")
        self.assertIn("strengths", p)

    def test_update_profile(self):
        result = self.profile.update({"level": "intermediate", "risk_tolerance": "low"})
        self.assertEqual(result["level"], "intermediate")
        self.assertEqual(result["risk_tolerance"], "low")

    def test_record_lesson(self):
        self.profile.record_lesson_completed(5)
        self.assertIn(5, self.profile.get()["completed_lessons"])

    def test_record_skill_score(self):
        self.profile.record_skill_score(85, "Advanced")
        prog = self.profile.get()["skill_progression"]
        self.assertEqual(prog[-1]["score"], 85)
        self.assertEqual(self.profile.get()["level"], "advanced")

    def test_infer_strengths_weaknesses(self):
        self.profile.infer_strengths_weaknesses(
            {"risk_management": 70, "consistency": 30, "strategy_quality": 50, "emotional_discipline": 40},
            [{"mistake": "Overtrading", "mistake_key": "overtrading", "severity": 60}],
        )
        p = self.profile.get()
        self.assertTrue(len(p["strengths"]) > 0)
        self.assertTrue(len(p["weaknesses"]) > 0)


class TestMistakeDetector(unittest.TestCase):
    def setUp(self):
        self.detector = MistakeDetector()

    def test_empty_trades(self):
        self.assertEqual(self.detector.analyze([]), [])

    def test_overtrading(self):
        trades = [{"type": "buy", "price": 100, "quantity": 5}] * 20
        result = self.detector.analyze(trades)
        keys = [m["mistake_key"] for m in result]
        self.assertIn("overtrading", keys)

    def test_oversized_positions(self):
        trades = [{"type": "buy", "price": 100, "quantity": 100}]
        result = self.detector.analyze(trades, initial_cash=10000)
        keys = [m["mistake_key"] for m in result]
        self.assertIn("oversized_positions", keys)

    def test_revenge_trading(self):
        trades = [
            {"type": "buy", "price": 100, "quantity": 5},
            {"type": "buy", "price": 100, "quantity": 20},
            {"type": "buy", "price": 100, "quantity": 50},
        ]
        result = self.detector.analyze(trades)
        keys = [m["mistake_key"] for m in result]
        self.assertIn("revenge_trading", keys)

    def test_mistake_has_recommendation(self):
        trades = [{"type": "buy", "price": 100, "quantity": 100}]
        result = self.detector.analyze(trades, initial_cash=10000)
        self.assertTrue(all("recommendation" in m for m in result))


class TestRecommendations(unittest.TestCase):
    def setUp(self):
        self.recs = AdaptiveRecommendations()

    def test_recommend_from_oversized(self):
        mistakes = [{"mistake_key": "oversized_positions", "mistake": "Oversized Positions", "severity": 80}]
        result = self.recs.recommend(mistakes)
        lesson_ids = [l["lesson_id"] for l in result["lessons"]]
        self.assertIn(5, lesson_ids)

    def test_recommend_from_chasing(self):
        mistakes = [{"mistake_key": "chasing_momentum", "mistake": "Chasing Momentum", "severity": 70}]
        result = self.recs.recommend(mistakes)
        lesson_ids = [l["lesson_id"] for l in result["lessons"]]
        self.assertIn(3, lesson_ids)

    def test_default_when_no_mistakes(self):
        result = self.recs.recommend([])
        self.assertGreater(len(result["lessons"]), 0)
        self.assertGreater(len(result["challenges"]), 0)


class TestScenarios(unittest.TestCase):
    def setUp(self):
        self.trainer = ScenarioTrainer()

    def test_list_scenarios(self):
        scenarios = self.trainer.list_scenarios()
        self.assertEqual(len(scenarios), 3)

    def test_get_scenario(self):
        s = self.trainer.get_scenario(1)
        self.assertIsNotNone(s)
        self.assertEqual(len(s["options"]), 4)

    def test_score_optimal_answer(self):
        s = self.trainer.get_scenario(1)
        result = self.trainer.score_answer(1, "reduce")
        self.assertTrue(result["was_optimal"])
        self.assertGreaterEqual(result["overall_score"], 85)

    def test_score_poor_answer(self):
        result = self.trainer.score_answer(1, "buy_more")
        self.assertFalse(result["was_optimal"])
        self.assertLess(result["overall_score"], 50)

    def test_invalid_scenario(self):
        result = self.trainer.score_answer(999, "hold")
        self.assertIn("error", result)


class TestProgress(unittest.TestCase):
    def setUp(self):
        self.tracker = ProgressTracker()

    def test_record_and_get(self):
        self.tracker.record_activity("lesson_completed", {"lesson_id": 1})
        p = self.tracker.get_progress()
        self.assertEqual(p["daily"]["lessons_completed"], 1)

    def test_skill_change(self):
        self.tracker.record_skill_change(50, "Beginner", {"risk_management": 50})
        self.tracker.record_skill_change(60, "Intermediate", {"risk_management": 60})
        p = self.tracker.get_progress()
        self.assertIsNotNone(p["skill_changes"]["current"])


class TestMentor(unittest.TestCase):
    def setUp(self):
        self.mentor = TradingMentor()

    def test_get_advice_shape(self):
        result = self.mentor.get_advice(
            trades=[{"type": "buy", "price": 100, "quantity": 50}],
            profile={"level": "beginner"},
            skill_score={"score": 45, "level": "Beginner", "components": {}},
            performance={"pnl": -500, "drawdown": 8},
            initial_cash=10000,
        )
        self.assertIn("summary", result)
        self.assertIn("strengths", result)
        self.assertIn("weaknesses", result)
        self.assertIn("next_lessons", result)
        self.assertIn("recommended_challenge", result)

    def test_ask_why_lost(self):
        result = self.mentor.ask(
            "Why did I lose money?",
            trades=[{"type": "buy", "price": 100, "quantity": 50}],
            profile={"level": "beginner"},
            skill_score={"score": 40, "level": "Beginner", "components": {}},
            performance={"pnl": -200, "drawdown": 5},
            initial_cash=10000,
        )
        self.assertIn("answer", result)
        self.assertIn("reasons", result)

    def test_ask_what_next(self):
        result = self.mentor.ask(
            "What should I practice next?",
            trades=[],
            profile={"level": "beginner"},
            skill_score={"score": 50, "level": "Beginner", "components": {}},
        )
        self.assertIn("next_lessons", result)

    def test_ask_bad_trade(self):
        result = self.mentor.ask(
            "Why was this trade bad?",
            trades=[{"type": "buy", "price": 150, "quantity": 10}],
            profile={},
            skill_score={"score": 50, "level": "Beginner", "components": {}},
        )
        self.assertIn("answer", result)


class TestMentorAPI(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()
        self.client.post("/api/profile", json={"level": "beginner", "risk_tolerance": "moderate"})

    def test_get_profile(self):
        resp = self.client.get("/api/profile")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("level", resp.get_json())

    def test_update_profile(self):
        resp = self.client.post("/api/profile", json={"level": "intermediate"})
        self.assertEqual(resp.get_json()["level"], "intermediate")

    def test_mistakes_endpoint(self):
        resp = self.client.get("/api/mistakes")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("mistakes", resp.get_json())

    def test_recommendations(self):
        resp = self.client.get("/api/recommendations")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("lessons", resp.get_json())

    def test_mentor_advice(self):
        resp = self.client.get("/api/mentor/advice")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("summary", data)
        self.assertIn("next_lessons", data)

    def test_mentor_ask(self):
        resp = self.client.post("/api/mentor/ask", json={"question": "What should I practice next?"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("answer", resp.get_json())

    def test_scenarios_list(self):
        resp = self.client.get("/api/scenarios")
        self.assertEqual(len(resp.get_json()["scenarios"]), 3)

    def test_scenario_answer(self):
        resp = self.client.post("/api/scenarios/1/answer", json={"action": "reduce"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["was_optimal"])

    def test_progress(self):
        resp = self.client.get("/api/progress")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("daily", resp.get_json())

    def test_mentor_page(self):
        resp = self.client.get("/mentor")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OctoMarket Mentor", resp.data)


if __name__ == "__main__":
    unittest.main()
