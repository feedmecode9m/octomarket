# Phase 13F — AI Chart Coach

## Objective

Add a trading **mentor** that reviews plans and execution using structured market state — not predictions or buy/sell calls.

```
Trade Plan → AI Coach → Review → Create Order
                ↓
         Post-trade plan vs actual comparison
```

## Components

| Module | Role |
|--------|------|
| `market_context.py` | Assemble price, indicators, drawings, trade plan |
| `plan_review.py` | Rule-based pre/post trade review logic |
| `chart_coach.py` | Orchestration + coach history store |

## Coach output

```json
{
  "grade": "B",
  "observations": [],
  "warnings": [],
  "questions": [],
  "risk_notes": []
}
```

## API

| Method | Path |
|--------|------|
| POST | `/api/ai/chart-review` |
| POST | `/api/ai/trade-review/<plan_id>` |
| GET | `/api/ai/coach-history/<symbol>` |

## Guardrails

- No buy/sell recommendations
- No autonomous execution
- No prediction claims
- Reasoning, risk education, process feedback only

## Tests

Target: 400+ passing (`test_chart_coach.py`, extend AI route tests).
