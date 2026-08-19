# AI Trading Learning Agent — Development Plan

## Vision

Transform the Real-Time Stock Trading Simulator into an educational paper-trading platform:
**"Duolingo + TradingView + Paper Trading Simulator"** — focused on learning, practice, and improving trading decisions.

**Constraints:** No real broker connections. No real money trades. Paper simulation only.

---

## Phase 1: Architecture Analysis (Complete)

### Current Project Structure

```
Real-Time-Stock-Trading-Simulator/
├── app.py                    # Flask app factory, entry point
├── src/
│   ├── core/
│   │   ├── data_fetcher.py   # Yahoo Finance data pipeline
│   │   └── strategy.py       # MA crossover + RSI strategy engine
│   ├── api/
│   │   └── routes.py         # REST API + background simulator thread
│   ├── models/
│   │   ├── state.py          # Thread-safe simulator state (singleton)
│   │   └── trade.py          # Trade & PortfolioSnapshot dataclasses
│   └── utils/
│       ├── config.py         # Environment-based configuration
│       ├── performance.py    # Performance helpers
│       └── validators.py     # Input validation
├── static/
│   ├── templates/index.html  # Dashboard (inline JS + Plotly charts)
│   ├── css/main.css
│   └── js/app.js             # Alternate JS (not wired to index.html)
└── tests/
    └── test_data_fetcher.py
```

### Component Map

| Component | Location | Role |
|-----------|----------|------|
| **Market Data Pipeline** | `src/core/data_fetcher.py` | Fetches OHLCV via yfinance; caching, retries, historical mode |
| **Strategy Engine** | `src/core/strategy.py` | MA crossover, RSI, momentum, volatility; buy/sell signals; position sizing |
| **Portfolio Model** | `src/models/state.py`, `trade.py` | In-memory trades list, portfolio value history, thread-safe state |
| **API Routes** | `src/api/routes.py` | `/api/start-simulator`, `/api/stock-data`, `/api/trades`, etc. |
| **Frontend Dashboard** | `static/templates/index.html` | Plotly charts, controls, trades table, strategy modal |

### Data Flow

```
Yahoo Finance (yfinance)
    → DataFetcher.get_real_time_data()
    → TradingStrategy.generate_signals()
    → SimulatorState (trades, portfolio_values, signals)
    → Flask API (/api/*)
    → Dashboard (Plotly charts, stats)
```

---

## Phase 2: AI Trading Coach Module

**New directory:** `src/ai_agent/`

| File | Responsibility |
|------|----------------|
| `agent.py` | `TradingCoachAgent` — orchestrates analysis, explains actions, educational feedback |
| `market_analyzer.py` | MA, RSI, momentum, volatility, volume analysis |
| `risk_coach.py` | Position sizing, stop loss, risk/reward, drawdown explanations |
| `trade_journal.py` | Record trades with rationale, entry/exit, result, lessons |

**Design principles:**
- Rule-based educational engine (no external LLM required for MVP)
- Accepts market state dicts; returns structured JSON for API consumption
- Integrates with existing `TradingStrategy` indicators where possible

---

## Phase 3: AI API Endpoints

**New routes** (in `src/api/ai_routes.py`, registered via blueprint):

### `POST /api/ai/analyze-market`

**Input:**
```json
{
  "symbol": "AAPL",
  "indicators": { "rsi": 55, "short_ma": 150, "long_ma": 148, ... },
  "portfolio": { "cash": 5000, "shares_held": 10, "current_value": 6500 }
}
```

**Output:**
```json
{
  "market_summary": "...",
  "possible_scenarios": ["...", "..."],
  "risk_warning": "...",
  "learning_points": ["...", "..."]
}
```

### `POST /api/ai/review-trade`

**Input:**
```json
{
  "trade_history": [...],
  "strategy": { "short_window": 5, "long_window": 20 },
  "outcome": { "total_return_pct": 2.5, "win_rate": 60 }
}
```

**Output:**
```json
{
  "mistakes": ["..."],
  "strengths": ["..."],
  "improvement_plan": ["..."]
}
```

### Additional endpoints

- `GET /api/ai/lessons` — list learning lessons
- `GET /api/ai/lessons/<id>` — single lesson detail
- `GET /api/ai/journal` — trade journal entries
- `POST /api/ai/journal` — add journal entry

---

## Phase 4: Dashboard — AI Coach Panel

**File:** `static/templates/index.html`

Add panel displaying:
- Market explanation (from `/api/ai/analyze-market`)
- Current trend badge
- Risk level indicator
- Strategy explanation
- Trade journal feedback (from `/api/ai/review-trade`)

Add Learning Mode tab/modal for browsing lessons from `/api/ai/lessons`.

Poll AI analysis on each data update cycle (when simulator running).

---

## Phase 5: Learning Mode

**New directory:** `src/learning/`

| File | Content |
|------|---------|
| `lessons.py` | 7 structured lessons with id, title, content, quiz questions |

**Lessons:**
1. Market orders vs limit orders
2. Moving averages
3. RSI
4. Support and resistance
5. Risk management
6. Backtesting
7. Psychology of trading

---

## Phase 6: Testing

**New tests:** `tests/test_ai_agent.py`, `tests/test_learning.py`

Coverage:
- AI agent input handling (valid/invalid payloads)
- Strategy explanation generation
- Risk calculations (position size, drawdown, R:R)
- Trade journal CRUD and persistence

Run: `pytest` — fix all failures before completion.

---

## Implementation Order & Commits

1. `docs: add DEVELOPMENT_PLAN.md with architecture analysis`
2. `feat: add AI trading coach module (ai_agent/)`
3. `feat: add learning mode lessons module`
4. `feat: add AI API endpoints (/api/ai/*)`
5. `feat: add AI Coach panel and Learning Mode to dashboard`
6. `test: add AI agent and learning mode tests`

---

## Side Effects & Considerations

| Change | Risk | Mitigation |
|--------|------|------------|
| New blueprint registration | Minimal; additive only | Register in `app.py` alongside existing `api_bp` |
| Dashboard HTML/JS changes | UI layout shift | Add panel below stats row; preserve existing charts |
| Trade journal storage | In-memory (matches existing state pattern) | Document; future: persist to file/DB |
| No LLM dependency | Educational text is template-based | Extensible for future OpenAI integration |

---

## Future Enhancements (Out of Scope)

- User accounts and progress tracking (Duolingo-style streaks)
- Interactive quizzes with scoring
- Manual paper trades (user-initiated buy/sell)
- LLM-powered personalized coaching
- Persistent trade journal (SQLite/JSON file)
