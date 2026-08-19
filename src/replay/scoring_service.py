"""Scoring service — deterministic DecisionScore from completed ReplayRecords."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .decision_score import (
    CATEGORY_DIMENSIONS,
    SCORING_SCHEMA_VERSION,
    aggregate_category,
    aggregate_decision_score,
    decision_quality_note,
    grade_from_score,
)
from . import replay_scoring as _engine


class ScoringService:
    """Compute and attach DecisionScore artifacts without mutating record behavior."""

    def score(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return build_decision_score(record)

    def apply_to_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(record)
        updated["scoring"] = self.score(record)
        if updated.get("metadata"):
            updated["metadata"] = dict(updated["metadata"])
            updated["metadata"]["updated_at"] = datetime.now().isoformat()
        return updated


def build_decision_score(record: Dict[str, Any]) -> Dict[str, Any]:
    """Build grouped DecisionScore artifact from a replay record."""
    plan = record.get("trade_intent") or {}
    market = record.get("market") or {}
    snapshot = (record.get("decision_context") or {}).get("market_snapshot") or {}
    outcome = record.get("outcome") or {}
    execution = record.get("execution") or {}
    status = record.get("status")
    asset_class = market.get("asset_class", "STOCK")
    direction = (plan.get("direction") or "LONG").upper()
    metrics = (record.get("metadata") or {}).get("replay_metrics") or {}

    dimensions: Dict[str, Dict[str, Any]] = {
        "trend_alignment": _engine._score_trend_alignment(snapshot, direction),
        "session_quality": _engine._score_session_quality(market, snapshot, asset_class),
        "risk_reward": _engine._score_risk_reward(plan, direction, asset_class),
        "entry_quality": _engine._score_entry_quality(plan, snapshot, execution),
        "volatility_context": _engine._score_volatility_context(plan, snapshot, asset_class, direction),
        "execution_quality": _engine._score_execution_quality(plan, execution, status),
        "outcome_result": _engine._score_outcome(outcome, execution, status, metrics),
    }

    categories = {
        name: aggregate_category(dimensions, dim_names)
        for name, dim_names in CATEGORY_DIMENSIONS.items()
    }

    decision_score = aggregate_decision_score(dimensions)
    outcome_score = (categories.get("outcome") or {}).get("score")
    total_score, completeness = _combined_score(
        decision_score, outcome_score, status, dimensions
    )

    reasons_positive, reasons_negative = _collect_reasons(dimensions)

    return {
        "schema_version": SCORING_SCHEMA_VERSION,
        "decision_score": decision_score,
        "decision_grade": grade_from_score(decision_score),
        "outcome_score": outcome_score,
        "total_score": total_score,
        "grade": grade_from_score(total_score),
        "completeness": completeness,
        "categories": categories,
        "dimensions": dimensions,
        "reasons_positive": reasons_positive,
        "reasons_negative": reasons_negative,
        "decision_quality_note": decision_quality_note(decision_score, outcome),
        "mode": record.get("mode"),
        "asset_class": asset_class,
        "instrument_id": market.get("instrument_id"),
        "continuous_id": market.get("continuous_id"),
        "scored_at": datetime.now().isoformat(),
    }


def _combined_score(
    decision_score: Optional[int],
    outcome_score: Optional[int],
    status: Optional[str],
    dimensions: Dict[str, Dict[str, Any]],
) -> Tuple[Optional[int], str]:
    has_outcome = not (dimensions.get("outcome_result") or {}).get("skipped", True)
    has_execution = not (dimensions.get("execution_quality") or {}).get("skipped", True)

    if decision_score is None and outcome_score is None:
        completeness = _completeness(status, has_execution, has_outcome)
        return None, completeness

    if decision_score is not None and outcome_score is not None and status == "closed":
        total = int(round(decision_score * 0.7 + outcome_score * 0.3))
        return max(0, min(100, total)), "full"

    if decision_score is not None:
        return decision_score, _completeness(status, has_execution, has_outcome)

    return outcome_score, _completeness(status, has_execution, has_outcome)


def _completeness(status: Optional[str], has_execution: bool, has_outcome: bool) -> str:
    if status == "closed" and has_execution and has_outcome:
        return "full"
    if status in ("filled", "submitted", "closed"):
        return "partial"
    return "decision_only"


def _collect_reasons(dimensions: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    positive: List[str] = []
    negative: List[str] = []
    for dim in dimensions.values():
        for reason in dim.get("reasons_positive") or []:
            if reason not in positive:
                positive.append(reason)
        for reason in dim.get("reasons_negative") or []:
            if reason not in negative:
                negative.append(reason)
    return positive, negative


_service_instance: Optional[ScoringService] = None


def get_scoring_service() -> ScoringService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ScoringService()
    return _service_instance


def score_replay_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible entry point."""
    return get_scoring_service().score(record)


def apply_scoring(record: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible attach helper."""
    return get_scoring_service().apply_to_record(record)
