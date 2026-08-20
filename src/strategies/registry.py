"""Strategy registry — catalog of deterministic baseline strategies."""

from __future__ import annotations

from typing import Dict, List, Optional

from ..market.asset_class import AssetClass
from .base import StrategyBase
from .forex_carry_momentum import ForexCarryMomentumStrategy
from .forex_mean_reversion import ForexMeanReversionStrategy
from .forex_momentum import ForexMomentumStrategy
from .futures_breakout import FuturesBreakoutStrategy
from .futures_momentum import FuturesMomentumStrategy
from .futures_trend import FuturesTrendStrategy


class StrategyRegistry:
    """Register and list strategies grouped by asset class."""

    def __init__(self):
        self._strategies: Dict[str, StrategyBase] = {}
        self._register_defaults()

    def register(self, strategy: StrategyBase) -> None:
        self._strategies[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> Optional[StrategyBase]:
        return self._strategies.get(strategy_id)

    def list_all(self) -> List[Dict]:
        return [s.metadata() for s in self._strategies.values()]

    def list_by_asset_class(self, asset_class: str) -> List[Dict]:
        key = asset_class.upper()
        return [
            s.metadata()
            for s in self._strategies.values()
            if key in s.asset_classes
        ]

    def catalog(self) -> Dict[str, List[Dict]]:
        return {
            AssetClass.FUTURES.value: self.list_by_asset_class(AssetClass.FUTURES.value),
            AssetClass.FOREX.value: self.list_by_asset_class(AssetClass.FOREX.value),
        }

    def _register_defaults(self) -> None:
        for strategy in (
            FuturesTrendStrategy(),
            FuturesBreakoutStrategy(),
            FuturesMomentumStrategy(),
            ForexMomentumStrategy(),
            ForexMeanReversionStrategy(),
            ForexCarryMomentumStrategy(),
        ):
            self.register(strategy)


_registry_instance: Optional[StrategyRegistry] = None


def get_strategy_registry() -> StrategyRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = StrategyRegistry()
    return _registry_instance
