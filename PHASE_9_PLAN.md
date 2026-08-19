# Phase 9 — Adaptive AI Trading Mentor

## Current Learning Loop

```
Market Data → Analysis → Strategy Creation → Backtest → Paper Trade
     → Performance Review → AI Coaching → Skill Improvement ↺
```

The platform has all stages but they operate **independently**. The coach explains markets and strategies but does not model **the trader's behavior** or adapt to their history.

## Missing Educational Capabilities

| Gap | Impact |
|-----|--------|
| No trader profile | Coach treats every user the same |
| No mistake pattern detection | Repeated errors go unnoticed |
| No personalized "what next?" | User must self-navigate lessons/challenges |
| No scenario practice | Real-time decision-making untrained |
| No progress history | Skill score is point-in-time only |
| Coach is market-focused | Cannot answer "Why did I lose money?" holistically |

## Architecture Changes (New Layer Only)

```
src/learning/
├── trader_profile.py      # NEW — experience, strengths, weaknesses
├── mistake_detector.py      # NEW — pattern analysis on trade history
├── recommendations.py       # NEW — adaptive lesson/challenge suggestions
└── progress.py              # NEW — daily/weekly tracking

src/ai_agent/
└── mentor.py                # NEW — personalized instructor

src/simulation/
└── scenarios.py             # NEW — market scenario exercises

src/api/
└── mentor_routes.py         # NEW — profile, mentor, scenarios, progress

static/templates/
└── mentor.html              # NEW — /mentor dashboard
```

**Unchanged:** Strategy Lab, replay engine, core simulator, existing coach endpoints.

## API Changes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/profile` | Get trader profile |
| POST | `/api/profile` | Update trader profile |
| GET | `/api/mentor/advice` | Personalized mentor guidance |
| POST | `/api/mentor/ask` | Answer specific questions |
| GET | `/api/mistakes` | Detected mistake patterns |
| GET | `/api/recommendations` | Adaptive lesson/challenge suggestions |
| GET | `/api/scenarios` | List scenario exercises |
| GET | `/api/scenarios/<id>` | Scenario detail |
| POST | `/api/scenarios/<id>/answer` | Submit decision, get score |
| GET | `/api/progress` | Daily/weekly progress |

## Testing Strategy

| Test File | Coverage |
|-----------|----------|
| `test_adaptive_learning.py::TestTraderProfile` | CRUD, persistence, level inference |
| `test_adaptive_learning.py::TestMistakeDetector` | Each mistake type, frequency, severity |
| `test_adaptive_learning.py::TestRecommendations` | Lesson mapping from mistakes |
| `test_adaptive_learning.py::TestScenarios` | Scoring, all scenario types |
| `test_adaptive_learning.py::TestMentor` | Advice shape, question handling |
| `test_adaptive_learning.py::TestProgress` | Daily/weekly aggregation |
| `test_adaptive_learning.py::TestMentorAPI` | Flask integration |

Run `pytest` — **do not finish until all tests pass.**

## Commit Plan

1. `docs: add phase 9 plan`
2. `feat: add trader profiles`
3. `feat: add mistake detection`
4. `feat: add AI mentor`
5. `feat: add scenario training`
6. `feat: add adaptive lessons`
7. `feat: add progress tracking`
8. `feat: add mentor dashboard`
9. `test: add adaptive learning coverage`

## Design Principles

- **Model the trader, not the market** — personalize from behavior
- **No autonomous trading** — mentor advises, user decides
- **Paper money only** — no broker connections
- **Rule-based mentor** — no external LLM required
- **Incremental layer** — extend, don't rewrite
