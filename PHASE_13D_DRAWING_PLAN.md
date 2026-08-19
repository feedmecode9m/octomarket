# Phase 13D — Trader Drawings & Market Thesis

## Objective

Turn the chart from price visualization into a **decision workspace** where traders annotate support, resistance, trends, and zones.

```
Market Data → Chart → Indicators ✅ → Drawings ← 13D → Trade Plan → Execution
```

## Architecture

| Module | Purpose |
|--------|---------|
| `drawing_models.py` | Horizontal, trendline, zone schemas |
| `drawing_store.py` | Per-symbol in-memory persistence |
| `drawings.py` | Validation, normalization, CRUD helpers |

## Drawing types

| Type | Fields | Use |
|------|--------|-----|
| `horizontal` | price, label, color | S/R, entry, SL, TP |
| `trendline` | start{time,price}, end{time,price} | Trend, channel |
| `zone` | top, bottom, label | Supply/demand zones |

## API

| Method | Path |
|--------|------|
| GET | `/api/chart/<symbol>/drawings` |
| POST | `/api/chart/<symbol>/drawings` |
| PUT | `/api/chart/<symbol>/drawings/<id>` |
| DELETE | `/api/chart/<symbol>/drawings/<id>` |

Workspace sync: `GET/PUT /api/chart/state` includes drawings for the active symbol from the store.

## Frontend

Draw toolbar in terminal chart: Horizontal · Trend · Zone · Delete

TradingView-style: select tool → click chart → create object.

## Out of scope

- Order engine, execution, session logic
- AI coaching / trade plan panel (Phase 13E)

## Tests

- `tests/test_drawings.py` — validation, store, symbol isolation
- `tests/test_drawing_api.py` — HTTP CRUD

Target: 330–340 passing tests.
