# Phase 12 — OctoMarket Identity

## Branding Changes

| Before | After |
|--------|-------|
| Real-Time Stock Trading Simulator | **OctoMarket** |
| AI Trading Mentor | OctoMarket Mentor |
| Strategy Lab | OctoMarket Lab |
| Trading Terminal | OctoMarket Terminal |
| Market Replay (dashboard) | OctoMarket Replay |
| Learning Mode | OctoMarket Academy |
| Trade journal (feature) | OctoMarket Journal |

**Tagline:** Practice. Analyze. Execute. Improve.

**Positioning:** AI-powered trading practice terminal — paper money only.

## UI Changes

| Area | Change |
|------|--------|
| Browser titles | `{Module} — OctoMarket` |
| `/` | New landing dashboard with product cards |
| `/replay` | Former main simulator (unchanged functionality) |
| `/terminal` | Top bar: market status, balance, equity, risk score |
| All pages | Shared OctoMarket navigation bar |
| Error pages | OctoMarket branding |
| Startup console | OctoMarket product name |

## README Changes

- Rename project to OctoMarket
- Update feature list to reflect mentor, lab, terminal, replay
- Keep install/run instructions unchanged
- Note paper-trading-only policy

## Future Module Naming

| Internal (unchanged) | Product label |
|---------------------|---------------|
| `src/api/terminal_routes.py` | OctoMarket Terminal |
| `src/api/mentor_routes.py` | OctoMarket Mentor |
| `src/api/strategy_lab_routes.py` | OctoMarket Lab |
| `src/simulation/market_replay.py` | OctoMarket Replay |
| `src/learning/` | OctoMarket Academy |
| `src/ai_agent/trade_journal.py` | OctoMarket Journal |

Backend paths and API URLs are **not** renamed.

## Migration Risks

| Risk | Mitigation |
|------|------------|
| Bookmarks to `/` expect old dashboard | `/replay` preserves simulator; `/` is new home |
| Hardcoded product strings in tests | Centralize in `src/config/product.py` |
| Template drift | Context processor injects product config |
| Broken nav links | Branding tests verify all routes return 200 |
| API clients | All `/api/*` paths unchanged |

## New Files

| File | Purpose |
|------|---------|
| `src/config/product.py` | Product name, version, tagline, labels |
| `static/assets/branding/theme.css` | OctoMarket design tokens |
| `static/assets/branding/logo.svg` | Logo placeholder |
| `static/templates/home.html` | Landing dashboard |
| `static/templates/partials/octo_nav.html` | Shared navigation |
| `static/templates/academy.html` | Lessons & challenges |
| `static/templates/journal.html` | Trade review journal |
| `tests/test_branding.py` | Config, routes, assets |
