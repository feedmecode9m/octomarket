"""Futures tick math, risk, and position sizing."""

from typing import Any, Dict, Optional

from .asset_class import AssetClass
from .contract import parse_contract_code
from .contract_specs import get_contract_spec
from .instrument import resolve_instrument


def tick_size(instrument_id: str) -> float:
    contract = parse_contract_code(_root_contract(instrument_id))
    return contract.tick_size


def tick_value(instrument_id: str) -> float:
    contract = parse_contract_code(_root_contract(instrument_id))
    return contract.tick_value


def point_value(instrument_id: str) -> float:
    contract = parse_contract_code(_root_contract(instrument_id))
    return contract.point_value()


def tick_distance(entry: float, stop: float, instrument_id: str) -> float:
    """Absolute stop distance in ticks."""
    if entry <= 0 or stop <= 0:
        raise ValueError("Entry and stop must be positive")
    contract = parse_contract_code(_root_contract(instrument_id))
    points = abs(entry - stop)
    return round(points / contract.tick_size, 1)


def point_distance(entry: float, stop: float) -> float:
    if entry <= 0 or stop <= 0:
        raise ValueError("Entry and stop must be positive")
    return round(abs(entry - stop), 4)


def risk_amount(
    entry: float,
    stop: float,
    contracts: int,
    instrument_id: str,
) -> float:
    """Dollar risk if stop is hit."""
    if contracts <= 0:
        raise ValueError("Contracts must be positive")
    ticks = tick_distance(entry, stop, instrument_id)
    tv = tick_value(instrument_id)
    return round(ticks * tv * contracts, 2)


def pnl(entry: float, exit_price: float, contracts: int, instrument_id: str) -> float:
    contract = parse_contract_code(_root_contract(instrument_id))
    return contract.pnl(entry, exit_price, contracts)


def margin_required(contracts: int, instrument_id: str) -> float:
    root = parse_contract_code(_root_contract(instrument_id)).root
    spec = get_contract_spec(root)
    return round(spec["margin"] * contracts, 2)


def calculate_futures_size(
    account_balance: float,
    risk_percent: float,
    entry: float,
    stop: float,
    instrument_id: str,
) -> Dict[str, Any]:
    """
    Size futures position from account risk budget.

    Contracts = Risk Amount / (Tick Risk × Tick Value)
    """
    if account_balance <= 0:
        raise ValueError("Account balance must be positive")
    if risk_percent <= 0 or risk_percent > 100:
        raise ValueError("Risk percent must be between 0 and 100")
    if entry <= 0 or stop <= 0:
        raise ValueError("Entry and stop must be positive")

    instrument = resolve_instrument(instrument_id)
    if instrument.asset_class != AssetClass.FUTURES:
        raise ValueError(f"{instrument_id} is not a futures instrument")

    contract_id = instrument.instrument_id
    risk_budget = round(account_balance * (risk_percent / 100), 2)
    tick_risk = tick_distance(entry, stop, contract_id)
    if tick_risk <= 0:
        raise ValueError("Stop must differ from entry")

    per_contract_risk = risk_amount(entry, stop, 1, contract_id)
    if per_contract_risk <= 0:
        raise ValueError("Per-contract risk must be positive")

    contracts = int(risk_budget // per_contract_risk)
    if contracts < 1:
        contracts = 1

    actual_risk = risk_amount(entry, stop, contracts, contract_id)
    root = parse_contract_code(_root_contract(contract_id)).root
    spec = get_contract_spec(root)

    return {
        "instrument_id": contract_id,
        "symbol": instrument.symbol,
        "asset_class": AssetClass.FUTURES.value,
        "contracts": contracts,
        "quantity": contracts,
        "risk_amount": actual_risk,
        "risk_percent": risk_percent,
        "tick_risk": tick_risk,
        "tick_value": spec["tick_value"],
        "tick_size": spec["tick_size"],
        "point_value": spec["point_value"],
        "margin_required": margin_required(contracts, contract_id),
        "account_balance": account_balance,
    }


def _root_contract(instrument_id: str) -> str:
    """Ensure parseable contract code — default ESZ26 for bare root."""
    text = (instrument_id or "").upper()
    if len(text) <= 4 and text.isalpha():
        return f"{text}Z26"
    return text
