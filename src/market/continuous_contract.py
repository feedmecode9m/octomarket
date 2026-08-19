"""Futures continuous contract identity — root symbol mapped to active expiration."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .asset_class import AssetClass
from .contract import FuturesContract, build_contract, parse_contract_code
from .contract_specs import FUTURES_CONTRACTS, get_contract_spec
from .instrument import FUTURES_CODE_PATTERN, FUTURES_CATALOG, normalize_symbol, resolve_instrument


@dataclass(frozen=True)
class ContinuousContract:
    """
    Continuous futures identity (e.g. ES) mapped to a catalog active contract.

    Replay and historical loaders can reference continuous_id while execution
    and plans continue to use expiration-specific instrument IDs.
    """

    continuous_id: str
    root_symbol: str
    exchange: str
    active_contract: str
    contract_month: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "continuous_id": self.continuous_id,
            "root_symbol": self.root_symbol,
            "exchange": self.exchange,
            "active_contract": self.active_contract,
            "contract_month": self.contract_month,
        }


def is_futures_root(symbol: str) -> bool:
    """Return True when symbol is a supported futures root (ES, NQ, CL, GC)."""
    return normalize_symbol(symbol) in FUTURES_CONTRACTS


def get_active_contract(root: str) -> FuturesContract:
    """Return the catalog-designated front-month contract for a futures root."""
    key = normalize_symbol(root)
    for catalog_root, contract_month in FUTURES_CATALOG:
        if catalog_root == key:
            return build_contract(catalog_root, contract_month)
    raise ValueError(f"No active contract configured for futures root: {root}")


def continuous_id_for(instrument_id: str) -> Optional[str]:
    """Return continuous root id for a futures instrument, else None."""
    continuous = resolve_continuous(instrument_id)
    return continuous.continuous_id if continuous else None


def resolve_continuous(instrument_id: str) -> Optional[ContinuousContract]:
    """
    Resolve a futures instrument or root to its continuous contract identity.

    Expiration-specific codes (ESZ26, ESH27) share the same continuous_id as
    their root. Stocks and forex return None.
    """
    normalized = normalize_symbol(instrument_id)

    if FUTURES_CODE_PATTERN.match(normalized):
        root = parse_contract_code(normalized).root
    elif is_futures_root(normalized):
        root = normalized
    else:
        instrument = resolve_instrument(normalized)
        if instrument.asset_class != AssetClass.FUTURES:
            return None
        root = instrument.symbol

    active = get_active_contract(root)
    spec = get_contract_spec(root)
    return ContinuousContract(
        continuous_id=root,
        root_symbol=root,
        exchange=spec.get("exchange", active.exchange),
        active_contract=active.contract,
        contract_month=active.contract_month,
    )
