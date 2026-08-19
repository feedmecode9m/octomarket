"""Pre-built strategy templates for the Strategy Lab."""

from typing import Any, Dict, List, Optional


STRATEGY_LIBRARY: List[Dict[str, Any]] = [
    {
        "id": "ma_crossover",
        "name": "Moving Average Crossover",
        "difficulty": "beginner",
        "description": "Buy when short MA crosses above long MA; sell on death cross.",
        "description_text": "Buy when the 20 day moving average crosses above the 50 day moving average",
        "rules": [
            {
                "indicator": "SMA",
                "fast_period": 20,
                "slow_period": 50,
                "signal": "crossover",
                "direction": "above",
                "action": "BUY",
            },
            {
                "indicator": "SMA",
                "fast_period": 20,
                "slow_period": 50,
                "signal": "crossover",
                "direction": "below",
                "action": "SELL",
            },
        ],
    },
    {
        "id": "rsi_reversal",
        "name": "RSI Reversal",
        "difficulty": "beginner",
        "description": "Buy oversold, sell overbought using RSI thresholds.",
        "description_text": "Buy when RSI goes below 30. Sell when RSI goes above 70.",
        "rules": [
            {"indicator": "RSI", "period": 14, "threshold": 30, "condition": "below", "action": "BUY"},
            {"indicator": "RSI", "period": 14, "threshold": 70, "condition": "above", "action": "SELL"},
        ],
    },
    {
        "id": "support_bounce",
        "name": "Support Bounce",
        "difficulty": "beginner",
        "description": "Buy when price bounces off recent support level.",
        "description_text": "Buy when price bounces at support",
        "rules": [
            {"indicator": "SUPPORT", "lookback": 20, "signal": "bounce", "action": "BUY"},
            {"indicator": "RSI", "period": 14, "threshold": 70, "condition": "above", "action": "SELL"},
        ],
    },
    {
        "id": "macd_trend",
        "name": "MACD Trend Following",
        "difficulty": "intermediate",
        "description": "Follow trends using MACD line crossing signal line.",
        "description_text": "Buy when MACD crosses above signal. Sell when MACD crosses below signal.",
        "rules": [
            {"indicator": "MACD", "signal": "crossover", "direction": "above", "action": "BUY"},
            {"indicator": "MACD", "signal": "crossover", "direction": "below", "action": "SELL"},
        ],
    },
    {
        "id": "volatility_breakout",
        "name": "Volatility Breakout",
        "difficulty": "intermediate",
        "description": "Enter when volatility expands beyond recent average.",
        "description_text": "Buy on volatility breakout",
        "rules": [
            {"indicator": "VOLATILITY", "period": 20, "multiplier": 1.5, "signal": "breakout", "action": "BUY"},
            {"indicator": "RSI", "period": 14, "threshold": 75, "condition": "above", "action": "SELL"},
        ],
    },
    {
        "id": "multi_confirm",
        "name": "Multi-Indicator Confirmation",
        "difficulty": "advanced",
        "description": "Require MA crossover AND RSI confirmation before entry.",
        "description_text": "Buy when 10 day MA crosses above 30 day MA. Sell when RSI goes above 70.",
        "rules": [
            {"indicator": "SMA", "fast_period": 10, "slow_period": 30, "signal": "crossover", "direction": "above", "action": "BUY"},
            {"indicator": "RSI", "period": 14, "threshold": 70, "condition": "above", "action": "SELL"},
            {"indicator": "SMA", "fast_period": 10, "slow_period": 30, "signal": "crossover", "direction": "below", "action": "SELL"},
        ],
    },
]


def get_strategy_library() -> List[Dict[str, Any]]:
    """Return library summaries without full backtest data."""
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "difficulty": s["difficulty"],
            "description": s["description"],
            "description_text": s.get("description_text", ""),
            "rule_count": len(s["rules"]),
        }
        for s in STRATEGY_LIBRARY
    ]


def get_strategy_by_id(strategy_id: str) -> Optional[Dict[str, Any]]:
    for s in STRATEGY_LIBRARY:
        if s["id"] == strategy_id:
            return {
                "name": s["name"],
                "description": s["description"],
                "rules": s["rules"],
                "risk_per_trade": 0.02,
                "stop_loss": 0.01,
                "take_profit": 0.02,
            }
    return None
