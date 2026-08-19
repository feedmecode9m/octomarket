"""AI execution coach — pre-trade review for order placement."""

from typing import Any, Dict, List, Optional

from ..learning.mistake_detector import MistakeDetector
from ..simulation.paper_portfolio import PaperPortfolio


class ExecutionCoach:
    """Review planned orders for position size, risk, and reward/risk."""

    DEFAULT_MAX_RISK_PCT = 2.0
    DEFAULT_MAX_POSITION_PCT = 25.0

    def review(
        self,
        order: Dict[str, Any],
        portfolio: Dict[str, Any],
        current_price: float,
        trade_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        warnings: List[str] = []
        suggestions: List[str] = []
        score = 0.0

        symbol = order.get("symbol", "")
        side = order.get("side", "buy")
        quantity = int(order.get("quantity", 0))
        order_type = order.get("order_type", "market")
        stop_loss = order.get("stop_loss")
        take_profit = order.get("take_profit")
        limit_price = order.get("limit_price") or current_price

        total_value = portfolio.get("total_value") or portfolio.get("cash", 10000)
        cash = portfolio.get("cash", total_value)
        entry_price = limit_price if order_type in ("limit", "stop_limit") else current_price

        if entry_price <= 0:
            return {
                "risk_score": 100,
                "warnings": ["Cannot review order without a valid price."],
                "suggestions": [],
                "lesson": "Wait for market data before placing orders.",
                "approved": False,
                "metrics": {},
            }

        position_value = entry_price * quantity
        position_pct = position_value / total_value * 100 if total_value > 0 else 0

        if position_pct > 50:
            score += 40
            warnings.append("Position size exceeds 50% of account — extreme concentration risk.")
        elif position_pct > self.DEFAULT_MAX_POSITION_PCT:
            score += 25
            warnings.append("Position size exceeds your normal risk tolerance.")

        if side == "buy" and position_value > cash:
            score += 20
            warnings.append("Order value exceeds available cash — may partial fill or reject.")

        dollar_risk = 0.0
        risk_pct = 0.0
        reward_risk_ratio = None

        if stop_loss and entry_price > 0:
            risk_per_share = abs(entry_price - stop_loss)
            dollar_risk = risk_per_share * quantity
            risk_pct = dollar_risk / total_value * 100 if total_value > 0 else 0

            if risk_pct > 5:
                score += 30
                warnings.append(f"Risking {risk_pct:.1f}% of account on one trade — aim for 1-2%.")
            elif risk_pct > self.DEFAULT_MAX_RISK_PCT:
                score += 15
                warnings.append(f"Risk at {risk_pct:.1f}% exceeds the 2% guideline.")

            if take_profit:
                reward = abs(take_profit - entry_price) * quantity
                reward_risk_ratio = round(reward / dollar_risk, 2) if dollar_risk > 0 else None
                if reward_risk_ratio and reward_risk_ratio < 1.5:
                    score += 15
                    warnings.append(f"Reward/risk ratio {reward_risk_ratio}:1 is below the 2:1 target.")
        else:
            score += 10
            suggestions.append("Set a stop loss before entering — define your invalidation level.")

        if not take_profit:
            suggestions.append("Consider setting a take-profit target to lock in a planned exit.")

        if order_type == "market":
            suggestions.append("Market orders fill immediately — use limit orders for better price control.")

        lesson = self._generate_lesson(warnings, trade_history, score)
        score = min(round(score, 1), 100)

        return {
            "risk_score": score,
            "warnings": warnings,
            "suggestions": suggestions,
            "lesson": lesson,
            "approved": score < 70,
            "metrics": {
                "position_value": round(position_value, 2),
                "position_pct": round(position_pct, 1),
                "dollar_risk": round(dollar_risk, 2),
                "account_risk_pct": round(risk_pct, 2),
                "reward_risk_ratio": reward_risk_ratio,
                "entry_price": round(entry_price, 2),
            },
        }

    def _generate_lesson(
        self,
        warnings: List[str],
        trade_history: Optional[List[Dict[str, Any]]],
        score: float,
    ) -> str:
        if any("exceeds your normal" in w or "50%" in w or "concentration" in w.lower() for w in warnings):
            return "Your previous losses were often caused by oversized positions. Size down to 1-2% risk per trade."
        if any("stop loss" in w.lower() for w in warnings):
            return "Every trade needs an invalidation point. Without a stop, one bad move can wipe out weeks of gains."
        if score >= 70:
            return "This order carries elevated risk. Review position size and stop distance before submitting."
        if trade_history:
            detector = MistakeDetector()
            mistakes = detector.analyze(trade_history, initial_cash=10000)
            for m in mistakes:
                if m.get("mistake_key") == "oversized_positions":
                    return "Pattern detected: you tend to oversize positions. Cut quantity in half on this trade."
        return "Solid execution plan. Stick to your entry, stop, and target — don't move stops against you."


_coach_instance: Optional[ExecutionCoach] = None


def get_execution_coach() -> ExecutionCoach:
    global _coach_instance
    if _coach_instance is None:
        _coach_instance = ExecutionCoach()
    return _coach_instance
