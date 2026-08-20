"""Forex carry momentum proxy — low-volatility trend continuation."""

from __future__ import annotations

from typing import Optional

from ..charting.indicators import compute_ema
from .base import StrategyBase
from .context import StrategyContext
from .signal import StrategySignal
from .technical import atr_percentile, compute_atr, last_valid


class ForexCarryMomentumStrategy(StrategyBase):
    """
    Low-volatility trend continuation (carry+momentum proxy).

    Without live rate data, uses SMA200 trend + subdued ATR percentile
    as a robust, explainable stand-in for carry-aligned momentum.
    """

    strategy_id = "forex_carry_momentum"
    name = "Carry Momentum"
    asset_classes = ("FOREX",)
    family = "carry_momentum"
    description = "Trend continuation when price aligns with SMA200 in low-volatility regime."
    min_bars = 210

    def evaluate(self, context: StrategyContext) -> Optional[StrategySignal]:
        if context.bar_count < self.min_bars:
            return None

        closes = context.closes
        sma200 = compute_ema(closes, 200)
        atr_vals = compute_atr(context.highs, context.lows, closes, 14)
        price = context.current_price
        trend = last_valid(sma200)
        atr_pct = atr_percentile(atr_vals, 50)

        if trend is None or atr_pct is None:
            return None

        if atr_pct > 55:
            return None

        direction = None
        setup_reasons = []
        confidence = 60

        if price > trend:
            direction = "LONG"
            setup_reasons.append("Price above SMA200 — structural uptrend")
            setup_reasons.append(f"Volatility subdued (ATR percentile {atr_pct}%)")
            setup_reasons.append("Low-vol trend continuation — carry-momentum proxy")
            confidence += 18
        elif price < trend:
            direction = "SHORT"
            setup_reasons.append("Price below SMA200 — structural downtrend")
            setup_reasons.append(f"Volatility subdued (ATR percentile {atr_pct}%)")
            setup_reasons.append("Low-vol trend continuation — carry-momentum proxy")
            confidence += 18
        else:
            return None

        pip = 0.0010 if "JPY" in context.instrument_id else 0.0040
        if direction == "LONG":
            stop = price - pip * 40
            target = price + pip * 80
        else:
            stop = price + pip * 40
            target = price - pip * 80

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            instrument_id=context.instrument_id,
            asset_class=context.asset_class,
            direction=direction,
            entry_price=price,
            stop_loss=stop,
            target=target,
            confidence=min(90, confidence),
            setup_reasons=setup_reasons,
            risk_reasons=["ATR-percentile regime filter applied", "Wider stop for low-vol trend"],
            indicators={"SMA200": round(trend, 6), "ATR_Percentile": atr_pct},
        )
