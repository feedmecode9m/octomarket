"""Learning journal entry schema — interpretation layer above ReplayRecord."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

JOURNAL_SCHEMA_VERSION = 1


def new_entry_id() -> str:
    return str(uuid.uuid4())


def build_learning_entry(
    *,
    record_id: str,
    plan_id: Optional[str],
    date: str,
    instrument_id: str,
    asset_class: str,
    mode: str,
    strategy_id: Optional[str],
    strategy_name: Optional[str],
    market_regime: Dict[str, Any],
    decision_summary: str,
    outcome_summary: str,
    lesson: str,
    repeat: List[str],
    avoid: List[str],
    confidence: str,
    similar_pattern: Optional[Dict[str, Any]] = None,
    scoring: Optional[Dict[str, Any]] = None,
    outcome: Optional[Dict[str, Any]] = None,
    continuous_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a LearningJournalEntry that references a ReplayRecord without copying it."""
    return {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "entry_type": "learning_journal",
        "id": new_entry_id(),
        "record_id": record_id,
        "plan_id": plan_id,
        "generated_at": datetime.now().isoformat(),
        "date": date,
        "instrument_id": instrument_id,
        "asset_class": asset_class,
        "continuous_id": continuous_id,
        "mode": mode,
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "market_regime": market_regime,
        "decision_summary": decision_summary,
        "outcome_summary": outcome_summary,
        "lesson": lesson,
        "repeat": repeat,
        "avoid": avoid,
        "confidence": confidence,
        "similar_pattern": similar_pattern or {},
        "scoring_snapshot": {
            "decision_score": (scoring or {}).get("decision_score"),
            "outcome_score": (scoring or {}).get("outcome_score"),
            "decision_grade": (scoring or {}).get("decision_grade"),
            "decision_quality_note": (scoring or {}).get("decision_quality_note"),
        },
        "outcome_snapshot": {
            "pnl": (outcome or {}).get("pnl"),
            "r_multiple": (outcome or {}).get("r_multiple"),
            "win_loss": (outcome or {}).get("win_loss"),
            "exit_reason": (outcome or {}).get("exit_reason"),
        },
    }
