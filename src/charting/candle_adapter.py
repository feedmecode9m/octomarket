"""Convert Phase 13A candle API payloads to chart-renderer bar records."""

from datetime import datetime
from typing import Any, Dict, List, Union

BarTime = Union[int, str]


def is_intraday_timeframe(timeframe: str) -> bool:
    """Return True when bars should use Unix timestamps (minutes/hours)."""
    tf = (timeframe or "1d").strip().lower()
    return tf.endswith("m") or tf.endswith("h") or tf in ("60m", "90m")


def to_chart_time(timestamp: str, timeframe: str) -> BarTime:
    """Map ISO timestamp string to Lightweight Charts time value."""
    if not timestamp:
        raise ValueError("timestamp is required")
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if is_intraday_timeframe(timeframe):
        return int(dt.timestamp())
    return dt.strftime("%Y-%m-%d")


def bars_from_candle_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert OHLCV API payload to candle + volume bar lists for the terminal renderer.

    Returns dict with keys: candles, volume (each a list of bar dicts).
    """
    count = int(payload.get("count") or 0)
    timeframe = payload.get("timeframe") or "1d"
    timestamps = payload.get("timestamps") or []
    opens = payload.get("open") or []
    highs = payload.get("high") or []
    lows = payload.get("low") or []
    closes = payload.get("close") or []
    volumes = payload.get("volume") or []

    candles: List[Dict[str, Any]] = []
    volume_bars: List[Dict[str, Any]] = []

    for i in range(count):
        t = to_chart_time(timestamps[i], timeframe)
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        v = volumes[i] if i < len(volumes) else 0
        candles.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        up = c >= o
        volume_bars.append(
            {
                "time": t,
                "value": v,
                "color": "rgba(0,255,136,0.45)" if up else "rgba(255,71,87,0.45)",
            }
        )

    return {"candles": candles, "volume": volume_bars, "timeframe": timeframe, "count": count}
