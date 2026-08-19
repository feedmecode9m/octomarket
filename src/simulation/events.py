"""Educational market events during simulation."""

import random
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


EVENT_TEMPLATES = [
    {
        "type": "earnings_surprise",
        "title": "Earnings Surprise",
        "description_template": "{symbol} reported earnings that beat expectations by 12%. Stock gapped up pre-market.",
        "impact": "positive",
        "responses": [
            {"action": "buy_breakout", "quality": 60, "note": "Momentum play — but gap may fade."},
            {"action": "wait_pullback", "quality": 90, "note": "Patient entry after initial excitement cools."},
            {"action": "sell_into_strength", "quality": 70, "note": "Valid if you already hold and want to take profits."},
        ],
        "risk_considerations": [
            "Gaps often fill partially within 48 hours.",
            "Elevated IV means options are expensive.",
            "Don't chase — let price establish support first.",
        ],
    },
    {
        "type": "market_selloff",
        "title": "Market Selloff",
        "description_template": "Broad market indices down 2.5% on inflation concerns. {symbol} falling with the tide.",
        "impact": "negative",
        "responses": [
            {"action": "reduce_exposure", "quality": 95, "note": "Cut position sizes when macro risk rises."},
            {"action": "hold_cash", "quality": 85, "note": "Preservation mode — wait for stabilization."},
            {"action": "buy_the_dip", "quality": 40, "note": "Risky without confirmation of a bottom."},
        ],
        "risk_considerations": [
            "Correlated selloffs hit all sectors — diversification helps but doesn't eliminate risk.",
            "VIX rising means wider stop losses needed.",
            "Don't average down in a macro-driven decline.",
        ],
    },
    {
        "type": "sector_rotation",
        "title": "Sector Rotation",
        "description_template": "Money rotating out of growth into value. {symbol}'s sector seeing outflows.",
        "impact": "neutral",
        "responses": [
            {"action": "review_allocation", "quality": 90, "note": "Check if your portfolio is overweight this sector."},
            {"action": "tighten_stops", "quality": 80, "note": "Sector weakness can persist for weeks."},
            {"action": "ignore", "quality": 50, "note": "Only if your thesis is company-specific, not sector-driven."},
        ],
        "risk_considerations": [
            "Sector trends can last months — don't fight persistent rotation.",
            "Consider hedging with sector ETFs.",
        ],
    },
    {
        "type": "volatility_spike",
        "title": "Volatility Spike",
        "description_template": "VIX jumped 25%. {symbol} daily range expanded to 2x normal.",
        "impact": "neutral",
        "responses": [
            {"action": "reduce_size", "quality": 95, "note": "Smaller positions in high-vol environments."},
            {"action": "widen_stops", "quality": 75, "note": "Normal noise is larger — adjust stops accordingly."},
            {"action": "trade_normally", "quality": 30, "note": "Same size in 2x volatility doubles your risk."},
        ],
        "risk_considerations": [
            "High volatility = larger potential gains AND losses.",
            "Consider waiting for VIX to normalize below 20.",
        ],
    },
]


class MarketEventEngine:
    """Generate and explain random educational market events."""

    def __init__(self, trigger_probability: float = 0.15):
        self._lock = threading.RLock()
        self._events: List[Dict[str, Any]] = []
        self._trigger_probability = trigger_probability

    def maybe_generate(self, symbol: str, session_index: int) -> Optional[Dict[str, Any]]:
        if session_index < 1 or random.random() > self._trigger_probability:
            return None

        template = random.choice(EVENT_TEMPLATES)
        event = {
            "id": str(uuid.uuid4()),
            "type": template["type"],
            "title": template["title"],
            "symbol": symbol.upper(),
            "description": template["description_template"].format(symbol=symbol.upper()),
            "impact": template["impact"],
            "what_happened": template["description_template"].format(symbol=symbol.upper()),
            "possible_responses": template["responses"],
            "risk_considerations": template["risk_considerations"],
            "timestamp": datetime.now().isoformat(),
            "session_index": session_index,
        }

        with self._lock:
            self._events.append(event)

        return event

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.copy() for e in self._events[-limit:]]

    def clear(self):
        with self._lock:
            self._events.clear()


_engine_instance: Optional[MarketEventEngine] = None


def get_event_engine() -> MarketEventEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MarketEventEngine()
    return _engine_instance
