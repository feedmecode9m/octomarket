"""Learning journal engine — deterministic lessons from closed ReplayRecords."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..replay.pattern_features import extract_pattern_features
from ..replay.pattern_service import get_pattern_service
from ..replay.replay_store import get_replay_store
from ..research.confidence import assess_sample_confidence
from ..research.regime import classify_trade_regimes
from .journal_entry import build_learning_entry
from .journal_patterns import scan_recurring_patterns, summarize_similar_for_entry
from .journal_store import LearningJournalStore, get_learning_journal_store


class LearningJournalService:
    """
    Generate LearningJournalEntry artifacts when ReplayRecords close.

    ReplayRecord remains the immutable source of truth.
    """

    def __init__(
        self,
        store: Optional[LearningJournalStore] = None,
        *,
        enabled: bool = True,
    ):
        self._store = store or get_learning_journal_store()
        self._enabled = enabled

    def on_record_closed(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return None
        if record.get("status") != "closed":
            return None
        existing = self._store.get_by_record_id(record["id"])
        if existing:
            return existing
        entry = self.build_entry(record)
        return self._store.save(entry)

    def build_entry(self, record: Dict[str, Any]) -> Dict[str, Any]:
        features = extract_pattern_features(record)
        market = record.get("market") or {}
        plan = record.get("trade_intent") or {}
        scoring = record.get("scoring") or {}
        outcome = record.get("outcome") or {}
        decision = features.get("decision") or {}

        regime_flags = classify_trade_regimes(record)
        active_regimes = [name for name, on in regime_flags.items() if on]

        similar_raw = get_pattern_service().find_similar(record, limit=12)
        similar = summarize_similar_for_entry(similar_raw)
        sample_conf = assess_sample_confidence(similar.get("match_count") or 0)

        decision_summary = _decision_summary(plan, decision, scoring)
        outcome_summary = _outcome_summary(outcome, scoring)
        lesson, repeat, avoid = _lesson_blocks(
            decision=decision,
            scoring=scoring,
            outcome=outcome,
            similar=similar,
            active_regimes=active_regimes,
            strategy_id=plan.get("strategy_id"),
        )

        finalized = (record.get("metadata") or {}).get("finalized_at") or record.get("updated_at")
        date = (finalized or datetime.now().isoformat())[:10]

        return build_learning_entry(
            record_id=record["id"],
            plan_id=record.get("plan_id"),
            date=date,
            instrument_id=market.get("instrument_id") or plan.get("instrument_id") or plan.get("symbol") or "",
            asset_class=market.get("asset_class") or plan.get("asset_class") or "STOCK",
            continuous_id=market.get("continuous_id"),
            mode=record.get("mode") or "live_paper",
            strategy_id=plan.get("strategy_id"),
            strategy_name=plan.get("strategy_name"),
            market_regime={
                "trend_state": decision.get("trend_state"),
                "volatility_state": decision.get("volatility_state"),
                "setup_quality": decision.get("setup_quality"),
                "active_regimes": active_regimes,
            },
            decision_summary=decision_summary,
            outcome_summary=outcome_summary,
            lesson=lesson,
            repeat=repeat,
            avoid=avoid,
            confidence=sample_conf["confidence_level"] if (similar.get("match_count") or 0) else "low",
            similar_pattern=similar,
            scoring=scoring,
            outcome=outcome,
        )

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(entry_id)

    def get_by_record_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get_by_record_id(record_id)

    def get_by_plan_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        record = get_replay_store().get_by_plan_id(plan_id)
        if not record:
            return None
        return self._store.get_by_record_id(record["id"])

    def list_entries(self, *, limit: int = 50, instrument_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if instrument_id:
            return self._store.list_for_instrument(instrument_id, limit=limit)
        return self._store.list_all(limit=limit)

    def recurring_patterns(self, *, min_trades: int = 5) -> List[Dict[str, Any]]:
        records = get_replay_store().list_all()
        return scan_recurring_patterns(records, min_trades=min_trades)


def _decision_summary(plan: Dict[str, Any], decision: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    strategy = plan.get("strategy_name") or plan.get("strategy_id") or "Manual"
    direction = (plan.get("direction") or "LONG").upper()
    trend = decision.get("trend_state") or "unknown"
    vol = decision.get("volatility_state") or "unknown"
    grade = scoring.get("decision_grade") or "—"
    score = scoring.get("decision_score")
    score_text = f"{score}/100 ({grade})" if score is not None else grade
    thesis = (plan.get("thesis") or "").strip()
    base = (
        f"{strategy} {direction} with trend={trend}, volatility={vol}. "
        f"Decision quality {score_text}."
    )
    if thesis:
        return f"{base} Thesis: {thesis}"
    return base


def _outcome_summary(outcome: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    win_loss = outcome.get("win_loss") or "unknown"
    pnl = outcome.get("pnl")
    r_mult = outcome.get("r_multiple")
    exit_reason = outcome.get("exit_reason") or "exit"
    outcome_score = scoring.get("outcome_score")
    parts = [f"Result: {win_loss} via {exit_reason}"]
    if pnl is not None:
        parts.append(f"P/L ${pnl}")
    if r_mult is not None:
        parts.append(f"{r_mult}R")
    if outcome_score is not None:
        parts.append(f"outcome score {outcome_score}")
    note = scoring.get("decision_quality_note")
    text = " · ".join(parts) + "."
    if note:
        text += f" {note}"
    return text


def _lesson_blocks(
    *,
    decision: Dict[str, Any],
    scoring: Dict[str, Any],
    outcome: Dict[str, Any],
    similar: Dict[str, Any],
    active_regimes: List[str],
    strategy_id: Optional[str],
) -> tuple:
    decision_score = scoring.get("decision_score")
    outcome_score = scoring.get("outcome_score")
    win_loss = outcome.get("win_loss")
    match_count = similar.get("match_count") or 0
    avg_r = similar.get("average_r_multiple")
    similar_wr = similar.get("win_rate")

    repeat: List[str] = []
    avoid: List[str] = []

    if decision_score is not None and decision_score >= 75:
        repeat.append("Keep the same decision process — setup and risk checklist scored well.")
    if decision.get("trend_state") == "aligned" and (decision_score or 0) >= 70:
        repeat.append("Trend-aligned entries matched a historically stronger process context.")
    if decision.get("volatility_state") == "high" and win_loss == "loss":
        avoid.append("High-volatility entries that lose may need tighter confirmation or smaller size.")
    if decision.get("trend_state") in ("counter", "neutral") and win_loss == "loss":
        avoid.append("Counter/neutral trend contexts underperformed on this trade — reduce countertrend frequency.")

    if decision_score is not None and outcome_score is not None:
        if decision_score >= 75 and (outcome_score or 0) < 55:
            lesson = (
                "High-quality decision with weak outcome — treat as variance unless the same pattern "
                "repeats across many samples."
            )
        elif decision_score < 60 and win_loss == "win":
            lesson = (
                "Lucky outcome on a weak process — do not reinforce the setup. Strengthen checklist next time."
            )
            avoid.append("Do not scale a weak-process win into larger size.")
        elif decision_score >= 75 and win_loss == "win":
            lesson = "Process and outcome aligned — candidate for a repeatable playbook entry."
        else:
            lesson = "Mixed process/outcome — review conditions before changing rules."
    else:
        lesson = "Trade closed — continue logging decisions to build statistical confidence."

    if match_count >= 5:
        wr_text = f"{int(similar_wr * 100)}% win rate" if similar_wr is not None else "n/a win rate"
        r_text = f"avg {avg_r}R" if avg_r is not None else "avg R n/a"
        lesson += f" Similar past trades: {match_count} matches · {wr_text} · {r_text}."
        if avg_r is not None and avg_r > 0:
            repeat.append("Historically similar setups produced positive average R — favor repeating conditions.")
        elif avg_r is not None and avg_r < 0:
            avoid.append("Historically similar setups had negative average R — pause or refine this pattern.")
    else:
        lesson += " Few similar historical matches — lesson confidence is low until sample size grows."

    if active_regimes:
        lesson += f" Active regimes: {', '.join(active_regimes)}."
    if strategy_id:
        lesson += f" Strategy tag: {strategy_id}."

    if not repeat:
        repeat.append("Maintain documented thesis, stop, and target before entry.")
    if not avoid:
        avoid.append("Avoid changing the plan mid-trade without a predefined invalidation rule.")

    return lesson, repeat[:4], avoid[:4]


_service_instance: Optional[LearningJournalService] = None


def get_learning_journal_service() -> LearningJournalService:
    global _service_instance
    if _service_instance is None:
        _service_instance = LearningJournalService()
    return _service_instance


def reset_learning_journal_service() -> None:
    global _service_instance
    from .journal_analytics import reset_journal_analytics_service
    from .journal_store import reset_learning_journal_store

    reset_learning_journal_store()
    reset_journal_analytics_service()
    _service_instance = None


def record_closed_trade(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Module-level hook used by ReplayMemory after a close."""
    return get_learning_journal_service().on_record_closed(record)
