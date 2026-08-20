"""Strategy comparison reports — batch validation under identical conditions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .regime import REGIME_LABELS, best_regime_fit

COMPARISON_SCHEMA_VERSION = 1


def new_comparison_id() -> str:
    return str(uuid.uuid4())


def build_comparison_report(
    *,
    instrument_id: str,
    asset_class: str,
    timeframe: str,
    period: str,
    strategy_reports: List[Dict[str, Any]],
    continuous_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a side-by-side validation report for strategies tested under the same conditions."""
    if not strategy_reports:
        raise ValueError("At least one strategy report is required")

    date_range = _merge_date_ranges(strategy_reports)
    summaries = [_strategy_summary(r) for r in strategy_reports]

    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "report_type": "comparison",
        "comparison_id": new_comparison_id(),
        "generated_at": datetime.now().isoformat(),
        "instrument_id": instrument_id,
        "asset_class": asset_class,
        "continuous_id": continuous_id or strategy_reports[0].get("continuous_id"),
        "timeframe": timeframe,
        "period": period,
        "date_range": date_range,
        "strategy_count": len(strategy_reports),
        "strategies": summaries,
        "comparison_tables": {
            "profitability": _rank_table(summaries, "profit_factor", "profit_factor"),
            "decision_quality": _rank_table(summaries, "average_decision_score", "average_decision_score"),
            "outcome_quality": _rank_table(summaries, "average_outcome_score", "average_outcome_score"),
            "trade_frequency": _rank_table(summaries, "trade_count", "trade_count"),
            "drawdown": _rank_table(summaries, "max_drawdown_pct", "max_drawdown_pct", ascending=True),
        },
        "regime_analysis": {
            s["strategy_id"]: {
                "regimes": s.get("regime_performance") or {},
                "best_fit": best_regime_fit(s.get("regime_performance") or {}),
            }
            for s in summaries
        },
        "characteristics": _characteristic_notes(summaries, instrument_id, period),
        "individual_report_ids": [r.get("report_id") for r in strategy_reports],
    }


def _strategy_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "report_id": report.get("report_id"),
        "strategy_id": report.get("strategy_id"),
        "strategy_name": report.get("strategy_name"),
        "trade_count": report.get("trade_count", 0),
        "win_rate": report.get("win_rate"),
        "profit_factor": report.get("profit_factor"),
        "expectancy": report.get("expectancy"),
        "max_drawdown_pct": report.get("max_drawdown_pct"),
        "average_decision_score": report.get("average_decision_score"),
        "average_outcome_score": report.get("average_outcome_score"),
        "average_total_score": report.get("average_total_score"),
        "total_pnl": report.get("total_pnl"),
        "best_conditions": report.get("best_conditions") or [],
        "weak_conditions": report.get("weak_conditions") or [],
        "regime_performance": report.get("regime_performance") or {},
        "benchmark_comparison": report.get("benchmark_comparison"),
        "confidence": report.get("confidence"),
        "transaction_costs": report.get("transaction_costs"),
        "gross_metrics": report.get("gross_metrics"),
    }


def _merge_date_ranges(reports: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    starts = [r.get("date_range", {}).get("start") for r in reports if r.get("date_range")]
    ends = [r.get("date_range", {}).get("end") for r in reports if r.get("date_range")]
    return {
        "start": min(s for s in starts if s) if any(starts) else None,
        "end": max(e for e in ends if e) if any(ends) else None,
    }


def _rank_table(
    summaries: List[Dict[str, Any]],
    key: str,
    label: str,
    *,
    ascending: bool = False,
) -> List[Dict[str, Any]]:
    rows = []
    for item in summaries:
        value = item.get(key)
        if value is None:
            continue
        rows.append({
            "strategy_id": item["strategy_id"],
            "strategy_name": item["strategy_name"],
            label: value,
        })
    rows.sort(key=lambda r: r[label], reverse=not ascending)
    return rows


def _characteristic_notes(
    summaries: List[Dict[str, Any]],
    instrument_id: str,
    period: str,
) -> List[str]:
    """Neutral observations — characteristics, not winners."""
    if not summaries:
        return []

    notes: List[str] = [
        f"Under tested conditions on {instrument_id} over {period}, "
        f"{len(summaries)} strategies were evaluated on identical market data.",
    ]

    by_decision = sorted(
        summaries,
        key=lambda s: s.get("average_decision_score") or 0,
        reverse=True,
    )
    top_dec = by_decision[0]
    if top_dec.get("average_decision_score") is not None:
        notes.append(
            f"{top_dec['strategy_name']} showed the highest average decision score "
            f"({top_dec['average_decision_score']}) across {top_dec['trade_count']} trades."
        )

    by_pf = sorted(
        [s for s in summaries if s.get("profit_factor") is not None],
        key=lambda s: s.get("profit_factor") or 0,
        reverse=True,
    )
    if by_pf:
        notes.append(
            f"{by_pf[0]['strategy_name']} produced profit factor {by_pf[0]['profit_factor']} "
            f"with win rate {int((by_pf[0].get('win_rate') or 0) * 100)}% — outcome only, not decision quality."
        )

    for item in summaries:
        regimes = item.get("regime_performance") or {}
        fit = best_regime_fit(regimes)
        if fit:
            notes.append(f"{item['strategy_name']} strongest regime context: {fit[0]}")

    divergence = [
        s for s in summaries
        if s.get("average_decision_score") is not None
        and s.get("average_outcome_score") is not None
        and s["average_decision_score"] >= 75
        and (s.get("average_outcome_score") or 0) < 60
    ]
    for item in divergence:
        notes.append(
            f"{item['strategy_name']} had strong decision quality ({item['average_decision_score']}) "
            f"but weaker outcomes ({item['average_outcome_score']}) — possible variance, not necessarily a bad process."
        )

    return notes[:8]
