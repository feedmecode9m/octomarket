"""Current market context for adaptive strategy recommendations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..charting.indicators import compute_ema
from ..market.instrument import resolve_instrument
from ..strategies.context import StrategyContext, build_strategy_context
from ..strategies.technical import atr_percentile, compute_atr, ema_slope, last_valid


def detect_market_context(
    instrument_id: str,
    *,
    timeframe: str = "1d",
    period: str = "3mo",
    context: Optional[StrategyContext] = None,
) -> Dict[str, Any]:
    """Classify current trend, volatility, session quality, and data coverage."""
    instrument = resolve_instrument(instrument_id)
    ctx = context or build_strategy_context(
        instrument.instrument_id,
        timeframe=timeframe,
        period=period,
    )
    return context_from_strategy(ctx, instrument=instrument, timeframe=timeframe)


def context_from_strategy(
    ctx: StrategyContext,
    *,
    instrument=None,
    timeframe: Optional[str] = None,
) -> Dict[str, Any]:
    tf = timeframe or ctx.timeframe
    ema20 = compute_ema(ctx.closes, 20) if ctx.closes else []
    ema50 = compute_ema(ctx.closes, 50) if ctx.closes else []
    e20 = last_valid(ema20)
    e50 = last_valid(ema50)
    slope = ema_slope(ema20) if ema20 else None
    atrs = compute_atr(ctx.highs, ctx.lows, ctx.closes) if ctx.closes else []
    atr_rank = atr_percentile(atrs) if atrs else None

    trend_state, trend_reasons = _classify_trend(ctx.current_price, e20, e50, slope)
    volatility_state, vol_reasons = _classify_volatility(atr_rank)
    session_quality, session_reasons = _session_quality(ctx.asset_class, instrument)

    active_regimes: List[str] = []
    if trend_state == "trending":
        active_regimes.append("trending")
    elif trend_state == "ranging":
        active_regimes.append("ranging")
    if volatility_state == "high":
        active_regimes.append("high_volatility")
    elif volatility_state == "low":
        active_regimes.append("low_volatility")

    data_quality = {
        "instrument": ctx.instrument_id,
        "interval": tf,
        "bars": ctx.bar_count,
        "missing_bars": 0,
        "market_sessions": ctx.bar_count,
        "data_quality": "complete" if ctx.bar_count >= 60 else ("thin" if ctx.bar_count else "none"),
        "warnings": [] if ctx.bar_count >= 60 else (
            [f"Only {ctx.bar_count} bars — limited history."] if ctx.bar_count else ["No historical candles available."]
        ),
    }

    return {
        "instrument_id": ctx.instrument_id,
        "asset_class": ctx.asset_class,
        "continuous_id": ctx.continuous_id,
        "timeframe": tf,
        "period": ctx.period,
        "trend_state": trend_state,
        "volatility_state": volatility_state,
        "session_quality": session_quality,
        "atr_percentile": atr_rank,
        "current_price": ctx.current_price,
        "bar_count": ctx.bar_count,
        "active_regimes": active_regimes,
        "reasons": trend_reasons + vol_reasons + session_reasons,
        "data_quality": data_quality,
        "indicators": {
            "EMA20": round(e20, 6) if e20 is not None else None,
            "EMA50": round(e50, 6) if e50 is not None else None,
            "ema_slope": round(slope, 4) if slope is not None else None,
            "atr_percentile": atr_rank,
        },
    }


def _classify_trend(price: float, e20: Optional[float], e50: Optional[float], slope: Optional[float]):
    reasons: List[str] = []
    if e20 is None or e50 is None or not price:
        return "unknown", ["Trend unknown — insufficient EMA history."]
    aligned = (price > e20 > e50) or (price < e20 < e50)
    slope_ok = slope is None or abs(slope) >= 0.05
    if aligned and slope_ok:
        reasons.append("Price aligned with EMA20/EMA50 — trending conditions.")
        return "trending", reasons
    reasons.append("EMAs mixed or price between averages — ranging / chop conditions.")
    return "ranging", reasons


def _classify_volatility(atr_rank: Optional[float]):
    if atr_rank is None:
        return "unknown", ["Volatility unknown — ATR history insufficient."]
    if atr_rank >= 70:
        return "high", [f"ATR percentile {atr_rank} — high volatility."]
    if atr_rank <= 30:
        return "low", [f"ATR percentile {atr_rank} — low volatility."]
    return "normal", [f"ATR percentile {atr_rank} — normal volatility."]


def _session_quality(asset_class: str, instrument) -> tuple:
    session = getattr(instrument, "session", None) if instrument is not None else None
    venue = getattr(session, "venue", None) if session is not None else None
    is_24h = bool(getattr(session, "is_24h", False)) if session is not None else False
    if (asset_class or "").upper() == "FOREX":
        label = "high" if is_24h else "adequate"
        return label, [f"Forex session quality {label}" + (f" ({venue})" if venue else "") + "."]
    if (asset_class or "").upper() == "FUTURES":
        return "high", ["Futures session supported extended-hour context."]
    return "adequate", ["Session quality recorded as adequate."]
