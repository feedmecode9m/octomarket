"""Daily and weekly progress tracking."""

import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class ProgressTracker:
    """Track daily and weekly learning activity."""

    def __init__(self):
        self._lock = threading.RLock()
        self._daily_log: List[Dict[str, Any]] = []
        self._skill_history: List[Dict[str, Any]] = []

    def record_activity(self, activity_type: str, details: Optional[Dict[str, Any]] = None):
        with self._lock:
            self._daily_log.append({
                "type": activity_type,
                "details": details or {},
                "timestamp": datetime.now().isoformat(),
            })
            if len(self._daily_log) > 500:
                self._daily_log = self._daily_log[-500:]

    def record_skill_change(self, score: int, level: str, components: Dict[str, float]):
        with self._lock:
            self._skill_history.append({
                "score": score,
                "level": level,
                "components": components,
                "timestamp": datetime.now().isoformat(),
            })

    def get_progress(self) -> Dict[str, Any]:
        with self._lock:
            today = datetime.now().date()
            week_ago = today - timedelta(days=7)

            today_entries = [e for e in self._daily_log if self._parse_date(e["timestamp"]) == today]
            week_entries = [e for e in self._daily_log if self._parse_date(e["timestamp"]) >= week_ago]

            daily = {
                "trades_reviewed": sum(1 for e in today_entries if e["type"] == "trade_reviewed"),
                "lessons_completed": sum(1 for e in today_entries if e["type"] == "lesson_completed"),
                "challenges_completed": sum(1 for e in today_entries if e["type"] == "challenge_completed"),
                "scenarios_completed": sum(1 for e in today_entries if e["type"] == "scenario_completed"),
                "backtests_run": sum(1 for e in today_entries if e["type"] == "backtest_run"),
            }

            weekly = {
                "total_activities": len(week_entries),
                "trades_reviewed": sum(1 for e in week_entries if e["type"] == "trade_reviewed"),
                "lessons_completed": sum(1 for e in week_entries if e["type"] == "lesson_completed"),
                "challenges_completed": sum(1 for e in week_entries if e["type"] == "challenge_completed"),
                "scenarios_completed": sum(1 for e in week_entries if e["type"] == "scenario_completed"),
            }

            improvement = self._weekly_improvement()

            return {
                "daily": daily,
                "weekly": weekly,
                "skill_changes": self._skill_changes_summary(),
                "improvement_areas": improvement,
                "streak_days": self._calculate_streak(),
            }

    def _weekly_improvement(self) -> List[str]:
        if len(self._skill_history) < 2:
            return ["Complete more activities to track improvement over time."]

        recent = self._skill_history[-1]["components"]
        older = self._skill_history[0]["components"]
        areas = []

        labels = {
            "risk_management": "Risk Management",
            "consistency": "Consistency",
            "strategy_quality": "Strategy Quality",
            "emotional_discipline": "Discipline",
        }
        for key, label in labels.items():
            diff = recent.get(key, 0) - older.get(key, 0)
            if diff > 5:
                areas.append(f"Improved in {label} (+{diff:.0f} points)")
            elif diff < -5:
                areas.append(f"Declined in {label} ({diff:.0f} points) — review recent trades")

        if not areas:
            areas.append("Skill components stable — keep practicing to see improvement.")
        return areas

    def _skill_changes_summary(self) -> Dict[str, Any]:
        if not self._skill_history:
            return {"current": None, "change_7d": 0}
        current = self._skill_history[-1]
        change = 0
        if len(self._skill_history) >= 2:
            change = current["score"] - self._skill_history[0]["score"]
        return {"current": current["score"], "level": current["level"], "change_7d": change}

    def _calculate_streak(self) -> int:
        if not self._daily_log:
            return 0
        dates = sorted({self._parse_date(e["timestamp"]) for e in self._daily_log}, reverse=True)
        streak = 0
        expected = datetime.now().date()
        for d in dates:
            if d == expected or d == expected - timedelta(days=1):
                streak += 1
                expected = d - timedelta(days=1)
            else:
                break
        return streak

    def _parse_date(self, ts: str):
        return datetime.fromisoformat(ts).date()


_tracker_instance: Optional[ProgressTracker] = None


def get_progress_tracker() -> ProgressTracker:
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = ProgressTracker()
    return _tracker_instance
