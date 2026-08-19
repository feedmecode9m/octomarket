# OctoMarket — Cursor Setup Guide

Prepared at **v0.1.0** before Phase 13 (Charting Engine).

## Installed in this repo

| Item | Path | Status |
|------|------|--------|
| Core rules | `.cursor/rules/octomarket-core.mdc` | ✅ |
| Python/Flask rules | `.cursor/rules/python-flask.mdc` | ✅ |
| Testing rules | `.cursor/rules/testing.mdc` | ✅ |
| Finance domain skill | `.cursor/skills/finance-domain/` | ✅ |
| Chart engine skill | `.cursor/skills/chart-engine/` | ✅ |

## Install manually in Cursor (recommended)

Open **Cursor Settings → Plugins / MCP** and add:

| Plugin | Priority | Use for OctoMarket |
|--------|----------|-------------------|
| **GitHub** | Must | PRs, issues, releases, commit review |
| **Playwright** | Must (Phase 13) | Terminal E2E: chart, orders, hotkeys, journal |
| **Postman** | Recommended | API collections for `/api/orders`, mentor, strategy |
| **Sentry** | Recommended (pre-release) | Frontend/chart/API error tracking |

## Not recommended

- Autonomous trading agents
- Stock prediction / "AI trader" plugins
- Live broker MCP servers (conflicts with paper-only mission)
- Random finance MCP until replay foundation is replaced intentionally

## Phase 13 stack summary

```
Cursor Rules (guardrails)
    + Finance Skill (domain)
    + Chart Skill (Phase 13)
    + Playwright (browser validation)
    + GitHub (shipping)
```

## Checkpoint tag

```bash
git tag octomarket-v0.1.0
git push origin octomarket-v0.1.0
```

## Product reference

- Config: `src/config/product.py`
- Tagline: *Practice. Analyze. Execute. Improve.*
- Home: `/` | Terminal: `/terminal` | Replay: `/replay`
