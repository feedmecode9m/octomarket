"""Trading challenges for skill progression."""

import threading
from typing import Any, Dict, List, Optional


CHALLENGES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Capital Preservation",
        "description": "Grow a $10,000 account without losing more than 10%.",
        "rules": {
            "initial_cash": 10000,
            "max_drawdown_pct": 10,
            "min_return_pct": 0,
        },
        "difficulty": "beginner",
    },
    {
        "id": 2,
        "title": "Risk Management Master",
        "description": "Complete 20 trades while keeping max drawdown under 5%.",
        "rules": {
            "min_trades": 20,
            "max_drawdown_pct": 5,
        },
        "difficulty": "intermediate",
    },
    {
        "id": 3,
        "title": "Beat Buy and Hold",
        "description": "Outperform a simple buy-and-hold benchmark over the replay session.",
        "rules": {
            "beat_benchmark": True,
        },
        "difficulty": "advanced",
    },
]


class ChallengeTracker:
    """Track challenge completion, score, and mistakes."""

    def __init__(self):
        self._lock = threading.RLock()
        self._progress: Dict[int, Dict[str, Any]] = {}

    def get_all(self) -> List[Dict[str, Any]]:
        return [{**c, "progress": self._progress.get(c["id"], self._empty_progress())} for c in CHALLENGES]

    def get_challenge(self, challenge_id: int) -> Optional[Dict[str, Any]]:
        for c in CHALLENGES:
            if c["id"] == challenge_id:
                return {**c, "progress": self._progress.get(challenge_id, self._empty_progress())}
        return None

    def evaluate(self, challenge_id: int, metrics: Dict[str, Any]) -> Dict[str, Any]:
        challenge = self.get_challenge(challenge_id)
        if not challenge:
            return {"error": "Challenge not found"}

        rules = challenge["rules"]
        mistakes = []
        score = 0
        completed = False

        if challenge_id == 1:
            initial = rules.get("initial_cash", 10000)
            dd = metrics.get("drawdown", 0)
            pnl = metrics.get("pnl", 0)
            if dd > rules["max_drawdown_pct"]:
                mistakes.append(f"Drawdown {dd:.1f}% exceeded {rules['max_drawdown_pct']}% limit.")
            else:
                score += 50
            if pnl > 0:
                score += 50
                completed = dd <= rules["max_drawdown_pct"]
            else:
                mistakes.append("Account did not grow — review entries and risk sizing.")

        elif challenge_id == 2:
            trades = metrics.get("total_trades", 0)
            dd = metrics.get("drawdown", 0)
            min_trades = rules.get("min_trades", 20)
            if trades < min_trades:
                mistakes.append(f"Only {trades}/{min_trades} trades completed.")
                score = int(trades / min_trades * 50)
            else:
                score += 50
            if dd > rules["max_drawdown_pct"]:
                mistakes.append(f"Drawdown {dd:.1f}% exceeded {rules['max_drawdown_pct']}% limit.")
            else:
                score += 50
                completed = trades >= min_trades and dd <= rules["max_drawdown_pct"]

        elif challenge_id == 3:
            beat = metrics.get("beat_benchmark")
            total_return = metrics.get("total_return_pct", 0)
            benchmark = metrics.get("benchmark_return_pct", 0)
            if beat:
                score = 100
                completed = True
            else:
                mistakes.append(
                    f"Return {total_return:.1f}% did not beat buy-and-hold {benchmark:.1f}%."
                )
                score = max(0, int(50 + (total_return - benchmark)))

        result = {
            "challenge_id": challenge_id,
            "completed": completed,
            "score": min(100, max(0, score)),
            "mistakes": mistakes,
            "metrics_snapshot": metrics,
        }

        with self._lock:
            self._progress[challenge_id] = {
                "completed": completed,
                "score": result["score"],
                "mistakes": mistakes,
                "last_evaluated": metrics,
            }

        return result

    def reset(self, challenge_id: Optional[int] = None):
        with self._lock:
            if challenge_id is not None:
                self._progress.pop(challenge_id, None)
            else:
                self._progress.clear()

    def _empty_progress(self) -> Dict[str, Any]:
        return {"completed": False, "score": 0, "mistakes": [], "last_evaluated": None}


_tracker_instance: Optional[ChallengeTracker] = None


def get_challenge_tracker() -> ChallengeTracker:
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = ChallengeTracker()
    return _tracker_instance


def get_all_challenges() -> List[Dict[str, Any]]:
    return get_challenge_tracker().get_all()
