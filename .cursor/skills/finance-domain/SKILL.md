---
description: OctoMarket finance domain — OHLCV, orders, execution, risk. Use for trading, portfolio, replay, and execution work.
---

# OctoMarket Finance Domain

## Product context

OctoMarket is a **paper-only** practice terminal. Users learn execution before real capital.

## OHLCV / candles

- Columns: `Open`, `High`, `Low`, `Close`, `Volume` (pandas DataFrame from `DataFetcher`).
- Session steps advance one candle; fills use candle high/low for limit/stop logic.
- Replay engine: `src/simulation/market_replay.py`; session: `src/simulation/session.py`.

## Order types (implemented)

| Type | Fill logic |
|------|------------|
| Market | Immediate at close + slippage |
| Limit | Buy when `low <= limit`; sell when `high >= limit` |
| Stop market | Trigger on price cross, fill at stop/close |
| Stop limit | Trigger stop, then limit fill rules |
| Bracket | Entry + linked SL (stop_market) + TP (limit) |

Engine: `src/trading/order_engine.py`, fills: `src/trading/execution.py`.

## Portfolio

- `PaperPortfolio`: commissions (0.1%), slippage (0.05%), multi-position, avg cost, partial sells.
- Risk score 0–100 from concentration, sector exposure, cash reserves.

## Indicators (existing)

- RSI, MA crossover in `src/core/strategy.py` and strategy lab backtester.
- Do not add live broker feeds; replay/session data is sufficient for practice.

## Risk management vocabulary

- Position sizing: 1–2% account risk per trade.
- Stop loss = invalidation level; take profit = planned exit.
- Execution coach: `src/ai_agent/execution_coach.py`.

## API surface (preserve)

Key prefixes: `/api/orders`, `/api/terminal/*`, `/api/session/*`, `/api/strategy/*`, `/api/mentor/*`, `/api/simulation/*`.

## Module labels (UI only)

From `src/config/product.py` — Terminal, Mentor, Lab, Replay, Academy, Journal.
