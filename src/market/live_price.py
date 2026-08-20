"""LIVE PAPER price resolution — never uses REPLAY session closes."""

from __future__ import annotations

from typing import Dict, Optional


def live_watchlist_prices() -> Dict[str, float]:
    """Return positive prices currently held on the LIVE watchlist."""
    from .watchlist import get_watchlist

    prices: Dict[str, float] = {}
    for entry in get_watchlist().get_all():
        price = float(entry.get("price") or 0)
        if price > 0:
            prices[str(entry.get("symbol", "")).upper()] = price
    return prices


def fetch_live_quote(symbol: str) -> float:
    """Fetch a fresh LIVE market last price (not session/replay)."""
    symbol = (symbol or "").upper()
    if not symbol:
        return 0.0
    from ..core.data_fetcher import DataFetcher

    fetcher = DataFetcher(symbol=symbol, interval="1d", period="5d")
    df = fetcher.get_real_time_data()
    if df is None or getattr(df, "empty", True):
        return 0.0
    return float(df["Close"].iloc[-1])


def resolve_live_price(symbol: str, *, allow_fetch: bool = True) -> float:
    """
    Resolve an authoritative LIVE PAPER execution price.

    Order of preference:
    1) LIVE watchlist quote
    2) fresh market fetch (optional)

    Never consult MarketSession / replay candle closes.
    """
    symbol = (symbol or "").upper()
    if not symbol:
        return 0.0

    prices = live_watchlist_prices()
    if symbol in prices and prices[symbol] > 0:
        return prices[symbol]

    if allow_fetch:
        return fetch_live_quote(symbol)
    return 0.0


def resolve_execution_prices(*, for_symbol: Optional[str] = None) -> Dict[str, float]:
    """
    Mode-aware price map for execution/valuation.

    REPLAY  → MarketSession candle closes (authoritative for replay fills)
    LIVE    → watchlist / live quotes only (never residual replay prices)
    """
    from ..replay.replay_session import is_replay_mode
    from ..simulation.session import get_market_session

    if is_replay_mode():
        return dict(get_market_session().get_state().get("prices") or {})

    prices = live_watchlist_prices()
    if for_symbol:
        sym = for_symbol.upper()
        if sym not in prices or prices[sym] <= 0:
            quote = resolve_live_price(sym, allow_fetch=True)
            if quote > 0:
                prices[sym] = quote
    return prices
