"""Futures trend following — dual EMA alignment with volatility filter."""

from __future__ import annotations

from typing import Optional

from ..charting.indicators import compute_ema, compute_rsi
from .base import StrategyBase
from .context import StrategyContext
from .signal import StrategySignal
from .technical import ema_slope, last_valid


class FuturesTrendStrategy(StrategyBase):
    """
    Classic trend following via EMA alignment.

    Robust baseline used by CTAs; explainable and compatible with trend_alignment scoring.
    """

    strategy_id = "futures_trend"
    name = "Trend Following"
    asset_classes = ("FUTURES",)
    family = "trend_following"
    description = "Enter when price aligns with EMA20 above EMA50 (long) or below (short)."
    min_bars = 55

    def evaluate(self, context: StrategyContext) -> Optional[StrategySignal]:
        if context.bar_count < self.min_bars:
            return None

        closes = context.closes
        ema20 = compute_ema(closes, 20)
        ema50 = compute_ema(closes, 50)
        rsi = compute_rsi(closes, 14)

        price = context.current_price
        e20 = last_valid(ema20)
        e50 = last_valid(ema50)
        rsi_val = last_valid(rsi)
        slope = ema_slope(ema20)

        if e20 is None or e50 is None:
            return None

        direction = None
        setup_reasons = []
        confidence = 55

        if price > e20 > e50:
            direction = "LONG"
            setup_reasons.append("Price above EMA20 above EMA50 — bullish alignment")
            confidence += 15
            if slope and slope > 0:
                setup_reasons.append("EMA20 slope positive — trend strengthening")
                confidence += 10
        elif price < e20 < e50:
            direction = "SHORT"
            setup_reasons.append("Price below EMA20 below EMA50 — bearish alignment")
            confidence += 15
            if slope and slope < 0:
                setup_reasons.append("EMA20 slope negative — downtrend strengthening")
                confidence += 10
        else:
            return None

        if rsi_val is not None:
            if direction == "LONG" and 40 <= rsi_val <= 65:
                setup_reasons.append("RSI supports continuation without extension")
                confidence += 10
            elif direction == "SHORT" and 35 <= rsi_val <= 60:
                setup_reasons.append("RSI supports bearish continuation without extension")
                confidence += 10
            elif direction == "LONG" and rsi_val > 72:
                setup_reasons.append("RSI extended — reduced confidence")
                confidence -= 10

        stop = price * (0.99 if direction == "LONG" else 1.01)
        target = price * (1.02 if direction == "LONG" else 0.98)

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            instrument_id=context.instrument_id,
            asset_class=context.asset_class,
            direction=direction,
            entry_price=price,
            stop_loss=stop,
            target=target,
            confidence=min(95, max(40, confidence)),
            setup_reasons=setup_reasons,
            risk_reasons=["Initial levels set — ATR refinement pending"],
            indicators={"EMA20": round(e20, 4), "EMA50": round(e50, 4), "RSI": rsi_val},
        )
