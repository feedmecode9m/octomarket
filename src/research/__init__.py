"""Strategy research evaluation layer."""

from .comparison import COMPARISON_SCHEMA_VERSION, build_comparison_report
from .regime import REGIMES, REGIME_LABELS, aggregate_regime_performance, classify_trade_regimes
from .report import REPORT_SCHEMA_VERSION, build_strategy_report
from .runner import StrategyBacktestRunner, get_strategy_backtest_runner
from .store import ResearchReportStore, get_research_report_store, reset_research_report_store
from .validation import StrategyValidationService, get_strategy_validation_service

__all__ = [
    "REPORT_SCHEMA_VERSION",
    "COMPARISON_SCHEMA_VERSION",
    "REGIMES",
    "REGIME_LABELS",
    "build_strategy_report",
    "build_comparison_report",
    "aggregate_regime_performance",
    "StrategyBacktestRunner",
    "get_strategy_backtest_runner",
    "StrategyValidationService",
    "get_strategy_validation_service",
    "ResearchReportStore",
    "get_research_report_store",
    "reset_research_report_store",
]
