"""Pattern memory and deterministic performance queries over ReplayRecords."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from .pattern_features import PATTERN_SCHEMA_VERSION, extract_pattern_features
from .pattern_store import PatternStore, get_pattern_store
from .replay_store import ReplayStore, get_replay_store


class PatternService:
    """Index and query completed trades without duplicating ReplayRecords."""

    def __init__(
        self,
        pattern_store: Optional[PatternStore] = None,
        record_store: Optional[ReplayStore] = None,
    ):
        self._patterns = pattern_store or get_pattern_store()
        self._records = record_store or get_replay_store()

    def index_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract and persist pattern index for a closed, scored record."""
        if record.get("status") != "closed":
            return None
        pattern = extract_pattern_features(record)
        return self._patterns.upsert(pattern)

    def index_by_record_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        record = self._records.get(record_id)
        if not record:
            return None
        return self.index_record(record)

    def find_similar(
        self,
        record: Dict[str, Any],
        *,
        limit: int = 5,
        exclude_self: bool = True,
    ) -> Dict[str, Any]:
        """Find historically similar decisions and summarize performance."""
        features = extract_pattern_features(record)
        candidates = self._patterns.list_closed()
        scored: List[Tuple[int, Dict[str, Any]]] = []

        for candidate in candidates:
            if exclude_self and candidate["record_id"] == features["record_id"]:
                continue
            similarity = _similarity_score(features, candidate)
            if similarity > 0:
                scored.append((similarity, candidate))

        scored.sort(key=lambda item: item[0], reverse=True)
        matches = [item[1] for item in scored[: max(0, limit)]]
        summary = _summarize_matches(matches)

        return {
            "schema_version": PATTERN_SCHEMA_VERSION,
            "query_type": "similar",
            "source_record_id": features["record_id"],
            "source_plan_id": features.get("plan_id"),
            "criteria": _similarity_criteria(features),
            "match_count": len(matches),
            "matches": matches,
            "summary": summary,
        }

    def find_similar_by_plan_id(self, plan_id: str, *, limit: int = 5) -> Dict[str, Any]:
        record = self._records.get_by_plan_id(plan_id)
        if not record:
            return _empty_query_result("similar", plan_id=plan_id)
        return self.find_similar(record, limit=limit)

    def query(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Filter indexed patterns by instrument, session, quality, or outcome."""
        filters = filters or {}
        candidates = self._patterns.list_closed()
        matched = [p for p in candidates if _matches_filters(p, filters)]
        matched.sort(
            key=lambda p: (
                p.get("decision", {}).get("decision_score") or 0,
                p.get("indexed_at", ""),
            ),
            reverse=True,
        )

        limit = filters.get("limit")
        if isinstance(limit, int) and limit > 0:
            matched = matched[:limit]

        summary = _summarize_matches(matched)
        if filters.get("winners_only"):
            summary["filter_note"] = "Winners only"
        elif filters.get("losers_only"):
            summary["filter_note"] = "Losers only"
        elif filters.get("min_decision_score"):
            summary["filter_note"] = f"Decision score >= {filters['min_decision_score']}"

        return {
            "schema_version": PATTERN_SCHEMA_VERSION,
            "query_type": "filter",
            "filters": filters,
            "match_count": len(matched),
            "matches": matched,
            "summary": summary,
        }

    def common_failures(self, filters: Optional[Dict[str, Any]] = None, *, limit: int = 5) -> List[Dict[str, Any]]:
        result = self.query(filters or {})
        failures = Counter()
        for pattern in result["matches"]:
            for tag in pattern.get("failure_tags") or []:
                failures[tag] += 1
        return [
            {"tag": tag, "count": count}
            for tag, count in failures.most_common(limit)
        ]


def _similarity_score(source: Dict[str, Any], candidate: Dict[str, Any]) -> int:
    src_market = source.get("market") or {}
    cand_market = candidate.get("market") or {}
    src_decision = source.get("decision") or {}
    cand_decision = candidate.get("decision") or {}

    if src_market.get("asset_class") != cand_market.get("asset_class"):
        return 0

    score = 0

    if _same_instrument_identity(src_market, cand_market):
        score += 40
    else:
        return 0

    if src_decision.get("direction") == cand_decision.get("direction"):
        score += 15

    if src_market.get("session_venue") and src_market.get("session_venue") == cand_market.get("session_venue"):
        score += 10

    if src_decision.get("volatility_state") == cand_decision.get("volatility_state"):
        score += 10
    elif "unknown" not in (src_decision.get("volatility_state"), cand_decision.get("volatility_state")):
        score += 3

    if src_decision.get("trend_state") == cand_decision.get("trend_state"):
        score += 10
    elif "unknown" not in (src_decision.get("trend_state"), cand_decision.get("trend_state")):
        score += 3

    if src_decision.get("setup_quality") == cand_decision.get("setup_quality"):
        score += 10

    src_setup = src_decision.get("setup_score")
    cand_setup = cand_decision.get("setup_score")
    if src_setup is not None and cand_setup is not None and abs(src_setup - cand_setup) <= 15:
        score += 5

    src_rr = src_decision.get("risk_reward")
    cand_rr = cand_decision.get("risk_reward")
    if src_rr is not None and cand_rr is not None and abs(src_rr - cand_rr) <= 0.5:
        score += 5

    return score


def _same_instrument_identity(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    a_id = (a.get("instrument_id") or "").upper()
    b_id = (b.get("instrument_id") or "").upper()
    if a_id and a_id == b_id:
        return True
    a_cont = (a.get("continuous_id") or "").upper()
    b_cont = (b.get("continuous_id") or "").upper()
    if a_cont and a_cont == b_cont:
        return True
    return False


def _similarity_criteria(features: Dict[str, Any]) -> Dict[str, Any]:
    market = features.get("market") or {}
    decision = features.get("decision") or {}
    criteria: Dict[str, Any] = {
        "asset_class": market.get("asset_class"),
        "direction": decision.get("direction"),
    }
    if market.get("continuous_id"):
        criteria["continuous_id"] = market["continuous_id"]
    else:
        criteria["instrument_id"] = market.get("instrument_id")
    if market.get("session_venue"):
        criteria["session_venue"] = market["session_venue"]
    if decision.get("volatility_state") != "unknown":
        criteria["volatility_state"] = decision["volatility_state"]
    if decision.get("trend_state") != "unknown":
        criteria["trend_state"] = decision["trend_state"]
    if decision.get("setup_quality") != "unknown":
        criteria["setup_quality"] = decision["setup_quality"]
    return criteria


def _matches_filters(pattern: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    market = pattern.get("market") or {}
    decision = pattern.get("decision") or {}
    outcome = pattern.get("outcome") or {}

    instrument_id = filters.get("instrument_id")
    if instrument_id and (market.get("instrument_id") or "").upper() != instrument_id.upper():
        if not _same_instrument_identity(market, {"instrument_id": instrument_id, "continuous_id": filters.get("continuous_id")}):
            return False

    continuous_id = filters.get("continuous_id")
    if continuous_id and (market.get("continuous_id") or "").upper() != continuous_id.upper():
        return False

    asset_class = filters.get("asset_class")
    if asset_class and market.get("asset_class") != asset_class:
        return False

    session_venue = filters.get("session_venue")
    if session_venue and (market.get("session_venue") or "").upper() != session_venue.upper():
        return False

    direction = filters.get("direction")
    if direction and decision.get("direction") != direction.upper():
        return False

    volatility_state = filters.get("volatility_state")
    if volatility_state and decision.get("volatility_state") != volatility_state:
        return False

    trend_state = filters.get("trend_state")
    if trend_state and decision.get("trend_state") != trend_state:
        return False

    setup_quality = filters.get("setup_quality")
    if setup_quality and decision.get("setup_quality") != setup_quality:
        return False

    min_decision_score = filters.get("min_decision_score")
    if min_decision_score is not None:
        score = decision.get("decision_score")
        if score is None or score < int(min_decision_score):
            return False

    max_decision_score = filters.get("max_decision_score")
    if max_decision_score is not None:
        score = decision.get("decision_score")
        if score is None or score > int(max_decision_score):
            return False

    if filters.get("winners_only") and outcome.get("win_loss") != "win":
        return False
    if filters.get("losers_only") and outcome.get("win_loss") != "loss":
        return False

    return True


def _summarize_matches(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not matches:
        return {
            "trade_count": 0,
            "average_r_multiple": None,
            "average_decision_score": None,
            "average_total_score": None,
            "win_rate": None,
            "common_failures": [],
        }

    r_values = [m["outcome"]["r_multiple"] for m in matches if (m.get("outcome") or {}).get("r_multiple") is not None]
    decision_scores = [
        m["decision"]["decision_score"]
        for m in matches
        if (m.get("decision") or {}).get("decision_score") is not None
    ]
    total_scores = [
        m["outcome"]["total_score"]
        for m in matches
        if (m.get("outcome") or {}).get("total_score") is not None
    ]
    wins = sum(1 for m in matches if (m.get("outcome") or {}).get("win_loss") == "win")
    losses = sum(1 for m in matches if (m.get("outcome") or {}).get("win_loss") == "loss")
    decided = wins + losses

    failures = Counter()
    for pattern in matches:
        for tag in pattern.get("failure_tags") or []:
            failures[tag] += 1

    return {
        "trade_count": len(matches),
        "average_r_multiple": round(sum(r_values) / len(r_values), 2) if r_values else None,
        "average_decision_score": int(round(sum(decision_scores) / len(decision_scores))) if decision_scores else None,
        "average_total_score": int(round(sum(total_scores) / len(total_scores))) if total_scores else None,
        "win_rate": round(wins / decided, 2) if decided else None,
        "common_failures": [
            {"tag": tag, "count": count}
            for tag, count in failures.most_common(5)
        ],
    }


def _empty_query_result(query_type: str, *, plan_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "schema_version": PATTERN_SCHEMA_VERSION,
        "query_type": query_type,
        "source_plan_id": plan_id,
        "match_count": 0,
        "matches": [],
        "summary": _summarize_matches([]),
    }


_service_instance: Optional[PatternService] = None


def get_pattern_service(
    pattern_store: Optional[PatternStore] = None,
    record_store: Optional[ReplayStore] = None,
) -> PatternService:
    global _service_instance
    if pattern_store is not None or record_store is not None:
        return PatternService(pattern_store=pattern_store, record_store=record_store)
    if _service_instance is None:
        _service_instance = PatternService()
    return _service_instance


def reset_pattern_service() -> None:
    global _service_instance
    _service_instance = None


def index_closed_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Public helper — index after close without coupling to ReplayRecord model."""
    return get_pattern_service().index_record(record)
