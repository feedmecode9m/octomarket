"""Market context for strategy evaluation — respects replay candle caps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..market.asset_class import AssetClass
from ..market.instrument import resolve_instrument


@dataclass
class StrategyContext:
    """Decision-time market context visible to a strategy."""

    instrument_id: str
    asset_class: str
    symbol: str
    timeframe: str
    period: str
    closes: List[float]
    opens: List[float]
    highs: List[float]
    lows: List[float]
    volumes: List[float]
    current_price: float
    bar_count: int
    session_capped: bool = False
    cap_index: Optional[int] = None
    continuous_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_enough_bars(self) -> bool:
        return self.bar_count >= 2 and self.current_price > 0


def build_strategy_context(
    instrument_id: str,
    *,
    timeframe: Optional[str] = None,
    period: Optional[str] = None,
) -> StrategyContext:
    """Load capped candles through the same pipeline as the chart."""
    instrument = resolve_instrument(instrument_id)
    from ..charting.candle_engine import get_candle_engine

    tf = timeframe or "1d"
    lookback = period or "3mo"
    payload = get_candle_engine().get_candles(
        instrument.instrument_id,
        interval=tf,
        period=lookback,
        respect_session=True,
    )

    closes = [float(c) for c in payload.get("close") or []]
    opens = [float(o) for o in payload.get("open") or []]
    highs = [float(h) for h in payload.get("high") or []]
    lows = [float(l) for l in payload.get("low") or []]
    volumes = [float(v) for v in payload.get("volume") or []]
    current = closes[-1] if closes else 0.0

    continuous_id = None
    if instrument.asset_class == AssetClass.FUTURES:
        continuous_id = instrument.continuous_id

    return StrategyContext(
        instrument_id=instrument.instrument_id,
        asset_class=instrument.asset_class.value,
        symbol=instrument.symbol,
        timeframe=tf,
        period=lookback,
        closes=closes,
        opens=opens,
        highs=highs,
        lows=lows,
        volumes=volumes,
        current_price=current,
        bar_count=len(closes),
        session_capped=bool(payload.get("session_capped")),
        cap_index=payload.get("cap_index"),
        continuous_id=continuous_id,
    )
