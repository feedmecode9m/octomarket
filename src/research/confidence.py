"""Statistical confidence metadata for research reports."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


MINIMUM_TRADES_RECOMMENDED = 30
LOW_CONFIDENCE_THRESHOLD = 10
MODERATE_CONFIDENCE_THRESHOLD = 30


def assess_sample_confidence(
    trade_count: int,
    *,
    minimum_recommended: int = MINIMUM_TRADES_RECOMMENDED,
) -> Dict[str, Any]:
    """Return confidence metadata based on closed trade sample size."""
    warnings: List[str] = []

    if trade_count <= 0:
        level = "none"
        warnings.append("No closed trades — results are not meaningful.")
    elif trade_count < LOW_CONFIDENCE_THRESHOLD:
        level = "low"
        warnings.append(
            f"Only {trade_count} trades — profit factor and win rate have low statistical confidence."
        )
    elif trade_count < MODERATE_CONFIDENCE_THRESHOLD:
        level = "moderate"
        warnings.append(
            f"{trade_count} trades — moderate sample size; {minimum_recommended}+ recommended for stability."
        )
    else:
        level = "high"

    return {
        "trade_count": trade_count,
        "confidence_level": level,
        "minimum_trades_recommended": minimum_recommended,
        "sample_adequate": trade_count >= minimum_recommended,
        "warnings": warnings,
    }


def enrich_report_confidence(report: Dict[str, Any]) -> Dict[str, Any]:
    """Attach confidence block to a strategy report dict."""
    report["confidence"] = assess_sample_confidence(report.get("trade_count", 0))
    return report
