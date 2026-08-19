"""Technical indicator calculations for OctoMarket chart analysis."""

import re
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np

from .indicator_models import BollingerResult, IndicatorSpec, MacdResult, SeriesResult

IndicatorOutput = Union[SeriesResult, MacdResult, BollingerResult]

DEFAULT_RSI_PERIOD = 14
DEFAULT_MACD = (12, 26, 9)
DEFAULT_BB = (20, 2.0)
EMA_PRESETS = (9, 20, 50, 200)

KNOWN_KEYS = {
    "RSI": IndicatorSpec("RSI", "RSI", DEFAULT_RSI_PERIOD),
    "MACD": IndicatorSpec("MACD", "MACD", params={"fast": 12, "slow": 26, "signal": 9}),
    "BB": IndicatorSpec("BB", "BB", DEFAULT_BB[0], params={"stddev": DEFAULT_BB[1]}),
    "BOLLINGER": IndicatorSpec("BB", "BB", DEFAULT_BB[0], params={"stddev": DEFAULT_BB[1]}),
}


def _null_series(length: int) -> List[Optional[float]]:
    return [None] * length


def _validate_period(period: int, min_period: int = 1, max_period: int = 500) -> int:
    if period < min_period or period > max_period:
        raise ValueError(f"Period must be between {min_period} and {max_period}, got {period}")
    return period


def compute_sma(closes: Sequence[float], period: int) -> List[Optional[float]]:
    period = _validate_period(period)
    n = len(closes)
    if n == 0:
        return []
    arr = np.asarray(closes, dtype=float)
    out: List[Optional[float]] = _null_series(n)
    if n < period:
        return out
    kernel = np.ones(period) / period
    sma = np.convolve(arr, kernel, mode="valid")
    for i, val in enumerate(sma):
        out[i + period - 1] = float(val)
    return out


def compute_ema(closes: Sequence[float], period: int) -> List[Optional[float]]:
    period = _validate_period(period)
    n = len(closes)
    if n == 0:
        return []
    arr = np.asarray(closes, dtype=float)
    out: List[Optional[float]] = _null_series(n)
    alpha = 2.0 / (period + 1)
    ema_val: Optional[float] = None
    for i, price in enumerate(arr):
        if ema_val is None:
            if i + 1 >= period:
                ema_val = float(np.mean(arr[i + 1 - period : i + 1]))
                out[i] = ema_val
        else:
            ema_val = alpha * float(price) + (1 - alpha) * ema_val
            out[i] = ema_val
    return out


def compute_rsi(closes: Sequence[float], period: int = DEFAULT_RSI_PERIOD) -> List[Optional[float]]:
    period = _validate_period(period)
    n = len(closes)
    if n == 0:
        return []
    arr = np.asarray(closes, dtype=float)
    out: List[Optional[float]] = _null_series(n)
    if n <= period:
        return out

    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    if avg_loss == 0:
        out[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, n):
        gain = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def compute_macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> MacdResult:
    fast = _validate_period(fast)
    slow = _validate_period(slow)
    signal = _validate_period(signal)
    if fast >= slow:
        raise ValueError("MACD fast period must be less than slow period")

    n = len(closes)
    result = MacdResult(fast=fast, slow=slow, signal=signal)
    if n == 0:
        return result

    ema_fast = compute_ema(closes, fast)
    ema_slow = compute_ema(closes, slow)
    macd_line: List[Optional[float]] = _null_series(n)
    for i in range(n):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    macd_for_signal = [v if v is not None else 0.0 for v in macd_line]
    first_idx = next((i for i, v in enumerate(macd_line) if v is not None), None)
    signal_line: List[Optional[float]] = _null_series(n)
    if first_idx is not None:
        alpha = 2.0 / (signal + 1)
        sig: Optional[float] = None
        for i in range(first_idx, n):
            val = macd_for_signal[i]
            if sig is None:
                window = macd_line[first_idx : i + 1]
                valid = [v for v in window if v is not None]
                if len(valid) >= signal:
                    sig = float(np.mean(valid[-signal:]))
                    signal_line[i] = sig
            else:
                sig = alpha * val + (1 - alpha) * sig
                signal_line[i] = sig

    histogram: List[Optional[float]] = _null_series(n)
    for i in range(n):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = macd_line[i] - signal_line[i]

    result.macd = macd_line
    result.signal_line = signal_line
    result.histogram = histogram
    return result


