"""Adaptive lesson and challenge recommendations based on mistakes."""

from typing import Any, Dict, List, Optional


LESSON_MAP = {
    "oversized_positions": {"lesson_id": 5, "title": "Risk Management", "reason": "You are risking too much per trade."},
    "poor_stop_loss": {"lesson_id": 5, "title": "Risk Management", "reason": "Stop losses protect your capital."},
    "ignoring_drawdown": {"lesson_id": 5, "title": "Risk Management", "reason": "Drawdown management is critical for survival."},
    "revenge_trading": {"lesson_id": 7, "title": "Psychology of Trading", "reason": "Revenge trading is an emotional trap."},
    "overtrading": {"lesson_id": 7, "title": "Psychology of Trading", "reason": "Overtrading erodes returns through poor entries."},
    "chasing_momentum": {"lesson_id": 3, "title": "RSI", "reason": "Avoid buying when momentum is already extended."},
}

CHALLENGE_MAP = {
    "oversized_positions": {"challenge_id": 1, "title": "Capital Preservation", "reason": "Practice growing account without large drawdowns."},
    "poor_stop_loss": {"challenge_id": 2, "title": "Risk Management Master", "reason": "Complete trades with strict risk rules."},
    "ignoring_drawdown": {"challenge_id": 1, "title": "Capital Preservation", "reason": "Learn to protect capital during downturns."},
    "revenge_trading": {"challenge_id": 2, "title": "Risk Management Master", "reason": "Build discipline with structured challenges."},
    "overtrading": {"challenge_id": 2, "title": "Risk Management Master", "reason": "Focus on quality trades over quantity."},
    "chasing_momentum": {"challenge_id": 3, "title": "Beat Buy and Hold", "reason": "Patient entries beat chasing momentum."},
}

DEFAULT_LESSONS = [
    {"lesson_id": 1, "title": "Market Orders vs Limit Orders", "reason": "Foundation for all trading."},
    {"lesson_id": 2, "title": "Moving Averages", "reason": "Core trend identification tool."},
]

DEFAULT_CHALLENGE = {"challenge_id": 1, "title": "Capital Preservation", "reason": "Start with capital protection."}


class AdaptiveRecommendations:
    """Recommend lessons and challenges based on detected mistakes and profile."""

    def recommend(
        self,
        mistakes: List[Dict[str, Any]],
        profile: Optional[Dict[str, Any]] = None,
        completed_lessons: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        profile = profile or {}
        completed = set(completed_lessons or profile.get("completed_lessons", []))

        lesson_recs = []
        challenge_recs = []
        seen_lessons = set()
        seen_challenges = set()

        for m in mistakes:
            key = m.get("mistake_key", "")
            if key in LESSON_MAP:
                rec = LESSON_MAP[key]
                if rec["lesson_id"] not in completed and rec["lesson_id"] not in seen_lessons:
                    lesson_recs.append({**rec, "priority": m.get("severity", 50)})
                    seen_lessons.add(rec["lesson_id"])
            if key in CHALLENGE_MAP:
                rec = CHALLENGE_MAP[key]
                if rec["challenge_id"] not in seen_challenges:
                    challenge_recs.append({**rec, "priority": m.get("severity", 50)})
                    seen_challenges.add(rec["challenge_id"])

        for default in DEFAULT_LESSONS:
            if default["lesson_id"] not in completed and default["lesson_id"] not in seen_lessons:
                lesson_recs.append({**default, "priority": 10})
                seen_lessons.add(default["lesson_id"])
            if len(lesson_recs) >= 3:
                break

        if not challenge_recs:
            challenge_recs.append({**DEFAULT_CHALLENGE, "priority": 10})

        lesson_recs.sort(key=lambda x: x.get("priority", 0), reverse=True)
        challenge_recs.sort(key=lambda x: x.get("priority", 0), reverse=True)

        return {
            "lessons": lesson_recs[:3],
            "challenges": challenge_recs[:2],
            "focus_area": mistakes[0]["mistake"] if mistakes else "Foundation building",
        }
