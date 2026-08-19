# Phase 10 — Live Market Practice Environment

## Current Simulation Limitations

| Limitation | Impact |
|------------|--------|
| Single-symbol focus | Can't practice multi-stock portfolio management |
| No watchlist | User must manually switch symbols |
| Replay ≠ session | No market open/close lifecycle |
| No price alerts | User must constantly watch charts |
| Portfolio lacks allocation view | No sector concentration or risk score |
| No live commentary | Mentor is reactive, not contextual during trading |
| Scattered UI | Practice mode split across dashboard pages |
| No market events | Missing earnings, selloffs, volatility spikes as teaching moments |

## Live Practice Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    /terminal Dashboard                       │
│  Watchlist │ Chart │ AI Mentor │ Positions │ Alerts │ Events │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
  src/market/      src/simulation/     src/ai_agent/
  watchlist.py     session.py          market_commentator.py
  alerts.py        events.py
         │                 │
         └────────┬────────┘
                  ▼
         paper_portfolio (upgraded)
                  ▼
         DataFetcher (yfinance — read only)
```

**Paper money only.** Data is fetched for display; no orders leave the simulator.

## Data Flow

```
1. User adds symbols to watchlist → fetch latest prices
2. User starts session → load OHLCV for watchlist symbols
3. Session steps → advance candles, update prices, check alerts
4. Random events may fire → AI explains context
5. User trades → paper portfolio (multi-position)
6. Commentator analyzes → concentration, risk/reward, diversification
7. Session closes → summary + mentor feedback
```

## API Changes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/watchlist` | List watchlist with prices |
| POST | `/api/watchlist` | Add symbol |
| DELETE | `/api/watchlist/<symbol>` | Remove symbol |
| POST | `/api/session/start` | Start market session |
| POST | `/api/session/step` | Advance time |
| POST | `/api/session/pause` | Pause session |
| POST | `/api/session/close` | Close session |
| GET | `/api/session/state` | Session state |
| GET | `/api/alerts` | List alerts |
| POST | `/api/alerts` | Create alert |
| DELETE | `/api/alerts/<id>` | Remove alert |
| GET | `/api/commentary` | AI market commentary |
| GET | `/api/events` | Recent market events |
| POST | `/api/terminal/trade` | BUY/SELL/HOLD from terminal |
| GET | `/api/terminal/portfolio` | Multi-position portfolio + risk |

**Existing endpoints unchanged.**

## New Files

| File | Purpose |
|------|---------|
| `src/market/watchlist.py` | Symbol tracking with price changes |
| `src/market/alerts.py` | Price and indicator alerts |
| `src/simulation/session.py` | Market session lifecycle |
| `src/simulation/events.py` | Educational market events |
| `src/ai_agent/market_commentator.py` | Live portfolio commentary |
| `src/api/terminal_routes.py` | Terminal API blueprint |
| `static/templates/terminal.html` | Trading terminal UI |
| `tests/test_live_practice.py` | Test coverage |

## Testing Strategy

| Test Class | Coverage |
|------------|----------|
| `TestWatchlist` | Add/remove, price tracking, trend |
| `TestMarketSession` | Start/step/pause/close, state |
| `TestPortfolioUpgrade` | Allocation, sector exposure, risk score |
| `TestAlerts` | Create, trigger, delete |
| `TestMarketEvents` | Event generation, scoring |
| `TestMarketCommentator` | Commentary output |
| `TestTerminalAPI` | Integration |

Run `pytest` — all tests must pass before completion.

## Commit Plan

1. `docs: add phase 10 plan`
2. `feat: add watchlist system`
3. `feat: add market session simulator`
4. `feat: upgrade portfolio engine`
5. `feat: add alerts`
6. `feat: add AI market commentary`
7. `feat: add trading terminal`
8. `feat: add market events`
9. `test: add live practice coverage`

## Design Principles

- **Terminal feel, paper execution** — realistic UX, zero real trades
- **Extend, don't rewrite** — upgrade PaperPortfolio, reuse DataFetcher
- **Educational events** — every surprise is a teaching moment
- **No broker APIs** — yfinance for market data display only
