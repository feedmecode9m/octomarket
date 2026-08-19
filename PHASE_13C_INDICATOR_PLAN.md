# Phase 13C — Technical Analysis Layer

## Objective

Add TradingView-style technical indicators between candlestick visualization and trade planning.

```
Market Data → Candlestick Chart ✅ → Indicators ← 13C → Drawings → Trade Plan → Execution
```

## Scope

| Component | Path |
|-----------|------|
| Indicator models | `src/charting/indicator_models.py` |
| Calculation engine | `src/charting/indicators.py` |
| API | `GET /api/chart/<symbol>/indicators?indicators=SMA20,RSI,MACD` |
| Frontend | `static/js/terminal_chart.js`, indicator toggles in `terminal.html` |

## Indicators

| Indicator | Defaults | Pane |
|-----------|----------|------|
| SMA | period 20 | overlay |
| EMA | 9, 20, 50, 200 | overlay |
| RSI | period 14 | sub-pane |
| MACD | 12 / 26 / 9 | sub-pane |
| Bollinger Bands | 20, stddev 2 | overlay |

## Out of scope

- Order engine, execution, portfolio, session lifecycle
- Drawing tools (Phase 13D)
- Chart-to-order workflow (Phase 13E)

## API contract

Query param `indicators` is comma-separated keys: `SMA20`, `EMA9`, `RSI`, `MACD`, `BB`.

Response values align with candle timestamps; warmup bars use `null`.

## Frontend

- Toggle panel in chart toolbar
- SMA/EMA/BB as line overlays on main chart
- RSI and MACD in dedicated sub-panels (synced time scale)
- Preserve candles, volume, crosshair, order price lines

## Tests

- `tests/test_indicators.py` — math, edge cases, parsing
- `tests/test_indicator_api.py` — HTTP payload, errors, integration

Target: 290+ passing tests.
