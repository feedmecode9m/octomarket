"""Market snapshot capture at trade decision time."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..market.asset_class import AssetClass
from ..market.continuous_contract import continuous_id_for
from ..market.instrument import resolve_instrument

RECENT_CANDLE_LIMIT = 20
DEFAULT_INDICATOR_QUERY = "SMA20,RSI"
SNAPSHOT_SCHEMA_VERSION = 1


def capture_market_snapshot(
    instrument_id: str,
    *,
    chart_state: Optional[Dict[str, Any]] = None,
    recent_candle_limit: int = RECENT_CANDLE_LIMIT,
) -> Dict[str, Any]:
    """
    Capture what the trader could see when making a decision.

    Copies decision-relevant market context; does not duplicate the full trade plan.
    """
    if chart_state is None:
        from ..charting.chart_state import get_chart_state

        chart_state = get_chart_state().get_state()

    instrument = resolve_instrument(instrument_id)
    timeframe = chart_state.get("timeframe")
    period = chart_state.get("period")

    candle_payload = _load_candles(instrument.instrument_id, timeframe, period)
    recent = _compact_candles(candle_payload, recent_candle_limit)
    indicator_query = _indicator_query_from_config(chart_state.get("indicators") or [])
    indicator_values = _compute_latest_indicators(candle_payload, indicator_query)
    session_context = _capture_session_context(instrument.instrument_id, candle_payload)
    drawings = _resolve_drawings(instrument.symbol, chart_state)

    snapshot: Dict[str, Any] = {
        "snapshot_id": str(uuid.uuid4()),
        "captured_at": datetime.now().isoformat(),
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "instrument": _instrument_block(instrument),
        "chart": {
            "timeframe": timeframe,
            "period": period,
            "zoom": deepcopy(chart_state.get("zoom") or {}),
            "display_symbol": chart_state.get("display_symbol") or instrument.display_symbol(),
        },
        "session_context": session_context,
        "price": _price_block(candle_payload, recent),
        "indicators": {
            "configured": deepcopy(chart_state.get("indicators") or []),
            "query": indicator_query,
            "latest": indicator_values,
        },
        "structure": {
            "drawings": drawings,
            "drawing_count": len(drawings),
        },
    }
    return snapshot


def _instrument_block(instrument) -> Dict[str, Any]:
    block: Dict[str, Any] = {
        "instrument_id": instrument.instrument_id,
        "asset_class": instrument.asset_class.value,
        "symbol": instrument.symbol,
        "session": instrument.session.to_dict() if instrument.session else None,
    }
    if instrument.asset_class == AssetClass.FUTURES:
        block["continuous_id"] = instrument.continuous_id or continuous_id_for(instrument.instrument_id)
        if instrument.contract:
            block["contract"] = instrument.contract
        if instrument.contract_month:
            block["contract_month"] = instrument.contract_month
    return block


def _load_candles(instrument_id: str, timeframe: Optional[str], period: Optional[str]) -> Dict[str, Any]:
    from ..charting.candle_engine import get_candle_engine

    interval = timeframe or "1d"
    lookback = period or "5d"
    try:
        return get_candle_engine().get_candles(
            instrument_id,
            interval=interval,
            period=lookback,
            respect_session=True,
        )
    except Exception:
        return _empty_candle_payload(instrument_id, interval, lookback)


def _empty_candle_payload(symbol: str, interval: str, period: str) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "timeframe": interval,
        "period": period,
        "count": 0,
        "session_capped": False,
        "cap_index": None,
        "timestamps": [],
        "open": [],
        "high": [],
        "low": [],
        "close": [],
        "volume": [],
    }


def _compact_candles(payload: Dict[str, Any], limit: int) -> Dict[str, Any]:
    count = int(payload.get("count") or 0)
    if count <= 0:
        return {"count": 0, "timestamps": [], "open": [], "high": [], "low": [], "close": [], "volume": []}

    start = max(0, count - limit)
    return {
        "count": count - start,
        "timestamps": payload.get("timestamps", [])[start:],
        "open": payload.get("open", [])[start:],
        "high": payload.get("high", [])[start:],
        "low": payload.get("low", [])[start:],
        "close": payload.get("close", [])[start:],
        "volume": payload.get("volume", [])[start:],
    }


def _price_block(candle_payload: Dict[str, Any], recent: Dict[str, Any]) -> Dict[str, Any]:
    closes = recent.get("close") or []
    highs = recent.get("high") or []
    lows = recent.get("low") or []
    current = closes[-1] if closes else None

    volatility: Dict[str, Any] = {}
    if closes and highs and lows:
        volatility["last_bar_range"] = round(highs[-1] - lows[-1], 6)
        if len(closes) >= 2 and closes[-2]:
            volatility["change_pct"] = round((closes[-1] - closes[-2]) / closes[-2] * 100, 4)

    return {
        "current": current,
        "candle_count": candle_payload.get("count", 0),
        "session_capped": bool(candle_payload.get("session_capped")),
        "cap_index": candle_payload.get("cap_index"),
        "recent_candles": recent,
        "volatility": volatility,
    }


def _capture_session_context(instrument_id: str, candle_payload: Dict[str, Any]) -> Dict[str, Any]:
    from ..simulation.session import get_market_session

    session = get_market_session()
    context: Dict[str, Any] = {
        "mode": "replay" if session.is_active() and session.has_symbol(instrument_id) else "live",
        "simulator_active": session.is_active(),
        "candle_index": session.get_session_index() if session.is_active() else None,
        "session_capped": bool(candle_payload.get("session_capped")),
    }
    if session.is_active():
        state = session.get_state()
        context["simulator_state"] = state.get("state")
        context["progress_pct"] = state.get("progress_pct")
    return context


def _resolve_drawings(symbol: str, chart_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    drawings = chart_state.get("drawings") or []
    if drawings:
        return deepcopy(drawings)

    from ..charting.drawing_store import get_drawing_store

    stored = get_drawing_store().list_drawings(symbol)
    return deepcopy(stored)


def _indicator_query_from_config(indicators: List[Dict[str, Any]]) -> str:
    tokens: List[str] = []
    for ind in indicators:
        ind_type = str(ind.get("type", "")).upper()
        period = ind.get("period")
        if ind_type in ("SMA", "EMA") and period:
            tokens.append(f"{ind_type}{period}")
        elif ind_type in ("RSI", "MACD", "BB"):
            tokens.append(ind_type)
    return ",".join(tokens) if tokens else DEFAULT_INDICATOR_QUERY


def _compute_latest_indicators(candle_payload: Dict[str, Any], query: str) -> Dict[str, Any]:
    if not candle_payload.get("close"):
        return {}
    try:
        from ..charting.indicators import compute_indicators_for_candles

        payload = compute_indicators_for_candles(candle_payload, query)
        return _latest_indicator_values(payload.get("indicators") or {})
    except Exception:
        return {}


def _latest_indicator_values(indicators: Dict[str, Any]) -> Dict[str, Any]:
    latest: Dict[str, Any] = {}
    for key, data in indicators.items():
        if not isinstance(data, dict):
            continue
        if "values" in data:
            values = [v for v in data["values"] if v is not None]
            if values:
                latest[key] = values[-1]
            continue
        if "macd" in data:
            macd_vals = [v for v in data.get("macd", []) if v is not None]
            signal_vals = [v for v in data.get("signal", []) if v is not None]
            hist_vals = [v for v in data.get("histogram", []) if v is not None]
            entry: Dict[str, Any] = {}
            if macd_vals:
                entry["macd"] = macd_vals[-1]
            if signal_vals:
                entry["signal"] = signal_vals[-1]
            if hist_vals:
                entry["histogram"] = hist_vals[-1]
            if entry:
                latest[key] = entry
            continue
        if "upper" in data:
            upper = [v for v in data.get("upper", []) if v is not None]
            middle = [v for v in data.get("middle", []) if v is not None]
            lower = [v for v in data.get("lower", []) if v is not None]
            entry = {}
            if upper:
                entry["upper"] = upper[-1]
            if middle:
                entry["middle"] = middle[-1]
            if lower:
                entry["lower"] = lower[-1]
            if entry:
                latest[key] = entry
    return latest
