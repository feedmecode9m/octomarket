"""Journal-derived trader profile — historical performance patterns only."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from ..strategies.registry import get_strategy_registry


class JournalTraderProfileService:
    """
    Derive strengths/weaknesses from LearningJournalEntry statistics.

    Labels describe historical performance patterns — never permanent identity labels.
    Distinct from learning.trader_profile.TraderProfile (mentor coaching state).
    """

    def build_profile(
        self,
        entries: List[Dict[str, Any]],
        *,
        min_trades: int = 5,
    ) -> Dict[str, Any]:
        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for entry in entries:
            area = _area_label(entry)
            buckets[area].append(entry)

        strengths: List[Dict[str, Any]] = []
        weaknesses: List[Dict[str, Any]] = []
        observed: List[Dict[str, Any]] = []

        for area, items in buckets.items():
            stats = _area_stats(area, items)
            observed.append(stats)
            if stats["trade_count"] < min_trades:
                continue
            avg_r = stats.get("avg_R")
            if avg_r is None:
                continue
            if avg_r >= 0.25 and (stats.get("avg_decision_score") or 0) >= 65:
                strengths.append(stats)
            elif avg_r <= -0.25:
                weaknesses.append(stats)

        strengths.sort(key=lambda s: (s.get("avg_R") or 0, s.get("trade_count") or 0), reverse=True)
        weaknesses.sort(key=lambda s: (s.get("avg_R") or 0, -(s.get("trade_count") or 0)))

        return {
            "profile_type": "historical_performance_pattern",
            "sample_size": len(entries),
            "min_trades": min_trades,
            "strengths": strengths[:8],
            "weaknesses": weaknesses[:8],
            "observed_areas": sorted(observed, key=lambda s: s.get("trade_count") or 0, reverse=True),
            "disclaimer": (
                "Patterns describe historical journal evidence only. "
                "They are not permanent labels and do not authorize trades."
            ),
        }


def _area_label(entry: Dict[str, Any]) -> str:
    strategy_id = (entry.get("strategy_id") or "").lower()
    if strategy_id:
        try:
            strategy = get_strategy_registry().get(strategy_id)
            if strategy and getattr(strategy, "family", None):
                return str(strategy.family)
        except Exception:
            pass
        if "trend" in strategy_id:
            return "trend_following"
        if "mean" in strategy_id or "reversion" in strategy_id:
            return "mean_reversion"
        if "breakout" in strategy_id:
            return "breakout"
        if "momentum" in strategy_id:
            return "momentum"
        return strategy_id

    mr = entry.get("market_regime") or {}
    trend = (mr.get("trend_state") or "").lower()
    if trend == "aligned":
        return "trend_continuation"
    if trend in ("counter", "neutral"):
        return "countertrend"
    vol = (mr.get("volatility_state") or "").lower()
    if vol == "high":
        return "high_volatility_entries"
    return "unclassified"


def _area_stats(area: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    wins = [
        e for e in items
        if (e.get("outcome_snapshot") or {}).get("win_loss") == "win"
    ]
    rs = [
        (e.get("outcome_snapshot") or {}).get("r_multiple")
        for e in items
        if (e.get("outcome_snapshot") or {}).get("r_multiple") is not None
    ]
    decisions = [
        (e.get("scoring_snapshot") or {}).get("decision_score")
        for e in items
        if (e.get("scoring_snapshot") or {}).get("decision_score") is not None
    ]
    return {
        "area": area,
        "evidence": f"{len(items)} trades",
        "trade_count": len(items),
        "win_rate": round(len(wins) / len(items), 2) if items else None,
        "avg_R": round(sum(rs) / len(rs), 2) if rs else None,
        "avg_decision_score": int(round(sum(decisions) / len(decisions))) if decisions else None,
        "entry_ids": [e.get("id") for e in items[:24]],
    }
