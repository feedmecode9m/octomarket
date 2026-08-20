"""Track price extremes and trades during replay for learning."""

from copy import deepcopy
from typing import Any, Dict, List, Optional


class ReplayMetrics:
    """Per-replay metrics for outcome comparison."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.symbol: Optional[str] = None
        self.high_reached: Optional[float] = None
        self.low_reached: Optional[float] = None
        self.trades: List[Dict[str, Any]] = []
        self.candle_count: int = 0

    def bind_symbol(self, symbol: str):
        self.reset()
        self.symbol = symbol.upper()

    def on_candle(self, candle: Dict[str, Any]):
        """Update running high/low from session candle."""
        if not candle:
            return
        high = float(candle.get("high", 0))
        low = float(candle.get("low", 0))
        if self.high_reached is None or high > self.high_reached:
            self.high_reached = high
        if self.low_reached is None or low < self.low_reached:
            self.low_reached = low
        self.candle_count += 1

    def record_trade(self, trade: Dict[str, Any]):
        self.trades.append(deepcopy(trade))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "high_reached": self.high_reached,
            "low_reached": self.low_reached,
            "trades": deepcopy(self.trades),
            "candle_count": self.candle_count,
        }
