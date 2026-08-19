"""Asset class taxonomy for OctoMarket instruments."""

from enum import Enum


class AssetClass(str, Enum):
    STOCK = "STOCK"
    FOREX = "FOREX"
    FUTURES = "FUTURES"

    @classmethod
    def from_value(cls, value: str) -> "AssetClass":
        normalized = (value or "").strip().upper()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Unknown asset class: {value}")


DEFAULT_EXCHANGES = {
    AssetClass.STOCK: "NYSE",
    AssetClass.FOREX: "FX",
    AssetClass.FUTURES: "CME",
}
