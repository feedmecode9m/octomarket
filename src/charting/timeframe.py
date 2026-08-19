"""Timeframe intervals and normalization for chart data."""

from typing import Dict, Optional, Tuple

# Intervals supported by DataFetcher and OctoMarket chart workspace
SUPPORTED_INTERVALS = (
    "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo",
)

DEFAULT_INTERVAL = "1d"

# Default yfinance period per interval when not specified
INTERVAL_DEFAULT_PERIOD: Dict[str, str] = {
    "1m": "5d",
    "2m": "5d",
    "5m": "5d",
    "15m": "5d",
    "30m": "1mo",
    "60m": "1mo",
    "90m": "1mo",
    "1h": "1mo",
    "1d": "6mo",
    "5d": "1y",
    "1wk": "2y",
    "1mo": "5y",
    "3mo": "10y",
}

SUPPORTED_PERIODS = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")


def normalize_interval(interval: str) -> str:
    """Normalize interval string to canonical form."""
    if not interval:
        return DEFAULT_INTERVAL
    key = interval.strip().lower()
    aliases = {"1min": "1m", "5min": "5m", "15min": "15m", "60min": "1h", "daily": "1d", "d": "1d"}
    key = aliases.get(key, key)
    if key not in SUPPORTED_INTERVALS:
        raise ValueError(f"Unsupported interval '{interval}'. Must be one of: {SUPPORTED_INTERVALS}")
    return key


def get_default_period(interval: str) -> str:
    """Return default lookback period for an interval."""
    interval = normalize_interval(interval)
    return INTERVAL_DEFAULT_PERIOD.get(interval, "6mo")


def validate_timeframe(interval: str, period: Optional[str] = None) -> Tuple[str, str]:
    """
    Validate and normalize interval + period pair.

    Returns:
        (normalized_interval, normalized_period)
    """
    norm_interval = normalize_interval(interval)
    norm_period = (period or get_default_period(norm_interval)).strip().lower()
    if norm_period not in SUPPORTED_PERIODS:
        raise ValueError(f"Unsupported period '{period}'. Must be one of: {SUPPORTED_PERIODS}")
    return norm_interval, norm_period


def interval_label(interval: str) -> str:
    """Human-readable label for UI (Phase 13B+)."""
    labels = {
        "1m": "1 minute",
        "5m": "5 minutes",
        "15m": "15 minutes",
        "1h": "1 hour",
        "1d": "1 day",
        "1wk": "1 week",
    }
    return labels.get(normalize_interval(interval), interval)
