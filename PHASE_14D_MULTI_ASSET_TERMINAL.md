# Phase 14D — Multi-Asset Terminal

## Objective

Make the existing terminal workflow instrument-aware for STOCK, FOREX, and FUTURES without redesigning the UI or breaking stock behavior.

## Architecture decisions

### Instrument-first state

Chart workspace state carries:

| Field | Example |
|-------|---------|
| `instrument_id` | ESZ26 |
| `symbol` | ES (chart/drawing storage key) |
| `asset_class` | FUTURES |
| `display_symbol` | ESZ26 |
| `session` | venue, 24h flag, windows |

Legacy `symbol` fields remain for backwards compatibility with drawings, watchlist, and order engine.

### Data flow

```
Instrument API (/api/instruments)
        ↓
Terminal selectors (asset + instrument)
        ↓
Chart state PUT (instrument_id)
        ↓
Candles / indicators / drawings (symbol key + data_feed_symbol)
        ↓
Trade plan (asset-class metrics)
        ↓
AI review → execution
```

### Symbol mapping

`src/market/symbol_map.py` maps instruments to yfinance feed symbols:

- AAPL → AAPL
- EURUSD → EURUSD=X
- ESZ26 → ES=F

Drawings and session caps continue to use workspace `symbol`.

### Session rules

Attached at instrument resolution time from `session_rules.py`:

- STOCK → NYSE hours
- FOREX → 24h weekly
- FUTURES → CME Globex

Displayed in terminal header (`marketSessionBadge`, `sessionLabel`).

## Supported instruments (Phase 14D catalog)

| Asset class | Examples |
|-------------|----------|
| STOCK | AAPL, MSFT, TSLA |
| FOREX | EURUSD, GBPUSD, USDJPY, AUDUSD |
| FUTURES | ESZ26, NQZ26, CLZ26, GCZ26 |

## Trade plan display by asset class

| Class | Quantity label | Risk unit |
|-------|----------------|-----------|
| STOCK | shares | points |
| FOREX | lots | pips |
| FUTURES | contracts | ticks |

Auto-sizing uses `account_balance` + `risk_percent` when provided.

## Future extension points

- Phase 15: replay engine uses `instrument_id` + session rules
- Broker integration: map `PositionUnit` to venue order types
- Additional contracts: extend `FUTURES_CATALOG` in `instrument.py`
- Live forex/futures data providers beyond yfinance

## Out of scope (14D)

- Replay / learning engine
- New AI capabilities
- Terminal visual redesign
- Live broker connectivity
