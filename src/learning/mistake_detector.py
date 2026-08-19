"""Detect recurring mistake patterns in trading history."""

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class MistakeDetector:
    """Analyze trades and portfolio behavior for common mistakes."""

    MISTAKE_DEFINITIONS = {
        "revenge_trading": {
            "label": "Revenge Trading",
            "description": "Increasing trade size or frequency after losses",
            "recommendation": "Stop after 2 consecutive losses. Walk away for 15 minutes before the next trade.",
        },
        "oversized_positions": {
            "label": "Oversized Positions",
            "description": "Position size exceeds 5% of portfolio per trade",
            "recommendation": "Study Lesson 5 (Risk Management). Risk only 1-2% of capital per trade.",
        },
        "poor_stop_loss": {
            "label": "Poor Stop Loss Usage",
            "description": "Holding losing positions beyond 3% loss without exit",
            "recommendation": "Set a stop loss before every entry. Never move stops further away.",
        },
        "chasing_momentum": {
            "label": "Chasing Momentum",
            "description": "Buying after large upward moves without pullback",
            "recommendation": "Study Lesson 3 (RSI). Wait for pullbacks instead of chasing green candles.",
        },
        "ignoring_drawdown": {
            "label": "Ignoring Drawdown",
            "description": "Continuing to trade aggressively during portfolio drawdown",
            "recommendation": "When drawdown exceeds 5%, reduce position sizes by 50% or pause trading.",
        },
        "overtrading": {
            "label": "Overtrading",
            "description": "Excessive trade frequency relative to session length",
            "recommendation": "Quality over quantity. Aim for 3-5 well-planned trades per session.",
        },
    }

    def analyze(
        self,
        trades: List[Dict[str, Any]],
        portfolio_values: Optional[List[float]] = None,
        initial_cash: float = 10000.0,
        performance: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not trades:
            return []

        detected = []
        portfolio_values = portfolio_values or []
        performance = performance or {}

        checks = [
            self._detect_revenge_trading(trades),
            self._detect_oversized_positions(trades, initial_cash),
            self._detect_poor_stop_loss(trades),
            self._detect_chasing_momentum(trades),
            self._detect_ignoring_drawdown(portfolio_values, initial_cash, trades),
            self._detect_overtrading(trades),
        ]

        for result in checks:
            if result:
                detected.append(result)

        detected.sort(key=lambda x: x["severity"], reverse=True)
        return detected

    def _detect_revenge_trading(self, trades: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        buys = [t for t in trades if t.get("type", t.get("action", "")).lower() == "buy"]
        if len(buys) < 3:
            return None

        revenge_count = 0
        for i in range(1, len(buys)):
            prev = buys[i - 1]
            curr = buys[i]
            prev_qty = int(prev.get("quantity", 0))
            curr_qty = int(curr.get("quantity", 0))
            if curr_qty > prev_qty * 1.5:
                revenge_count += 1

        if revenge_count == 0:
            return None

        return self._format_mistake("revenge_trading", revenge_count, len(buys))

    def _detect_oversized_positions(
        self, trades: List[Dict[str, Any]], initial_cash: float
    ) -> Optional[Dict[str, Any]]:
        oversized = 0
        for t in trades:
            if t.get("type", t.get("action", "")).lower() != "buy":
                continue
            price = float(t.get("price", t.get("fill_price", 0)))
            qty = int(t.get("quantity", 0))
            if price > 0 and (price * qty) > initial_cash * 0.05:
                oversized += 1

        if oversized == 0:
            return None
        return self._format_mistake("oversized_positions", oversized, len(trades))

    def _detect_poor_stop_loss(self, trades: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        buys = [t for t in trades if t.get("type", t.get("action", "")).lower() == "buy"]
        sells = [t for t in trades if t.get("type", t.get("action", "")).lower() == "sell"]
        if not buys or not sells:
            return None

        large_losses = 0
        for i in range(min(len(buys), len(sells))):
            buy_p = float(buys[i].get("price", buys[i].get("fill_price", 0)))
            sell_p = float(sells[i].get("price", sells[i].get("fill_price", 0)))
            if buy_p > 0 and (sell_p - buy_p) / buy_p < -0.03:
                large_losses += 1

        if large_losses == 0:
            return None
        return self._format_mistake("poor_stop_loss", large_losses, len(sells))

    def _detect_chasing_momentum(self, trades: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        buys = [t for t in trades if t.get("type", t.get("action", "")).lower() == "buy"]
        if len(buys) < 2:
            return None

        chase_count = 0
        for i in range(1, len(buys)):
            prev_p = float(buys[i - 1].get("price", buys[i - 1].get("fill_price", 0)))
            curr_p = float(buys[i].get("price", buys[i].get("fill_price", 0)))
            if prev_p > 0 and (curr_p - prev_p) / prev_p > 0.02:
                chase_count += 1

        if chase_count == 0:
            return None
        return self._format_mistake("chasing_momentum", chase_count, len(buys))

    def _detect_ignoring_drawdown(
        self,
        portfolio_values: List[float],
        initial_cash: float,
        trades: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if len(portfolio_values) < 3 or len(trades) < 3:
            return None

        peak = initial_cash
        trades_during_dd = 0
        trade_idx = 0

        for i, val in enumerate(portfolio_values):
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100 if peak > 0 else 0
            if dd > 5 and trade_idx < len(trades):
                trades_during_dd += 1
            if i % max(1, len(portfolio_values) // len(trades)) == 0:
                trade_idx += 1

        if trades_during_dd < 2:
            return None
        return self._format_mistake("ignoring_drawdown", trades_during_dd, len(trades))

    def _detect_overtrading(self, trades: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if len(trades) <= 15:
            return None
        return self._format_mistake("overtrading", len(trades), len(trades))

    def _format_mistake(self, key: str, count: int, total: int) -> Dict[str, Any]:
        defn = self.MISTAKE_DEFINITIONS[key]
        frequency = round(count / total * 100, 1) if total > 0 else 0
        severity = min(100, int(frequency * 1.5 + count * 5))

        return {
            "mistake": defn["label"],
            "mistake_key": key,
            "description": defn["description"],
            "frequency": frequency,
            "occurrences": count,
            "severity": severity,
            "recommendation": defn["recommendation"],
        }
