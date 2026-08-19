"""Personalized AI Trading Mentor — models trader behavior, not just markets."""

from typing import Any, Dict, List, Optional

from ..learning.recommendations import AdaptiveRecommendations
from ..learning.mistake_detector import MistakeDetector


class TradingMentor:
    """Personalized trading instructor based on trader history and profile."""

    def __init__(
        self,
        mistake_detector: Optional[MistakeDetector] = None,
        recommendations: Optional[AdaptiveRecommendations] = None,
    ):
        self.mistake_detector = mistake_detector or MistakeDetector()
        self.recommendations = recommendations or AdaptiveRecommendations()

    def get_advice(
        self,
        trades: List[Dict[str, Any]],
        profile: Dict[str, Any],
        skill_score: Dict[str, Any],
        performance: Optional[Dict[str, Any]] = None,
        portfolio_values: Optional[List[float]] = None,
        initial_cash: float = 10000.0,
    ) -> Dict[str, Any]:
        """Generate comprehensive personalized mentor guidance."""
        performance = performance or {}
        mistakes = self.mistake_detector.analyze(
            trades, portfolio_values, initial_cash, performance
        )
        recs = self.recommendations.recommend(mistakes, profile)

        summary = self._build_summary(profile, skill_score, mistakes, performance)
        strengths = self._identify_strengths(profile, skill_score, mistakes)
        weaknesses = self._identify_weaknesses(profile, mistakes, performance)

        return {
            "summary": summary,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "detected_mistakes": mistakes,
            "next_lessons": recs["lessons"],
            "recommended_challenge": recs["challenges"][0] if recs["challenges"] else None,
            "recommended_challenges": recs["challenges"],
            "focus_area": recs["focus_area"],
            "skill_score": skill_score.get("score", 0),
            "skill_level": skill_score.get("level", "Novice"),
        }

    def ask(
        self,
        question: str,
        trades: List[Dict[str, Any]],
        profile: Dict[str, Any],
        skill_score: Dict[str, Any],
        performance: Optional[Dict[str, Any]] = None,
        portfolio_values: Optional[List[float]] = None,
        initial_cash: float = 10000.0,
        strategies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Answer specific mentor questions."""
        question_lower = question.lower().strip()
        performance = performance or {}
        mistakes = self.mistake_detector.analyze(
            trades, portfolio_values, initial_cash, performance
        )
        advice = self.get_advice(
            trades, profile, skill_score, performance, portfolio_values, initial_cash
        )

        if "lose" in question_lower or "lost" in question_lower or "losing" in question_lower:
            return self._answer_why_lost(trades, performance, mistakes, advice)
        if "bad trade" in question_lower or "wrong" in question_lower:
            return self._answer_bad_trade(trades, mistakes, advice)
        if "practice" in question_lower or "next" in question_lower or "should i" in question_lower:
            return self._answer_what_next(advice, profile)

        return {
            "question": question,
            "answer": advice["summary"],
            "details": advice,
        }

    def _answer_why_lost(
        self,
        trades: List[Dict[str, Any]],
        performance: Dict[str, Any],
        mistakes: List[Dict[str, Any]],
        advice: Dict[str, Any],
    ) -> Dict[str, Any]:
        pnl = performance.get("pnl", 0)
        reasons = []

        if pnl >= 0:
            reasons.append("Actually, your overall P&L is positive. Review individual losing trades instead.")
        else:
            reasons.append(f"Your portfolio is down ${abs(pnl):.2f}.")

        if mistakes:
            top = mistakes[0]
            reasons.append(f"Primary issue: {top['mistake']} — {top['description']}")
            reasons.append(f"Recommendation: {top['recommendation']}")
        else:
            reasons.append("No major behavioral patterns detected — review individual trade entries and exits.")

        dd = performance.get("drawdown", 0)
        if dd > 5:
            reasons.append(f"Drawdown of {dd:.1f}% suggests position sizes may be too large.")

        return {
            "question": "Why did I lose money?",
            "answer": " ".join(reasons),
            "reasons": reasons,
            "mistakes": mistakes,
            "next_lessons": advice["next_lessons"],
            "recommended_challenge": advice["recommended_challenge"],
        }

    def _answer_bad_trade(
        self,
        trades: List[Dict[str, Any]],
        mistakes: List[Dict[str, Any]],
        advice: Dict[str, Any],
    ) -> Dict[str, Any]:
        reasons = []
        if not trades:
            reasons.append("No trades to review yet. Start paper trading to build history.")
        else:
            last = trades[-1]
            action = last.get("type", last.get("action", ""))
            reasons.append(f"Your last trade was a {action} at ${float(last.get('price', last.get('fill_price', 0))):.2f}.")

            if mistakes:
                m = mistakes[0]
                reasons.append(f"This may relate to: {m['mistake']}.")
                reasons.append(m["recommendation"])
            else:
                reasons.append("Review: Did you have a stop loss? Was the entry planned or impulsive?")

        return {
            "question": "Why was this trade bad?",
            "answer": " ".join(reasons),
            "reasons": reasons,
            "next_lessons": advice["next_lessons"],
        }

    def _answer_what_next(
        self, advice: Dict[str, Any], profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        level = profile.get("level", "beginner")
        lessons = advice["next_lessons"]
        challenge = advice["recommended_challenge"]

        parts = [f"At {level} level, focus on: {advice['focus_area']}."]
        if lessons:
            parts.append(f"Next lesson: {lessons[0]['title']} — {lessons[0]['reason']}.")
        if challenge:
            parts.append(f"Try challenge: {challenge['title']} — {challenge['reason']}.")

        return {
            "question": "What should I practice next?",
            "answer": " ".join(parts),
            "next_lessons": lessons,
            "recommended_challenge": challenge,
        }

    def _build_summary(
        self,
        profile: Dict[str, Any],
        skill_score: Dict[str, Any],
        mistakes: List[Dict[str, Any]],
        performance: Dict[str, Any],
    ) -> str:
        level = profile.get("level", "beginner")
        score = skill_score.get("score", 0)
        pnl = performance.get("pnl", 0)

        parts = [f"You are a {level} trader with a skill score of {score}/100."]

        if pnl > 0:
            parts.append(f"Your paper portfolio is up ${pnl:.2f} — good progress.")
        elif pnl < 0:
            parts.append(f"Your paper portfolio is down ${abs(pnl):.2f} — focus on risk management.")

        if mistakes:
            parts.append(f"Top area to improve: {mistakes[0]['mistake']}.")
        else:
            parts.append("No major mistake patterns detected — keep building consistency.")

        return " ".join(parts)

    def _identify_strengths(
        self,
        profile: Dict[str, Any],
        skill_score: Dict[str, Any],
        mistakes: List[Dict[str, Any]],
    ) -> List[str]:
        strengths = list(profile.get("strengths", []))
        components = skill_score.get("components", {})
        if components.get("risk_management", 0) >= 65 and "risk management" not in strengths:
            strengths.append("risk management")
        if components.get("consistency", 0) >= 65:
            strengths.append("trade consistency")
        if not mistakes:
            strengths.append("disciplined trading habits")
        if not strengths:
            strengths.append("willingness to learn and practice")
        return strengths[:5]

    def _identify_weaknesses(
        self,
        profile: Dict[str, Any],
        mistakes: List[Dict[str, Any]],
        performance: Dict[str, Any],
    ) -> List[str]:
        weaknesses = list(profile.get("weaknesses", []))
        for m in mistakes[:3]:
            w = m["mistake"].lower()
            if w not in weaknesses:
                weaknesses.append(w)
        if performance.get("drawdown", 0) > 10 and "drawdown control" not in weaknesses:
            weaknesses.append("drawdown control")
        return weaknesses[:5]


_mentor_instance: Optional[TradingMentor] = None


def get_trading_mentor() -> TradingMentor:
    global _mentor_instance
    if _mentor_instance is None:
        _mentor_instance = TradingMentor()
    return _mentor_instance
