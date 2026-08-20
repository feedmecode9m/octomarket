"""Futures breakout — Donchian channel breakout system."""

from __future__ import annotations

from typing import Optional

from .base import StrategyBase
from .context import StrategyContext
from .signal import StrategySignal
from .technical import donchian_channel, last_valid


class FuturesBreakoutStrategy(StrategyBase):
    """
    N-period high/low breakout (Turtle-style).

    Simple, robust breakout baseline with clear invalidation levels.
    """

    strategy_id = "futures_breakout"
    name = "Breakout"
    asset_classes = ("FUTURES",)
    family = "breakout"
    description = "Enter on close breaking prior 20-bar high or low."
    min_bars = 25
    channel_period = 20

    def evaluate(self, context: StrategyContext) -> Optional[StrategySignal]:
        if context.bar_count < self.min_bars:
            return None

        upper, lower = donchian_channel(context.highs, context.lows, self.channel_period)
        price = context.current_price
        prior_upper = upper[-2] if len(upper) >= 2 else None
        prior_lower = lower[-2] if len(lower) >= 2 else None

        if prior_upper is None or prior_lower is None:
            return None

        direction = None
        setup_reasons = []
        confidence = 60

        if price > prior_upper:
            direction = "LONG"
            setup_reasons.append(f"Close broke {self.channel_period}-bar high ({prior_upper:.2f})")
            setup_reasons.append("Breakout confirmed — momentum entry")
            confidence += 15
        elif price < prior_lower:
            direction = "SHORT"
            setup_reasons.append(f"Close broke {self.channel_period}-bar low ({prior_lower:.2f})")
            setup_reasons.append("Breakdown confirmed — short momentum entry")
            confidence += 15
        else:
            return None

        channel_width = prior_upper - prior_lower
        if channel_width > 0:
            setup_reasons.append(f"Channel width {channel_width:.2f} defines volatility context")
            confidence += 5

        if direction == "LONG":
            stop = prior_lower
            target = price + channel_width
        else:
            stop = prior_upper
            target = price - channel_width

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
            risk_reasons=["Stop beyond opposite channel edge", "Target sized to channel width"],
            indicators={
                "DonchianUpper": round(prior_upper, 4),
                "DonchianLower": round(prior_lower, 4),
                "ChannelWidth": round(channel_width, 4),
            },
        )
