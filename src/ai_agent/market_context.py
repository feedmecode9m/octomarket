"""Build structured market context for AI chart coaching."""

from typing import Any, Dict, List, Optional


def _summarize_macd(macd_data: Optional[Dict[str, Any]]) -> str:
    if not macd_data:
        return "unavailable"
    macd_line = macd_data.get("macd") or []
    signal_line = macd_data.get("signal") or []
    if not macd_line or not signal_line:
        return "unavailable"
    last_macd = next((v for v in reversed(macd_line) if v is not None), None)
    last_signal = next((v for v in reversed(signal_line) if v is not None), None)
    if last_macd is None or last_signal is None:
        return "unavailable"
    if last_macd > last_signal:
        return "bullish crossover"
    if last_macd < last_signal:
        return "bearish crossover"
    return "neutral"


def _summarize_rsi(rsi_values: Optional[List[Any]]) -> Optional[float]:
    if not rsi_values:
        return None
    for val in reversed(rsi_values):
        if val is not None:
            return round(float(val), 2)
    return None


def _summarize_sma(sma_values: Optional[List[Any]]) -> Optional[float]:
    if not sma_values:
        return None
    for val in reversed(sma_values):
        if val is not None:
            return round(float(val), 2)
    return None


def normalize_drawings(drawings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize drawing list for coach context."""
    result = []
    for d in drawings or []:
        dtype = d.get("type", "level")
        label = (d.get("label") or "").lower()
        entry: Dict[str, Any] = {"type": dtype, "id": d.get("id")}
        if dtype == "horizontal":
            entry["price"] = d.get("price")
            if "resist" in label:
                entry["role"] = "resistance"
            elif "support" in label or "demand" in label:
                entry["role"] = "support"
            else:
                entry["role"] = "level"
        elif dtype == "zone":
            entry["top"] = d.get("top")
            entry["bottom"] = d.get("bottom")
            entry["role"] = "supply" if "supply" in label else "demand" if "demand" in label else "zone"
        elif dtype == "trendline":
            entry["start"] = d.get("start")
            entry["end"] = d.get("end")
            entry["role"] = "trend"
        if d.get("label"):
            entry["label"] = d["label"]
        result.append(entry)
    return result


def normalize_trade_plan(plan: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not plan:
        return None
    entry = plan.get("entry") or {}
    stop = plan.get("stop_loss") or {}
    target = plan.get("target") or {}
    direction = (plan.get("direction") or "LONG").upper()
    quantity = int(plan.get("quantity") or 1)
    entry_price = entry.get("price") if isinstance(entry, dict) else entry
    stop_price = stop.get("price") if isinstance(stop, dict) else stop
    target_price = target.get("price") if isinstance(target, dict) else target

    rr = plan.get("risk_reward") or plan.get("rr")
    risk_points = plan.get("risk_points")
    reward_points = plan.get("reward_points")
    if rr is None and entry_price and stop_price and target_price:
        try:
            from ..trading.trade_plan import calculate_risk_reward
            metrics = calculate_risk_reward(direction, float(entry_price), float(stop_price), float(target_price), quantity)
            rr = metrics["risk_reward"]
            risk_points = metrics["risk_points"]
            reward_points = metrics["reward_points"]
        except ValueError:
            pass

    return {
        "id": plan.get("id"),
        "symbol": plan.get("symbol"),
        "direction": direction,
        "thesis": plan.get("thesis"),
        "entry": entry_price,
        "entry_source": entry.get("source") if isinstance(entry, dict) else None,
        "stop": stop_price,
        "target": target_price,
        "rr": rr,
        "risk_points": risk_points,
        "reward_points": reward_points,
        "status": plan.get("status"),
        "setup": plan.get("setup") or {},
    }


def build_indicator_summary(indicator_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract coach-friendly indicator snapshot from Phase 13C payload."""
    if not indicator_payload:
        return {}
    indicators = indicator_payload.get("indicators") or indicator_payload
    summary: Dict[str, Any] = {}

    if isinstance(indicators, dict):
        if "SMA20" in indicators:
            sma = indicators["SMA20"]
            val = _summarize_sma(sma.get("values") if isinstance(sma, dict) else sma)
            if val is not None:
                summary["SMA20"] = val
        if "RSI" in indicators:
            rsi = indicators["RSI"]
            val = _summarize_rsi(rsi.get("values") if isinstance(rsi, dict) else rsi)
            if val is not None:
                summary["RSI"] = val
        if "MACD" in indicators:
            macd = indicators["MACD"]
            summary["MACD"] = _summarize_macd(macd if isinstance(macd, dict) else None)
        for key, item in indicators.items():
            if key in summary:
                continue
            if isinstance(item, dict) and item.get("values"):
                val = _summarize_sma(item["values"])
                if val is not None:
                    summary[key] = val
    return summary


def build_market_context(
    symbol: str,
    price: Optional[float] = None,
    indicator_payload: Optional[Dict[str, Any]] = None,
    drawings: Optional[List[Dict[str, Any]]] = None,
    trade_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble structured state for chart coach (no raw pixels)."""
    symbol = symbol.upper()
    indicators = build_indicator_summary(indicator_payload)
    norm_drawings = normalize_drawings(drawings or [])
    norm_plan = normalize_trade_plan(trade_plan)

    if price is None and norm_plan and norm_plan.get("entry"):
        price = norm_plan["entry"]

    return {
        "symbol": symbol,
        "price": price,
        "indicators": indicators,
        "drawings": norm_drawings,
        "trade_plan": norm_plan,
    }
