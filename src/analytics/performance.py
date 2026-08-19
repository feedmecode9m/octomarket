"""Trading performance analytics."""

import math
from typing import Any, Dict, List, Optional


class TradingPerformanceAnalytics:
    """Calculate trading performance metrics from trades and portfolio history."""

    RISK_FREE_RATE = 0.05  # 5% annualized for Sharpe approximation

    def calculate(
        self,
        trades: List[Dict[str, Any]],
        portfolio_values: Optional[List[float]] = None,
        initial_cash: float = 10000.0,
        benchmark_return_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        portfolio_values = portfolio_values or []
        round_trips = self._pair_trades(trades)

        wins = [r for r in round_trips if r["pnl"] > 0]
        losses = [r for r in round_trips if r["pnl"] <= 0]

        total_trades = len(round_trips)
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0

        avg_gain = sum(r["pnl_pct"] for r in wins) / len(wins) if wins else 0
        avg_loss = sum(r["pnl_pct"] for r in losses) / len(losses) if losses else 0

        gross_profit = sum(r["pnl"] for r in wins)
        gross_loss = abs(sum(r["pnl"] for r in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0)

        current_value = portfolio_values[-1] if portfolio_values else initial_cash
        pnl = current_value - initial_cash
        total_return_pct = (pnl / initial_cash * 100) if initial_cash > 0 else 0

        max_drawdown = self._max_drawdown(portfolio_values, initial_cash)
        sharpe = self._sharpe_ratio(portfolio_values, initial_cash)
        risk_adjusted = self._risk_adjusted_return(total_return_pct, max_drawdown)

        lessons = self._generate_lessons(
            win_rate, max_drawdown, profit_factor, sharpe, total_trades, avg_loss
        )

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "pnl": round(pnl, 2),
            "total_return_pct": round(total_return_pct, 2),
            "drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 3),
            "profit_factor": round(profit_factor, 3) if profit_factor != float("inf") else None,
            "average_gain_pct": round(avg_gain, 2),
            "average_loss_pct": round(avg_loss, 2),
            "risk_adjusted_return": round(risk_adjusted, 3),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "benchmark_return_pct": benchmark_return_pct,
            "beat_benchmark": (
                total_return_pct > benchmark_return_pct
                if benchmark_return_pct is not None
                else None
            ),
            "lessons": lessons,
        }

    def _pair_trades(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Pair buy/sell trades into round trips."""
        round_trips = []
        buys = [t for t in trades if t.get("type", t.get("action", "")).lower() == "buy"]
        sells = [t for t in trades if t.get("type", t.get("action", "")).lower() == "sell"]

        for i in range(min(len(buys), len(sells))):
            buy_price = float(buys[i].get("price", buys[i].get("fill_price", 0)))
            sell_price = float(sells[i].get("price", sells[i].get("fill_price", 0)))
            qty = int(buys[i].get("quantity", 0))
            if buy_price <= 0:
                continue
            pnl = (sell_price - buy_price) * qty
            pnl_pct = (sell_price - buy_price) / buy_price * 100
            round_trips.append({"pnl": pnl, "pnl_pct": pnl_pct, "quantity": qty})

        return round_trips

    def _max_drawdown(self, values: List[float], initial: float) -> float:
        if not values:
            return 0.0
        peak = initial
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
        return max_dd

    def _sharpe_ratio(self, values: List[float], initial: float) -> float:
        if len(values) < 3:
            return 0.0

        returns = []
        prev = initial
        for v in values:
            if prev > 0:
                returns.append((v - prev) / prev)
            prev = v

        if len(returns) < 2:
            return 0.0

        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(variance) if variance > 0 else 0

        if std_r == 0:
            return 0.0

        # Annualize assuming ~252 trading periods; scale by sqrt(n) for short series
        daily_rf = self.RISK_FREE_RATE / 252
        sharpe = (mean_r - daily_rf) / std_r
        return sharpe * math.sqrt(min(len(returns), 252))

    def _risk_adjusted_return(self, total_return_pct: float, max_drawdown: float) -> float:
        if max_drawdown <= 0:
            return total_return_pct
        return total_return_pct / max_drawdown

    def _generate_lessons(
        self,
        win_rate: float,
        drawdown: float,
        profit_factor: float,
        sharpe: float,
        total_trades: int,
        avg_loss: float,
    ) -> List[str]:
        lessons = []

        if total_trades == 0:
            lessons.append("No completed trades yet — start replay mode and practice BUY/SELL/HOLD decisions.")
            return lessons

        if win_rate < 40:
            lessons.append("Win rate below 40% — review Lesson 3 (RSI) and avoid chasing overbought entries.")
        elif win_rate >= 55:
            lessons.append(f"Strong win rate ({win_rate:.0f}%) — focus on letting winners run with trailing stops.")

        if drawdown > 10:
            lessons.append("Drawdown exceeded 10% — study Lesson 5 (Risk Management) and reduce position sizes.")
        elif drawdown < 3:
            lessons.append("Excellent drawdown control — your risk discipline is protecting capital.")

        if profit_factor != float("inf") and profit_factor < 1:
            lessons.append("Profit factor below 1.0 — losses exceed gains. Tighten stops or improve entries.")
        elif profit_factor and profit_factor >= 1.5:
            lessons.append("Healthy profit factor — winners outweigh losers on a dollar basis.")

        if sharpe < 0:
            lessons.append("Negative Sharpe ratio — returns don't compensate for volatility. Trade less, plan more.")
        elif sharpe > 1:
            lessons.append("Sharpe above 1.0 — good risk-adjusted performance for a learning account.")

        if avg_loss < -3:
            lessons.append("Average loss exceeds 3% — your stop losses may be too wide.")

        if not lessons:
            lessons.append("Keep journaling every trade — consistency builds the skill progression system rewards.")

        return lessons
