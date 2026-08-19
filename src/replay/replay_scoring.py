"""Deterministic trade quality scoring from ReplayRecord artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..market.asset_class import AssetClass

SCORING_SCHEMA_VERSION = 1

DIMENSION_WEIGHTS = {
    "trend_alignment": 0.20,
    "session_quality": 0.15,
    "risk_reward": 0.20,
    "entry_quality": 0.15,
    "volatility_context": 0.10,
    "execution_quality": 0.20,
}


def score_replay_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score a replay record using only decision-time snapshot + plan + outcome.

    Does not use future data beyond what is stored on the record.
    """
    plan = record.get("trade_intent") or {}
    market = record.get("market") or {}
    snapshot = (record.get("decision_context") or {}).get("market_snapshot") or {}
    outcome = record.get("outcome") or {}
    execution = record.get("execution") or {}
    asset_class = market.get("asset_class", AssetClass.STOCK.value)
    direction = (plan.get("direction") or "LONG").upper()

    dimensions: Dict[str, Dict[str, Any]] = {
        "trend_alignment": _score_trend_alignment(snapshot, direction),
        "session_quality": _score_session_quality(market, snapshot, asset_class),
        "risk_reward": _score_risk_reward(plan, direction, asset_class),
        "entry_quality": _score_entry_quality(plan, snapshot, execution),
        "volatility_context": _score_volatility_context(plan, snapshot, asset_class, direction),
        "execution_quality": _score_execution_quality(plan, outcome, execution, record.get("status")),
    }

    total_score, completeness = _aggregate_score(dimensions, record.get("status"))
    reasons_positive, reasons_negative = _collect_reasons(dimensions)

    return {
        "total_score": total_score,
        "grade": _grade_from_score(total_score),
        "dimensions": dimensions,
        "reasons_positive": reasons_positive,
        "reasons_negative": reasons_negative,
        "completeness": completeness,
        "asset_class": asset_class,
        "instrument_id": market.get("instrument_id"),
        "continuous_id": market.get("continuous_id"),
        "scored_at": datetime.now().isoformat(),
        "schema_version": SCORING_SCHEMA_VERSION,
    }


def apply_scoring(record: Dict[str, Any]) -> Dict[str, Any]:
    """Compute scoring and attach to a replay record copy."""
    updated = dict(record)
    updated["scoring"] = score_replay_record(record)
    if updated.get("metadata"):
        updated["metadata"] = dict(updated["metadata"])
        updated["metadata"]["updated_at"] = datetime.now().isoformat()
    return updated


def _aggregate_score(dimensions: Dict[str, Dict[str, Any]], status: Optional[str]) -> Tuple[int, str]:
    weighted_sum = 0.0
    weight_total = 0.0
    for name, weight in DIMENSION_WEIGHTS.items():
        dim = dimensions.get(name) or {}
        if dim.get("skipped"):
            continue
        score = dim.get("score")
        if score is None:
            continue
        weighted_sum += float(score) * weight
        weight_total += weight

    if weight_total <= 0:
        return 0, _completeness(status, False)

    total = int(round(weighted_sum / weight_total))
    total = max(0, min(100, total))
    has_execution = not (dimensions.get("execution_quality") or {}).get("skipped", True)
    return total, _completeness(status, has_execution)


def _completeness(status: Optional[str], has_execution: bool) -> str:
    if status == "closed" and has_execution:
        return "full"
    if status in ("filled", "submitted", "planned"):
        return "partial"
    return "decision_only"


