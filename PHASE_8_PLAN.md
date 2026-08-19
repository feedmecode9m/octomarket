# Phase 8 — AI Strategy Lab

## Current Architecture

```
app.py
├── api_bp (routes.py)           — Auto-simulator, stock data, trades
├── ai_bp (ai_routes.py)         — Coach, lessons, pre/post trade review
└── simulation_bp (simulation_routes.py) — Replay, paper portfolio, performance, challenges

src/core/strategy.py             — Fixed MA+RSI strategy (not user-configurable)
src/simulation/paper_portfolio.py — Commissions, slippage, P/L
src/analytics/performance.py     — Sharpe, drawdown, profit factor
src/ai_agent/agent.py            — Market/trade coaching
src/learning/                    — Lessons, challenges
```

**Data flow today:** Yahoo Finance → DataFetcher → TradingStrategy (hardcoded) → SimulatorState → Dashboard.

Users can replay candles and trade manually, but cannot define, backtest, or compare custom strategies.

## Strategy Engine Limitations

| Limitation | Impact |
|------------|--------|
| Single hardcoded strategy in `TradingStrategy` | No user experimentation |
| Parameters in localStorage only | Not validated via backtest before live sim |
| No rule representation | Cannot serialize/share strategies |
| No backtest pipeline | Users can't see historical performance before trading |
| No comparison | Can't evaluate strategy A vs B vs buy-and-hold |
| Coach reviews trades, not strategies | Missing feedback on strategy design |

**Phase 8 does not modify `src/core/strategy.py`.** The Strategy Lab is a parallel layer that produces rule-based strategies and backtests them independently.

## New Files Required

| File | Purpose |
|------|---------|
| `PHASE_8_PLAN.md` | This document |
| `src/strategy_lab/__init__.py` | Package exports |
| `src/strategy_lab/strategy_builder.py` | Natural-language → rule JSON (regex-based) |
| `src/strategy_lab/backtester.py` | Run rules on OHLCV via PaperPortfolio |
| `src/strategy_lab/comparator.py` | Compare strategies + buy-and-hold |
| `src/strategy_lab/library.py` | Beginner/intermediate/advanced templates |
| `src/learning/skill_score.py` | 0–100 skill rating |
| `src/api/strategy_lab_routes.py` | Strategy Lab API blueprint |
| `static/templates/strategy_lab.html` | Strategy Lab page (optional route) |
| `tests/test_strategy_lab.py` | Full test coverage |

## API Changes

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/strategy/parse` | Convert description → rules |
| POST | `/api/strategy/backtest` | Run backtest on rules + symbol |
| POST | `/api/strategy/compare` | Compare 2+ strategies vs benchmark |
| GET | `/api/strategy/library` | List template strategies |
| GET | `/api/strategy/library/<id>` | Get template detail |
| POST | `/api/ai/review-strategy` | AI coach strategy feedback |
| GET | `/api/skill-score` | User skill rating 0–100 |

**Existing endpoints unchanged.**

## Strategy Rule Schema

```json
{
  "name": "MA Crossover",
  "rules": [
    {
      "indicator": "SMA",
      "fast_period": 20,
      "slow_period": 50,
      "signal": "crossover",
      "direction": "above",
      "action": "BUY"
    },
    {
      "indicator": "RSI",
      "period": 14,
      "threshold": 70,
      "condition": "above",
      "action": "SELL"
    }
  ],
  "risk_per_trade": 0.02,
  "stop_loss": 0.01,
  "take_profit": 0.02
}
```

## Testing Approach

| Test Class | Coverage |
|------------|----------|
| `TestStrategyBuilder` | MA crossover, RSI, MACD, multi-rule, invalid input |
| `TestBacktester` | Trades generated, commissions applied, metrics returned |
| `TestComparator` | Best performer, buy-and-hold baseline, weaknesses |
| `TestStrategyLibrary` | All templates load, valid rules |
| `TestSkillScore` | Score bounds, component weighting |
| `TestStrategyCoach` | review-strategy API response shape |
| `TestStrategyLabAPI` | Flask integration |

Run `pytest` after each commit group; **do not finish until all tests pass.**

## Commit Plan

1. `docs: add phase 8 plan`
2. `feat: add strategy builder`
3. `feat: add strategy backtester`
4. `feat: add strategy comparison`
5. `feat: add strategy coach`
6. `feat: add strategy library`
7. `feat: add skill scoring`
8. `test: add strategy lab coverage`

## Design Principles

- **New layer only** — no rewrites of core simulator, replay, or coach
- **Rule-based parsing** — no external LLM
- **Reuse PaperPortfolio + TradingPerformanceAnalytics**
- **Paper money only**
