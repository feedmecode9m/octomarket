# Phase 11 — TradingView Style Execution Simulator

## TradingView Execution Behaviors Being Modeled

| Behavior | TradingView | Our Simulator |
|----------|-------------|---------------|
| Order types | Market, Limit, Stop, Stop-Limit | Same four types |
| Order ticket | Symbol, side, qty, price, SL, TP | Trading panel with risk metrics |
| Bracket orders | Entry + SL + TP linked | Auto-create on bracket placement |
| Chart orders | Click/drag price levels | Click chart + editable SL/TP lines |
| Order book panel | Pending / Filled / Cancelled tabs | Orders tab with status filters |
| Positions panel | Size, entry, P/L | Positions tab with live P/L |
| History | Closed trades with duration | History tab from journal + fills |
| Account | Balance, equity, drawdown | Account tab (paper margin = 0) |
| Hotkeys | B/S shortcuts, cancel | B=buy, S=sell, X=close, ESC=cancel |
| Fill behavior | Market instant, limit on touch | Candle high/low simulation |
| Slippage & fees | Broker-dependent | Configurable paper rates |

**Paper money only.** No broker API, no real orders, no autonomous execution.

## Current Terminal Limitations

| Limitation | Impact |
|------------|--------|
| Instant market-only trades | No limit/stop practice |
| No order lifecycle | Can't learn pending → filled flow |
| No bracket orders | No SL/TP management training |
| No chart price placement | Disconnected from visual levels |
| Simple BUY/SELL buttons | Not TradingView-style ticket |
| No order history tabs | Hard to review execution quality |
| No pre-trade execution review | User doesn't get sizing warnings |
| Basic journal | Missing trade plan and exit review |

## Architecture Changes

```
┌─────────────────────────────────────────────────────────────┐
│                    /terminal (upgraded)                      │
│  Order Ticket │ Chart + Lines │ Positions/Orders/History    │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
  src/trading/      src/trading/      src/ai_agent/
  order_engine.py   execution.py      execution_coach.py
         │                 │
         └────────┬────────┘
                  ▼
         paper_portfolio + trade_journal
                  ▼
         session.step() → process pending orders per candle
```

### Order Lifecycle

```
CREATED → PENDING → TRIGGERED → FILLED
              ↓         ↓
          CANCELLED  REJECTED
```

### Bracket Flow

```
Entry FILLED → activate SL + TP orders
SL or TP FILLED → cancel sibling + close position
```

## API Changes

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/orders` | Place order (supports bracket) |
| GET | `/api/orders` | List orders (filter by status) |
| GET | `/api/orders/<id>` | Get single order |
| PUT | `/api/orders/<id>` | Update prices (chart drag) |
| DELETE | `/api/orders/<id>` | Cancel order |
| POST | `/api/orders/close-position` | Close position (X hotkey) |
| GET | `/api/terminal/account` | Balance, equity, drawdown |
| GET | `/api/terminal/history` | Closed trade history |
| POST | `/api/ai/review-execution` | Pre-trade execution coach |
| PUT | `/api/journal/<id>/review` | Post-exit execution review |

**Existing endpoints unchanged.** `/api/terminal/trade` retained for backward compatibility.

## New Files

| File | Purpose |
|------|---------|
| `src/trading/order_engine.py` | Order CRUD, lifecycle, brackets |
| `src/trading/execution.py` | Fill simulation on candles |
| `src/trading/__init__.py` | Module exports |
| `src/ai_agent/execution_coach.py` | Pre-trade risk review |
| `src/api/execution_routes.py` | Order and account APIs |
| `tests/test_execution.py` | Full execution test coverage |

## Testing Strategy

| Area | Tests |
|------|-------|
| Order engine | Create, cancel, status transitions, bracket linking |
| Market fill | Immediate fill with slippage |
| Limit fill | Fill when candle touches limit |
| Stop trigger | Stop-market activation on price cross |
| Bracket | SL/TP creation, sibling cancel on fill |
| Execution | Commission, slippage, partial fill |
| Execution coach | Risk score, warnings, lesson generation |
| Journal | Trade plan recording, exit review |
| API | Order CRUD, review-execution endpoint |

Run: `pytest tests/test_execution.py` and full suite.

## Educational Goal

Users learn execution habits that transfer to TradingView Paper Trading and eventually broker platforms:

- Placing typed orders (not just market clicks)
- Setting stop loss and take profit before entry
- Reading fill prices, slippage, and commissions
- Managing pending vs filled orders
- Reviewing trade plans and execution discipline

Still **paper money only.**