def _collect_reasons(dimensions: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    positive: List[str] = []
    negative: List[str] = []
    for dim in dimensions.values():
        for reason in dim.get("reasons_positive") or []:
            if reason not in positive:
                positive.append(reason)
        for reason in dim.get("reasons_negative") or []:
            if reason not in negative:
                negative.append(reason)
    return positive, negative


def _score_trend_alignment(snapshot: Dict[str, Any], direction: str) -> Dict[str, Any]:
    price = (snapshot.get("price") or {}).get("current")
    latest = (snapshot.get("indicators") or {}).get("latest") or {}
    sma20 = latest.get("SMA20")
    rsi = latest.get("RSI")

    score = 60
    reasons_pos: List[str] = []
    reasons_neg: List[str] = []

    if price is not None and sma20 is not None:
        if direction == "LONG":
            if price >= sma20:
                score += 20
                reasons_pos.append("Price aligned above SMA20 at decision time.")
            else:
                score -= 15
                reasons_neg.append("Long plan taken below SMA20 — weak trend alignment.")
        elif price <= sma20:
            score += 20
            reasons_pos.append("Price aligned below SMA20 at decision time.")
        else:
            score -= 15
            reasons_neg.append("Short plan taken above SMA20 — weak trend alignment.")

    if rsi is not None:
        if direction == "LONG":
            if 45 <= rsi <= 65:
                score += 10
                reasons_pos.append("RSI supported continuation without extreme extension.")
            elif rsi > 70:
                score -= 10
                reasons_neg.append("RSI was extended at entry — late trend participation.")
            elif rsi < 35:
                score += 5
                reasons_pos.append("RSI suggested oversold bounce potential.")
        else:
            if 35 <= rsi <= 55:
                score += 10
                reasons_pos.append("RSI supported bearish continuation without extreme extension.")
            elif rsi < 30:
                score -= 10
                reasons_neg.append("RSI was oversold at entry — poor short timing.")

    if not latest:
        reasons_neg.append("Limited indicator context in decision snapshot.")

    return _dimension_result("trend_alignment", max(0, min(100, score)), reasons_pos, reasons_neg)


def _score_session_quality(market: Dict[str, Any], snapshot: Dict[str, Any], asset_class: str) -> Dict[str, Any]:
    session = market.get("session") or (snapshot.get("instrument") or {}).get("session") or {}
    is_24h = bool(session.get("is_24h"))
    venue = session.get("venue", "")

    score = 70
    reasons_pos: List[str] = []
    reasons_neg: List[str] = []

    if asset_class == AssetClass.FOREX.value:
        if is_24h:
            score = 88
            reasons_pos.append("Forex 24h session provided continuous liquidity context.")
        else:
            score = 65
            reasons_neg.append("Forex session metadata incomplete for liquidity assessment.")
    elif asset_class == AssetClass.FUTURES.value:
        score = 82
        reasons_pos.append("Futures Globex-style session supported extended-hour context.")
        if market.get("continuous_id"):
            reasons_pos.append(f"Continuous identity preserved ({market['continuous_id']}).")
    else:
        if not is_24h:
            score = 78
            reasons_pos.append("Stock plan evaluated against regular-session liquidity context.")
        else:
            score = 70
            reasons_pos.append("Stock session marked extended — verify liquidity assumptions.")

    if venue:
        reasons_pos.append(f"Session venue recorded ({venue}).")

    return _dimension_result("session_quality", max(0, min(100, score)), reasons_pos, reasons_neg)


def _score_risk_reward(plan: Dict[str, Any], direction: str, asset_class: str) -> Dict[str, Any]:
    entry = _level_price(plan.get("entry"))
    stop = _level_price(plan.get("stop_loss"))
    target = _level_price(plan.get("target"))
    rr = plan.get("risk_reward")

    score = 55
    reasons_pos: List[str] = []
    reasons_neg: List[str] = []

    if entry and stop and target:
        valid_stop = (direction == "LONG" and stop < entry) or (direction == "SHORT" and stop > entry)
        valid_target = (direction == "LONG" and target > entry) or (direction == "SHORT" and target < entry)
        if valid_stop and valid_target:
            score += 15
            reasons_pos.append("Stop and target were directionally valid at plan time.")
        else:
            score -= 25
            reasons_neg.append("Plan levels were not valid for trade direction.")

    if rr is not None:
        if rr >= 2:
            score += 25
            reasons_pos.append("Risk/reward met the 2:1 guideline.")
        elif rr >= 1.5:
            score += 10
            reasons_pos.append("Acceptable risk/reward above 1.5:1.")
        else:
            score -= 15
            reasons_neg.append("Risk/reward below 1.5:1 — reward did not justify risk.")

    unit = plan.get("quantity_unit") or plan.get("unit_type")
    if asset_class == AssetClass.FOREX.value and plan.get("pip_risk"):
        reasons_pos.append(f"Pip risk defined ({plan['pip_risk']} pips).")
        score += 5
    elif asset_class == AssetClass.FUTURES.value and plan.get("tick_risk"):
        reasons_pos.append(f"Tick risk defined ({plan['tick_risk']} ticks).")
        score += 5
    elif asset_class == AssetClass.STOCK.value and plan.get("quantity"):
        reasons_pos.append("Share quantity specified in plan.")
        score += 5

    if plan.get("risk_amount"):
        reasons_pos.append("Dollar risk amount was calculated.")

    return _dimension_result("risk_reward", max(0, min(100, score)), reasons_pos, reasons_neg)


def _score_entry_quality(
    plan: Dict[str, Any],
    snapshot: Dict[str, Any],
    execution: Dict[str, Any],
) -> Dict[str, Any]:
    planned_entry = _level_price(plan.get("entry"))
    current = (snapshot.get("price") or {}).get("current")
    filled_entry = (execution.get("entry") or {}).get("price")
    reference = filled_entry or planned_entry

    score = 60
    reasons_pos: List[str] = []
    reasons_neg: List[str] = []

    if plan.get("thesis"):
        score += 10
        reasons_pos.append("Thesis documented at decision time.")
    else:
        score -= 10
        reasons_neg.append("No thesis documented in trade plan.")

    setup = plan.get("setup") or {}
    if setup.get("indicators") or setup.get("drawings"):
        score += 5
        reasons_pos.append("Setup context captured in plan.")

    structure_count = (snapshot.get("structure") or {}).get("drawing_count", 0)
    if structure_count:
        score += 5
        reasons_pos.append("Chart structure annotations were available at decision time.")

    if reference and current:
        diff_pct = abs(reference - current) / max(current, 1e-9) * 100
        if diff_pct <= 0.5:
            score += 20
            reasons_pos.append("Entry aligned closely with prevailing price at decision time.")
        elif diff_pct <= 2:
            score += 10
            reasons_pos.append("Entry was reasonably close to decision-time price.")
        else:
            score -= 10
            reasons_neg.append("Planned entry diverged from decision-time market price.")

    return _dimension_result("entry_quality", max(0, min(100, score)), reasons_pos, reasons_neg)


def _score_volatility_context(
    plan: Dict[str, Any],
    snapshot: Dict[str, Any],
    asset_class: str,
    direction: str,
) -> Dict[str, Any]:
    entry = _level_price(plan.get("entry"))
    stop = _level_price(plan.get("stop_loss"))
    volatility = (snapshot.get("price") or {}).get("volatility") or {}
    last_range = volatility.get("last_bar_range")

    score = 70
    reasons_pos: List[str] = []
    reasons_neg: List[str] = []

    if entry and stop and last_range and last_range > 0:
        stop_distance = abs(entry - stop)
        ratio = stop_distance / last_range
        if ratio >= 2:
            score += 15
            reasons_pos.append("Stop distance respected recent bar volatility.")
        elif ratio >= 1:
            score += 5
            reasons_pos.append("Stop distance matched recent volatility.")
        else:
            score -= 20
            reasons_neg.append("Stop was tight relative to recent bar volatility.")

    if asset_class == AssetClass.FOREX.value and plan.get("pip_risk"):
        if plan["pip_risk"] >= 15:
            reasons_pos.append("Forex stop allowed meaningful pip cushion.")
        elif plan["pip_risk"] < 8:
            reasons_neg.append("Forex stop risk was very tight in pip terms.")
            score -= 10
    elif asset_class == AssetClass.FUTURES.value and plan.get("tick_risk"):
        if plan["tick_risk"] >= 8:
            reasons_pos.append("Futures stop provided adequate tick cushion.")
        elif plan["tick_risk"] < 4:
            reasons_neg.append("Futures stop risk was very tight in tick terms.")
            score -= 10

    if not last_range:
        reasons_neg.append("Limited volatility context in decision snapshot.")

    return _dimension_result("volatility_context", max(0, min(100, score)), reasons_pos, reasons_neg)


def _score_execution_quality(
    plan: Dict[str, Any],
    outcome: Dict[str, Any],
    execution: Dict[str, Any],
    status: Optional[str],
) -> Dict[str, Any]:
    if status != "closed" or not execution.get("exit"):
        return _dimension_result(
            "execution_quality",
            None,
            [],
            ["Execution incomplete — outcome scoring deferred."],
            skipped=True,
        )

    score = 60
    reasons_pos: List[str] = []
    reasons_neg: List[str] = []

    win_loss = outcome.get("win_loss")
    r_multiple = outcome.get("r_multiple")
    exit_reason = outcome.get("exit_reason") or (execution.get("exit") or {}).get("reason")

    if win_loss == "win":
        score += 20
        reasons_pos.append("Trade closed profitably.")
    elif win_loss == "loss":
        score -= 20
        reasons_neg.append("Trade closed at a loss.")
    else:
        reasons_pos.append("Trade closed near breakeven.")

    if r_multiple is not None:
        if r_multiple >= 1.5:
            score += 20
            reasons_pos.append(f"Achieved strong R-multiple ({r_multiple}R).")
        elif r_multiple >= 1:
            score += 10
            reasons_pos.append(f"Achieved positive R-multiple ({r_multiple}R).")
        elif r_multiple <= -1:
            score -= 15
            reasons_neg.append(f"Loss exceeded planned risk ({r_multiple}R).")

    if exit_reason == "take_profit":
        score += 10
        reasons_pos.append("Exit followed planned take-profit path.")
    elif exit_reason == "stop_loss":
        reasons_neg.append("Exit triggered by stop — review invalidation level.")

    entry_fill = (execution.get("entry") or {}).get("price")
    planned_entry = _level_price(plan.get("entry"))
    if entry_fill and planned_entry:
        slip_pct = abs(entry_fill - planned_entry) / max(planned_entry, 1e-9) * 100
        if slip_pct <= 0.25:
            score += 5
            reasons_pos.append("Entry fill matched planned level closely.")
        elif slip_pct > 2:
            score -= 5
            reasons_neg.append("Entry fill diverged from planned level.")

    return _dimension_result("execution_quality", max(0, min(100, score)), reasons_pos, reasons_neg)


def _dimension_result(
    name: str,
    score: Optional[int],
    reasons_positive: List[str],
    reasons_negative: List[str],
    *,
    skipped: bool = False,
) -> Dict[str, Any]:
    return {
        "name": name,
        "score": score,
        "weight": DIMENSION_WEIGHTS[name],
        "reasons_positive": reasons_positive,
        "reasons_negative": reasons_negative,
        "skipped": skipped,
    }


def _grade_from_score(score: int) -> str:
    if score >= 90:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 75:
        return "B+"
    if score >= 65:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def _level_price(level: Any) -> Optional[float]:
    if level is None:
        return None
    if isinstance(level, dict):
        level = level.get("price")
    if level is None:
        return None
    return float(level)
