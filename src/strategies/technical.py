"""Technical helpers for deterministic strategy evaluation."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from ..charting.indicators import compute_ema, compute_rsi, compute_sma


def last_valid(values: Sequence[Optional[float]]) -> Optional[float]:
    for val in reversed(values):
        if val is not None:
            return float(val)
    return None


def compute_atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> List[Optional[float]]:
    n = len(closes)
    if n == 0:
        return []
    out: List[Optional[float]] = [None] * n
    if n <= period:
        return out

    trs: List[float] = []
    for i in range(1, n):
        high = float(highs[i])
        low = float(lows[i])
        prev_close = float(closes[i - 1])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    atr = sum(trs[:period]) / period
    out[period] = atr
    for i in range(period + 1, n):
        tr = trs[i - 1]
        atr = (atr * (period - 1) + tr) / period
        out[i] = atr
    return out


def donchian_channel(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 20,
) -> Tuple[List[Optional[float]], List[Optional[float]]]:
    n = len(highs)
    upper: List[Optional[float]] = [None] * n
    lower: List[Optional[float]] = [None] * n
    for i in range(period, n):
        window_high = max(float(h) for h in highs[i - period : i])
        window_low = min(float(l) for l in lows[i - period : i])
        upper[i] = window_high
        lower[i] = window_low
    return upper, lower


def bollinger_bands(
    closes: Sequence[float],
    period: int = 20,
    stddev: float = 2.0,
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    sma = compute_sma(closes, period)
    n = len(closes)
    upper: List[Optional[float]] = [None] * n
    middle: List[Optional[float]] = [None] * n
    lower: List[Optional[float]] = [None] * n

    for i in range(period - 1, n):
        window = closes[i + 1 - period : i + 1]
        mean = sum(float(x) for x in window) / period
        variance = sum((float(x) - mean) ** 2 for x in window) / period
        sd = variance ** 0.5
        middle[i] = mean
        upper[i] = mean + stddev * sd
        lower[i] = mean - stddev * sd
    return upper, middle, lower


def rate_of_change(closes: Sequence[float], period: int = 10) -> List[Optional[float]]:
    n = len(closes)
    out: List[Optional[float]] = [None] * n
    for i in range(period, n):
        prev = float(closes[i - period])
        if prev == 0:
            continue
        out[i] = (float(closes[i]) - prev) / prev * 100
    return out


def ema_slope(ema_values: Sequence[Optional[float]], lookback: int = 3) -> Optional[float]:
    valid = [v for v in ema_values if v is not None]
    if len(valid) < lookback + 1:
        return None
    recent = valid[-lookback - 1 :]
    return (recent[-1] - recent[0]) / max(abs(recent[0]), 1e-9) * 100


def atr_percentile(atr_values: Sequence[Optional[float]], window: int = 50) -> Optional[float]:
    valid = [v for v in atr_values if v is not None]
    if len(valid) < 2:
        return None
    current = valid[-1]
    sample = valid[-window:] if len(valid) >= window else valid
    rank = sum(1 for v in sample if v <= current)
    return round(rank / len(sample) * 100, 1)
