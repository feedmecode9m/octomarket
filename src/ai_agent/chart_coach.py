"""Chart coach — mentor reviews using structured market context."""

import threading
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from .market_context import build_market_context
from .plan_review import review_post_trade, review_pre_trade


class ChartCoach:
    """Educational chart and trade plan coach (no buy/sell recommendations)."""

    def __init__(self):
        self._lock = threading.RLock()
        self._history: Dict[str, List[Dict[str, Any]]] = {}

    def review_chart(
        self,
        symbol: str,
        price: Optional[float] = None,
        indicator_payload: Optional[Dict[str, Any]] = None,
        drawings: Optional[List[Dict[str, Any]]] = None,
        trade_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = build_market_context(
            symbol=symbol,
            price=price,
            indicator_payload=indicator_payload,
            drawings=drawings,
            trade_plan=trade_plan,
        )
        review = review_pre_trade(context)
        return self._store_review(symbol, context, review)

    def review_trade_plan(
        self,
        trade_plan: Dict[str, Any],
        price: Optional[float] = None,
        indicator_payload: Optional[Dict[str, Any]] = None,
        drawings: Optional[List[Dict[str, Any]]] = None,
        execution: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        symbol = trade_plan.get("symbol", "AAPL")
        context = build_market_context(
            symbol=symbol,
            price=price,
            indicator_payload=indicator_payload,
            drawings=drawings,
            trade_plan=trade_plan,
        )
        if execution:
            review = review_post_trade(context, execution)
        else:
            review = review_pre_trade(context)
        review["plan_id"] = trade_plan.get("id")
        return self._store_review(symbol, context, review)

    def get_history(self, symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
        symbol = symbol.upper()
        with self._lock:
            items = self._history.get(symbol, [])
            return deepcopy(items[:limit])

    def reset(self):
        with self._lock:
            self._history.clear()

    def _store_review(
        self,
        symbol: str,
        context: Dict[str, Any],
        review: Dict[str, Any],
    ) -> Dict[str, Any]:
        symbol = symbol.upper()
        entry = {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "context": context,
            **review,
        }
        with self._lock:
            self._history.setdefault(symbol, []).insert(0, deepcopy(entry))
            self._history[symbol] = self._history[symbol][:50]
        return deepcopy(entry)


_coach_instance: Optional[ChartCoach] = None


def get_chart_coach() -> ChartCoach:
    global _coach_instance
    if _coach_instance is None:
        _coach_instance = ChartCoach()
    return _coach_instance
