"""Compare trade plan vs replay outcome for learning feedback."""

from typing import Any, Dict, List, Optional


def _grade_from_score(score: int) -> str:
    if score >= 90:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 75:
        return "B+"
    if score >= 65:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def compare_plan_to_outcome(
    plan: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    execution: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate learning feedback comparing planned vs actual replay outcome.

    Returns plan grade, good points, and improvements.
    """
    good: List[str] = []
    improve: List[str] = []
    score = 70

    entry = _level_price(plan.get("entry"))
    stop = _level_price(plan.get("stop_loss"))
    target = _level_price(plan.get("target"))
    direction = (plan.get("direction") or "LONG").upper()
    rr = plan.get("risk_reward")

    exit_price = None
    if execution:
        exit_price = execution.get("exit_price") or execution.get("fill_price")

    high = (metrics or {}).get("high_reached")
    low = (metrics or {}).get("low_reached")

    if entry and stop and rr and rr >= 2:
        good.append("Risk/reward met the 2:1 planning guideline.")
        score += 10
    elif rr is not None and rr < 1.5:
        improve.append("Reward did not sufficiently exceed risk in the plan.")
        score -= 10

    if entry and stop:
        if direction == "LONG" and stop < entry:
            good.append("Stop was placed below entry — risk was defined.")
        if direction == "SHORT" and stop > entry:
            good.append("Stop was placed above entry — risk was defined.")

    if high is not None and target and direction == "LONG":
        if high >= target:
            good.append(f"Price reached planned target zone (high {high:.2f} vs target {target:.2f}).")
            score += 10
        else:
            improve.append(f"Target {target:.2f} was not reached (session high {high:.2f}).")

    if low is not None and stop and direction == "LONG":
        if low <= stop:
            improve.append(f"Stop level {stop:.2f} was tested (low {low:.2f}) — review stop placement.")
            score -= 5
        elif abs(low - stop) / max(entry or low, 1) < 0.02:
            improve.append("Stop was close to session volatility — consider wider invalidation.")

    if entry and exit_price:
        if direction == "LONG" and exit_price >= entry:
            good.append("Exit was at or above planned entry — trade captured upside.")
            score += 5
        diff_pct = abs(exit_price - entry) / max(entry, 1) * 100
        if diff_pct < 1:
            good.append("Entry execution matched plan closely.")

    if plan.get("thesis"):
        good.append("Thesis was documented before execution.")
        score += 5
    else:
        improve.append("Document a thesis before the next replay session.")

    if not good:
        good.append("Replay completed — review chart structure for the next attempt.")

    return {
        "plan_grade": _grade_from_score(max(0, min(100, score))),
        "good": good,
        "improve": improve,
        "planned": {
            "entry": entry,
            "stop": stop,
            "target": target,
            "direction": direction,
            "rr": rr,
        },
        "actual": {
            "high_reached": high,
            "low_reached": low,
            "exit": exit_price,
        },
    }


def _level_price(level: Any) -> Optional[float]:
    if level is None:
        return None
    if isinstance(level, dict):
        level = level.get("price")
    if level is None:
        return None
    return float(level)
