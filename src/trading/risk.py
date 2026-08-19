"""Risk calculations across asset classes."""

from typing import Any, Dict, Optional

from ..market.asset_class import AssetClass
from ..market.forex import pip_distance, pip_value, units_to_lots
from ..market.instrument import resolve_instrument


def max_loss(
    entry: float,
    stop: float,
    size: float,
    asset_class: AssetClass,
    symbol: str,
    account_currency: str = "USD",
) -> float:
    """Maximum loss if stop is hit."""
    if entry <= 0 or stop <= 0 or size <= 0:
        raise ValueError("Entry, stop, and size must be positive")

    if asset_class == AssetClass.FOREX:
        pip_risk = pip_distance(entry, stop, symbol)
        lots = size if size < 1000 else units_to_lots(int(size))
        per_lot = pip_value(symbol, entry, lots=1.0, account_currency=account_currency)
        return round(pip_risk * per_lot * lots, 2)

    points = abs(entry - stop)
    return round(points * size, 2)


def reward_ratio(risk_amount: float, reward_amount: float) -> float:
    if risk_amount <= 0:
        raise ValueError("Risk amount must be positive")
    return round(reward_amount / risk_amount, 2)


def account_risk_percent(risk_amount: float, account_balance: float) -> float:
    if account_balance <= 0:
        raise ValueError("Account balance must be positive")
    return round(risk_amount / account_balance * 100, 2)


def validate_forex_risk(
    plan: Dict[str, Any],
    account_balance: float,
    max_risk_percent: float = 2.0,
) -> Dict[str, Any]:
    """Validate forex plan risk against account budget."""
    risk_amount = plan.get("risk_amount")
    if risk_amount is None:
        risk_amount = max_loss(
            _price(plan.get("entry")),
            _price(plan.get("stop_loss")),
            plan.get("position_lots") or units_to_lots(plan.get("quantity", 0)),
            AssetClass.FOREX,
            plan.get("instrument_id") or plan.get("symbol"),
        )

    pct = account_risk_percent(risk_amount, account_balance)
    warnings = []
    if pct > max_risk_percent:
        warnings.append(f"Plan risks {pct}% of account (max recommended {max_risk_percent}%)")

    return {
        "risk_amount": round(risk_amount, 2),
        "account_risk_percent": pct,
        "within_limit": pct <= max_risk_percent,
        "warnings": warnings,
    }


def _price(level: Any) -> float:
    if isinstance(level, dict):
        return float(level["price"])
    return float(level)
