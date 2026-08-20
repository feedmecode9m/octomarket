"""Futures time-series momentum — sign of recent return with trend filter."""

from __future__ import annotations

from typing import Optional

from ..charting.indicators import compute_sma
from .base import StrategyBase
from .context import StrategyContext
from .signal import StrategySignal
from .technical import last_valid, rate_of_change


class FuturesMomentumStrategy(StrategyBase):
    """
    Time-series momentum (12-bar return sign + SMA50 filter).

    Academically robust baseline; avoids complex parameter optimization.
    """

    strategy_id = "futures_momentum"
    name = "Momentum"
    asset_classes = ("FUTURES",)
    family = "momentum"
    description = "Trade in direction of 12-bar momentum when aligned with SMA50."
    min_bars = 55
    momentum_period = 12

    def evaluate(self, context: StrategyContext) -> Optional[StrategySignal]:
        if context.bar_count < self.min_bars:
            return None

        closes = context.closes
        roc = rate_of_change(closes, self.momentum_period)
        sma50 = compute_sma(closes, 50)
        price = context.current_price
        mom = last_valid(roc)
        trend = last_valid(sma50)

        if mom is None or trend is None:
            return None

        direction = None
        setup_reasons = []
        confidence = 58

        if mom > 0 and price > trend:
            direction = "LONG"
            setup_reasons.append(f"{self.momentum_period}-bar momentum positive ({mom:.2f}%)")
            setup_reasons.append("Price above SMA50 — trend filter confirmed")
            confidence += 20
        elif mom < 0 and price < trend:
            direction = "SHORT"
            setup_reasons.append(f"{self.momentum_period}-bar momentum negative ({mom:.2f}%)")
            setup_reasons.append("Price below SMA50 — bearish trend filter confirmed")
            confidence += 20
        else:
            return None

        stop = price * (0.985 if direction == "LONG" else 1.015)
        target = price * (1.03 if direction == "LONG" else 0.97)

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
            risk_reasons=["Momentum stop/target pending ATR refinement"],
            indicators={"ROC12": round(mom, 4), "SMA50": round(trend, 4)},
        )
