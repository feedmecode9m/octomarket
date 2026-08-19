# Phase 13E — Trade Plan Panel

## Objective

Insert a reasoning layer between chart analysis and order execution.

```
Observation → Analysis → Trade Plan ← 13E → Order → Execution → Journal
```

Traders must express thesis, levels, and risk before placing orders.

## Components

| Path | Role |
|------|------|
| `src/trading/trade_plan.py` | Model, validation, risk math, state machine |
| `src/api/trade_plan_routes.py` | REST API |
| `terminal.html` | Trade Plan panel above Order Ticket |

## Trade plan model

- Symbol, direction (LONG/SHORT), thesis
- Entry / stop / target with optional drawing source
- Risk points, reward points, R:R ratio
- Setup snapshot: active indicators + drawings at plan time
- Status: DRAFT → REVIEWED → APPROVED → ORDER_CREATED → COMPLETED

## API

| Method | Path |
|--------|------|
| POST | `/api/trade-plan` |
| GET | `/api/trade-plan/<symbol>` |
| PUT | `/api/trade-plan/<id>` |
| POST | `/api/trade-plan/<id>/review` |
| POST | `/api/trade-plan/<id>/approve` |
| POST | `/api/trade-plan/<id>/create-order` |

`create-order` bridges to existing `order_engine` — no execution engine changes.

## Out of scope

- Order engine / execution engine modifications
- AI coach enhancements (Phase 13F)

## Tests

Target: 370+ passing (`test_trade_plan.py`, `test_trade_plan_api.py`).
