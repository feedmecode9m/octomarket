"""Improvement tracking — compare recurring journal patterns across time."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional


class ImprovementTracker:
    """
    Split recurring pattern buckets into earlier vs later periods and compare stats.

    Detects improvement / regression from evidence — does not prescribe actions.
    """

    def track(
        self,
        entries: List[Dict[str, Any]],
        *,
        min_trades_per_period: int = 5,
        split_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for entry in entries:
            key = _pattern_key(entry)
            buckets[key].append(entry)

        findings: List[Dict[str, Any]] = []
        for key, items in buckets.items():
            dated = sorted(items, key=lambda e: e.get("date") or e.get("generated_at") or "")
            if len(dated) < min_trades_per_period * 2:
                continue
            midpoint = split_date or _midpoint_date(dated)
            if not midpoint:
                continue
            before = [e for e in dated if (e.get("date") or "") < midpoint]
            after = [e for e in dated if (e.get("date") or "") >= midpoint]
            if len(before) < min_trades_per_period or len(after) < min_trades_per_period:
                # Fall back to half-split when calendar split is unbalanced
                mid = len(dated) // 2
                before, after = dated[:mid], dated[mid:]
            if len(before) < min_trades_per_period or len(after) < min_trades_per_period:
                continue

            before_stats = _period_stats(before)
            after_stats = _period_stats(after)
            delta_r = None
            if before_stats.get("average_r_multiple") is not None and after_stats.get("average_r_multiple") is not None:
                delta_r = round(after_stats["average_r_multiple"] - before_stats["average_r_multiple"], 2)
            delta_wr = None
            if before_stats.get("win_rate") is not None and after_stats.get("win_rate") is not None:
                delta_wr = round(after_stats["win_rate"] - before_stats["win_rate"], 2)

            status = "insufficient_change"
            if delta_r is not None:
                if delta_r >= 0.4 or (delta_wr is not None and delta_wr >= 0.15):
                    status = "improvement_detected"
                elif delta_r <= -0.4 or (delta_wr is not None and delta_wr <= -0.15):
                    status = "regression_detected"

            strategy_id, regime = key.split("|", 1)
            findings.append({
                "pattern": {
                    "strategy_id": strategy_id,
                    "regime": regime,
                },
                "split_date": midpoint,
                "before": before_stats,
                "after": after_stats,
                "delta_r_multiple": delta_r,
                "delta_win_rate": delta_wr,
                "status": status,
                "evidence_only": True,
            })

        findings.sort(
            key=lambda f: abs(f.get("delta_r_multiple") or 0),
            reverse=True,
        )
        return findings


def _pattern_key(entry: Dict[str, Any]) -> str:
    strategy = entry.get("strategy_id") or "manual"
    mr = entry.get("market_regime") or {}
    active = mr.get("active_regimes") or []
    if active:
        regime = str(active[0])
    else:
        regime = mr.get("trend_state") or mr.get("volatility_state") or "unclassified"
    return f"{strategy}|{regime}"


def _midpoint_date(entries: List[Dict[str, Any]]) -> Optional[str]:
    dates = [e.get("date") for e in entries if e.get("date")]
    if not dates:
        return None
    return dates[len(dates) // 2]


def _period_stats(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    wins = [
        e for e in entries
        if (e.get("outcome_snapshot") or {}).get("win_loss") == "win"
    ]
    rs = [
        (e.get("outcome_snapshot") or {}).get("r_multiple")
        for e in entries
        if (e.get("outcome_snapshot") or {}).get("r_multiple") is not None
    ]
    dates = [e.get("date") for e in entries if e.get("date")]
    return {
        "period": {
            "from": dates[0] if dates else None,
            "to": dates[-1] if dates else None,
        },
        "trades": len(entries),
        "win_rate": round(len(wins) / len(entries), 2) if entries else None,
        "average_r_multiple": round(sum(rs) / len(rs), 2) if rs else None,
    }
