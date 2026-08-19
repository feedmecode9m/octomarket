"""Backtest rule-based strategies against historical OHLCV data."""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..analytics.performance import TradingPerformanceAnalytics
from ..simulation.paper_portfolio import PaperPortfolio


class StrategyBacktester:
    """Run a strategy rule set against historical candles using PaperPortfolio."""

    def __init__(self):
        self.analytics = TradingPerformanceAnalytics()

    def run(
        self,
        strategy: Dict[str, Any],
        data: pd.DataFrame,
        symbol: str = "STOCK",
        initial_cash: float = 10000.0,
    ) -> Dict[str, Any]:
        if data.empty:
            raise ValueError("No historical data for backtest")

        rules = strategy.get("rules", [])
        if not rules:
            raise ValueError("Strategy has no rules")

        indicators = self._compute_indicators(data, rules)
        signals = self._generate_signals(data, rules, indicators)

        portfolio = PaperPortfolio(initial_cash=initial_cash)
        portfolio_values = [initial_cash]
        trades: List[Dict[str, Any]] = []
        shares_held = 0
        risk_per_trade = strategy.get("risk_per_trade", 0.02)
        stop_loss = strategy.get("stop_loss", 0.01)
        take_profit = strategy.get("take_profit", 0.02)
        entry_price = 0.0

        for i in range(len(data)):
            row = data.iloc[i]
            price = float(row["Close"])
            ts = data.index[i].isoformat() if hasattr(data.index[i], "isoformat") else str(data.index[i])
            signal = signals.iloc[i] if i < len(signals) else 0

            if shares_held > 0 and entry_price > 0:
                if price <= entry_price * (1 - stop_loss):
                    signal = -1
                elif price >= entry_price * (1 + take_profit):
                    signal = -1

            if signal == 1 and shares_held == 0:
                risk_amount = portfolio.cash * risk_per_trade
                qty = max(1, int(risk_amount / (price * stop_loss))) if price > 0 else 1
                qty = min(qty, int(portfolio.cash / price)) if price > 0 else 0
                if qty > 0:
                    result = portfolio.buy(symbol, price, qty, ts, strategy.get("name", "backtest"))
                    if result.get("success"):
                        shares_held = qty
                        entry_price = result["fill_price"]
                        trades.append(self._trade_dict(result, ts, "buy"))

            elif signal == -1 and shares_held > 0:
                result = portfolio.sell(symbol, price, shares_held, ts, strategy.get("name", "backtest"))
                if result.get("success"):
                    trades.append(self._trade_dict(result, ts, "sell"))
                    shares_held = 0
                    entry_price = 0.0

            value = portfolio.get_portfolio_value({symbol: price})
            portfolio_values.append(value)

        if shares_held > 0:
            price = float(data.iloc[-1]["Close"])
            ts = data.index[-1].isoformat() if hasattr(data.index[-1], "isoformat") else str(data.index[-1])
            result = portfolio.sell(symbol, price, shares_held, ts, "end of backtest")
            if result.get("success"):
                trades.append(self._trade_dict(result, ts, "sell"))
            portfolio_values[-1] = portfolio.get_portfolio_value({symbol: price})

        benchmark_return = self._buy_and_hold_return(data)
        metrics = self.analytics.calculate(
            trades=trades,
            portfolio_values=portfolio_values,
            initial_cash=initial_cash,
            benchmark_return_pct=benchmark_return,
        )

        return {
            "strategy_name": strategy.get("name", "Unknown"),
            "trades": trades,
            "total_return": metrics["total_return_pct"],
            "total_return_pct": metrics["total_return_pct"],
            "pnl": metrics["pnl"],
            "win_rate": metrics["win_rate"],
            "max_drawdown": metrics["drawdown"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "profit_factor": metrics["profit_factor"],
            "total_trades": metrics["total_trades"],
            "portfolio_values": portfolio_values,
            "benchmark_comparison": {
                "buy_and_hold_return_pct": round(benchmark_return, 2),
                "strategy_return_pct": metrics["total_return_pct"],
                "alpha": round(metrics["total_return_pct"] - benchmark_return, 2),
                "beat_benchmark": metrics["beat_benchmark"],
            },
            "commissions_paid": round(portfolio.total_commissions, 2),
            "slippage_paid": round(portfolio.total_slippage, 2),
        }

    def _compute_indicators(self, data: pd.DataFrame, rules: List[Dict[str, Any]]) -> Dict[str, pd.Series]:
        close = data["Close"].astype(float)
        indicators: Dict[str, pd.Series] = {}

        for rule in rules:
            ind = rule.get("indicator", "").upper()
            if ind in ("SMA", "EMA"):
                fast = rule.get("fast_period", 20)
                slow = rule.get("slow_period", 50)
                if ind == "EMA":
                    indicators[f"ema_{fast}"] = close.ewm(span=fast, adjust=False).mean()
                    indicators[f"ema_{slow}"] = close.ewm(span=slow, adjust=False).mean()
                else:
                    indicators[f"sma_{fast}"] = close.rolling(fast, min_periods=1).mean()
                    indicators[f"sma_{slow}"] = close.rolling(slow, min_periods=1).mean()

            elif ind == "RSI":
                period = rule.get("period", 14)
                indicators[f"rsi_{period}"] = self._rsi(close, period)

            elif ind == "MACD":
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd = ema12 - ema26
                signal_line = macd.ewm(span=9, adjust=False).mean()
                indicators["macd"] = macd
                indicators["macd_signal"] = signal_line

            elif ind == "SUPPORT":
                lookback = rule.get("lookback", 20)
                indicators["support"] = close.rolling(lookback, min_periods=1).min()

            elif ind == "VOLATILITY":
                period = rule.get("period", 20)
                indicators["volatility"] = close.rolling(period, min_periods=1).std()

        return indicators

    def _generate_signals(
        self, data: pd.DataFrame, rules: List[Dict[str, Any]], indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        signals = pd.Series(0, index=data.index)
        close = data["Close"].astype(float)

        for rule in rules:
            ind = rule.get("indicator", "").upper()
            action = rule.get("action", "BUY").upper()
            signal_val = 1 if action == "BUY" else -1

            if ind in ("SMA", "EMA"):
                fast = rule.get("fast_period", 20)
                slow = rule.get("slow_period", 50)
                prefix = "ema" if ind == "EMA" else "sma"
                fast_col = indicators.get(f"{prefix}_{fast}")
                slow_col = indicators.get(f"{prefix}_{slow}")
                if fast_col is None or slow_col is None:
                    continue
                direction = rule.get("direction", "above")
                if direction == "above":
                    cross = (fast_col > slow_col) & (fast_col.shift(1) <= slow_col.shift(1))
                else:
                    cross = (fast_col < slow_col) & (fast_col.shift(1) >= slow_col.shift(1))
                signals[cross] = signal_val

            elif ind == "RSI":
                period = rule.get("period", 14)
                rsi = indicators.get(f"rsi_{period}")
                if rsi is None:
                    continue
                threshold = rule.get("threshold", 70)
                condition = rule.get("condition", "above")
                if condition == "above":
                    trigger = (rsi > threshold) & (rsi.shift(1) <= threshold)
                else:
                    trigger = (rsi < threshold) & (rsi.shift(1) >= threshold)
                signals[trigger] = signal_val

            elif ind == "MACD":
                macd = indicators.get("macd")
                macd_sig = indicators.get("macd_signal")
                if macd is None or macd_sig is None:
                    continue
                direction = rule.get("direction", "above")
                if direction == "above":
                    cross = (macd > macd_sig) & (macd.shift(1) <= macd_sig.shift(1))
                else:
                    cross = (macd < macd_sig) & (macd.shift(1) >= macd_sig.shift(1))
                signals[cross] = signal_val

            elif ind == "SUPPORT":
                support = indicators.get("support")
                if support is None:
                    continue
                bounce = (close <= support * 1.01) & (close.shift(1) > support.shift(1) * 1.01)
                signals[bounce] = signal_val

            elif ind == "VOLATILITY":
                vol = indicators.get("volatility")
                if vol is None:
                    continue
                avg_vol = vol.rolling(20, min_periods=1).mean()
                mult = rule.get("multiplier", 1.5)
                breakout = vol > avg_vol * mult
                signals[breakout] = signal_val

        return signals

    def _rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        avg_gains = gains.ewm(span=period, adjust=False).mean()
        avg_losses = losses.ewm(span=period, adjust=False).mean()
        rs = avg_gains / avg_losses.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _buy_and_hold_return(self, data: pd.DataFrame) -> float:
        if len(data) < 2:
            return 0.0
        start = float(data["Close"].iloc[0])
        end = float(data["Close"].iloc[-1])
        return ((end - start) / start * 100) if start > 0 else 0.0

    def _trade_dict(self, result: Dict[str, Any], ts: str, trade_type: str) -> Dict[str, Any]:
        return {
            "type": trade_type,
            "action": trade_type,
            "price": result.get("fill_price", 0),
            "fill_price": result.get("fill_price", 0),
            "quantity": result.get("quantity", 0),
            "time": ts,
            "commission": result.get("commission", 0),
        }
