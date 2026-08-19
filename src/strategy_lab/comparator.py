"""Compare multiple strategies against each other and buy-and-hold."""

from typing import Any, Dict, List, Optional

import pandas as pd

from .backtester import StrategyBacktester


class StrategyComparator:
    """Compare strategy backtest results and identify best performer."""

    def __init__(self, backtester: Optional[StrategyBacktester] = None):
        self.backtester = backtester or StrategyBacktester()

    def compare(
        self,
        strategies: List[Dict[str, Any]],
        data: pd.DataFrame,
        symbol: str = "STOCK",
        initial_cash: float = 10000.0,
        include_buy_and_hold: bool = True,
    ) -> Dict[str, Any]:
        if not strategies:
            raise ValueError("At least one strategy is required")

        results = []
        for strategy in strategies:
            bt = self.backtester.run(strategy, data, symbol, initial_cash)
            results.append({
                "name": strategy.get("name", "Unnamed"),
                "total_return_pct": bt["total_return_pct"],
                "win_rate": bt["win_rate"],
                "max_drawdown": bt["max_drawdown"],
                "sharpe_ratio": bt["sharpe_ratio"],
                "total_trades": bt["total_trades"],
                "profit_factor": bt["profit_factor"],
                "benchmark_comparison": bt["benchmark_comparison"],
                "backtest": bt,
            })

        buy_hold_return = self.backtester._buy_and_hold_return(data)
        if include_buy_and_hold:
            results.append({
                "name": "Buy and Hold",
                "total_return_pct": round(buy_hold_return, 2),
                "win_rate": 100.0 if buy_hold_return > 0 else 0.0,
                "max_drawdown": self._estimate_buy_hold_drawdown(data),
                "sharpe_ratio": 0.0,
                "total_trades": 1,
                "profit_factor": None,
                "benchmark_comparison": {"buy_and_hold_return_pct": buy_hold_return},
                "backtest": None,
            })

        ranked = sorted(results, key=lambda r: r["total_return_pct"], reverse=True)
        best = ranked[0]
        weaknesses = self._find_weaknesses(results)
        risk_diff = self._risk_differences(results)

        return {
            "best_performer": best["name"],
            "rankings": [
                {
                    "rank": i + 1,
                    "name": r["name"],
                    "total_return_pct": r["total_return_pct"],
                    "max_drawdown": r["max_drawdown"],
                    "sharpe_ratio": r["sharpe_ratio"],
                }
                for i, r in enumerate(ranked)
            ],
            "risk_differences": risk_diff,
            "weaknesses": weaknesses,
            "results": results,
        }

    def _estimate_buy_hold_drawdown(self, data: pd.DataFrame) -> float:
        close = data["Close"].astype(float)
        peak = close.iloc[0]
        max_dd = 0.0
        for price in close:
            if price > peak:
                peak = price
            dd = (peak - price) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
        return round(max_dd, 2)

    def _find_weaknesses(self, results: List[Dict[str, Any]]) -> List[str]:
        weaknesses = []
        for r in results:
            name = r["name"]
            if name == "Buy and Hold":
                continue
            if r["max_drawdown"] > 15:
                weaknesses.append(f"{name}: High drawdown ({r['max_drawdown']:.1f}%) — tighten stops or reduce size.")
            if r["win_rate"] < 40 and r["total_trades"] >= 3:
                weaknesses.append(f"{name}: Low win rate ({r['win_rate']:.0f}%) — entries may be poorly timed.")
            bc = r.get("benchmark_comparison") or {}
            if bc.get("beat_benchmark") is False:
                weaknesses.append(
                    f"{name}: Underperforms buy-and-hold by {abs(bc.get('alpha', 0)):.1f}%."
                )
            if r["total_trades"] == 0:
                weaknesses.append(f"{name}: No trades generated — rules may be too restrictive.")
        return weaknesses

    def _risk_differences(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(results) < 2:
            return []
        diffs = []
        for i, a in enumerate(results):
            for b in results[i + 1:]:
                diffs.append({
                    "strategy_a": a["name"],
                    "strategy_b": b["name"],
                    "return_diff_pct": round(a["total_return_pct"] - b["total_return_pct"], 2),
                    "drawdown_diff_pct": round(a["max_drawdown"] - b["max_drawdown"], 2),
                    "lower_risk": a["name"] if a["max_drawdown"] < b["max_drawdown"] else b["name"],
                })
        return diffs
