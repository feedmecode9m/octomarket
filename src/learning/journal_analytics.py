"""Journal analytics facade — profile, search, improvement, recommendation context."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .improvement_tracker import ImprovementTracker
from .journal_query import JournalQueryService
from .journal_service import LearningJournalService, get_learning_journal_service
from .journal_profile import JournalTraderProfileService


class JournalAnalyticsService:
    """
    Read-only analytics over LearningJournalEntry memory.

    Never creates TradePlans, Orders, or mutates ReplayRecords / scoring.
    """

    def __init__(
        self,
        journal: Optional[LearningJournalService] = None,
        *,
        query: Optional[JournalQueryService] = None,
        profile: Optional[JournalTraderProfileService] = None,
        improvements: Optional[ImprovementTracker] = None,
    ):
        self._journal = journal or get_learning_journal_service()
        self._query = query or JournalQueryService()
        self._profile = profile or JournalTraderProfileService()
        self._improvements = improvements or ImprovementTracker()

    def _all_entries(self, limit: int = 5000) -> List[Dict[str, Any]]:
        return self._journal.list_entries(limit=limit)

    def trader_profile(self, *, min_trades: int = 5) -> Dict[str, Any]:
        return self._profile.build_profile(self._all_entries(), min_trades=min_trades)

    def search(self, **filters) -> Dict[str, Any]:
        return self._query.search(self._all_entries(), **filters)

    def improvement_tracking(
        self,
        *,
        min_trades_per_period: int = 5,
        split_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        findings = self._improvements.track(
            self._all_entries(),
            min_trades_per_period=min_trades_per_period,
            split_date=split_date,
        )
        return {
            "findings": findings,
            "count": len(findings),
            "evidence_only": True,
        }

    def recommendation_context(
        self,
        *,
        instrument_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        strategy_family: Optional[str] = None,
        min_trades: int = 5,
    ) -> Dict[str, Any]:
        """
        Historical trader context for recommendation UIs.

        Read-only decision support. Never alters recommendation ranking weights
        into execution — callers must keep human approval required.
        """
        entries = self._all_entries()
        if instrument_id:
            entries = [
                e
                for e in entries
                if (e.get("instrument_id") or "").upper() == instrument_id.upper()
                or (e.get("continuous_id") or "").upper() == instrument_id.upper()
            ]

        profile = self._profile.build_profile(entries, min_trades=min_trades)
        matched_strength = None
        matched_weakness = None
        target = (strategy_family or strategy_id or "").lower()

        if target:
            for item in profile.get("strengths") or []:
                if target in (item.get("area") or "").lower() or target == (item.get("area") or "").lower():
                    matched_strength = item
                    break
            for item in profile.get("weaknesses") or []:
                if target in (item.get("area") or "").lower() or target == (item.get("area") or "").lower():
                    matched_weakness = item
                    break

        if matched_strength:
            alignment = "positive"
            narrative = (
                f"Trader history: positive results in {matched_strength['area']} "
                f"({matched_strength['evidence']}, avg R {matched_strength.get('avg_R')}). "
                "Evidence alignment only — human approval still required."
            )
            evidence = matched_strength
        elif matched_weakness:
            alignment = "negative"
            narrative = (
                f"Trader history: weaker results in {matched_weakness['area']} "
                f"({matched_weakness['evidence']}, avg R {matched_weakness.get('avg_R')}). "
                "Treat as caution context only — human approval still required."
            )
            evidence = matched_weakness
        elif len(entries) < min_trades:
            alignment = "insufficient"
            narrative = (
                "Trader history: insufficient journal samples for this instrument/setup. "
                "No additional confidence adjustment."
            )
            evidence = {"trade_count": len(entries)}
        else:
            alignment = "neutral"
            narrative = (
                "Trader history available but no clear strength/weakness match for this family. "
                "Human approval still required."
            )
            evidence = {"sample_size": len(entries)}

        return {
            "decision_support_only": True,
            "read_only": True,
            "does_not_create_plans": True,
            "does_not_create_orders": True,
            "does_not_alter_execution": True,
            "trader_history": {
                "alignment": alignment,
                "instrument_id": instrument_id,
                "strategy_id": strategy_id,
                "strategy_family": strategy_family,
                "evidence": evidence,
                "narrative": narrative,
            },
        }


_analytics_instance: Optional[JournalAnalyticsService] = None


def get_journal_analytics_service() -> JournalAnalyticsService:
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = JournalAnalyticsService()
    return _analytics_instance


def reset_journal_analytics_service() -> None:
    global _analytics_instance
    _analytics_instance = None
