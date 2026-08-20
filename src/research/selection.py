"""Adaptive strategy selection — decision support, not autonomous trading."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..market.instrument import resolve_instrument
from ..strategies.registry import get_strategy_registry
from .confidence import LOW_CONFIDENCE_THRESHOLD, assess_sample_confidence
from .degradation import assess_performance_degradation
from .market_context import detect_market_context
from .store import ResearchReportStore, get_research_report_store

SELECTION_SCHEMA_VERSION = 1

FAMILY_REGIME_FIT = {
    "trend_following": ("trending",),
    "breakout": ("trending", "high_volatility"),
    "momentum": ("trending",),
    "mean_reversion": ("ranging", "low_volatility"),
    "carry_momentum": ("low_volatility", "trending"),
}

EXCLUDED_CONFIDENCE = ("none", "low")


class AdaptiveStrategySelector:
    """Match current market context to historical strategy characteristics."""

    def __init__(
        self,
        report_store: Optional[ResearchReportStore] = None,
        registry=None,
    ):
        self._reports = report_store or get_research_report_store()
        self._registry = registry or get_strategy_registry()

    def recommend(
        self,
        instrument_id: str,
        *,
        timeframe: str = "1d",
        period: str = "3mo",
        market_context: Optional[Dict[str, Any]] = None,
        strategy_reports: Optional[List[Dict[str, Any]]] = None,
        walk_forward_reports: Optional[List[Dict[str, Any]]] = None,
        min_trades: int = LOW_CONFIDENCE_THRESHOLD,
        require_cost_adjusted_edge: bool = True,
    ) -> Dict[str, Any]:
        instrument = resolve_instrument(instrument_id)
        context = market_context or detect_market_context(
            instrument.instrument_id,
            timeframe=timeframe,
            period=period,
        )
        reports = strategy_reports
        if reports is None:
            reports = self._reports.list_strategy_reports(
                instrument_id=instrument.instrument_id,
                asset_class=instrument.asset_class.value,
            )
            if not reports:
                reports = self._reports.list_strategy_reports(asset_class=instrument.asset_class.value)

        wf_reports = walk_forward_reports
        if wf_reports is None:
            wf_reports = self._reports.list_walk_forward(instrument_id=instrument.instrument_id)

        matches, rejected, warnings = self._match_reports(
            reports,
            context,
            wf_reports or [],
            min_trades=min_trades,
            require_cost_adjusted_edge=require_cost_adjusted_edge,
        )

        data_quality = context.get("data_quality") or {}
        warnings.extend(data_quality.get("warnings") or [])

        recommendation = self._build_recommendation(matches, context, warnings)
        return {
            "schema_version": SELECTION_SCHEMA_VERSION,
            "report_type": "recommendation",
            "generated_at": datetime.now().isoformat(),
            "instrument_id": instrument.instrument_id,
            "asset_class": instrument.asset_class.value,
            "market_context": context,
            "recommendation": recommendation,
            "candidates": matches,
            "rejected": rejected,
            "warnings": _unique(warnings + (recommendation.get("warnings") or [])),
            "decision_support_only": True,
        }

    def _match_reports(
        self,
        reports: List[Dict[str, Any]],
        context: Dict[str, Any],
        walk_forwards: List[Dict[str, Any]],
        *,
        min_trades: int,
        require_cost_adjusted_edge: bool,
    ) -> tuple:
        active = set(context.get("active_regimes") or [])
        asset_class = context.get("asset_class")
        wf_by_strategy = {
            w.get("strategy_id"): w
            for w in walk_forwards
            if w.get("strategy_id")
        }

        matches: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for report in reports:
            if asset_class and report.get("asset_class") and report["asset_class"] != asset_class:
                continue
            strategy = self._registry.get(report.get("strategy_id", ""))
            family = (strategy.family if strategy else None) or report.get("family") or "unknown"
            fit_regimes = FAMILY_REGIME_FIT.get(family, ())
            if fit_regimes and active and not active.intersection(fit_regimes):
                rejected.append({
                    "strategy_id": report.get("strategy_id"),
                    "strategy_family": family,
                    "reason": "Family does not historically fit the current regime set.",
                })
                continue

            matched_regimes = _matched_regime_metrics(report, active)
            sample_count = _regime_sample_count(matched_regimes, report)
            confidence = assess_sample_confidence(sample_count)
            overall = report.get("confidence") or {}
            overall_level = overall.get("confidence_level")
            net_pf = report.get("profit_factor")
            gross_pf = (report.get("gross_metrics") or {}).get("profit_factor_gross")
            candidate_warnings: List[str] = list(confidence.get("warnings") or [])

            wf = wf_by_strategy.get(report.get("strategy_id"))
            degradation = assess_performance_degradation((wf or {}).get("windows") or [])
            if degradation["detected"]:
                candidate_warnings.extend(degradation["warnings"])

            reject_reason = None
            if overall_level in EXCLUDED_CONFIDENCE or confidence["confidence_level"] in EXCLUDED_CONFIDENCE:
                reject_reason = "low confidence"
            elif sample_count < min_trades:
                reject_reason = "insufficient regime sample"
            elif require_cost_adjusted_edge and net_pf is not None and net_pf < 1.0:
                reject_reason = "cost-adjusted profit factor below 1.0"

            payload = {
                "strategy_id": report.get("strategy_id"),
                "strategy_name": report.get("strategy_name"),
                "strategy_family": family,
                "report_id": report.get("report_id"),
                "historical_conditions": {
                    "matched_regimes": matched_regimes,
                    "active_regimes": sorted(active),
                    "best_conditions": report.get("best_conditions") or [],
                },
                "trade_count": sample_count,
                "overall_trade_count": report.get("trade_count", 0),
                "profit_factor": net_pf,
                "profit_factor_gross": gross_pf,
                "oos_profit_factor": degradation.get("oos_pf"),
                "average_decision_score": _matched_decision_score(matched_regimes, report),
                "confidence": confidence,
                "degradation": degradation,
                "supporting_records": (report.get("record_ids") or [])[:12],
                "warnings": candidate_warnings,
            }

            if reject_reason:
                payload["reason"] = reject_reason
                rejected.append(payload)
                continue
            matches.append(payload)

        matches.sort(
            key=lambda m: (
                m.get("average_decision_score") or 0,
                m.get("oos_profit_factor") or m.get("profit_factor") or 0,
                m.get("trade_count") or 0,
            ),
            reverse=True,
        )
        return matches, rejected, []

    def _build_recommendation(
        self,
        matches: List[Dict[str, Any]],
        context: Dict[str, Any],
        warnings: List[str],
    ) -> Dict[str, Any]:
        if not matches:
            return {
                "strategy_family": None,
                "confidence": "none",
                "historical_conditions": {
                    "active_regimes": context.get("active_regimes") or [],
                    "trend_state": context.get("trend_state"),
                    "volatility_state": context.get("volatility_state"),
                },
                "supporting_records": [],
                "warnings": warnings + [
                    "No strategy family met reliability filters under current conditions.",
                ],
                "narrative": (
                    "No recommendation. Either research coverage is missing or surviving "
                    "samples are too small / cost-adjusted results are not viable."
                ),
            }

        top = matches[0]
        family = top["strategy_family"]
        family_matches = [m for m in matches if m["strategy_family"] == family]
        conf_levels = [m["confidence"]["confidence_level"] for m in family_matches]
        confidence = "high" if "high" in conf_levels else (conf_levels[0] if conf_levels else "moderate")

        rec_warnings = list(warnings)
        for item in family_matches:
            rec_warnings.extend(item.get("warnings") or [])

        supporting = []
        for item in family_matches:
            supporting.extend(item.get("supporting_records") or [])

        names = ", ".join(m["strategy_name"] for m in family_matches)
        regimes = ", ".join(context.get("active_regimes") or []) or "unclassified"
        narrative = (
            f"{_family_label(family)} historically matched these conditions ({regimes}). "
            f"Evidence from {names}. Human approval is still required before a TradePlan is created."
        )
        return {
            "strategy_family": family,
            "confidence": confidence,
            "historical_conditions": {
                "active_regimes": context.get("active_regimes") or [],
                "trend_state": context.get("trend_state"),
                "volatility_state": context.get("volatility_state"),
                "session_quality": context.get("session_quality"),
                "matched_strategies": [
                    {
                        "strategy_id": m["strategy_id"],
                        "strategy_name": m["strategy_name"],
                        "trade_count": m["trade_count"],
                        "profit_factor": m["profit_factor"],
                        "oos_profit_factor": m.get("oos_profit_factor"),
                        "average_decision_score": m["average_decision_score"],
                    }
                    for m in family_matches
                ],
            },
            "supporting_records": supporting[:24],
            "warnings": _unique(rec_warnings),
            "narrative": narrative,
        }


def _matched_regime_metrics(report: Dict[str, Any], active: set) -> Dict[str, Any]:
    regimes = report.get("regime_performance") or {}
    if not active:
        return regimes
    return {name: metrics for name, metrics in regimes.items() if name in active}


def _regime_sample_count(matched: Dict[str, Any], report: Dict[str, Any]) -> int:
    if matched:
        return max(int(m.get("trade_count") or 0) for m in matched.values())
    return int(report.get("trade_count") or 0)


def _matched_decision_score(matched: Dict[str, Any], report: Dict[str, Any]) -> Optional[int]:
    scores = [
        m.get("average_decision_score")
        for m in matched.values()
        if m.get("average_decision_score") is not None
    ]
    if scores:
        return int(round(sum(scores) / len(scores)))
    return report.get("average_decision_score")


def preferred_strategy_from_recommendation(payload: Dict[str, Any]) -> Optional[str]:
    """Pick the highest-evidence strategy id from a recommendation payload. No side effects."""
    rec = payload.get("recommendation") if "recommendation" in payload else payload
    if not isinstance(rec, dict):
        return None
    matched = ((rec.get("historical_conditions") or {}).get("matched_strategies") or [])
    if matched:
        return matched[0].get("strategy_id")
    candidates = payload.get("candidates") or []
    if candidates:
        return candidates[0].get("strategy_id")
    return None


def _family_label(family: str) -> str:
    return {
        "trend_following": "Trend family",
        "breakout": "Breakout family",
        "momentum": "Momentum family",
        "mean_reversion": "Mean-reversion family",
        "carry_momentum": "Carry-momentum family",
    }.get(family, family.replace("_", " ").title())


def _unique(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


_selector_instance: Optional[AdaptiveStrategySelector] = None


def get_adaptive_strategy_selector() -> AdaptiveStrategySelector:
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = AdaptiveStrategySelector()
    return _selector_instance
