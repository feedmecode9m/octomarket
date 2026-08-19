# Phase 13B — Terminal Candlestick Workspace

## Chosen chart library

**TradingView Lightweight Charts v4** (`lightweight-charts.standalone.production.js` via CDN).

| Criterion | Lightweight Charts | Plotly (existing) |
|-----------|-------------------|-------------------|
| TradingView-style UX | Native candlesticks, crosshair, scroll/zoom | Possible but heavier config |
| Volume sub-pane | Built-in histogram + separate scale | Subplot layout boilerplate |
| Performance | Canvas, optimized for live financial data | Good for static, less terminal-like |
| Bundle | ~45 KB standalone | Already loaded but line-chart oriented |

Plotly remains on `/replay` and other pages; only `/terminal` switches to Lightweight Charts for Phase 13B.

## Frontend architecture

```
terminal.html
├── Chart toolbar (symbol label, timeframe select, crosshair readout)
├── #chartDiv (Lightweight Charts mount point)
└── terminal_chart.js — OctoMarketTerminalChart class
    ├── createChart() — price pane + volume pane (scale margins)
    ├── load(symbol, timeframe) — PUT state + GET /api/chart/<symbol>
    ├── updatePriceLines(entry, sl, tp) — order ticket overlays
    ├── subscribeClick → order ticket price
    └── subscribeCrosshairMove → OHLCV readout
```

**State flow**

1. Page load: `GET /api/chart/state` → sync symbol/timeframe UI.
2. Symbol change (watchlist): `PUT /api/chart/state { symbol }` → reload candles.
3. Timeframe change: `PUT /api/chart/state { timeframe }` → reload candles.
4. Session step: reload chart (API respects session cap by default).

**Zoom / pan**

- Mouse wheel + drag scroll: Lightweight Charts defaults (`handleScroll`, `handleScale`).
- No custom zoom state persisted yet (Phase 13C+ can sync via `chart_state.zoom`).

## API mapping

| UI action | API | Notes |
|-----------|-----|-------|
| Initial load | `GET /api/chart/state` | Default symbol/timeframe/period |
| Load candles | `GET /api/chart/<symbol>?timeframe=<tf>` | Uses workspace period unless overridden |
| Switch symbol | `PUT /api/chart/state { "symbol": "AAPL" }` | Then GET candles |
| Switch timeframe | `PUT /api/chart/state { "timeframe": "1h" }` | Period auto from `timeframe.py` defaults |
| Session step refresh | `GET /api/chart/<symbol>` | `respect_session=true` (default) caps future bars |

**Phase 13A payload → renderer**

```json
{
  "timestamps": ["2024-06-01T00:00:00", ...],
  "open": [], "high": [], "low": [], "close": [], "volume": []
}
```

Converted in `src/charting/candle_adapter.py` (Python, tested) and `terminal_chart.js` (browser):

- Intraday (`1m`, `5m`, `15m`, `1h`, …): Unix seconds (`UTCTimestamp`).
- Daily+ (`1d`, `1wk`, …): `YYYY-MM-DD` business-day strings.

Volume bars colored green/red from close vs open.

**Unchanged APIs (order/session)**

- Order ticket: `/api/orders`, `/api/ai/review-execution`
- Session controls: `/api/session/*`
- Legacy line chart endpoint `/api/session/chart/<symbol>` is not used by terminal UI after 13B.

## Future indicator compatibility

Phase 13C–13F can extend without replacing the renderer:

| Feature | Integration point |
|---------|-------------------|
| Overlays (SMA, EMA, VWAP) | `chart.addLineSeries()` fed from backend or client calc |
| Oscillators (RSI, MACD) | Separate pane via `priceScaleId` + `scaleMargins` (same as volume) |
| Workspace indicators | `chart_state.indicators[]` → `PUT /api/chart/state`; backend computes in Phase 13C |
| Drawings | `chart_state.drawings[]` → price lines / plugins; Phase 13D |
| Sync zoom | Persist `visibleRange` to `chart_state.zoom` on `timeScale().subscribeVisibleLogicalRangeChange` |

Lightweight Charts supports multiple series and custom plugins; indicator data should follow the same `{ time, value }` series contract as candles.

## Files added / modified

| File | Purpose |
|------|---------|
| `PHASE_13B_IMPLEMENTATION_NOTES.md` | This document |
| `static/js/terminal_chart.js` | Chart renderer module |
| `static/templates/terminal.html` | Toolbar, LWC integration, remove Plotly |
| `src/charting/candle_adapter.py` | Payload → bar records (shared contract, tested) |
| `tests/test_terminal_chart.py` | Rendering adapter + API + page smoke |
| `tests/e2e/test_terminal_chart_smoke.py` | Optional Playwright smoke |

## Out of scope (Phase 13B)

- Indicators, drawing tools, persisted zoom
- Changes to `order_engine`, `execution`, or session logic
