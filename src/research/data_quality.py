"""Historical data coverage metadata for research reliability."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

import pandas as pd


def assess_ohlcv_quality(
    df: Optional[pd.DataFrame],
    *,
    instrument_id: Optional[str] = None,
    interval: str = "1d",
) -> Dict[str, Any]:
    """Describe coverage of a candle series without repairing gaps."""
    if df is None or df.empty:
        return {
            "instrument": instrument_id,
            "interval": interval,
            "bars": 0,
            "missing_bars": None,
            "market_sessions": 0,
            "data_quality": "none",
            "warnings": ["No historical candles available."],
        }

    bars = len(df)
    missing = _count_missing_bars(df.index, interval)
    if missing is None:
        quality = "unknown"
    elif missing == 0:
        quality = "complete"
    elif missing / max(bars, 1) < 0.05:
        quality = "partial"
    else:
        quality = "incomplete"

    warnings = []
    if quality == "partial":
        warnings.append(f"{missing} missing bars detected — coverage is usable but incomplete.")
    elif quality == "incomplete":
        warnings.append(f"{missing} missing bars — regime matching may be biased.")
    elif bars < 60:
        warnings.append(f"Only {bars} bars — limited history for context detection.")
        if quality == "complete":
            quality = "thin"

    start = df.index[0]
    end = df.index[-1]
    return {
        "instrument": instrument_id,
        "interval": interval,
        "period": {
            "start": start.date().isoformat() if hasattr(start, "date") else str(start)[:10],
            "end": end.date().isoformat() if hasattr(end, "date") else str(end)[:10],
        },
        "bars": bars,
        "missing_bars": missing if missing is not None else 0,
        "market_sessions": bars,
        "data_quality": quality,
        "warnings": warnings,
    }


def assess_series_quality(
    timestamps: Sequence[Any],
    *,
    instrument_id: Optional[str] = None,
    interval: str = "1d",
) -> Dict[str, Any]:
    if not timestamps:
        return assess_ohlcv_quality(None, instrument_id=instrument_id, interval=interval)
    index = pd.DatetimeIndex(pd.to_datetime(list(timestamps)))
    df = pd.DataFrame({"Close": [1.0] * len(index)}, index=index)
    return assess_ohlcv_quality(df, instrument_id=instrument_id, interval=interval)


def _count_missing_bars(index: pd.DatetimeIndex, interval: str) -> Optional[int]:
    if len(index) < 2:
        return 0
    if interval not in ("1d", "1wk"):
        return None
    freq = "B" if interval == "1d" else "W-FRI"
    expected = pd.bdate_range(index.min(), index.max()) if interval == "1d" else pd.date_range(
        index.min(), index.max(), freq=freq
    )
    actual = pd.DatetimeIndex(pd.to_datetime(index).normalize())
    expected_norm = pd.DatetimeIndex(expected.normalize())
    missing = expected_norm.difference(actual)
    return int(len(missing))
