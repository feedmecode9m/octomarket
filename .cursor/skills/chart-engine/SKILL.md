---
description: OctoMarket chart engine — candlesticks, timeframes, drawing tools, TradingView-style UX. Use for Phase 13 charting, terminal UI, and Plotly/chart work.
---

# OctoMarket Chart Engine

## Phase 13 goal

Build a TradingView-style practice chart: **Chart → Analyze → Plan → Execute → Review**.

## Current stack

- **Plotly** in `static/templates/terminal.html` and `index.html` (replay).
- Chart data: `GET /api/session/chart/<symbol>` → `{ timestamps, prices }`.
- Click-to-set price on terminal chart; horizontal lines for entry / SL / TP via `layout.shapes`.

## Candlestick concepts

- Each bar: open, high, low, close over a timeframe (1d default in session).
- Wicks show high/low; body shows open→close.
- Phase 13 should add proper OHLC candlestick traces, not only line charts.

## Timeframes

- Session uses `interval` + `period` params on start (default `1d` / `5d`).
- Preserve stepping one candle at a time for educational pacing.

## Drawing tools (roadmap)

| Tool | Purpose |
|------|---------|
| Horizontal line | Entry, SL, TP (partial) |
| Trend line | Structure / support-resistance teaching |
| Order markers | Visual link to `order_engine` orders |

Sync drawing prices with `PUT /api/orders/<id>` for editable levels.

## TradingView workflow to mirror

1. Select symbol (watchlist)
2. Read chart / indicators
3. Open order ticket (side, type, qty, SL, TP)
4. AI execution review (`POST /api/ai/review-execution`)
5. Place order → pending/filled states
6. Manage position in bottom panel
7. Journal review on exit

## Hotkeys (terminal)

- `B` buy, `S` sell, `X` close position, `ESC` cancel pending order

## Browser testing (Playwright)

When Playwright plugin is installed, E2E flows:

```
Open /terminal → Start session → Step → Place limit order → Verify orders tab → Close position → Check /journal
```

## Implementation constraints

- No external charting SaaS required; extend Plotly or add lightweight canvas layer.
- Keep paper-only; chart clicks create orders in `order_engine`, not external APIs.
- Match OctoMarket theme: `static/assets/branding/theme.css` (`--om-accent`, dark terminal).

## Key files

- `static/templates/terminal.html` — terminal chart + ticket
- `static/templates/index.html` — replay chart
- `src/api/terminal_routes.py` — session/chart endpoints
- `src/simulation/session.py` — candle state
