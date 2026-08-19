# Phase 13 — OctoMarket Chart Intelligence Engine

## Objective

Phase 13 does **not** mean "add a chart widget."

It means teaching the same workflow a trader uses in TradingView:

**Observe → Analyze → Plan → Execute → Review**

OctoMarket already executes trades (order engine, bracket orders, journal, AI execution coach). The missing layer is the **visual decision workspace** — where the trader reads structure, applies indicators, draws levels, and forms a plan before clicking BUY.

Still **paper trading only.** No broker connections, no autonomous trading, no stock picks.

---

## Current vs Target Flow

### Current (execution-first)

```
Market Data → Strategy → Order Ticket → Execution → Journal → AI Review
```

The trader can place orders without ever analyzing structure on a proper chart.

### Target (TradingView-style)

```
Chart
  ↓
Market Structure
  ↓
Indicators
  ↓
Drawing / Levels
  ↓
Trade Plan
  ↓
Order Placement
  ↓
Position Management
  ↓
Review
```

Phase 13 adds the **middle** of this pipeline.

---

## Current State (v0.1.0 baseline)

| Area | Today | Limitation |
|------|-------|------------|
| Terminal chart | Plotly line chart | No candlesticks, volume, or crosshair |
| Chart data | `GET /api/session/chart/<symbol>` | Close prices only, no OHLCV payload |
| Session | `MarketSession` + `DataFetcher` | OHLCV in memory; not exposed to chart layer |
| Drawings | Static `layout.shapes` in JS | Not persisted; no trend lines or zones |
| Indicators | RSI/MA in strategy lab & replay | Not on terminal chart |
| Trade plan | Partial in journal `trade_plan` | Not a first-class pre-order step |
| AI coach | `execution_coach.py` | Generic sizing warnings; no chart context |

**Tag checkpoint:** `octomarket-v0.1.0`

**Tests:** 226 passing

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    /terminal (upgraded workspace)                │
│  Watchlist │ Candle Chart + Volume │ Indicators │ Drawings       │
│            │ Trade Plan Panel      │ Order Ticket │ AI Chart Coach │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       src/charting/   src/trading/   src/ai_agent/
       (new)            order_engine   chart_coach.py (new)
              │              │
              └──────┬───────┘
                     ▼
            MarketSession + DataFetcher (read-only OHLCV)
                     ▼
            ChartState (per-user workspace memory)
