"""Strategy research report schema and aggregation."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from .regime import aggregate_regime_performance
from .confidence import assess_sample_confidence
from .costs import gross_profit_metrics, summarize_transaction_costs

REPORT_SCHEMA_VERSION = 3


def new_report_id() -> str:
    return str(uuid.uuid4())


def build_strategy_report(
    *,
    strategy_id: str,
    strategy_name: str,
    instrument_id: str,
    asset_class: str,
    timeframe: str,
    period: str,
    date_range: Dict[str, Optional[str]],
    records: List[Dict[str, Any]],
    equity_curve: List[Dict[str, Any]],
    continuous_id: Optional[str] = None,
    benchmark_comparison: Optional[Dict[str, Any]] = None,
    transaction_costs: Optional[Dict[str, Any]] = None,
    initial_cash: Optional[float] = None,
) -> Dict[str, Any]:
    """Aggregate closed ReplayRecords into a StrategyReport."""
    closed = [r for r in records if r.get("status") == "closed"]
    wins = [r for r in closed if (r.get("outcome") or {}).get("win_loss") == "win"]
    losses = [r for r in closed if (r.get("outcome") or {}).get("win_loss") == "loss"]

    gross_profit = sum((r.get("outcome") or {}).get("pnl") or 0 for r in wins)
    gross_loss = abs(sum((r.get("outcome") or {}).get("pnl") or 0 for r in losses))
    pnls = [(r.get("outcome") or {}).get("pnl") for r in closed if (r.get("outcome") or {}).get("pnl") is not None]

    decision_scores = [
        (r.get("scoring") or {}).get("decision_score")
        for r in closed
        if (r.get("scoring") or {}).get("decision_score") is not None
    ]
    outcome_scores = [
        (r.get("scoring") or {}).get("outcome_score")
        for r in closed
        if (r.get("scoring") or {}).get("outcome_score") is not None
    ]

    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    win_rate = round(len(wins) / len(closed), 2) if closed else None
    expectancy = round(sum(pnls) / len(pnls), 2) if pnls else None

    best, weak = _condition_analysis(closed)
    regime_performance = aggregate_regime_performance(closed)

    total_costs = (transaction_costs or {}).get("total_costs") or 0.0
    gross_metrics = gross_profit_metrics(closed, total_costs)
    confidence = assess_sample_confidence(len(closed))

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_type": "strategy",
        "report_id": new_report_id(),
        "generated_at": datetime.now().isoformat(),
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "instrument_id": instrument_id,
        "asset_class": asset_class,
        "continuous_id": continuous_id,
        "timeframe": timeframe,
        "period": period,
        "date_range": date_range,
        "initial_cash": initial_cash,
        "trade_count": len(closed),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "max_drawdown_pct": _max_drawdown_pct(equity_curve),
        "average_decision_score": _avg_int(decision_scores),
        "average_outcome_score": _avg_int(outcome_scores),
        "average_total_score": _avg_int([
            (r.get("scoring") or {}).get("total_score")
            for r in closed
            if (r.get("scoring") or {}).get("total_score") is not None
        ]),
        "total_pnl": round(sum(pnls), 2) if pnls else 0,
        "best_conditions": best,
        "weak_conditions": weak,
        "regime_performance": regime_performance,
        "record_ids": [r["id"] for r in closed],
        "benchmark_comparison": benchmark_comparison,
        "transaction_costs": transaction_costs,
        "gross_metrics": gross_metrics,
        "confidence": confidence,
    }
    return report


def _avg_int(values: List[int]) -> Optional[int]:
    if not values:
        return None
    return int(round(sum(values) / len(values)))


def _max_drawdown_pct(equity_curve: List[Dict[str, Any]]) -> Optional[float]:
    if len(equity_curve) < 2:
        return None
    peak = equity_curve[0].get("equity", 0)
    max_dd = 0.0
    for point in equity_curve:
        equity = float(point.get("equity") or 0)
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak * 100
            max_dd = max(max_dd, dd)
    return round(max_dd, 2)


def _condition_analysis(clords: List[Dict[str, Any]]) -> tuple:
    """Summarize conditions where strategy decision quality was strong vs weak."""
    from ..replay.pattern_features import extract_pattern_features

    high_decision: List[Dict[str, Any]] = []
    low_decision: List[Dict[str, Any]] = []
    for record in clords:
        score = (record.get("scoring") or {}).get("decision_score")
        if score is None:
            continue
        features = extract_pattern_features(record)
        bucket = {
            "trend": features.get("decision", {}).get("trend_state"),
            "volatility": features.get("decision", {}).get("volatility_state"),
            "setup_quality": features.get("decision", {}).get("setup_quality"),
            "win_loss": (record.get("outcome") or {}).get("win_loss"),
            "decision_score": score,
        }
        if score >= 75:
            high_decision.append(bucket)
        elif score < 60:
            low_decision.append(bucket)

    return _summarize_buckets(high_decision, "best"), _summarize_buckets(low_decision, "weak")


def _summarize_buckets(items: List[Dict[str, Any]], label: str) -> List[str]:
    if not items:
        return []
    notes: List[str] = []
    trends = Counter(i["trend"] for i in items if i.get("trend") and i["trend"] != "unknown")
    vols = Counter(i["volatility"] for i in items if i.get("volatility") and i["volatility"] != "unknown")
    setups = Counter(i["setup_quality"] for i in items if i.get("setup_quality") and i["setup_quality"] != "unknown")

    if trends:
        top, count = trends.most_common(1)[0]
        notes.append(f"{label.title()} trend state: {top} ({count} trades)")
    if vols:
        top, count = vols.most_common(1)[0]
        notes.append(f"{label.title()} volatility: {top} ({count} trades)")
    if setups:
        top, count = setups.most_common(1)[0]
        notes.append(f"{label.title()} setup quality: {top} ({count} trades)")

    wins = sum(1 for i in items if i.get("win_loss") == "win")
    if items:
        notes.append(f"Win rate in this bucket: {round(wins / len(items) * 100)}%")
    return notes[:4]
