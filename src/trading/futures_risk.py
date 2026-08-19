"""Futures-specific risk and margin validation."""

from typing import Any, Dict

from ..market.asset_class import AssetClass
from ..market.futures import margin_required, risk_amount, tick_distance
from .risk import account_risk_percent


def max_loss(
    entry: float,
    stop: float,
    contracts: int,
    instrument_id: str,
) -> float:
    return risk_amount(entry, stop, int(contracts), instrument_id)


def validate_futures_margin(
    contracts: int,
    instrument_id: str,
    account_balance: float,
) -> Dict[str, Any]:
    """Check whether account can support initial margin."""
    required = margin_required(contracts, instrument_id)
    available = account_balance
    warnings = []
    if required > available:
        warnings.append(
            f"Margin ${required:,.0f} exceeds available balance ${available:,.0f}"
        )
    return {
        "margin_required": required,
        "account_balance": available,
        "within_margin": required <= available,
        "warnings": warnings,
    }


def validate_futures_risk(
    plan: Dict[str, Any],
    account_balance: float,
    max_risk_percent: float = 2.0,
) -> Dict[str, Any]:
    """Validate futures plan risk and margin."""
    instrument_id = plan.get("instrument_id") or plan.get("symbol", "")
    entry = _price(plan.get("entry"))
    stop = _price(plan.get("stop_loss"))
    contracts = int(plan.get("contracts") or plan.get("quantity") or 1)

    risk = plan.get("risk_amount")
    if risk is None:
        risk = max_loss(entry, stop, contracts, instrument_id)

    pct = account_risk_percent(risk, account_balance)
    margin = validate_futures_margin(contracts, instrument_id, account_balance)

    warnings = list(margin["warnings"])
    if pct > max_risk_percent:
        warnings.append(f"Plan risks {pct}% of account (max recommended {max_risk_percent}%)")

    return {
        "risk_amount": round(risk, 2),
        "account_risk_percent": pct,
        "tick_risk": plan.get("tick_risk") or tick_distance(entry, stop, instrument_id),
        "within_limit": pct <= max_risk_percent and margin["within_margin"],
        "margin_required": margin["margin_required"],
        "warnings": warnings,
    }


def mixed_asset_max_loss(
    entry: float,
    stop: float,
    size: float,
    asset_class: AssetClass,
    instrument_id: str,
    account_currency: str = "USD",
) -> float:
    """Unified max-loss entry point across asset classes."""
    if asset_class == AssetClass.FUTURES:
        return max_loss(entry, stop, int(size), instrument_id)
    from .risk import max_loss as unified

    return unified(entry, stop, size, asset_class, instrument_id, account_currency)


def _price(level: Any) -> float:
    if isinstance(level, dict):
        return float(level["price"])
    return float(level)