def compute_bollinger(
    closes: Sequence[float],
    period: int = 20,
    stddev: float = 2.0,
) -> BollingerResult:
    period = _validate_period(period)
    if stddev <= 0:
        raise ValueError("Bollinger stddev must be positive")

    n = len(closes)
    result = BollingerResult(period=period, stddev=stddev)
    if n == 0:
        return result

    arr = np.asarray(closes, dtype=float)
    middle = compute_sma(closes, period)
    upper: List[Optional[float]] = _null_series(n)
    lower: List[Optional[float]] = _null_series(n)

    for i in range(period - 1, n):
        window = arr[i + 1 - period : i + 1]
        std = float(np.std(window, ddof=0))
        mid = middle[i]
        if mid is not None:
            upper[i] = mid + stddev * std
            lower[i] = mid - stddev * std

    result.middle = middle
    result.upper = upper
    result.lower = lower
    return result


def parse_indicator_token(token: str) -> IndicatorSpec:
    """Parse indicator query token (e.g. SMA20, EMA9, RSI, MACD, BB)."""
    raw = (token or "").strip().upper()
    if not raw:
        raise ValueError("Empty indicator token")

    if raw in KNOWN_KEYS:
        spec = KNOWN_KEYS[raw]
        return IndicatorSpec(spec.key, spec.indicator_type, spec.period, dict(spec.params))

    match = re.match(r"^(SMA|EMA|RSI|BB|BOLLINGER)(\d+)?$", raw)
    if not match:
        raise ValueError(f"Unknown indicator '{token}'")

    kind, num = match.group(1), match.group(2)
    if kind == "SMA":
        period = int(num) if num else 20
        return IndicatorSpec(f"SMA{period}", "SMA", period)
    if kind == "EMA":
        period = int(num) if num else 20
        return IndicatorSpec(f"EMA{period}", "EMA", period)
    if kind == "RSI":
        period = int(num) if num else DEFAULT_RSI_PERIOD
        return IndicatorSpec("RSI" if period == DEFAULT_RSI_PERIOD else f"RSI{period}", "RSI", period)
    period = int(num) if num else DEFAULT_BB[0]
    return IndicatorSpec("BB" if period == DEFAULT_BB[0] else f"BB{period}", "BB", period, {"stddev": DEFAULT_BB[1]})


def parse_indicators_query(query: str) -> List[IndicatorSpec]:
    if not query or not query.strip():
        return []
    specs: List[IndicatorSpec] = []
    seen = set()
    for part in query.split(","):
        part = part.strip()
        if not part:
            continue
        spec = parse_indicator_token(part)
        if spec.key not in seen:
            specs.append(spec)
            seen.add(spec.key)
    return specs


def compute_indicator(closes: Sequence[float], spec: IndicatorSpec) -> IndicatorOutput:
    if not closes:
        if spec.indicator_type == "MACD":
            return MacdResult()
        if spec.indicator_type == "BB":
            return BollingerResult(period=spec.period or DEFAULT_BB[0])
        return SeriesResult(indicator=spec.indicator_type, period=spec.period, values=[])

    if spec.indicator_type == "SMA":
        period = spec.period or 20
        return SeriesResult("SMA", period, compute_sma(closes, period))
    if spec.indicator_type == "EMA":
        period = spec.period or 20
        return SeriesResult("EMA", period, compute_ema(closes, period))
    if spec.indicator_type == "RSI":
        period = spec.period or DEFAULT_RSI_PERIOD
        return SeriesResult("RSI", period, compute_rsi(closes, period))
    if spec.indicator_type == "MACD":
        p = spec.params
        return compute_macd(
            closes,
            fast=int(p.get("fast", DEFAULT_MACD[0])),
            slow=int(p.get("slow", DEFAULT_MACD[1])),
            signal=int(p.get("signal", DEFAULT_MACD[2])),
        )
    if spec.indicator_type == "BB":
        period = spec.period or DEFAULT_BB[0]
        stddev = float(spec.params.get("stddev", DEFAULT_BB[1]))
        return compute_bollinger(closes, period, stddev)
    raise ValueError(f"Unsupported indicator type '{spec.indicator_type}'")


def compute_indicators_for_candles(
    candle_payload: Dict[str, Any],
    indicator_query: str,
) -> Dict[str, Any]:
    """Compute requested indicators from a Phase 13A candle payload."""
    specs = parse_indicators_query(indicator_query)
    closes = candle_payload.get("close") or []
    count = candle_payload.get("count") or len(closes)
    timestamps = candle_payload.get("timestamps") or []

    indicators: Dict[str, Any] = {}
    for spec in specs:
        result = compute_indicator(closes, spec)
        if isinstance(result, MacdResult):
            indicators[spec.key] = result.to_dict()
        elif isinstance(result, BollingerResult):
            indicators[spec.key] = result.to_dict()
        else:
            indicators[spec.key] = result.to_dict()

    return {
        "symbol": candle_payload.get("symbol"),
        "timeframe": candle_payload.get("timeframe"),
        "period": candle_payload.get("period"),
        "count": count,
        "timestamps": timestamps,
        "indicators": indicators,
    }
