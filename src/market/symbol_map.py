"""Map instrument ids to market data feed symbols."""

from .asset_class import AssetClass
from .instrument import resolve_instrument


def data_feed_symbol(instrument_id: str) -> str:
    """Resolve yfinance-compatible symbol for OHLCV fetch."""
    instrument = resolve_instrument(instrument_id)
    if instrument.asset_class == AssetClass.FOREX:
        return f"{instrument.symbol}=X"
    if instrument.asset_class == AssetClass.FUTURES:
        return f"{instrument.symbol}=F"
    return instrument.symbol


def chart_storage_symbol(instrument_id: str) -> str:
    """Symbol key for drawings/watchlist (workspace symbol field)."""
    return resolve_instrument(instrument_id).symbol
