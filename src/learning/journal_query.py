"""Journal search — filter LearningJournalEntry artifacts by evidence fields."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class JournalQueryService:
    """Deterministic filters over stored journal entries. Read-only."""

    def search(
        self,
        entries: List[Dict[str, Any]],
        *,
        instrument_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        regime: Optional[str] = None,
        result: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        decision_score_min: Optional[float] = None,
        decision_score_max: Optional[float] = None,
        outcome_score_min: Optional[float] = None,
        outcome_score_max: Optional[float] = None,
        mode: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        filtered = [
            e
            for e in entries
            if _matches(
                e,
                instrument_id=instrument_id,
                strategy_id=strategy_id,
                regime=regime,
                result=result,
                date_from=date_from,
                date_to=date_to,
                decision_score_min=decision_score_min,
                decision_score_max=decision_score_max,
                outcome_score_min=outcome_score_min,
                outcome_score_max=outcome_score_max,
                mode=mode,
            )
        ]
        filtered.sort(key=lambda e: e.get("date") or e.get("generated_at") or "", reverse=True)
        limited = filtered[: max(0, limit)]
        return {
            "entries": limited,
            "count": len(limited),
            "total_matched": len(filtered),
            "filters": {
                "instrument_id": instrument_id,
                "strategy_id": strategy_id,
                "regime": regime,
                "result": result,
                "date_from": date_from,
                "date_to": date_to,
                "decision_score_min": decision_score_min,
                "decision_score_max": decision_score_max,
                "outcome_score_min": outcome_score_min,
                "outcome_score_max": outcome_score_max,
                "mode": mode,
            },
            "common_factors": _common_factors(limited),
        }


def _matches(
    entry: Dict[str, Any],
    *,
    instrument_id: Optional[str],
    strategy_id: Optional[str],
    regime: Optional[str],
    result: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    decision_score_min: Optional[float],
    decision_score_max: Optional[float],
    outcome_score_min: Optional[float],
    outcome_score_max: Optional[float],
    mode: Optional[str],
) -> bool:
    if instrument_id:
        key = instrument_id.upper()
        inst = (entry.get("instrument_id") or "").upper()
        cont = (entry.get("continuous_id") or "").upper()
        if key not in (inst, cont) and key not in inst and key not in cont:
            return False
    if strategy_id:
        sid = (entry.get("strategy_id") or "manual").lower()
        if sid != strategy_id.lower():
            return False
    if regime:
        if not _regime_match(entry, regime):
            return False
    if result:
        win_loss = ((entry.get("outcome_snapshot") or {}).get("win_loss") or "").lower()
        if win_loss != result.lower():
            return False
    date = entry.get("date") or ""
    if date_from and date and date < date_from:
        return False
    if date_to and date and date > date_to:
        return False
    decision = (entry.get("scoring_snapshot") or {}).get("decision_score")
    if decision_score_min is not None and (decision is None or decision < decision_score_min):
        return False
    if decision_score_max is not None and (decision is None or decision > decision_score_max):
        return False
    outcome = (entry.get("scoring_snapshot") or {}).get("outcome_score")
    if outcome_score_min is not None and (outcome is None or outcome < outcome_score_min):
        return False
    if outcome_score_max is not None and (outcome is None or outcome > outcome_score_max):
        return False
    if mode and (entry.get("mode") or "") != mode:
        return False
    return True


def _regime_match(entry: Dict[str, Any], regime: str) -> bool:
    needle = regime.lower().replace(" ", "_")
    mr = entry.get("market_regime") or {}
    active = [str(x).lower() for x in (mr.get("active_regimes") or [])]
    if needle in active:
        return True
    for field in ("trend_state", "volatility_state", "setup_quality"):
        if str(mr.get(field) or "").lower() == needle:
            return True
    return False


def _common_factors(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not entries:
        return {"sample_size": 0}
    regimes: Dict[str, int] = {}
    strategies: Dict[str, int] = {}
    decisions = []
    rs = []
    for e in entries:
        sid = e.get("strategy_id") or "manual"
        strategies[sid] = strategies.get(sid, 0) + 1
        mr = e.get("market_regime") or {}
        for r in mr.get("active_regimes") or []:
            regimes[str(r)] = regimes.get(str(r), 0) + 1
        d = (e.get("scoring_snapshot") or {}).get("decision_score")
        if d is not None:
            decisions.append(d)
        r_mult = (e.get("outcome_snapshot") or {}).get("r_multiple")
        if r_mult is not None:
            rs.append(r_mult)
    top_regime = max(regimes.items(), key=lambda kv: kv[1])[0] if regimes else None
    top_strategy = max(strategies.items(), key=lambda kv: kv[1])[0] if strategies else None
    return {
        "sample_size": len(entries),
        "top_regime": top_regime,
        "top_strategy": top_strategy,
        "average_decision_score": int(round(sum(decisions) / len(decisions))) if decisions else None,
        "average_r_multiple": round(sum(rs) / len(rs), 2) if rs else None,
        "regime_counts": regimes,
        "strategy_counts": strategies,
    }
