"""Position sizing by asset class."""

from typing import Any, Dict, Optional

from ..market.asset_class import AssetClass
from ..market.forex import lot_to_units, pip_distance, pip_value
from ..market.instrument import resolve_instrument


def calculate_forex_size(
    account_balance: float,
    risk_percent: float,
    entry: float,
    stop: float,
    symbol: str,
    account_currency: str = "USD",
) -> Dict[str, Any]:
    """
    Size a forex position from account risk budget.

    Lot Size = (Account × Risk%) / (Pip Risk × Pip Value per lot)
    """
    if account_balance <= 0:
        raise ValueError("Account balance must be positive")
    if risk_percent <= 0 or risk_percent > 100:
        raise ValueError("Risk percent must be between 0 and 100")
    if entry <= 0 or stop <= 0:
        raise ValueError("Entry and stop must be positive")

    pair = resolve_instrument(symbol)
    if pair.asset_class != AssetClass.FOREX:
        raise ValueError(f"{symbol} is not a forex instrument")

    risk_amount = round(account_balance * (risk_percent / 100), 2)
    pip_risk = pip_distance(entry, stop, pair.symbol)
    if pip_risk <= 0:
        raise ValueError("Stop must differ from entry")

    pip_val = pip_value(pair.symbol, entry, lots=1.0, account_currency=account_currency)
    if pip_val <= 0:
        raise ValueError("Pip value must be positive")

    lots = risk_amount / (pip_risk * pip_val)
    lots = round(lots, 2)

    return {
        "symbol": pair.symbol,
        "instrument_id": pair.symbol,
        "asset_class": AssetClass.FOREX.value,
        "lots": lots,
        "units": lot_to_units(lots),
        "risk_amount": risk_amount,
        "risk_percent": risk_percent,
        "pip_risk": pip_risk,
        "pip_value_per_lot": round(pip_val, 4),
        "account_balance": account_balance,
        "account_currency": account_currency,
    }
