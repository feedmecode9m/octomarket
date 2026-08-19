"""Unified market instrument model — stocks, forex, and futures."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_class import DEFAULT_EXCHANGES, AssetClass
from .contract import FuturesContract, build_contract, parse_contract_code
from .session_rules import SessionRules, get_session_rules

FUTURES_CODE_PATTERN = re.compile(r"^([A-Z]{1,4})([FGHJKMNQUVXZ])(\d{2})$")
FOREX_SPECS: Dict[str, Dict[str, Any]] = {
    "EURUSD": {"pip_size": 0.0001, "quote_currency": "USD", "base_currency": "EUR"},
    "GBPUSD": {"pip_size": 0.0001, "quote_currency": "USD", "base_currency": "GBP"},
    "USDJPY": {"pip_size": 0.01, "quote_currency": "JPY", "base_currency": "USD"},
    "AUDUSD": {"pip_size": 0.0001, "quote_currency": "USD", "base_currency": "AUD"},
}

STOCK_SPECS: Dict[str, Dict[str, Any]] = {
    "AAPL": {"exchange": "NASDAQ", "currency": "USD", "tick_size": 0.01},
    "MSFT": {"exchange": "NASDAQ", "currency": "USD", "tick_size": 0.01},
    "TSLA": {"exchange": "NASDAQ", "currency": "USD", "tick_size": 0.01},
}


@dataclass
class Instrument:
    """Tradeable instrument with asset-class-specific metadata."""

    symbol: str
    asset_class: AssetClass
    exchange: str
    tick_size: float
    currency: str = "USD"
    contract: Optional[str] = None
    contract_month: Optional[str] = None
    continuous_id: Optional[str] = None
    point_value: Optional[float] = None
    tick_value: Optional[float] = None
    multiplier: Optional[float] = None
    pip_size: Optional[float] = None
    base_currency: Optional[str] = None
    quote_currency: Optional[str] = None
    session: Optional[SessionRules] = field(default=None, repr=False)

    def display_symbol(self) -> str:
        if self.asset_class == AssetClass.FOREX and len(self.symbol) == 6:
            return f"{self.symbol[:3]}/{self.symbol[3:]}"
        if self.contract:
            return self.contract
        return self.symbol

    @property
    def instrument_id(self) -> str:
        """Canonical id for chart, plans, and journal."""
        return self.contract or self.symbol

    def pip_value(self, lot_units: int = 100_000) -> Optional[float]:
        """Quote-currency pip value for a standard lot size."""
        if self.asset_class != AssetClass.FOREX or not self.pip_size:
            return None
        return round(self.pip_size * lot_units, 4)

    def pips_between(self, entry: float, exit: float) -> Optional[float]:
        if self.asset_class != AssetClass.FOREX or not self.pip_size:
            return None
        return round(abs(exit - entry) / self.pip_size, 1)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "symbol": self.symbol,
            "instrument_id": self.instrument_id,
            "display_symbol": self.display_symbol(),
            "asset_class": self.asset_class.value,
            "exchange": self.exchange,
            "tick_size": self.tick_size,
            "currency": self.currency,
        }
        if self.contract:
            payload["contract"] = self.contract
        if self.contract_month:
            payload["contract_month"] = self.contract_month
        if self.continuous_id:
            payload["continuous_id"] = self.continuous_id
        if self.point_value is not None:
            payload["point_value"] = self.point_value
        if self.tick_value is not None:
            payload["tick_value"] = self.tick_value
        if self.multiplier is not None:
            payload["multiplier"] = self.multiplier
        if self.pip_size is not None:
            payload["pip_size"] = self.pip_size
        if self.base_currency:
            payload["base_currency"] = self.base_currency
        if self.quote_currency:
            payload["quote_currency"] = self.quote_currency
        if self.session:
            payload["session"] = self.session.to_dict()
        return payload


def normalize_symbol(raw: str) -> str:
    """Normalize user input to internal symbol form (EUR/USD → EURUSD)."""
    text = (raw or "").strip().upper().replace(" ", "")
    if not text:
        raise ValueError("Symbol required")

    if "/" in text:
        base, quote = text.split("/", 1)
        if len(base) == 3 and len(quote) == 3 and base.isalpha() and quote.isalpha():
            return f"{base}{quote}"

    return text.replace("/", "")


def detect_asset_class(symbol: str) -> AssetClass:
    normalized = normalize_symbol(symbol)
    if FUTURES_CODE_PATTERN.match(normalized):
        return AssetClass.FUTURES
    if normalized in FOREX_SPECS or (len(normalized) == 6 and normalized.isalpha()):
        return AssetClass.FOREX
    return AssetClass.STOCK


def resolve_instrument(raw: str) -> Instrument:
    """Build an Instrument from symbol or contract code."""
    normalized = normalize_symbol(raw)

    if FUTURES_CODE_PATTERN.match(normalized):
        contract = parse_contract_code(normalized)
        return _instrument_from_contract(contract)

    asset_class = detect_asset_class(normalized)
    if asset_class == AssetClass.FOREX:
        return _instrument_from_forex(normalized)
    return _instrument_from_stock(normalized)


def _instrument_from_stock(symbol: str) -> Instrument:
    spec = STOCK_SPECS.get(symbol, {})
    exchange = spec.get("exchange", DEFAULT_EXCHANGES[AssetClass.STOCK])
    session = get_session_rules(AssetClass.STOCK, exchange)
    return Instrument(
        symbol=symbol,
        asset_class=AssetClass.STOCK,
        exchange=exchange,
        tick_size=float(spec.get("tick_size", 0.01)),
        currency=spec.get("currency", "USD"),
        session=session,
    )


def _instrument_from_forex(symbol: str) -> Instrument:
    spec = FOREX_SPECS.get(symbol, {"pip_size": 0.0001, "quote_currency": "USD", "base_currency": symbol[:3]})
    pip_size = float(spec.get("pip_size", 0.0001))
    session = get_session_rules(AssetClass.FOREX, "FX")
    return Instrument(
        symbol=symbol,
        asset_class=AssetClass.FOREX,
        exchange="FX",
        tick_size=pip_size / 10,
        currency=spec.get("quote_currency", "USD"),
        pip_size=pip_size,
        base_currency=spec.get("base_currency", symbol[:3]),
        quote_currency=spec.get("quote_currency", symbol[3:]),
        session=session,
    )


def _instrument_from_contract(contract: FuturesContract) -> Instrument:
    session = get_session_rules(AssetClass.FUTURES, contract.exchange)
    return Instrument(
        symbol=contract.root,
        asset_class=AssetClass.FUTURES,
        exchange=contract.exchange,
        tick_size=contract.tick_size,
        currency="USD",
        contract=contract.contract,
        contract_month=contract.contract_month,
        continuous_id=contract.root,
        point_value=contract.point_value(),
        tick_value=contract.tick_value,
        multiplier=contract.multiplier,
        session=session,
    )


def list_instruments(asset_class: Optional[AssetClass] = None) -> List[Dict[str, Any]]:
    """Catalog of supported terminal instruments."""
    items: List[Instrument] = []
    for sym in STOCK_SPECS:
        items.append(_instrument_from_stock(sym))
    for sym in FOREX_SPECS:
        items.append(_instrument_from_forex(sym))
    for root, month in FUTURES_CATALOG:
        items.append(_instrument_from_contract(build_contract(root, month)))
    if asset_class:
        items = [i for i in items if i.asset_class == asset_class]
    return [i.to_dict() for i in items]


FUTURES_CATALOG = (
    ("ES", "2026-12"),
    ("NQ", "2026-12"),
    ("CL", "2026-12"),
    ("GC", "2026-12"),
)
