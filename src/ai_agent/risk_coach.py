"""Risk management coaching for the AI Trading Coach."""

from typing import Any, Dict, List, Optional


class RiskCoach:
    """Explain position sizing, stop loss, risk/reward, and drawdown."""

    DEFAULT_RISK_PER_TRADE = 0.02
    DEFAULT_STOP_LOSS = 0.01

    def assess_risk(
        self,
        portfolio: Dict[str, Any],
        indicators: Optional[Dict[str, Any]] = None,
        strategy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Produce a comprehensive risk assessment."""
        cash = self._safe_float(portfolio.get("cash"), 0)
        current_value = self._safe_float(portfolio.get("current_value"), cash)
        initial_cash = self._safe_float(portfolio.get("initial_cash"), current_value)
        shares_held = int(portfolio.get("shares_held", 0) or 0)
        current_price = self._safe_float(
            (indicators or {}).get("current_price") or (indicators or {}).get("price"), 0
        )

        strategy = strategy or {}
        stop_loss_pct = self._safe_float(strategy.get("stop_loss"), self.DEFAULT_STOP_LOSS)
        risk_per_trade = self._safe_float(strategy.get("risk_per_trade"), self.DEFAULT_RISK_PER_TRADE)

        position_sizing = self.explain_position_sizing(cash, current_price, risk_per_trade, stop_loss_pct)
        stop_loss = self.explain_stop_loss(current_price, stop_loss_pct, shares_held)
        risk_reward = self.explain_risk_reward(current_price, stop_loss_pct, strategy.get("profit_threshold", 0.02))
        drawdown = self.explain_drawdown(initial_cash, current_value, portfolio.get("portfolio_values", []))

        risk_level = self._calculate_risk_level(
            drawdown["drawdown_pct"], shares_held, cash, current_value, indicators
        )

        return {
            "risk_level": risk_level,
            "position_sizing": position_sizing,
            "stop_loss": stop_loss,
            "risk_reward": risk_reward,
            "drawdown": drawdown,
            "warnings": self._generate_warnings(risk_level, drawdown, shares_held, cash, current_price),
        }

    def explain_position_sizing(
        self,
        cash: float,
        price: float,
        risk_per_trade: float = DEFAULT_RISK_PER_TRADE,
        stop_loss_pct: float = DEFAULT_STOP_LOSS,
    ) -> Dict[str, Any]:
        """Explain how many shares to buy based on risk."""
        if price <= 0 or cash <= 0:
            return {
                "recommended_shares": 0,
                "explanation": "Cannot calculate position size without valid cash and price.",
            }

        risk_amount = cash * risk_per_trade
        risk_per_share = price * stop_loss_pct
        recommended = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
        max_affordable = int(cash / price)
        recommended = min(recommended, max_affordable)
        recommended = max(recommended, 0)

        explanation = (
            f"With ${cash:,.2f} cash and risking {risk_per_trade:.0%} per trade (${risk_amount:.2f}), "
            f"a {stop_loss_pct:.0%} stop loss on a ${price:.2f} stock risks ${risk_per_share:.2f} per share. "
            f"Recommended position: {recommended} shares (${recommended * price:,.2f}). "
            "Never risk more than 1-2% of your portfolio on a single trade."
        )

        return {
            "recommended_shares": recommended,
            "risk_amount": round(risk_amount, 2),
            "position_value": round(recommended * price, 2),
            "explanation": explanation,
        }

    def explain_stop_loss(
        self, entry_price: float, stop_loss_pct: float, shares_held: int = 0
    ) -> Dict[str, Any]:
        """Explain stop loss placement."""
        if entry_price <= 0:
            return {"stop_price": None, "explanation": "Set a stop loss after entering a position."}

        stop_price = entry_price * (1 - stop_loss_pct)
        max_loss = shares_held * entry_price * stop_loss_pct if shares_held > 0 else entry_price * stop_loss_pct

        explanation = (
            f"A {stop_loss_pct:.0%} stop loss at ${stop_price:.2f} limits your downside. "
            f"Stop losses protect capital — exit when the trade thesis is wrong, not when you're uncomfortable."
        )
        if shares_held > 0:
            explanation += f" Current position max loss at stop: ${max_loss:.2f}."

        return {
            "stop_price": round(stop_price, 2),
            "stop_loss_pct": stop_loss_pct,
            "max_loss": round(max_loss, 2),
            "explanation": explanation,
        }

    def explain_risk_reward(
        self, entry_price: float, stop_loss_pct: float, profit_target_pct: float = 0.02
    ) -> Dict[str, Any]:
        """Explain risk/reward ratio."""
        if entry_price <= 0:
            return {"ratio": None, "explanation": "Calculate risk/reward after identifying entry price."}

        risk = entry_price * stop_loss_pct
        reward = entry_price * profit_target_pct
        ratio = reward / risk if risk > 0 else 0

        quality = "favorable" if ratio >= 2 else "acceptable" if ratio >= 1 else "poor"

        explanation = (
            f"Risk ${risk:.2f} to make ${reward:.2f} — a 1:{ratio:.1f} risk/reward ratio ({quality}). "
            "Aim for at least 1:2 (risk $1 to make $2). Lower ratios require higher win rates."
        )

        return {
            "ratio": round(ratio, 2),
            "risk_amount": round(risk, 2),
            "reward_amount": round(reward, 2),
            "quality": quality,
            "explanation": explanation,
        }

    def explain_drawdown(
        self, initial_value: float, current_value: float, portfolio_values: Optional[List] = None
    ) -> Dict[str, Any]:
        """Explain current and maximum drawdown."""
        if initial_value <= 0:
            return {"drawdown_pct": 0, "explanation": "No portfolio history yet."}

        current_dd = max(0, (initial_value - current_value) / initial_value * 100)
        max_dd = current_dd

        if portfolio_values:
            peak = initial_value
            for val in portfolio_values:
                v = self._safe_float(val, initial_value)
                if v > peak:
                    peak = v
                dd = (peak - v) / peak * 100 if peak > 0 else 0
                max_dd = max(max_dd, dd)

        if max_dd > 10:
            severity = "high"
            explanation = (
                f"Drawdown is {max_dd:.1f}% — significant. "
                "Reduce position sizes and review your strategy. Never add to losing positions recklessly."
            )
        elif max_dd > 5:
            severity = "moderate"
            explanation = (
                f"Drawdown is {max_dd:.1f}%. Normal market fluctuation, but monitor closely."
            )
        else:
            severity = "low"
            explanation = f"Drawdown is {max_dd:.1f}%. Portfolio is near peak — good risk control."

        return {
            "drawdown_pct": round(max_dd, 2),
            "current_drawdown_pct": round(current_dd, 2),
            "severity": severity,
            "explanation": explanation,
        }

    def _calculate_risk_level(
        self,
        drawdown_pct: float,
        shares_held: int,
        cash: float,
        current_value: float,
        indicators: Optional[Dict[str, Any]],
    ) -> str:
        score = 0
        if drawdown_pct > 10:
            score += 3
        elif drawdown_pct > 5:
            score += 2
        elif drawdown_pct > 2:
            score += 1

        if current_value > 0 and shares_held * (indicators or {}).get("current_price", 0) > current_value * 0.8:
            score += 2

        vol = (indicators or {}).get("volatility")
        price = (indicators or {}).get("current_price") or (indicators or {}).get("price")
        if vol and price and price > 0 and (vol / price) * 100 > 3:
            score += 1

        if score >= 4:
            return "high"
        if score >= 2:
            return "moderate"
        return "low"

    def _generate_warnings(
        self,
        risk_level: str,
        drawdown: Dict[str, Any],
        shares_held: int,
        cash: float,
        price: float,
    ) -> List[str]:
        warnings = []
        if risk_level == "high":
            warnings.append("High risk environment — consider reducing exposure or waiting for clearer signals.")
        if drawdown.get("severity") == "high":
            warnings.append(f"Portfolio drawdown at {drawdown['drawdown_pct']:.1f}%. Review recent trades.")
        if shares_held > 0 and cash < price:
            warnings.append("Low cash reserves — limited ability to average down or take new opportunities.")
        if not warnings:
            warnings.append("Risk levels are manageable. Stick to your plan and position sizing rules.")
        return warnings

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            result = float(value)
            return default if result != result else result
        except (TypeError, ValueError):
            return default
