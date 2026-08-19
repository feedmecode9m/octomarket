# Phase 7 — Trading Simulation Realism

## Current Limitations

| Area | Limitation |
|------|------------|
| **Market data** | Auto-simulator streams all candles at once; no candle-by-candle replay |
| **User agency** | Strategy trades automatically; user cannot practice BUY/SELL/HOLD decisions |
| **Portfolio** | Simple cash + shares; no commissions, slippage, or P/L breakdown |
| **Analytics** | Basic win rate / drawdown in `/api/performance-metrics`; no Sharpe, profit factor, or lessons |
| **AI Coach** | Post-hoc review only; no pre-trade prompts or confidence scoring |
| **Progression** | Lessons exist but no challenges, scores, or skill tracking |
| **Dashboard** | No replay controls, journal timeline, or challenge progress UI |

## Proposed Changes

### 1. Market Replay Engine (`src/simulation/market_replay.py`)

- Load OHLCV DataFrame from `DataFetcher`
- Step one candle at a time with `step()`, `reset()`, `seek()`
- Play/pause/speed state (`1x`, `2x`, `4x`) for background thread integration
- Expose current candle (Open/High/Low/Close/Volume) to API and dashboard

### 2. Paper Trading Realism (`src/simulation/paper_portfolio.py`)

- Commission (default 0.1% per trade)
- Slippage (default 0.05% adverse on fills)
- Cash balance, shares held, cost basis
- Unrealized P/L (open position vs current price)
- Realized P/L (closed round-trips)
- Position history log

### 3. Trading Analytics (`src/analytics/performance.py`)

Calculate from trades + portfolio value series:

- Win rate, average gain/loss
- Maximum drawdown
- Sharpe ratio (annualized, simplified daily returns)
- Profit factor (gross profit / gross loss)
- Risk-adjusted return
- Educational `lessons` array derived from metrics

New endpoint: **`GET /api/performance`** (comprehensive; keeps existing `/api/performance-metrics` intact)

### 4. AI Coach Upgrade (`src/ai_agent/agent.py`)

Add methods:

- `pre_trade_review(action, market_state, portfolio)` → "Why are you entering?"
- `post_trade_review(trade, outcome)` → "What happened?"
- `trade_confidence_score(indicators, strategy, risk_level)` → 0–100 score

New endpoints:

- `POST /api/ai/pre-trade-review`
- `POST /api/ai/post-trade-review`

### 5. Trading Challenges (`src/learning/challenges.py`)

Three built-in challenges with scoring:

1. Grow $10k without >10% drawdown
2. Complete 20 trades with risk management
3. Beat buy-and-hold benchmark

Track completion, score, mistakes per user session (in-memory).

Endpoints: `GET /api/challenges`, `GET /api/challenges/<id>`, `POST /api/challenges/<id>/evaluate`

### 6. Dashboard Upgrade (`static/templates/index.html`)

Add sections (incremental HTML/JS):

- **Replay Controls**: ▶ Play, ⏸ Pause, ⏩ Speed, Step
- **Manual Trade Panel**: BUY / SELL / HOLD buttons during replay
- **Performance Dashboard**: Sharpe, profit factor, drawdown from `/api/performance`
- **Journal Timeline**: Chronological trade + coach feedback entries
- **Challenge Progress**: Active challenge status and score

### 7. API Routes (`src/api/simulation_routes.py`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/simulation/replay/load` | Load symbol/date OHLCV |
| GET | `/api/simulation/replay/status` | Current candle, progress, state |
| POST | `/api/simulation/replay/step` | Advance one candle |
| POST | `/api/simulation/replay/play` | Start auto-stepping |
| POST | `/api/simulation/replay/pause` | Pause auto-stepping |
| POST | `/api/simulation/replay/speed` | Set speed multiplier |
| POST | `/api/simulation/trade` | Manual BUY/SELL/HOLD |
| GET | `/api/simulation/portfolio` | Full paper portfolio state |
| GET | `/api/performance` | Comprehensive analytics |
| GET | `/api/challenges` | List challenges |

## Files Affected

| File | Change |
|------|--------|
| `PHASE_7_PLAN.md` | **New** — this document |
| `src/simulation/__init__.py` | **New** |
| `src/simulation/market_replay.py` | **New** — replay engine |
| `src/simulation/paper_portfolio.py` | **New** — realistic portfolio |
| `src/analytics/__init__.py` | **New** |
| `src/analytics/performance.py` | **New** — trading metrics |
| `src/learning/challenges.py` | **New** — challenge definitions |
| `src/api/simulation_routes.py` | **New** — replay + trade + performance + challenges |
| `src/ai_agent/agent.py` | **Extend** — pre/post trade, confidence score |
| `src/api/ai_routes.py` | **Extend** — new coach endpoints |
| `app.py` | **Extend** — register simulation blueprint |
| `static/templates/index.html` | **Extend** — replay, performance, journal, challenges UI |
| `tests/test_simulation.py` | **New** — replay, portfolio, analytics, challenges |

**Not changed:** `src/core/strategy.py`, `src/core/data_fetcher.py` (used as-is), existing auto-simulator flow in `routes.py`.

## Testing Strategy

| Test File | Coverage |
|-----------|----------|
| `test_simulation.py::TestMarketReplay` | Load data, step, pause/play, speed, boundaries |
| `test_simulation.py::TestPaperPortfolio` | Buy/sell with commission/slippage, P/L calculations |
| `test_simulation.py::TestTradingAnalytics` | Sharpe, drawdown, profit factor, edge cases |
| `test_simulation.py::TestChallenges` | Scoring, completion detection, mistake tracking |
| `test_simulation.py::TestSimulationAPI` | Endpoint integration via Flask test client |
| `test_ai_agent.py` | Extend for pre/post trade review, confidence score |

Run `pytest` after each commit group; **do not proceed if tests fail**.

## Commit Plan

1. `docs: add PHASE_7_PLAN.md`
2. `feat: add market replay engine`
3. `feat: improve paper trading realism`
4. `feat: add trading analytics`
5. `feat: upgrade AI coaching feedback`
6. `feat: add trading challenges`
7. `feat: add replay and performance dashboard UI`
8. `test: add simulation coverage`

## Design Principles

- **Incremental only** — extend existing singletons/blueprints, no rewrites
- **Paper money only** — no broker APIs
- **Backward compatible** — existing `/api/start-simulator` flow unchanged
- **Replay mode is additive** — optional practice path alongside auto-simulator
