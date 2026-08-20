"""Recurring behavior patterns from closed ReplayRecords / journal evidence."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..replay.pattern_features import extract_pattern_features
from ..research.confidence import assess_sample_confidence
from ..research.regime import classify_trade_regimes


def scan_recurring_patterns(
    records: List[Dict[str, Any]],
    *,
    min_trades: int = 5,
) -> List[Dict[str, Any]]:
    """
    Deterministic pattern scanner — groups closed trades by strategy × regime tags.

    Returns evidence-backed findings, not advice from an LLM.
    """
    closed = [r for r in records if r.get("status") == "closed"]
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for record in closed:
        strategy = (record.get("trade_intent") or {}).get("strategy_id") or "manual"
        flags = classify_trade_regimes(record)
        active = [name for name, on in flags.items() if on] or ["unclassified"]
        for regime in active:
            key = f"{strategy}|{regime}"
            buckets[key].append(record)

    findings: List[Dict[str, Any]] = []
    for key, items in buckets.items():
        if len(items) < min_trades:
            continue
        strategy_id, regime = key.split("|", 1)
        metrics = _bucket_metrics(items)
        confidence = assess_sample_confidence(len(items))
        pf = metrics.get("profit_factor")
        decision = metrics.get("average_decision_score")

        if pf is not None and pf < 1.0 and (decision or 0) >= 70:
            finding = (
                f"{strategy_id} underperformed in {regime.replace('_', ' ')} conditions "
                f"despite solid decision quality — review timing or filters."
            )
            action = f"Be selective with {strategy_id} when regime is {regime.replace('_', ' ')}."
        elif pf is not None and pf >= 1.2 and (decision or 0) >= 70:
            finding = (
                f"{strategy_id} showed durable process+outcome alignment in "
                f"{regime.replace('_', ' ')} conditions."
            )
            action = f"Prioritize repeating {strategy_id} setups when regime is {regime.replace('_', ' ')}."
        else:
            finding = (
                f"{strategy_id} produced mixed evidence in {regime.replace('_', ' ')} "
                f"({len(items)} trades)."
            )
            action = "Gather more samples before changing process rules."

        findings.append({
            "strategy_id": strategy_id,
            "regime": regime,
            "trade_count": len(items),
            "profit_factor": pf,
            "win_rate": metrics.get("win_rate"),
            "average_decision_score": decision,
            "average_r_multiple": metrics.get("average_r"),
            "confidence": confidence["confidence_level"],
            "finding": finding,
            "recommendation": action,
            "record_ids": [r["id"] for r in items[:24]],
        })

    findings.sort(
        key=lambda f: (f.get("trade_count") or 0, f.get("average_decision_score") or 0),
        reverse=True,
    )
    return findings


def summarize_similar_for_entry(similar: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize PatternService.find_similar output for a journal entry."""
    summary = similar.get("summary") or {}
    return {
        "match_count": similar.get("match_count", 0),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "average_r_multiple": summary.get("average_r_multiple"),
        "average_decision_score": summary.get("average_decision_score"),
        "criteria": similar.get("criteria") or {},
    }


def _bucket_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    wins = [r for r in records if (r.get("outcome") or {}).get("win_loss") == "win"]
    losses = [r for r in records if (r.get("outcome") or {}).get("win_loss") == "loss"]
    gross_profit = sum((r.get("outcome") or {}).get("pnl") or 0 for r in wins)
    gross_loss = abs(sum((r.get("outcome") or {}).get("pnl") or 0 for r in losses))
    rs = [
        (r.get("outcome") or {}).get("r_multiple")
        for r in records
        if (r.get("outcome") or {}).get("r_multiple") is not None
    ]
    decisions = [
        (r.get("scoring") or {}).get("decision_score")
        for r in records
        if (r.get("scoring") or {}).get("decision_score") is not None
    ]
    return {
        "win_rate": round(len(wins) / len(records), 2) if records else None,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
        "average_r": round(sum(rs) / len(rs), 2) if rs else None,
        "average_decision_score": int(round(sum(decisions) / len(decisions))) if decisions else None,
    }
