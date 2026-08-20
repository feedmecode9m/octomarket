"""Strategy base class — evaluate market context, emit optional signals."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import StrategyContext
    from .signal import StrategySignal


class StrategyBase(ABC):
    """Deterministic strategy that produces explainable trade intents."""

    strategy_id: str = ""
    name: str = ""
    asset_classes: tuple = ()
    description: str = ""
    family: str = ""
    default_timeframe: str = "1d"
    default_period: str = "3mo"
    min_bars: int = 50

    @abstractmethod
    def evaluate(self, context: "StrategyContext") -> Optional["StrategySignal"]:
        """Return a trade signal or None when conditions are not met."""

    def metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id,
            "name": self.name,
            "asset_classes": list(self.asset_classes),
            "description": self.description,
            "family": self.family,
            "default_timeframe": self.default_timeframe,
            "default_period": self.default_period,
            "min_bars": self.min_bars,
        }

    def required_indicators(self) -> List[str]:
        return []
