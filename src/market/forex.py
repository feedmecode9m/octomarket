"""Forex pip and lot calculations."""

from typing import Optional

STANDARD_LOT_UNITS = 100_000
MINI_LOT_UNITS = 10_000
MICRO_LOT_UNITS = 1_000

FOREX_PIP_SIZES = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "AUDUSD": 0.0001,
    "USDJPY": 0.01,
    "EURJPY": 0.01,
    "GBPJPY": 0.01,
}

JPY_QUOTE_PAIRS = {"USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"}


def normalize_pair(symbol: str) -> str:
    text = (symbol or "").strip().upper().replace(" ", "").replace("/", "")
    if not text or len(text) != 6:
        raise ValueError(f"Invalid forex pair: {symbol}")
    return text


def pip_size(symbol: str) -> float:
    """Pip size for a currency pair."""
    pair = normalize_pair(symbol)
    if pair in FOREX_PIP_SIZES:
        return FOREX_PIP_SIZES[pair]
    if pair.endswith("JPY"):
        return 0.01
    return 0.0001


def quote_currency(symbol: str) -> str:
    return normalize_pair(symbol)[3:6]


def pip_distance(entry: float, stop: float, symbol: str) -> float:
    """Absolute stop distance in pips."""
    if entry <= 0 or stop <= 0:
        raise ValueError("Entry and stop must be positive")
    size = pip_size(symbol)
    return round(abs(entry - stop) / size, 1)


def lot_to_units(lots: float) -> int:
    """Convert standard-lot fraction to base units."""
    if lots <= 0:
        raise ValueError("Lots must be positive")
    return int(round(lots * STANDARD_LOT_UNITS))


def units_to_lots(units: int) -> float:
    return round(units / STANDARD_LOT_UNITS, 4)


def pip_value(
    symbol: str,
    entry_price: float,
    lots: float = 1.0,
    account_currency: str = "USD",
) -> float:
    """
    Pip value in account currency for a given lot size.

    USD-quoted pairs (EURUSD): pip_size × units.
    JPY-quoted pairs (USDJPY): pip_size × units / entry_rate when account is USD.
    """
    if entry_price <= 0:
        raise ValueError("Entry price must be positive")
    if lots <= 0:
        raise ValueError("Lots must be positive")

    pair = normalize_pair(symbol)
    units = lot_to_units(lots)
    pip = pip_size(pair)
    account_currency = account_currency.upper()
    quote = quote_currency(pair)

    if quote == account_currency:
        return round(pip * units, 4)

    if quote == "JPY" and account_currency == "USD":
        return round(pip * units / entry_price, 4)

    # Fallback for other crosses — pip value in quote currency
    return round(pip * units, 4)


def pips_between(entry: float, exit_price: float, symbol: str) -> float:
    return pip_distance(entry, exit_price, symbol)
