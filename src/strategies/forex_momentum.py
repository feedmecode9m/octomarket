"""Forex currency momentum — EMA crossover with ROC confirmation."""

from __future__ import annotations

from typing import Optional

from ..charting.indicators import compute_ema
from .base import StrategyBase
from .context import StrategyContext
from .signal import StrategySignal
from .technical import last_valid, rate_of_change


class ForexMomentumStrategy(StrategyBase):
    """
    Currency momentum via EMA 9/21 crossover and 10-bar ROC.

    Simple, explainable FX trend strategy compatible with session scoring.
    """

    strategy_id = "forex_momentum"
    name = "Currency Momentum"
    asset_classes = ("FOREX",)
    family = "momentum"
    description = "EMA 9/21 crossover confirmed by positive/negative 10-bar momentum."
    min_bars = 30

    def evaluate(self, context: StrategyContext) -> Optional[StrategySignal]:
        if context.bar_count < self.min_bars:
            return None

        closes = context.closes
        ema9 = compute_ema(closes, 9)
        ema21 = compute_ema(closes, 21)
        roc = rate_of_change(closes, 10)

        price = context.current_price
        fast = last_valid(ema9)
        slow = last_valid(ema21)
        prev_fast = ema9[-2] if len(ema9) >= 2 else None
        prev_slow = ema21[-2] if len(ema21) >= 2 else None
        mom = last_valid(roc)

        if fast is None or slow is None or prev_fast is None or prev_slow is None:
            return None

        direction = None
        setup_reasons = []
        confidence = 55

        crossed_up = prev_fast <= prev_slow and fast > slow
        crossed_down = prev_fast >= prev_slow and fast < slow
        aligned_long = fast > slow and price > fast
        aligned_short = fast < slow and price < fast

        if (crossed_up or aligned_long) and mom is not None and mom > 0:
            direction = "LONG"
            setup_reasons.append("EMA9 above EMA21 — bullish FX momentum")
            if crossed_up:
                setup_reasons.append("Fresh bullish EMA crossover")
                confidence += 15
            setup_reasons.append(f"10-bar momentum positive ({mom:.2f}%)")
            confidence += 15
        elif (crossed_down or aligned_short) and mom is not None and mom < 0:
            direction = "SHORT"
            setup_reasons.append("EMA9 below EMA21 — bearish FX momentum")
            if crossed_down:
                setup_reasons.append("Fresh bearish EMA crossover")
                confidence += 15
            setup_reasons.append(f"10-bar momentum negative ({mom:.2f}%)")
            confidence += 15
        else:
            return None

        pip = 0.0010 if "JPY" in context.instrument_id else 0.0050
        if direction == "LONG":
            stop = price - pip * 30
            target = price + pip * 60
        else:
            stop = price + pip * 30
            target = price - pip * 60

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            instrument_id=context.instrument_id,
            asset_class=context.asset_class,
            direction=direction,
            entry_price=price,
            stop_loss=stop,
            target=target,
            confidence=min(92, confidence),
            setup_reasons=setup_reasons,
            risk_reasons=["Pip-based stop pending ATR refinement"],
            indicators={"EMA9": round(fast, 6), "EMA21": round(slow, 6), "ROC10": mom},
        )
