"""Walk-forward evaluation — research, validation, and out-of-sample windows."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..market.instrument import resolve_instrument
from .dates import resolve_walk_forward_windows
from .runner import StrategyBacktestRunner
from .store import ResearchReportStore, get_research_report_store

WALK_FORWARD_SCHEMA_VERSION = 1


def new_walk_forward_id() -> str:
    return str(uuid.uuid4())


class WalkForwardService:
    """Run the same strategy across sequential date windows without parameter tuning."""

    def __init__(
        self,
        runner: Optional[StrategyBacktestRunner] = None,
        report_store: Optional[ResearchReportStore] = None,
    ):
        self._runner = runner or StrategyBacktestRunner()
        self._reports = report_store or get_research_report_store()

    def run(
        self,
        strategy_id: str,
        instrument_id: str,
        *,
        period: str = "2y",
        interval: str = "1d",
        initial_cash: float = 10000.0,
        cooldown_bars: int = 1,
        max_trades: Optional[int] = None,
        windows: Optional[List[Dict[str, str]]] = None,
        research_ratio: float = 0.5,
        validation_ratio: float = 0.25,
        out_of_sample_ratio: float = 0.25,
        persist: bool = True,
    ) -> Dict[str, Any]:
        instrument = resolve_instrument(instrument_id)
        from ..market.data_provider import get_market_data_provider

        ohlcv = get_market_data_provider().candles(
            instrument.instrument_id,
            interval,
            period=period,
        )
        if ohlcv.empty:
            raise ValueError("No historical data for walk-forward evaluation")

        window_defs = resolve_walk_forward_windows(
            ohlcv,
            windows=windows,
            research_ratio=research_ratio,
            validation_ratio=validation_ratio,
            out_of_sample_ratio=out_of_sample_ratio,
        )

        window_reports: List[Dict[str, Any]] = []
        for window in window_defs:
            report = self._runner.run(
                strategy_id,
                instrument.instrument_id,
                period=period,
                interval=interval,
                initial_cash=initial_cash,
                cooldown_bars=cooldown_bars,
                max_trades=max_trades,
                start_date=window["start"],
                end_date=window["end"],
                persist_report=persist,
            )
            window_reports.append({
                "window": window,
                "report": _window_summary(report),
            })

        payload = build_walk_forward_report(
            strategy_id=strategy_id,
            strategy_name=window_reports[0]["report"].get("strategy_name", strategy_id),
            instrument_id=instrument.instrument_id,
            asset_class=instrument.asset_class.value,
            continuous_id=instrument.continuous_id,
            timeframe=interval,
            period=period,
            windows=window_reports,
        )
        if persist:
            self._reports.save(payload)
        return payload


def _window_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "report_id": report.get("report_id"),
        "strategy_id": report.get("strategy_id"),
        "strategy_name": report.get("strategy_name"),
        "date_range": report.get("date_range"),
        "trade_count": report.get("trade_count"),
        "win_rate": report.get("win_rate"),
        "profit_factor": report.get("profit_factor"),
        "profit_factor_gross": (report.get("gross_metrics") or {}).get("profit_factor_gross"),
        "average_decision_score": report.get("average_decision_score"),
        "max_drawdown_pct": report.get("max_drawdown_pct"),
        "benchmark_comparison": report.get("benchmark_comparison"),
        "confidence": report.get("confidence"),
        "transaction_costs": report.get("transaction_costs"),
    }


def build_walk_forward_report(
    *,
    strategy_id: str,
    strategy_name: str,
    instrument_id: str,
    asset_class: str,
    timeframe: str,
    period: str,
    windows: List[Dict[str, Any]],
    continuous_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate per-window summaries into a walk-forward research report."""
    characteristics = _walk_forward_characteristics(windows)
    stability = _behavior_stability(windows)

    return {
        "schema_version": WALK_FORWARD_SCHEMA_VERSION,
        "report_type": "walk_forward",
        "walk_forward_id": new_walk_forward_id(),
        "generated_at": datetime.now().isoformat(),
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "instrument_id": instrument_id,
        "asset_class": asset_class,
        "continuous_id": continuous_id,
        "timeframe": timeframe,
        "period": period,
        "windows": windows,
        "stability": stability,
        "characteristics": characteristics,
    }


def _walk_forward_characteristics(windows: List[Dict[str, Any]]) -> List[str]:
    notes: List[str] = [
        "Walk-forward evaluation tests whether strategy behavior persists across unseen time windows.",
        "No parameter optimization was applied between windows.",
    ]
    for item in windows:
        window = item["window"]
        report = item["report"]
        pf = report.get("profit_factor")
        trades = report.get("trade_count", 0)
        conf = (report.get("confidence") or {}).get("confidence_level", "unknown")
        pf_text = f"PF {pf}" if pf is not None else "PF n/a"
        notes.append(
            f"{window['label']} ({window['start']} → {window['end']}): "
            f"{trades} trades, {pf_text}, confidence {conf}."
        )
    return notes


def _behavior_stability(windows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Neutral stability read — not a pass/fail grade."""
    pfs = [
        item["report"].get("profit_factor")
        for item in windows
        if item["report"].get("profit_factor") is not None
    ]
    decisions = [
        item["report"].get("average_decision_score")
        for item in windows
        if item["report"].get("average_decision_score") is not None
    ]

    notes: List[str] = []
    if len(pfs) >= 2:
        if all(pf >= 1.0 for pf in pfs):
            notes.append("Profit factor remained at or above 1.0 in all tested windows.")
        elif pfs[-1] is not None and pfs[0] is not None and pfs[-1] < pfs[0] * 0.7:
            notes.append(
                "Out-of-sample profit factor declined materially vs research window — "
                "behavior may not generalize under these splits."
            )
        else:
            notes.append("Profit factor varied across windows — review regime context before trusting results.")

    if len(decisions) >= 2:
        spread = max(decisions) - min(decisions)
        if spread <= 10:
            notes.append("Decision quality remained relatively stable across windows.")
        else:
            notes.append("Decision quality varied across windows — process consistency should be reviewed.")

    return {
        "window_count": len(windows),
        "profit_factors_by_window": [
            {
                "name": item["window"]["name"],
                "profit_factor": item["report"].get("profit_factor"),
            }
            for item in windows
        ],
        "notes": notes,
    }


_service_instance: Optional[WalkForwardService] = None


def get_walk_forward_service() -> WalkForwardService:
    global _service_instance
    if _service_instance is None:
        _service_instance = WalkForwardService()
    return _service_instance
