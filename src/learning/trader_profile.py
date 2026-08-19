"""Trader profile for personalized coaching."""

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class TraderProfile:
    """Track learner experience, preferences, and progression."""

    DEFAULT = {
        "level": "beginner",
        "experience_months": 0,
        "preferred_strategies": [],
        "risk_tolerance": "moderate",
        "strengths": [],
        "weaknesses": [],
        "completed_lessons": [],
        "challenge_history": [],
        "skill_progression": [],
        "common_mistakes": [],
        "created_at": None,
        "updated_at": None,
    }

    def __init__(self):
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self.reset()

    def reset(self):
        with self._lock:
            now = datetime.now().isoformat()
            self._data = {**self.DEFAULT, "created_at": now, "updated_at": now}

    def get(self) -> Dict[str, Any]:
        with self._lock:
            return self._data.copy()

    def update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            allowed = {
                "level", "experience_months", "preferred_strategies",
                "risk_tolerance", "strengths", "weaknesses",
            }
            for key, value in updates.items():
                if key in allowed:
                    self._data[key] = value
            self._data["updated_at"] = datetime.now().isoformat()
            return self._data.copy()

    def record_lesson_completed(self, lesson_id: int):
        with self._lock:
            if lesson_id not in self._data["completed_lessons"]:
                self._data["completed_lessons"].append(lesson_id)
                self._data["updated_at"] = datetime.now().isoformat()

    def record_challenge(self, challenge_id: int, score: int, completed: bool):
        with self._lock:
            entry = {
                "challenge_id": challenge_id,
                "score": score,
                "completed": completed,
                "timestamp": datetime.now().isoformat(),
            }
            self._data["challenge_history"].append(entry)
            self._data["updated_at"] = datetime.now().isoformat()

    def record_skill_score(self, score: int, level: str):
        with self._lock:
            self._data["skill_progression"].append({
                "score": score,
                "level": level,
                "timestamp": datetime.now().isoformat(),
            })
            if len(self._data["skill_progression"]) > 100:
                self._data["skill_progression"] = self._data["skill_progression"][-100:]
            self._infer_level(score)

    def set_mistakes(self, mistakes: List[str]):
        with self._lock:
            self._data["common_mistakes"] = mistakes
            self._data["updated_at"] = datetime.now().isoformat()

    def infer_strengths_weaknesses(
        self,
        skill_components: Dict[str, float],
        detected_mistakes: List[Dict[str, Any]],
    ):
        with self._lock:
            strengths = []
            weaknesses = []

            labels = {
                "risk_management": "risk management",
                "consistency": "trade consistency",
                "strategy_quality": "strategy design",
                "emotional_discipline": "emotional discipline",
            }
            for key, label in labels.items():
                val = skill_components.get(key, 50)
                if val >= 65:
                    strengths.append(label)
                elif val < 45:
                    weaknesses.append(label)

            for m in detected_mistakes[:3]:
                w = m.get("mistake", "").lower()
                if w and w not in weaknesses:
                    weaknesses.append(w)

            if strengths:
                self._data["strengths"] = strengths
            if weaknesses:
                self._data["weaknesses"] = weaknesses

    def _infer_level(self, score: int):
        if score >= 80:
            self._data["level"] = "advanced"
        elif score >= 65:
            self._data["level"] = "intermediate"
        elif score >= 40:
            self._data["level"] = "beginner"
        else:
            self._data["level"] = "novice"


_profile_instance: Optional[TraderProfile] = None


def get_trader_profile() -> TraderProfile:
    global _profile_instance
    if _profile_instance is None:
        _profile_instance = TraderProfile()
    return _profile_instance
