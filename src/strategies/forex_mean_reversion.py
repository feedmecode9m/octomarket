"""Forex mean reversion — RSI extremes at Bollinger band edges."""

from __future__ import annotations

from typing import Optional

from ..charting.indicators import compute_rsi
from .base import StrategyBase
from .context import StrategyContext
from .signal import StrategySignal
from .technical import bollinger_bands, last_valid


class ForexMeanReversionStrategy(StrategyBase):
    """
    Mean reversion at RSI extremes near Bollinger bands.

    Classic range-market FX approach; clear setup/risk narrative for scoring.
    """

    strategy_id = "forex_mean_reversion"
    name = "Mean Reversion"
    asset_classes = ("FOREX",)
    family = "mean_reversion"
    description = "Fade RSI extremes when price touches Bollinger band."
    min_bars = 25

    def evaluate(self, context: StrategyContext) -> Optional[StrategySignal]:
        if context.bar_count < self.min_bars:
            return None

        closes = context.closes
        rsi = compute_rsi(closes, 14)
        upper, middle, lower = bollinger_bands(closes, 20, 2.0)

        price = context.current_price
        rsi_val = last_valid(rsi)
        bb_upper = last_valid(upper)
        bb_lower = last_valid(lower)
        bb_mid = last_valid(middle)

        if rsi_val is None or bb_upper is None or bb_lower is None or bb_mid is None:
            return None

        direction = None
        setup_reasons = []
        confidence = 58
        tolerance = abs(bb_upper - bb_lower) * 0.05

        if rsi_val <= 32 and price <= bb_lower + tolerance:
            direction = "LONG"
            setup_reasons.append(f"RSI oversold ({rsi_val:.1f}) at lower Bollinger band")
            setup_reasons.append("Mean reversion long — expect reversion toward mid-band")
            confidence += 20
        elif rsi_val >= 68 and price >= bb_upper - tolerance:
            direction = "SHORT"
            setup_reasons.append(f"RSI overbought ({rsi_val:.1f}) at upper Bollinger band")
            setup_reasons.append("Mean reversion short — expect reversion toward mid-band")
            confidence += 20
        else:
            return None

        if direction == "LONG":
            stop = bb_lower - tolerance
            target = bb_mid
        else:
            stop = bb_upper + tolerance
            target = bb_mid

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            instrument_id=context.instrument_id,
            asset_class=context.asset_class,
            direction=direction,
            entry_price=price,
            stop_loss=stop,
            target=target,
            confidence=min(88, confidence),
            setup_reasons=setup_reasons,
            risk_reasons=["Stop beyond band extension", "Target at Bollinger mid-band"],
            indicators={
                "RSI": round(rsi_val, 2),
                "BB_Upper": round(bb_upper, 6),
                "BB_Lower": round(bb_lower, 6),
                "BB_Mid": round(bb_mid, 6),
            },
        )
