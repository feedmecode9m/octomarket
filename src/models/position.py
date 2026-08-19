"""Asset-aware position model."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..market.asset_class import AssetClass
from ..market.instrument import resolve_instrument


@dataclass
class Position:
    """Open or planned position with asset-class-specific sizing."""

    instrument_id: str
    asset_class: AssetClass
    direction: str
    entry_price: float
    quantity: float
    quantity_unit: str
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    symbol: Optional[str] = field(default=None)

    def __post_init__(self):
        self.direction = self.direction.upper()
        self.instrument_id = self.instrument_id.upper()
        if self.symbol is None:
            self.symbol = self.instrument_id

    @classmethod
    def from_trade_plan(cls, plan: Dict[str, Any]) -> "Position":
        instrument_id = plan.get("instrument_id") or plan.get("symbol", "")
        instrument = resolve_instrument(instrument_id)
        asset_class = AssetClass.from_value(plan.get("asset_class") or instrument.asset_class.value)

        if asset_class == AssetClass.FOREX:
            lots = plan.get("position_lots")
            if lots is None and plan.get("quantity"):
                from ..market.forex import units_to_lots
                lots = units_to_lots(int(plan["quantity"]))
            quantity = float(lots or 0)
            unit = "lots"
        elif asset_class == AssetClass.FUTURES:
            quantity = float(plan.get("contracts") or plan.get("quantity") or 0)
            unit = "contracts"
        else:
            quantity = float(plan.get("quantity") or 0)
            unit = "shares"

        return cls(
            instrument_id=instrument.instrument_id,
            asset_class=asset_class,
            direction=plan.get("direction", "LONG"),
            entry_price=_price(plan.get("entry")),
            quantity=quantity,
            quantity_unit=unit,
            stop_price=_price(plan.get("stop_loss")) if plan.get("stop_loss") else None,
            target_price=_price(plan.get("target")) if plan.get("target") else None,
            symbol=instrument.symbol,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "quantity_unit": self.quantity_unit,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
        }


def _price(level: Any) -> float:
    if isinstance(level, dict):
        return float(level["price"])
    return float(level)
