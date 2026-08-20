"""Candle streaming with future-leak prevention."""

from typing import Any, Dict, List, Optional

import pandas as pd


def get_start_timestamp(df: pd.DataFrame) -> Optional[str]:
    if df is None or df.empty:
        return None
    ts = df.index[0]
    return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)


def validate_visible_index(current_index: int, total: int, requested_index: Optional[int] = None) -> int:
    """Ensure index does not expose future candles."""
    if total <= 0:
        return -1
    cap = min(current_index, total - 1)
    if requested_index is None:
        return cap
    if requested_index > cap:
        raise ValueError(f"Future candle access denied: requested {requested_index}, cap {cap}")
    return max(-1, min(requested_index, cap))


def slice_visible_df(df: pd.DataFrame, current_index: int) -> pd.DataFrame:
    """Return OHLCV rows visible at current_index (inclusive)."""
    if df is None or df.empty or current_index < 0:
        return pd.DataFrame()
    cap = validate_visible_index(current_index, len(df))
    return df.iloc[: cap + 1].copy()


def serialize_candles(df: pd.DataFrame, current_index: int) -> Dict[str, Any]:
    """Serialize visible candle series for API/chart."""
    visible = slice_visible_df(df, current_index)
    if visible.empty:
        return {
            "count": 0,
            "timestamps": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
            "cap_index": current_index,
        }

    timestamps = [t.isoformat() if hasattr(t, "isoformat") else str(t) for t in visible.index]
    return {
        "count": len(visible),
        "timestamps": timestamps,
        "open": [float(x) for x in visible["Open"]],
        "high": [float(x) for x in visible["High"]],
        "low": [float(x) for x in visible["Low"]],
        "close": [float(x) for x in visible["Close"]],
        "volume": [float(x) for x in visible["Volume"]],
        "cap_index": current_index,
        "session_capped": True,
    }


def count_hidden_candles(total: int, current_index: int) -> int:
    """Number of future candles still hidden."""
    if total <= 0 or current_index < 0:
        return total
    return max(0, total - (current_index + 1))
