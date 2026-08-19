"""Futures contract specifications catalog."""

from typing import Any, Dict

FUTURES_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "ES": {
        "name": "E-mini S&P 500",
        "exchange": "CME",
        "tick_size": 0.25,
        "tick_value": 12.50,
        "point_value": 50.0,
        "multiplier": 50,
        "margin": 13200,
    },
    "NQ": {
        "name": "E-mini Nasdaq-100",
        "exchange": "CME",
        "tick_size": 0.25,
        "tick_value": 5.00,
        "point_value": 20.0,
        "multiplier": 20,
        "margin": 18700,
    },
    "CL": {
        "name": "Crude Oil",
        "exchange": "NYMEX",
        "tick_size": 0.01,
        "tick_value": 10.00,
        "point_value": 1000.0,
        "multiplier": 1000,
        "margin": 6800,
    },
    "GC": {
        "name": "Gold",
        "exchange": "COMEX",
        "tick_size": 0.10,
        "tick_value": 10.00,
        "point_value": 100.0,
        "multiplier": 100,
        "margin": 9800,
    },
}


def get_contract_spec(root: str) -> Dict[str, Any]:
    """Return spec dict for a futures root symbol."""
    key = (root or "").upper()
    spec = FUTURES_CONTRACTS.get(key)
    if not spec:
        raise ValueError(f"Unknown futures root symbol: {root}")
    return dict(spec)
