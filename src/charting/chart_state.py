"""Chart workspace state — symbol, timeframe, range, indicators, drawings."""

import threading
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from .timeframe import DEFAULT_INTERVAL, normalize_interval, validate_timeframe
from ..market.asset_class import AssetClass
from ..market.instrument import resolve_instrument
from ..market.session_rules import get_session_rules


class ChartStateManager:
    """Persist the trader's chart decision workspace in memory."""

    def __init__(self):
        self._lock = threading.RLock()
        self._state = self._default_state()

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._state)

    def update(self, **fields) -> Dict[str, Any]:
        with self._lock:
            if "symbol" in fields and fields["symbol"]:
                self._apply_instrument(str(fields["symbol"]))

            if "instrument_id" in fields and fields["instrument_id"]:
                self._apply_instrument(str(fields["instrument_id"]))

            if "timeframe" in fields and fields["timeframe"]:
                interval = normalize_interval(fields["timeframe"])
                period = fields.get("period")
                _, norm_period = validate_timeframe(interval, period or self._state.get("period"))
                self._state["timeframe"] = interval
                self._state["period"] = norm_period

            if "period" in fields and fields["period"] and "timeframe" not in fields:
                _, norm_period = validate_timeframe(self._state["timeframe"], fields["period"])
                self._state["period"] = norm_period

            if "zoom" in fields and fields["zoom"] is not None:
                zoom = fields["zoom"]
                self._state["zoom"] = {
                    "start": zoom.get("start"),
                    "end": zoom.get("end"),
                }

            if "indicators" in fields and fields["indicators"] is not None:
                self._state["indicators"] = self._normalize_indicators(fields["indicators"])

            if "drawings" in fields and fields["drawings"] is not None:
                self._state["drawings"] = self._normalize_drawings(fields["drawings"])

            self._state["updated_at"] = datetime.now().isoformat()
            return deepcopy(self._state)

    def add_indicator(self, indicator: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            entry = {
                "id": indicator.get("id") or str(uuid.uuid4()),
                "type": indicator.get("type", "").upper(),
                "period": indicator.get("period"),
                "pane": indicator.get("pane", "main"),
                "params": indicator.get("params") or {},
            }
            self._state["indicators"].append(entry)
            self._state["updated_at"] = datetime.now().isoformat()
            return deepcopy(entry)

    def add_drawing(self, drawing: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            entry = {
                "id": drawing.get("id") or str(uuid.uuid4()),
                "type": drawing.get("type", "horizontal"),
                "price": drawing.get("price"),
                "top": drawing.get("top"),
                "bottom": drawing.get("bottom"),
                "label": drawing.get("label", ""),
                "points": drawing.get("points") or [],
            }
            self._state["drawings"].append(entry)
            self._state["updated_at"] = datetime.now().isoformat()
            return deepcopy(entry)

    def _apply_instrument(self, raw: str):
        instrument = resolve_instrument(raw)
        session = get_session_rules(instrument.asset_class, instrument.exchange)
        self._state["symbol"] = instrument.symbol
        self._state["instrument_id"] = instrument.instrument_id
        self._state["asset_class"] = instrument.asset_class.value
        self._state["display_symbol"] = instrument.display_symbol()
        self._state["session"] = session.to_dict()

    def reset(self):
        with self._lock:
            self._state = self._default_state()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "symbol": "AAPL",
            "instrument_id": "AAPL",
            "asset_class": "STOCK",
            "display_symbol": "AAPL",
            "session": get_session_rules(AssetClass.STOCK, "NASDAQ").to_dict(),
            "timeframe": DEFAULT_INTERVAL,
            "period": "5d",
            "zoom": {"start": None, "end": None},
            "indicators": [],
            "drawings": [],
            "updated_at": datetime.now().isoformat(),
        }

    def _normalize_indicators(self, indicators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for ind in indicators:
            if not ind.get("type"):
                continue
            result.append({
                "id": ind.get("id") or str(uuid.uuid4()),
                "type": str(ind["type"]).upper(),
                "period": ind.get("period"),
                "pane": ind.get("pane", "main"),
                "params": ind.get("params") or {},
            })
        return result

    def _normalize_drawings(self, drawings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for d in drawings:
            if not d.get("type"):
                continue
            result.append({
                "id": d.get("id") or str(uuid.uuid4()),
                "type": d["type"],
                "price": d.get("price"),
                "top": d.get("top"),
                "bottom": d.get("bottom"),
                "label": d.get("label", ""),
                "points": d.get("points") or [],
            })
        return result


_manager_instance: Optional[ChartStateManager] = None


def get_chart_state() -> ChartStateManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ChartStateManager()
    return _manager_instance
