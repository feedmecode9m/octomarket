"""Deterministic feature extraction from completed ReplayRecords."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

PATTERN_SCHEMA_VERSION = 1

VOLATILITY_STATES = ("low", "normal", "high", "unknown")
TREND_STATES = ("aligned", "counter", "neutral", "unknown")
SETUP_QUALITY_BUCKETS = ("high", "medium", "low", "unknown")


def extract_pattern_features(record: Dict[str, Any]) -> Dict[str, Any]:
    """Build indexable pattern metadata from a replay record (no full record copy)."""
    market = record.get("market") or {}
    plan = record.get("trade_intent") or {}
    snapshot = (record.get("decision_context") or {}).get("market_snapshot") or {}
    scoring = record.get("scoring") or {}
    outcome = record.get("outcome") or {}
    categories = scoring.get("categories") or {}
    setup_score = (categories.get("setup") or {}).get("score")

    volatility_state = _classify_volatility(plan, snapshot, scoring)
    trend_state = _classify_trend(plan, snapshot, scoring)
    setup_bucket = _setup_quality_bucket(setup_score)

    session = market.get("session") or (snapshot.get("instrument") or {}).get("session") or {}
    direction = (plan.get("direction") or "LONG").upper()
    win_loss = outcome.get("win_loss")

    failure_tags = _extract_failure_tags(scoring)
    query_tags = _build_query_tags(
        market=market,
        direction=direction,
        session_venue=session.get("venue"),
        volatility_state=volatility_state,
        trend_state=trend_state,
        setup_bucket=setup_bucket,
        win_loss=win_loss,
        decision_score=scoring.get("decision_score"),
    )

    return {
        "schema_version": PATTERN_SCHEMA_VERSION,
        "record_id": record["id"],
        "plan_id": record.get("plan_id"),
        "status": record.get("status"),
        "mode": record.get("mode"),
        "indexed_at": datetime.now().isoformat(),
        "market": {
            "instrument_id": market.get("instrument_id"),
            "asset_class": market.get("asset_class"),
            "continuous_id": market.get("continuous_id"),
            "symbol": market.get("symbol"),
            "session_venue": session.get("venue"),
            "timeframe": (record.get("decision_context") or {}).get("timeframe"),
        },
        "decision": {
            "direction": direction,
            "risk_reward": plan.get("risk_reward"),
            "setup_score": setup_score,
            "setup_quality": setup_bucket,
            "decision_score": scoring.get("decision_score"),
            "volatility_state": volatility_state,
            "trend_state": trend_state,
        },
        "outcome": {
            "r_multiple": outcome.get("r_multiple"),
            "win_loss": win_loss,
            "total_score": scoring.get("total_score"),
            "pnl": outcome.get("pnl"),
        },
        "query_tags": query_tags,
        "failure_tags": failure_tags,
    }


def _classify_volatility(
    plan: Dict[str, Any],
    snapshot: Dict[str, Any],
    scoring: Dict[str, Any],
) -> str:
    dim = (scoring.get("dimensions") or {}).get("volatility_context") or {}
    for reason in dim.get("reasons_negative") or []:
        lower = reason.lower()
        if "tight relative" in lower or "very tight" in lower:
            return "high"
    for reason in dim.get("reasons_positive") or []:
        lower = reason.lower()
        if "respected recent bar volatility" in lower or "adequate" in lower:
            return "normal"

    entry = _level_price(plan.get("entry"))
    stop = _level_price(plan.get("stop_loss"))
    last_range = ((snapshot.get("price") or {}).get("volatility") or {}).get("last_bar_range")
    if entry and stop and last_range and last_range > 0:
        ratio = abs(entry - stop) / last_range
        if ratio >= 2:
            return "normal"
        if ratio >= 1:
            return "normal"
        return "high"
    return "unknown"


def _classify_trend(
    plan: Dict[str, Any],
    snapshot: Dict[str, Any],
    scoring: Dict[str, Any],
) -> str:
    dim = (scoring.get("dimensions") or {}).get("trend_alignment") or {}
    score = dim.get("score")
    if score is not None:
        if score >= 75:
            return "aligned"
        if score <= 45:
            return "counter"
        return "neutral"

    direction = (plan.get("direction") or "LONG").upper()
    price = (snapshot.get("price") or {}).get("current")
    sma20 = ((snapshot.get("indicators") or {}).get("latest") or {}).get("SMA20")
    if price is None or sma20 is None:
        return "unknown"
    if direction == "LONG":
        return "aligned" if price >= sma20 else "counter"
    return "aligned" if price <= sma20 else "counter"


def _setup_quality_bucket(setup_score: Optional[int]) -> str:
    if setup_score is None:
        return "unknown"
    if setup_score >= 75:
        return "high"
    if setup_score >= 55:
        return "medium"
    return "low"


def _extract_failure_tags(scoring: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    for dim in (scoring.get("dimensions") or {}).values():
        for reason in dim.get("reasons_negative") or []:
            tag = _normalize_failure_tag(reason)
            if tag and tag not in tags:
                tags.append(tag)
    return tags


def _normalize_failure_tag(reason: str) -> str:
    lower = reason.lower()
    if "late trend" in lower or "extended at entry" in lower:
        return "late_entry"
    if "below sma20" in lower or "above sma20" in lower or "weak trend" in lower:
        return "poor_trend_alignment"
    if "risk/reward below" in lower or "below 1.5" in lower:
        return "poor_risk_reward"
    if "tight relative" in lower or "very tight" in lower:
        return "tight_stop"
    if "no thesis" in lower:
        return "missing_thesis"
    if "diverged from" in lower and "entry" in lower:
        return "entry_divergence"
    if "stop level" in lower or "invalid" in lower:
        return "invalid_levels"
    if "unknown" in lower:
        return "missing_context"
    return reason[:80]


def _build_query_tags(
    *,
    market: Dict[str, Any],
    direction: str,
    session_venue: Optional[str],
    volatility_state: str,
    trend_state: str,
    setup_bucket: str,
    win_loss: Optional[str],
    decision_score: Optional[int],
) -> List[str]:
    tags = [
        f"asset:{market.get('asset_class', 'unknown')}",
        f"instrument:{(market.get('instrument_id') or '').upper()}",
        f"direction:{direction}",
        f"volatility:{volatility_state}",
        f"trend:{trend_state}",
        f"setup:{setup_bucket}",
    ]
    if market.get("continuous_id"):
        tags.append(f"continuous:{market['continuous_id'].upper()}")
    if session_venue:
        tags.append(f"session:{session_venue.upper()}")
    if win_loss:
        tags.append(f"result:{win_loss}")
    if decision_score is not None:
        if decision_score >= 75:
            tags.append("decision:high")
        elif decision_score < 55:
            tags.append("decision:low")
        else:
            tags.append("decision:medium")
    return tags


def _level_price(level: Any) -> Optional[float]:
    if level is None:
        return None
    if isinstance(level, dict):
        level = level.get("price")
    if level is None:
        return None
    return float(level)
