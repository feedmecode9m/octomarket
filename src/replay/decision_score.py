"""DecisionScore artifact — grouped deterministic post-trade analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

SCORING_SCHEMA_VERSION = 2

CATEGORY_ORDER = ("setup", "risk", "execution", "outcome")

CATEGORY_LABELS = {
    "setup": "Setup Quality",
    "risk": "Risk Quality",
    "execution": "Execution Quality",
    "outcome": "Outcome",
}

# Decision-time dimensions (do not depend on trade result).
DECISION_DIMENSIONS = (
    "trend_alignment",
    "session_quality",
    "volatility_context",
    "risk_reward",
    "entry_quality",
)

OUTCOME_DIMENSIONS = ("outcome_result",)

EXECUTION_DIMENSIONS = ("execution_quality",)

CATEGORY_DIMENSIONS: Dict[str, tuple] = {
    "setup": ("trend_alignment", "session_quality", "volatility_context"),
    "risk": ("risk_reward",),
    "execution": ("entry_quality", "execution_quality"),
    "outcome": ("outcome_result",),
}

DECISION_WEIGHTS = {
    "trend_alignment": 0.22,
    "session_quality": 0.18,
    "volatility_context": 0.15,
    "risk_reward": 0.25,
    "entry_quality": 0.20,
}


def aggregate_category(
    dimensions: Dict[str, Dict[str, Any]],
    names: tuple,
) -> Dict[str, Any]:
    """Average available dimension scores within a category."""
    scores: List[int] = []
    unknown = 0
    skipped = 0
    reasons_pos: List[str] = []
    reasons_neg: List[str] = []

    for name in names:
        dim = dimensions.get(name) or {}
        if dim.get("skipped"):
            skipped += 1
            continue
        score = dim.get("score")
        if score is None:
            unknown += 1
            continue
        scores.append(int(score))
        for reason in dim.get("reasons_positive") or []:
            if reason not in reasons_pos:
                reasons_pos.append(reason)
        for reason in dim.get("reasons_negative") or []:
            if reason not in reasons_neg:
                reasons_neg.append(reason)

    if not scores:
        state = "unknown" if skipped or unknown else "unknown"
        return {
            "score": None,
            "state": state,
            "dimensions": list(names),
            "reasons_positive": reasons_pos,
            "reasons_negative": reasons_neg,
        }

    state = "partial" if unknown or skipped else "known"
    return {
        "score": int(round(sum(scores) / len(scores))),
        "state": state,
        "dimensions": list(names),
        "reasons_positive": reasons_pos,
        "reasons_negative": reasons_neg,
    }


def aggregate_decision_score(dimensions: Dict[str, Dict[str, Any]]) -> Optional[int]:
    weighted = 0.0
    weight_total = 0.0
    for name, weight in DECISION_WEIGHTS.items():
        dim = dimensions.get(name) or {}
        if dim.get("skipped") or dim.get("score") is None:
            continue
        weighted += float(dim["score"]) * weight
        weight_total += weight
    if weight_total <= 0:
        return None
    return max(0, min(100, int(round(weighted / weight_total))))


def decision_quality_note(
    decision_score: Optional[int],
    outcome: Dict[str, Any],
) -> Optional[str]:
    """Heuristic narrative separating decision quality from result."""
    if decision_score is None:
        return None
    win_loss = outcome.get("win_loss")
    if win_loss == "loss" and decision_score >= 70:
        return "High-quality decision process; loss may reflect normal variance."
    if win_loss == "win" and decision_score < 65:
        return "Trade was profitable, but decision quality was weak — review plan discipline."
    if win_loss == "win" and decision_score >= 70:
        return "Strong decision process aligned with a favorable outcome."
    if win_loss == "loss" and decision_score < 55:
        return "Weak decision quality contributed to a losing outcome."
    return None


def grade_from_score(score: Optional[int]) -> str:
    if score is None:
        return "—"
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
