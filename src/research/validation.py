"""Strategy validation — batch evaluation and comparison under identical conditions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..market.instrument import resolve_instrument
from ..strategies.registry import get_strategy_registry
from .comparison import build_comparison_report
from .runner import StrategyBacktestRunner
from .store import ResearchReportStore, get_research_report_store


class StrategyValidationService:
    """Run all compatible strategies on the same instrument/period and compare results."""

    def __init__(
        self,
        runner: Optional[StrategyBacktestRunner] = None,
        report_store: Optional[ResearchReportStore] = None,
    ):
        self._runner = runner or StrategyBacktestRunner()
        self._reports = report_store or get_research_report_store()
        self._registry = get_strategy_registry()

    def run_batch(
        self,
        instrument_id: str,
        *,
        period: str = "6mo",
        interval: str = "1d",
        initial_cash: float = 10000.0,
        cooldown_bars: int = 1,
        max_trades: Optional[int] = None,
        strategy_ids: Optional[List[str]] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Evaluate all (or selected) compatible strategies and return a comparison report."""
        instrument = resolve_instrument(instrument_id)
        asset_class = instrument.asset_class.value

        if strategy_ids:
            candidates = strategy_ids
        else:
            candidates = [s["id"] for s in self._registry.list_by_asset_class(asset_class)]

        individual_reports: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        for strategy_id in candidates:
            strategy = self._registry.get(strategy_id)
            if not strategy or asset_class not in strategy.asset_classes:
                errors.append({"strategy_id": strategy_id, "error": "Not compatible with instrument"})
                continue
            try:
                report = self._runner.run(
                    strategy_id,
                    instrument.instrument_id,
                    period=period,
                    interval=interval,
                    initial_cash=initial_cash,
                    cooldown_bars=cooldown_bars,
                    max_trades=max_trades,
                    persist_report=persist,
                )
                individual_reports.append(report)
            except ValueError as exc:
                errors.append({"strategy_id": strategy_id, "error": str(exc)})

        if not individual_reports:
            raise ValueError("No strategy reports produced")

        comparison = build_comparison_report(
            instrument_id=instrument.instrument_id,
            asset_class=asset_class,
            timeframe=interval,
            period=period,
            strategy_reports=individual_reports,
            continuous_id=instrument.continuous_id,
        )
        if errors:
            comparison["errors"] = errors

        if persist:
            self._reports.save(comparison)
        return comparison


_service_instance: Optional[StrategyValidationService] = None


def get_strategy_validation_service() -> StrategyValidationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = StrategyValidationService()
    return _service_instance
