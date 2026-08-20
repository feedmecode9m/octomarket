"""Strategy signal artifact — explainable trade intent before TradePlan creation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StrategySignal:
    """Optional trade intent produced by a strategy evaluation."""

    strategy_id: str
    strategy_name: str
    instrument_id: str
    asset_class: str
    direction: str
    entry_price: float
    stop_loss: float
    target: float
    confidence: float
    setup_reasons: List[str] = field(default_factory=list)
    risk_reasons: List[str] = field(default_factory=list)
    indicators: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_plan_data(
        self,
        *,
        account_balance: Optional[float] = None,
        risk_percent: Optional[float] = None,
        quantity: Optional[int] = None,
        contracts: Optional[int] = None,
        position_lots: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Convert signal into TradePlanManager.create_plan payload."""
        thesis_parts = [f"{self.strategy_name}: {self.direction}"]
        if self.setup_reasons:
            thesis_parts.append(self.setup_reasons[0])
        thesis = " — ".join(thesis_parts)

        indicator_keys = []
        for key in self.indicators:
            if key not in ("direction", "confidence"):
                indicator_keys.append({"key": key, "value": self.indicators[key]})

        payload: Dict[str, Any] = {
            "instrument_id": self.instrument_id,
            "symbol": self.instrument_id,
            "asset_class": self.asset_class,
            "direction": self.direction,
            "thesis": thesis,
            "entry": {"price": self.entry_price, "source": {"type": "strategy", "id": self.strategy_id}},
            "stop_loss": {"price": self.stop_loss, "source": {"type": "strategy", "method": "atr"}},
            "target": {"price": self.target, "source": {"type": "strategy", "method": "reward_risk"}},
            "setup": {
                "strategy": {
                    "id": self.strategy_id,
                    "name": self.strategy_name,
                    "confidence": self.confidence,
                    "setup": self.setup_reasons,
                    "risk": self.risk_reasons,
                },
                "indicators": indicator_keys,
            },
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_confidence": self.confidence,
        }

        if account_balance is not None:
            payload["account_balance"] = account_balance
        if risk_percent is not None:
            payload["risk_percent"] = risk_percent
        if quantity is not None:
            payload["quantity"] = quantity
        if contracts is not None:
            payload["contracts"] = contracts
        if position_lots is not None:
            payload["position_lots"] = position_lots

        return payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "instrument_id": self.instrument_id,
            "asset_class": self.asset_class,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "confidence": self.confidence,
            "setup": self.setup_reasons,
            "risk": self.risk_reasons,
            "indicators": self.indicators,
            "metadata": self.metadata,
        }
