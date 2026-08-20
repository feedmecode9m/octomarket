"""Market regime classification from closed ReplayRecords."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

REGIMES = ("trending", "ranging", "high_volatility", "low_volatility")

REGIME_LABELS = {
    "trending": "Trending",
    "ranging": "Ranging / chop",
    "high_volatility": "High volatility",
    "low_volatility": "Low volatility",
}


def classify_trade_regimes(record: Dict[str, Any]) -> Dict[str, bool]:
    """Tag a closed trade with applicable regime flags (multi-label)."""
    from ..replay.pattern_features import extract_pattern_features

    features = extract_pattern_features(record)
    decision = features.get("decision") or {}
    trend = decision.get("trend_state", "unknown")
    vol = decision.get("volatility_state", "unknown")

    return {
        "trending": trend == "aligned",
        "ranging": trend in ("neutral", "counter"),
        "high_volatility": vol == "high",
        "low_volatility": vol in ("normal", "low"),
    }


def aggregate_regime_performance(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Summarize trade outcomes by regime bucket."""
    closed = [r for r in records if r.get("status") == "closed"]
    buckets: Dict[str, List[Dict[str, Any]]] = {name: [] for name in REGIMES}

    for record in closed:
        flags = classify_trade_regimes(record)
        for regime, active in flags.items():
            if active:
                buckets[regime].append(record)

    result: Dict[str, Dict[str, Any]] = {}
    for regime, items in buckets.items():
        if not items:
            continue
        result[regime] = _regime_metrics(regime, items)
    return result


def _regime_metrics(regime: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    wins = sum(1 for r in records if (r.get("outcome") or {}).get("win_loss") == "win")
    pnls = [(r.get("outcome") or {}).get("pnl") for r in records if (r.get("outcome") or {}).get("pnl") is not None]
    decision_scores = [
        (r.get("scoring") or {}).get("decision_score")
        for r in records
        if (r.get("scoring") or {}).get("decision_score") is not None
    ]
    outcome_scores = [
        (r.get("scoring") or {}).get("outcome_score")
        for r in records
        if (r.get("scoring") or {}).get("outcome_score") is not None
    ]
    gross_profit = sum((r.get("outcome") or {}).get("pnl") or 0 for r in records if (r.get("outcome") or {}).get("win_loss") == "win")
    gross_loss = abs(sum((r.get("outcome") or {}).get("pnl") or 0 for r in records if (r.get("outcome") or {}).get("win_loss") == "loss"))

    from .confidence import assess_sample_confidence

    confidence = assess_sample_confidence(len(records))
    return {
        "label": REGIME_LABELS.get(regime, regime),
        "trade_count": len(records),
        "win_rate": round(wins / len(records), 2) if records else None,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
        "average_pnl": round(sum(pnls) / len(pnls), 2) if pnls else None,
        "average_decision_score": _avg_int(decision_scores),
        "average_outcome_score": _avg_int(outcome_scores),
        "confidence": confidence,
        "confidence_level": confidence["confidence_level"],
    }


def best_regime_fit(regime_performance: Dict[str, Dict[str, Any]]) -> List[str]:
    """Describe regimes where decision quality was strongest (not profitability claims)."""
    if not regime_performance:
        return []

    ranked = sorted(
        regime_performance.items(),
        key=lambda item: (
            item[1].get("average_decision_score") or 0,
            item[1].get("trade_count") or 0,
        ),
        reverse=True,
    )
    notes: List[str] = []
    for regime, metrics in ranked[:2]:
        if metrics.get("trade_count", 0) < 1:
            continue
        label = REGIME_LABELS.get(regime, regime)
        dec = metrics.get("average_decision_score")
        wr = metrics.get("win_rate")
        notes.append(
            f"{label}: {metrics['trade_count']} trades"
            + (f", avg decision {dec}" if dec is not None else "")
            + (f", win rate {int(wr * 100)}%" if wr is not None else "")
        )
    return notes


def _avg_int(values: List[int]) -> Optional[int]:
    if not values:
        return None
    return int(round(sum(values) / len(values)))
