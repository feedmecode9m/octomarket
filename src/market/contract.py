"""Futures contract model — month codes, tick value, and P/L."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# CME month codes (single-letter)
MONTH_CODES = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}

REVERSE_MONTH_CODES = {v: k for k, v in MONTH_CODES.items()}

# Root symbol specs used in Phase 14A (expanded in 14C)
FUTURES_SPECS: Dict[str, Dict[str, float]] = {
    "ES": {"tick_size": 0.25, "tick_value": 12.50, "multiplier": 50},
    "NQ": {"tick_size": 0.25, "tick_value": 5.00, "multiplier": 20},
    "CL": {"tick_size": 0.01, "tick_value": 10.00, "multiplier": 1000},
    "GC": {"tick_size": 0.10, "tick_value": 10.00, "multiplier": 100},
}

CONTRACT_PATTERN = re.compile(r"^([A-Z]{1,4})([FGHJKMNQUVXZ])(\d{2})$")


@dataclass
class FuturesContract:
    """Single futures contract (e.g. ESZ26)."""

    root: str
    month_code: str
    year_suffix: int
    tick_size: float
    tick_value: float
    multiplier: float
    exchange: str = "CME"

    @property
    def symbol(self) -> str:
        return self.root

    @property
    def contract(self) -> str:
        return f"{self.root}{self.month_code}{self.year_suffix:02d}"

    @property
    def contract_month(self) -> str:
        month = MONTH_CODES.get(self.month_code.upper(), 1)
        year = 2000 + self.year_suffix if self.year_suffix < 100 else self.year_suffix
        return f"{year}-{month:02d}"

    def point_value(self) -> float:
        """Dollar value per 1.00 index/point move."""
        if self.tick_size <= 0:
            return 0.0
        return round(self.tick_value / self.tick_size, 4)

    def pnl(self, entry: float, exit: float, contracts: int = 1) -> float:
        """Realized P/L for a futures position."""
        points = exit - entry
        return round(points * self.point_value() * contracts, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.root,
            "contract": self.contract,
            "contract_month": self.contract_month,
            "exchange": self.exchange,
            "tick_size": self.tick_size,
            "tick_value": self.tick_value,
            "multiplier": self.multiplier,
            "point_value": self.point_value(),
        }


def parse_contract_code(code: str, exchange: str = "CME") -> FuturesContract:
    """Parse ESZ26-style contract codes."""
    normalized = (code or "").upper().replace(" ", "")
    match = CONTRACT_PATTERN.match(normalized)
    if not match:
        raise ValueError(f"Invalid futures contract code: {code}")

    root, month_code, year_suffix = match.group(1), match.group(2), int(match.group(3))
    specs = FUTURES_SPECS.get(root)
    if not specs:
        raise ValueError(f"Unknown futures root symbol: {root}")

    return FuturesContract(
        root=root,
        month_code=month_code,
        year_suffix=year_suffix,
        tick_size=specs["tick_size"],
        tick_value=specs["tick_value"],
        multiplier=specs["multiplier"],
        exchange=exchange,
    )


def build_contract(root: str, contract_month: str, exchange: str = "CME") -> FuturesContract:
    """Build contract from root + YYYY-MM month string."""
    root = root.upper()
    year_str, month_str = contract_month.split("-")
    year = int(year_str)
    month = int(month_str)
    month_code = REVERSE_MONTH_CODES.get(month)
    if not month_code:
        raise ValueError(f"Invalid contract month: {contract_month}")

    specs = FUTURES_SPECS.get(root)
    if not specs:
        raise ValueError(f"Unknown futures root symbol: {root}")

    return FuturesContract(
        root=root,
        month_code=month_code,
        year_suffix=year % 100,
        tick_size=specs["tick_size"],
        tick_value=specs["tick_value"],
        multiplier=specs["multiplier"],
        exchange=exchange,
    )