```

### Design principles

1. **Chart has memory** — symbol, timeframe, zoom, indicators, drawings persist in workspace state.
2. **Backend owns truth** — indicators computed server-side for consistency with tests and AI coach.
3. **Drawings link to orders** — horizontal lines and zones can seed entry/stop/target on the trade plan.
4. **Preserve API compatibility** — existing `/api/orders`, `/api/session/*`, `/api/terminal/*` unchanged; add `/api/chart/*`.
5. **Incremental sub-phases** — 13A before 13B; no indicators before candle foundation.

---

## New Module: `src/charting/`

| File | Responsibility |
|------|----------------|
| `chart_state.py` | Workspace state CRUD: symbol, timeframe, zoom, indicators, drawings |
| `candle_engine.py` | OHLCV slice, candle serialization, volume bars |
| `timeframe.py` | Interval/period mapping, resampling rules, session alignment |
| `indicators.py` | SMA, RSI, MACD, Bollinger — pure pandas, testable |
| `drawings.py` | Horizontal line, trend line, zone models + validation |

### Chart workspace model

```json
{
  "symbol": "AAPL",
  "timeframe": "15m",
  "zoom": {
    "start": "2026-01-01T00:00:00",
    "end": "2026-08-01T00:00:00"
  },
  "indicators": [
    { "id": "sma20", "type": "SMA", "period": 20, "pane": "main" },
    { "id": "rsi14", "type": "RSI", "period": 14, "pane": "sub" }
  ],
  "drawings": [
    { "id": "d1", "type": "horizontal", "price": 215, "label": "Resistance" },
    { "id": "d2", "type": "zone", "top": 220, "bottom": 215, "label": "Resistance Zone" },
    { "id": "d3", "type": "trendline", "x1": "...", "y1": 200, "x2": "...", "y2": 218 }
  ],
  "crosshair": { "enabled": true },
  "updated_at": "2026-08-19T18:00:00"
}
```

Singleton pattern (consistent with `get_market_session()`, `get_order_engine()`):

```python
def get_chart_state() -> ChartStateManager: ...
```

---

## Sub-Phases

### Phase 13A — Chart Foundation (implement first)

**Goal:** Chart workspace with memory; no indicators yet.

| Deliverable | Details |
|-------------|---------|
| `src/charting/*` | All five modules; minimal implementations |
| Chart state API | GET/PUT `/api/chart/state` |
| Candle API | GET `/api/chart/candles/<symbol>?timeframe=15m` |
| OHLCV payload | `{ timestamps, open, high, low, close, volume }` |
| Session integration | Candles respect `MarketSession` index (no future leak) |

**Do not start 13B until 13A tests pass.**

---

### Phase 13B — Candlestick Terminal

**Goal:** Replace line chart with professional candle workspace.

| Feature | Implementation |
|---------|----------------|
| Candlesticks | Plotly `candlestick` trace |
| Volume | Sub-pane histogram, color by close vs open |
| Crosshair | Plotly spike lines + price readout |
| Current price line | Horizontal dashed line at last close |
| Zoom / pan | Plotly `dragmode`, range slider optional |
| Layout | Watchlist \| Chart \| Coach; indicator bar below chart |

**Terminal layout target:**

```
┌──────────┬─────────────────────────────┬──────────┐
│Watchlist │     Candle Chart + Volume    │ AI Coach │
│          ├─────────────────────────────┤          │
│          │  Indicators: SMA RSI MACD …  │ Order    │
├──────────┴─────────────────────────────┴──────────┤
│ Positions │ Orders │ History │ Trade Plan          │
└───────────────────────────────────────────────────┘
```

Reuse OctoMarket theme: `static/assets/branding/theme.css`.

---

### Phase 13C — Market Analysis Tools

**Goal:** Indicators computed server-side, rendered client-side.

| Indicator | Params | Pane | Use case |
|-----------|--------|------|----------|
| SMA 20 / 50 / 200 | period | main overlay | Trend, dynamic S/R |
| RSI | period=14 | sub | Momentum, OB/OS |
| MACD | 12, 26, 9 | sub | Trend change, momentum shift |
| Bollinger Bands | 20, 2σ | main overlay | Volatility, squeeze |

API:

```
GET  /api/chart/indicators/<symbol>?types=SMA20,RSI,MACD
POST /api/chart/indicators          # add to workspace state
DELETE /api/chart/indicators/<id>
```

Reuse logic from `src/strategy_lab/backtester.py` (`_rsi`) and `src/core/strategy.py` where possible — do not duplicate silently; extract shared helpers if needed.

---

### Phase 13D — Drawing Tools

**Goal:** TradingView muscle memory — levels on chart persist and sync.

| Tool | Model | Sync |
|------|-------|------|
| Horizontal line | `{ type, price, label }` | → trade plan entry/stop/target |
| Trend line | `{ x1, y1, x2, y2 }` | Structure annotation |
| Zone | `{ top, bottom, label }` | Support/resistance bands |

API:

```
GET    /api/chart/drawings
POST   /api/chart/drawings
PUT    /api/chart/drawings/<id>    # drag to edit price
DELETE /api/chart/drawings/<id>
```

Drawings stored in `chart_state`; rendered as Plotly shapes + annotations.

Existing order-ticket horizontal lines (entry/SL/TP) migrate to drawing-backed levels where possible.

---

### Phase 13E — Trade Planning Layer

**Goal:** Mandatory cognitive step before order placement.

**Trade plan schema:**

```json
{
  "symbol": "AAPL",
  "setup": "Breakout",
  "entry": 220,
  "stop": 215,
  "target": 230,
  "risk_dollars": 500,
  "reward_dollars": 1000,
  "reason": "Breaking resistance after third test",
  "drawings_used": ["d1", "d2"]
}
```

Flow:

1. User analyzes chart → adds drawings/indicators
2. User fills **Trade Plan** panel (or auto-fill from drawings)
3. `POST /api/chart/trade-plan/review` → AI validates R:R, stop placement, entry vs structure
4. User confirms → `POST /api/orders` with `trade_plan` attached (already supported in order engine)

Bridge: extend `execution_coach.py` or add `trade_plan_validator.py` to consume chart context.

---

### Phase 13F — AI Chart Coach

**Goal:** Context-aware coaching, not generic tips.

**New:** `src/ai_agent/chart_coach.py`

Inputs:

- Current OHLCV slice
- Active indicators (e.g. price vs SMA200)
- Drawings (resistance tests, zones)
- Trade plan draft

Example output:

> "AAPL is above the 200 SMA. Price has tested 220 resistance twice. A breakout entry should wait for confirmation above 220 with volume."

API:

```
POST /api/ai/chart-coach
Body: { symbol, trade_plan?, include_indicators: true }
```

Rule-based first (consistent with existing AI modules); no external LLM required for v0.2.

---

## API Changes Summary

| Method | Path | Phase | Purpose |
|--------|------|-------|---------|
| GET | `/api/chart/state` | 13A | Workspace state |
| PUT | `/api/chart/state` | 13A | Update symbol, timeframe, zoom |
| GET | `/api/chart/candles/<symbol>` | 13A | OHLCV series |
| GET | `/api/chart/indicators/<symbol>` | 13C | Computed indicator series |
| POST/DELETE | `/api/chart/indicators` | 13C | Manage workspace indicators |
| GET/POST/PUT/DELETE | `/api/chart/drawings` | 13D | Drawing CRUD |
| POST | `/api/chart/trade-plan/review` | 13E | Validate plan before order |
| POST | `/api/ai/chart-coach` | 13F | Structure-aware commentary |

**Unchanged:** `/api/orders`, `/api/session/*`, `/api/terminal/*`, `/api/execution/*`, `/api/mentor/*`, `/api/strategy/*`.

New blueprint: `src/api/chart_routes.py` → register in `app.py`.

---

## Data Flow

```
1. User selects symbol on watchlist
2. PUT /api/chart/state { symbol, timeframe }
3. GET /api/chart/candles/AAPL → OHLCV (session-index capped)
4. User toggles SMA20 → POST /api/chart/indicators
5. GET /api/chart/indicators/AAPL → overlay series for Plotly
6. User draws resistance line → POST /api/chart/drawings
7. User builds trade plan → POST /api/chart/trade-plan/review
8. AI chart coach enriches review with structure context
9. User PLACE ORDER → existing order engine + journal trade_plan
10. Session step → candles/indicators recalculate; drawings persist
11. Exit → journal execution review (existing)
```

**No future candle leak:** `candle_engine` must never return bars beyond `session.current_index`.

---

## Testing Strategy

| Current | Target |
|---------|--------|
| 226 tests | **300+ tests** |

### Unit tests (`tests/test_charting.py`)

| Area | Cases |
|------|-------|
| `candle_engine` | OHLCV load, session cap, empty data |
| `timeframe` | Interval mapping, invalid timeframe |
| `indicators` | SMA, RSI, MACD, BB values vs known fixtures |
| `chart_state` | CRUD, indicator list, drawing list |
| `drawings` | Validate horizontal, zone, trendline |
| Trade plan | R:R calc, missing stop rejection |

### API tests (`tests/test_chart_api.py`)

- State GET/PUT round-trip
- Candles return 404 for unknown symbol
- Drawings sync with state
- Existing order tests still pass

### E2E (Playwright — after plugin installed)

```
Open /terminal
→ Select AAPL
→ Change timeframe
→ Add SMA
→ Draw support line
→ Fill trade plan
→ Create order
→ Verify chart drawing + order ticket sync
→ Step session
→ Close position
→ Verify journal entry
```

Target: `tests/e2e/terminal_chart.spec.ts` (or Python playwright).

---

## Implementation Order & Commits

| # | Commit message | Scope |
|---|----------------|-------|
| 1 | `docs: add phase 13 charting plan` | This document |
| 2 | `feat: add chart foundation modules` | 13A — `src/charting/` |
| 3 | `feat: add chart state API` | 13A — routes + tests |
| 4 | `feat: add candlestick terminal` | 13B — terminal UI |
| 5 | `feat: add chart indicators` | 13C |
| 6 | `feat: add drawing tools` | 13D |
| 7 | `feat: add trade planning layer` | 13E |
| 8 | `feat: add AI chart coach` | 13F |
| 9 | `test: add charting coverage` | Unit + API tests |
| 10 | `test: add terminal chart e2e` | Playwright (optional gate) |

**Version bump:** `0.2.0` in `src/config/product.py` when 13B ships (first user-visible chart).

---

## Migration & Risk

| Risk | Mitigation |
|------|------------|
| Plotly performance with many candles | Limit default range; lazy load on zoom |
| Indicator drift vs strategy lab | Shared math helpers; cross-test fixtures |
| Drawing/order desync | Single source in `chart_state`; order ticket reads drawings |
| Session step leaks future data | Enforce cap in `candle_engine.get_candles()` |
| UI complexity | Sub-phase gates; 13A tests before 13B UI |
| API breakage | New prefix `/api/chart/*` only |

---

## Reuse Map (avoid duplication)

| Existing | Reuse in Phase 13 |
|----------|-------------------|
| `DataFetcher` | OHLCV source |
| `MarketSession.get_chart_data()` | Extend to full OHLCV |
| `strategy_lab/backtester._rsi` | Extract or mirror for `indicators.py` |
| `execution_coach.py` | Extend for trade plan + chart context |
| `trade_journal.trade_plan` | Persist plan fields from 13E |
| `order_engine.trade_plan` | Already on orders |
| Plotly in terminal.html | Upgrade traces, keep library |

---

## Cursor / Skills Reference

- Rules: `.cursor/rules/octomarket-core.mdc` (paper-only, API preserve)
- Skills: `.cursor/skills/finance-domain/`, `.cursor/skills/chart-engine/`
- Setup: `.cursor/CURSOR_SETUP.md` (Playwright before 13B E2E)

---

## Future Phases (post-13)

| Phase | Focus |
|-------|-------|
| **14 — Advanced Market Intelligence** | Earnings, news sim, economic calendar, sector analysis |
| **15 — Professional Risk Desk** | Portfolio heat map, correlation, exposure limits |
| **16 — TradingView Workflow Mastery** | Replay challenges, daily sessions, trader scoring |

---

## Success Criteria

Phase 13 is complete when a user can:

1. Open OctoMarket Terminal
2. View **candlesticks + volume** for a watchlist symbol
3. Add **SMA / RSI / MACD / Bollinger** overlays
4. Draw **support, resistance, and zones**
5. Write a **trade plan** and receive **structure-aware AI feedback**
6. Place an order linked to the plan
7. Review the trade in the journal

All without leaving the terminal — and all on **paper money**.

---

## Immediate Next Step

**Phase 13A only:** implement `src/charting/` + chart state API + tests.

Do not build indicators or drawing UI until candle foundation and state persistence are verified.

```bash
# After 13A
pytest tests/test_charting.py tests/test_chart_api.py -q
```

Then proceed to 13B candlestick terminal.
