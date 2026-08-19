"""Structured trading lessons for Learning Mode."""

from typing import Any, Dict, List, Optional


LESSONS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Market Orders vs Limit Orders",
        "category": "order_types",
        "difficulty": "beginner",
        "summary": "Learn the difference between market and limit orders and when to use each.",
        "content": """
## Market Orders vs Limit Orders

### Market Order
A **market order** executes immediately at the best available price.

- **Pros:** Guaranteed execution (in liquid markets)
- **Cons:** Price may differ from what you see (slippage)
- **Use when:** You need immediate entry/exit and the stock is highly liquid

### Limit Order
A **limit order** executes only at your specified price or better.

- **Pros:** Price control — you never pay more (buy) or receive less (sell) than your limit
- **Cons:** No guarantee of execution if price doesn't reach your limit
- **Use when:** You have a specific entry/exit price in mind

### Paper Trading Tip
This simulator uses market-order logic (immediate execution at current price).
In real trading, limit orders help you avoid buying at spikes or selling at dips.

### Key Takeaway
Market orders = speed. Limit orders = price control. Professional traders use both strategically.
        """.strip(),
        "key_points": [
            "Market orders execute immediately at current price",
            "Limit orders give you price control but may not fill",
            "Use limits for entries; market orders for urgent exits (stop losses)",
        ],
        "quiz": [
            {
                "question": "Which order type guarantees price but not execution?",
                "options": ["Market order", "Limit order", "Stop order", "Trailing stop"],
                "answer": 1,
            },
            {
                "question": "When is a market order most appropriate?",
                "options": [
                    "You want a specific entry price",
                    "You need immediate execution in a liquid stock",
                    "The market is closed",
                    "You want to avoid all risk",
                ],
                "answer": 1,
            },
        ],
    },
    {
        "id": 2,
        "title": "Moving Averages",
        "category": "technical_analysis",
        "difficulty": "beginner",
        "summary": "Understand how moving averages smooth price data and reveal trends.",
        "content": """
## Moving Averages (MA)

A **moving average** is the average price over a set number of periods. It smooths out noise to reveal the trend.

### Types
- **Simple Moving Average (SMA):** Average of last N closing prices
- **Exponential Moving Average (EMA):** Gives more weight to recent prices (faster reaction)

### Common Periods
- **Short-term:** 5, 10, 20 periods — captures recent momentum
- **Long-term:** 50, 100, 200 periods — identifies major trends

### Trading Signals
- **Golden Cross:** Short MA crosses above long MA → bullish signal
- **Death Cross:** Short MA crosses below long MA → bearish signal
- **Price above MA:** Uptrend; **price below MA:** downtrend

### In This Simulator
The strategy uses a 5-period short MA and 20-period long MA crossover.
Watch the chart — when the lines cross, a signal may fire.

### Key Takeaway
Moving averages lag price. They confirm trends but won't catch exact tops or bottoms.
        """.strip(),
        "key_points": [
            "MAs smooth price data to reveal trends",
            "Golden cross = bullish; death cross = bearish",
            "Shorter periods react faster but produce more false signals",
        ],
        "quiz": [
            {
                "question": "What is a golden cross?",
                "options": [
                    "Price crosses above resistance",
                    "Short MA crosses above long MA",
                    "RSI crosses above 70",
                    "Volume doubles",
                ],
                "answer": 1,
            },
        ],
    },
    {
        "id": 3,
        "title": "RSI (Relative Strength Index)",
        "category": "technical_analysis",
        "difficulty": "beginner",
        "summary": "Learn to read RSI for overbought and oversold conditions.",
        "content": """
## RSI — Relative Strength Index

RSI measures the speed and magnitude of price changes on a 0–100 scale.

### Key Levels
- **Above 70:** Overbought — price may be extended; caution on new buys
- **Below 30:** Oversold — potential bounce zone; not automatic buy signal
- **50:** Neutral midpoint

### How It Works
RSI compares average gains vs average losses over N periods (default 14).
Rising RSI = strengthening momentum. Falling RSI = weakening momentum.

### Using RSI in This Simulator
The strategy filters buy signals: RSI must be below 75.
Sell signals require RSI above 25. This avoids buying at extremes.

### Common Mistakes
- Buying just because RSI is oversold (trends can stay oversold)
- Ignoring RSI in strong trends (RSI can stay above 70 in bull runs)

### Key Takeaway
RSI is a momentum oscillator, not a standalone signal. Always combine with price action and trend.
        """.strip(),
        "key_points": [
            "RSI ranges from 0 to 100",
            "Above 70 = overbought; below 30 = oversold",
            "Use RSI as a filter, not a standalone buy/sell signal",
        ],
        "quiz": [
            {
                "question": "RSI above 70 typically indicates:",
                "options": ["Oversold", "Overbought", "Neutral", "Bear market"],
                "answer": 1,
            },
        ],
    },
    {
        "id": 4,
        "title": "Support and Resistance",
        "category": "technical_analysis",
        "difficulty": "intermediate",
        "summary": "Identify price levels where buying and selling pressure concentrate.",
        "content": """
## Support and Resistance

**Support** is a price level where buying interest prevents further decline.
**Resistance** is where selling pressure prevents further rise.

### Why They Matter
- Price tends to bounce at support and reject at resistance
- Breakouts above resistance or below support can signal trend changes
- Previous resistance often becomes new support (and vice versa)

### How to Identify
- **Horizontal levels:** Prior highs and lows where price reversed multiple times
- **Moving averages:** Often act as dynamic support/resistance
- **Round numbers:** $100, $50 — psychological levels

### In This Simulator
The AI Coach estimates support/resistance from recent price highs and lows.
Use these levels to understand where the strategy might trigger signals.

### Trading Application
- Buy near support with a stop below it
- Take profits near resistance
- Wait for confirmation on breakouts (volume + close above level)

### Key Takeaway
Support and resistance are zones, not exact prices. Allow some flexibility.
        """.strip(),
        "key_points": [
            "Support = floor where buyers step in",
            "Resistance = ceiling where sellers appear",
            "Breakouts need volume confirmation",
        ],
        "quiz": [
            {
                "question": "When price breaks above resistance with high volume, it often:",
                "options": [
                    "Immediately reverses",
                    "Continues higher (breakout)",
                    "Stays flat forever",
                    "Triggers a stop loss only",
                ],
                "answer": 1,
            },
        ],
    },
    {
        "id": 5,
        "title": "Risk Management",
        "category": "risk",
        "difficulty": "beginner",
        "summary": "Master position sizing, stop losses, and protecting your capital.",
        "content": """
## Risk Management — The Foundation of Trading

Most traders fail not because of bad entries, but because of poor risk management.

### The 1-2% Rule
Never risk more than **1-2% of your portfolio** on a single trade.
With $5,000, that's $50–$100 max loss per trade.

### Position Sizing Formula
```
Shares = (Portfolio × Risk%) / (Entry Price × Stop Loss%)
```
Example: $5,000 portfolio, 2% risk, $150 stock, 1% stop
→ ($100) / ($1.50) = 66 shares

### Stop Losses
- Set before you enter — not after you're losing
- Place below support (for longs) or above resistance (for shorts)
- This simulator uses a 1% automatic stop loss

### Risk/Reward Ratio
Aim for at least **1:2** — risk $1 to make $2.
A 40% win rate is profitable with 1:2 R:R.

### Key Takeaway
Preservation of capital is job #1. You can't trade without money.
        """.strip(),
        "key_points": [
            "Risk only 1-2% of portfolio per trade",
            "Always set a stop loss before entering",
            "Aim for at least 1:2 risk/reward ratio",
        ],
        "quiz": [
            {
                "question": "With a $10,000 portfolio and 2% risk per trade, max loss per trade is:",
                "options": ["$20", "$100", "$200", "$500"],
                "answer": 2,
            },
        ],
    },
    {
        "id": 6,
        "title": "Backtesting",
        "category": "strategy",
        "difficulty": "intermediate",
        "summary": "Test your strategy on historical data before risking real capital.",
        "content": """
## Backtesting — Test Before You Trade

**Backtesting** runs your strategy on historical data to see how it would have performed.

### Why Backtest?
- Validates whether a strategy has an edge
- Reveals weaknesses before real money is at risk
- Builds confidence (or saves you from a bad strategy)

### How to Backtest in This Simulator
1. Enable **Historical Mode** on the dashboard
2. Select a past date
3. Start the simulator — it replays that day's data
4. Review trades, win rate, and drawdown in the AI Coach panel

### Backtesting Pitfalls
- **Overfitting:** Tuning parameters to fit past data perfectly (won't work going forward)
- **Survivorship bias:** Testing only on stocks that still exist today
- **Look-ahead bias:** Using information that wouldn't have been available at the time

### Good Backtesting Practice
- Test across multiple dates and market conditions (bull, bear, sideways)
- Keep parameters simple — fewer rules = more robust
- Focus on risk-adjusted returns, not just total profit

### Key Takeaway
Past performance doesn't guarantee future results, but backtesting eliminates obviously bad strategies.
        """.strip(),
        "key_points": [
            "Backtest on historical data before live trading",
            "Use Historical Mode in this simulator",
            "Avoid overfitting — simple strategies are more robust",
        ],
        "quiz": [
            {
                "question": "What is overfitting in backtesting?",
                "options": [
                    "Testing on too many stocks",
                    "Tuning strategy to match past data too closely",
                    "Using real money during tests",
                    "Trading too frequently",
                ],
                "answer": 1,
            },
        ],
    },
    {
        "id": 7,
        "title": "Psychology of Trading",
        "category": "psychology",
        "difficulty": "intermediate",
        "summary": "Understand emotional traps that destroy trading performance.",
        "content": """
## Psychology of Trading

Technical skills account for ~20% of trading success. Psychology accounts for the rest.

### Common Emotional Traps

**FOMO (Fear of Missing Out)**
Chasing a stock after a big move. Fix: Have a plan before the market opens.

**Revenge Trading**
Doubling down after a loss to "get even." Fix: Walk away after 2 consecutive losses.

**Analysis Paralysis**
Too many indicators, never pulling the trigger. Fix: Simplify to 2-3 tools max.

**Holding Losers, Selling Winners**
The disposition effect. Fix: Use automatic stop losses (like this simulator does).

### Building Discipline
1. **Trade journal:** Write why you entered every trade (this app does this automatically)
2. **Rules-based system:** Follow the strategy — don't override signals emotionally
3. **Accept losses:** Losses are tuition. A 50% win rate with good R:R is profitable.

### The Learning Loop
Trade → Journal → Review (AI Coach) → Learn → Improve → Trade

This is exactly what this platform is designed for.

### Key Takeaway
Your biggest enemy in trading is yourself. Systems and journals protect you from emotional decisions.
        """.strip(),
        "key_points": [
            "FOMO and revenge trading are the top performance killers",
            "Use a trade journal to build self-awareness",
            "Follow your system — emotions override logic under stress",
        ],
        "quiz": [
            {
                "question": "Revenge trading is:",
                "options": [
                    "Trading only winning stocks",
                    "Increasing size after a loss to recover quickly",
                    "Using a stop loss",
                    "Backtesting a strategy",
                ],
                "answer": 1,
            },
        ],
    },
]


def get_all_lessons() -> List[Dict[str, Any]]:
    """Return all lessons (summary view without full content for listing)."""
    return [
        {
            "id": lesson["id"],
            "title": lesson["title"],
            "category": lesson["category"],
            "difficulty": lesson["difficulty"],
            "summary": lesson["summary"],
            "key_points": lesson["key_points"],
        }
        for lesson in LESSONS
    ]


def get_lesson_by_id(lesson_id: int) -> Optional[Dict[str, Any]]:
    """Return full lesson content by ID."""
    for lesson in LESSONS:
        if lesson["id"] == lesson_id:
            return lesson.copy()
    return None


def get_lessons_by_category(category: str) -> List[Dict[str, Any]]:
    """Return lessons filtered by category."""
    return [l for l in get_all_lessons() if l["category"] == category]
