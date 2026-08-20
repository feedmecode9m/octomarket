"""Date window helpers for research replay."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..simulation.session import MarketSession


def apply_session_date_window(
    session: MarketSession,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Restrict an active MarketSession to an inclusive date window."""
    if not start_date and not end_date:
        return {"start": None, "end": None}

    start_ts = pd.Timestamp(start_date) if start_date else None
    end_ts = pd.Timestamp(end_date) if end_date else None

    with session._lock:
        filtered_ranges: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
        for symbol, df in session._data.items():
            subset = df
            if start_ts is not None:
                subset = subset[subset.index >= start_ts]
            if end_ts is not None:
                subset = subset[subset.index <= end_ts]
            if subset.empty:
                raise ValueError(
                    f"No candles for {symbol} between {start_date or '...'} and {end_date or '...'}"
                )
            session._data[symbol] = subset
            start_label = subset.index[0].isoformat() if hasattr(subset.index[0], "isoformat") else str(subset.index[0])
            end_label = subset.index[-1].isoformat() if hasattr(subset.index[-1], "isoformat") else str(subset.index[-1])
            filtered_ranges[symbol] = (start_label, end_label)

        session._max_length = max(len(df) for df in session._data.values())
        session._index = -1
        session._prev_closes = {
            sym: float(df["Close"].iloc[0]) for sym, df in session._data.items()
        }

    first = next(iter(filtered_ranges.values()))
    return {"start": first[0], "end": first[1]}


def validate_non_overlapping_windows(windows: List[Dict[str, str]]) -> None:
    """Reject overlapping walk-forward windows so later periods cannot leak into earlier ones."""
    parsed = []
    for window in windows:
        start = pd.Timestamp(window["start"])
        end = pd.Timestamp(window["end"])
        if end < start:
            raise ValueError(f"Invalid window '{window.get('name')}': end before start")
        parsed.append((start, end, window.get("name") or "window"))
    parsed.sort(key=lambda item: item[0])
    for idx in range(1, len(parsed)):
        prev_start, prev_end, prev_name = parsed[idx - 1]
        start, end, name = parsed[idx]
        if start <= prev_end:
            raise ValueError(
                f"Walk-forward windows overlap: {prev_name} ({prev_start} → {prev_end}) "
                f"and {name} ({start} → {end})"
            )


def split_date_range(
    index: pd.DatetimeIndex,
    *,
    research_ratio: float = 0.5,
    validation_ratio: float = 0.25,
    out_of_sample_ratio: float = 0.25,
) -> List[Dict[str, str]]:
    """Split a datetime index into research / validation / out-of-sample windows."""
    if len(index) < 3:
        raise ValueError("Need at least 3 candles to split walk-forward windows")

    total = research_ratio + validation_ratio + out_of_sample_ratio
    if abs(total - 1.0) > 0.01:
        raise ValueError("Walk-forward ratios must sum to 1.0")

    n = len(index)
    research_end = max(1, int(n * research_ratio))
    validation_end = max(research_end + 1, int(n * (research_ratio + validation_ratio)))
    validation_end = min(validation_end, n - 1)

    def _label(ts) -> str:
        if hasattr(ts, "isoformat"):
            return ts.isoformat()
        return str(ts)

    return [
        {
            "name": "research",
            "label": "Research window",
            "start": _label(index[0]),
            "end": _label(index[research_end - 1]),
        },
        {
            "name": "validation",
            "label": "Validation window",
            "start": _label(index[research_end]),
            "end": _label(index[validation_end - 1]),
        },
        {
            "name": "out_of_sample",
            "label": "Out-of-sample window",
            "start": _label(index[validation_end]),
            "end": _label(index[-1]),
        },
    ]


def resolve_walk_forward_windows(
    ohlcv: pd.DataFrame,
    *,
    windows: Optional[List[Dict[str, str]]] = None,
    research_ratio: float = 0.5,
    validation_ratio: float = 0.25,
    out_of_sample_ratio: float = 0.25,
) -> List[Dict[str, str]]:
    if windows:
        validate_non_overlapping_windows(windows)
        return windows
    resolved = split_date_range(
        ohlcv.index,
        research_ratio=research_ratio,
        validation_ratio=validation_ratio,
        out_of_sample_ratio=out_of_sample_ratio,
    )
    validate_non_overlapping_windows(resolved)
    return resolved
