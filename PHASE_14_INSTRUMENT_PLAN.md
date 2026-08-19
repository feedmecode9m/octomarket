# Phase 14 — Multi-Asset Instrument Foundation

## Checkpoint

Phase 13F completes OctoMarket v0.2 (`octomarket-v0.2.0`): Observe → Analyze → Plan → Review → Execute → Learn.

Replay & Learning moves to **Phase 15** after instruments are modeled correctly.

## Roadmap

| Phase | Scope |
|-------|--------|
| 14A | Instrument abstraction (stocks, forex, futures) |
| 14B | Forex trading — pips, lots, 24h sessions |
| 14C | Futures trading — contracts, tick value, margin |
| 14D | Multi-asset terminal — asset/contract selectors |
| 15 | Replay & learning engine |

## 14A modules

```
src/market/
├── asset_class.py
├── instrument.py
├── contract.py
└── session_rules.py
```

## Instrument model

Unified instrument replaces stock-only `symbol` assumptions:

```json
{
  "symbol": "EURUSD",
  "asset_class": "FOREX",
  "exchange": "FX",
  "tick_size": 0.00001,
  "currency": "USD"
}
```

```json
{
  "symbol": "ES",
  "asset_class": "FUTURES",
  "exchange": "CME",
  "contract": "ESZ26",
  "tick_size": 0.25,
  "point_value": 50
}
```

## Rules

- Normalize forex symbols (`EUR/USD` → `EURUSD`)
- Session rules vary by asset class (NYSE vs 24h FX vs Globex)
- Do not modify order/execution engine internals in 14A
- Chart layer unchanged — instruments feed metadata only

## Tests

`tests/test_instrument.py` — normalization, pip math, contract parsing, session lookup
