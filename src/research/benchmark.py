"""Benchmark comparison for strategy research reports."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd


def buy_and_hold_return_pct(df: Optional[pd.DataFrame]) -> Optional[float]:
    """Simple buy-and-hold return over the candle window."""
    if df is None or len(df) < 2:
        return None
    start = float(df["Close"].iloc[0])
    end = float(df["Close"].iloc[-1])
    if start <= 0:
        return None
    return round((end - start) / start * 100, 2)


def strategy_return_pct(equity_curve: list, initial_cash: float) -> Optional[float]:
    if not equity_curve or initial_cash <= 0:
        return None
    final_equity = float(equity_curve[-1].get("equity") or initial_cash)
    return round((final_equity - initial_cash) / initial_cash * 100, 2)


def compute_benchmark_comparison(
    *,
    ohlcv: Optional[pd.DataFrame],
    equity_curve: list,
    initial_cash: float,
    asset_class: str,
) -> Dict[str, Any]:
    """Compare strategy return against a passive benchmark for the same window."""
    benchmark_return = buy_and_hold_return_pct(ohlcv)
    strategy_return = strategy_return_pct(equity_curve, initial_cash)

    if asset_class.upper() == "FOREX":
        benchmark_type = "buy_and_hold_currency"
        benchmark_label = "Buy-and-hold currency return"
    else:
        benchmark_type = "buy_and_hold"
        benchmark_label = "Buy-and-hold"

    alpha = None
    beat = None
    if benchmark_return is not None and strategy_return is not None:
        alpha = round(strategy_return - benchmark_return, 2)
        beat = strategy_return > benchmark_return

    return {
        "benchmark_type": benchmark_type,
        "benchmark_label": benchmark_label,
        "buy_and_hold_return_pct": benchmark_return,
        "strategy_return_pct": strategy_return,
        "alpha": alpha,
        "beat_benchmark": beat,
        "interpretation": _interpretation(beat, alpha, benchmark_return),
    }


def _interpretation(
    beat: Optional[bool],
    alpha: Optional[float],
    benchmark_return: Optional[float],
) -> str:
    if beat is None or alpha is None or benchmark_return is None:
        return "Insufficient data for benchmark comparison."
    if beat:
        return f"Strategy exceeded passive benchmark by {alpha} percentage points over the tested window."
    if alpha == 0:
        return "Strategy matched passive benchmark over the tested window."
    return (
        f"Strategy lagged passive benchmark by {abs(alpha)} percentage points — "
        "passive exposure may have been sufficient."
    )
