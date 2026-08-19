"""Trading session rules by asset class and venue."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .asset_class import AssetClass


@dataclass(frozen=True)
class SessionWindow:
    """One continuous trading window (local exchange time description)."""

    label: str
    open_time: str
    close_time: str
    timezone: str
    days: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "open": self.open_time,
            "close": self.close_time,
            "timezone": self.timezone,
            "days": self.days,
        }


@dataclass(frozen=True)
class SessionRules:
    """Session behavior for an instrument or venue."""

    asset_class: AssetClass
    venue: str
    is_24h: bool
    windows: List[SessionWindow]
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_class": self.asset_class.value,
            "venue": self.venue,
            "is_24h": self.is_24h,
            "windows": [w.to_dict() for w in self.windows],
            "notes": self.notes,
        }


NYSE_REGULAR = SessionRules(
    asset_class=AssetClass.STOCK,
    venue="NYSE",
    is_24h=False,
    windows=[
        SessionWindow("Regular", "09:30", "16:00", "America/New_York", "Mon-Fri"),
        SessionWindow("Pre-market", "04:00", "09:30", "America/New_York", "Mon-Fri"),
        SessionWindow("After-hours", "16:00", "20:00", "America/New_York", "Mon-Fri"),
    ],
    notes="US equities regular and extended hours.",
)

FOREX_WEEK = SessionRules(
    asset_class=AssetClass.FOREX,
    venue="FX",
    is_24h=True,
    windows=[
        SessionWindow("Weekly", "00:00", "23:59", "UTC", "Sun-Fri"),
    ],
    notes="Forex runs continuously Sunday open through Friday close.",
)

ES_GLOBEX = SessionRules(
    asset_class=AssetClass.FUTURES,
    venue="CME_GLOBEX",
    is_24h=False,
    windows=[
        SessionWindow("Globex", "18:00", "17:00", "America/Chicago", "Sun-Fri"),
    ],
    notes="ES trades nearly 24h with daily maintenance break.",
)

SESSION_REGISTRY: Dict[str, SessionRules] = {
    "NYSE": NYSE_REGULAR,
    "FX": FOREX_WEEK,
    "CME": ES_GLOBEX,
    "CME_GLOBEX": ES_GLOBEX,
}


def get_session_rules(
    asset_class: AssetClass,
    exchange: Optional[str] = None,
) -> SessionRules:
    """Resolve session rules for an asset class and optional exchange."""
    if exchange:
        key = exchange.upper()
        if key in SESSION_REGISTRY:
            return SESSION_REGISTRY[key]

    defaults = {
        AssetClass.STOCK: NYSE_REGULAR,
        AssetClass.FOREX: FOREX_WEEK,
        AssetClass.FUTURES: ES_GLOBEX,
    }
    return defaults[asset_class]
