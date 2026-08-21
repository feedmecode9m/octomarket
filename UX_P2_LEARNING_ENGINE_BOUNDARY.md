# UX-P2 — Learning Engine Boundary Plan

**Status:** FROZEN PRODUCT CONTRACT — do not implement until a separate Pilot gate is authorized  
**Frozen:** 2026-08-21 · baseline `0e1d2d5` (UX-P1 repair PASS) · UX-P1 `6908614` · A1 `0f0c9aa`  
**Relation to UX-P1:** UX-P1 = surfaces (“what is this?”). UX-P2 = habits (“how to operate”).

> Changes to this document after freeze require an explicit product decision.  
> Pilot code is **not** authorized by this freeze.

```text
Terminal
   |
   +--> Chart system          (may fail without killing learning)
   +--> Replay system         (A1 contracts intact)
   +--> Learning / onboarding (UX-P1 tour + UX-P2 path — separate modules)
```

---

## Mission

Teach process before action, in context, until disciplined behavior becomes automatic — without trapping experienced users, inventing fake history, or weakening trading/session contracts.

**Philosophy line:** The product teaches process before action.

---

## Hard boundaries (non-negotiable)

| Must | Must not |
|------|----------|
| Client-only learning state for V1 | New `/api/learning/*` progress APIs in V1 |
| Use real Replay / Plan / Review / Journal surfaces | Second simulation engine |
| Explicit `instrument_id` on Replay start (A1) | Silent defaults / empty `session/start` |
| Soft coaching with escape | Hard permanent blocks on order placement |
| Prove learning via real user actions | Fake fills, fake journal rows, fake Decision Review records |
| Decouple learning boot from chart success | Gate coaching init behind chart init |
| Separate storage key from UX-P1 tour | Overwrite `octomarket.onboarding.v1` for curriculum |

---

## 1. Learning state ownership

### Decision: V1 = local-only

| Question | V1 answer |
|----------|-----------|
| Where does progress live? | Browser `localStorage` only |
| Account / backend profile? | **Out of scope** for V1 |
| Cross-device sync? | No |

**Storage key (proposed):** `octomarket.learning.v1`  
*(Separate from `octomarket.onboarding.v1` — tour completion ≠ curriculum progress.)*

**Schema (proposed):**

```text
{
  "version": 1,
  "mode": "beginner" | "experienced",
  "active_lesson_id": "observe_before_trade" | null,
  "status": "idle" | "in_progress" | "lesson_complete" | "path_paused",
  "completed": ["observe_before_trade"],
  "dismissed": {
    "observe_before_trade": { "at": "<iso>", "reason": "skip_lesson" | "continue_anyway" | "experienced_mode" }
  },
  "counters": {
    "observe_before_trade": { "replay_steps": 0, "impulse_prompts_shown": 0 }
  },
  "prefs": {
    "coaching_enabled": true,
    "quiet_until": null
  }
}
```

**Pros:** no backend, no auth dependency, matches UX-P1 discipline.  
**Cons:** lost on clear-storage / new device — accepted for V1.

### Future (explicitly not V1)

```text
User
 └── Learning Progress
      ├── Completed lessons
      ├── Weak areas (from real Review/Journal signals)
      └── Coaching preference / mode
```

Backend profile may later *mirror* the same lesson IDs; V1 schema should stay migrate-friendly (`version` field).

---

## 2. Lesson engine model

### Decision: lessons are data (content + rules), not hard-coded animation scripts

UX-P1 tour states are a linear walkthrough. UX-P2 lessons are **triggered coaching units** that can fire when the user attempts a behavior.

**Lesson record:**

```text
Lesson
 ├── id                 string
 ├── title              string
 ├── objective          one sentence
 ├── bad_habit          what we prevent
 ├── trigger            when coach may appear
 ├── guidance           best-practice copy (not “click because tutorial”)
 ├── success            observable completion rule
 ├── soft_block         optional pre-action checklist (dismissible)
 ├── next_lesson_id     string | null
 └── modes             which user modes receive this lesson
```

### Curriculum map (full path — content backlog, not V1 ship set)

| # | id | Bad habit | Success signal (real action) |
|---|-----|-----------|------------------------------|
| 0 | `start_here` | Jumping cold into tickets | Terminal open; path known (may be implicit after UX-P1) |
| 1 | `observe_before_trade` | Impulse entries | ≥ N Replay **Step**s with active Replay; no order placed during active lesson window *or* user dismissed after checklist |
| 2 | `trade_needs_reason` | Guess entries | Plan UI has thesis + levels filled (durable save optional in early lessons) |
| 3 | `know_invalidation` | No stop / “hope” | Invalidation/stop stated before execute encouragement |
| 4 | `replay_is_arena` | LIVE-as-casino | Short Replay loop with explicit instrument |
| 5 | `execute_from_plan` | Orphan clicks | Real plan→order linkage when user chooses to act |
| 6 | `review_process` | P/L worship | Decision Review after a **real** closed planned trade |
| 7 | `journal_the_lesson` | Repeat same error | Visit Journal when an entry exists |
| 8 | `improve_next` | One-and-done | Resume path / next lesson available |

### Pilot (only lesson authorized for first implementation gate later)

**`observe_before_trade`**

```text
id:          observe_before_trade
objective:   Observe market context before acting
bad_habit:   Impulse order entry without Replay observation
trigger:     User attempts order / Buy-Sell path while coaching on
             AND (no active Replay OR replay_steps < N)
guidance:    “You are about to place an order. Best practice: observe
             with Replay Step first so the decision has context.”
success:     N Replay steps completed in current session while lesson
             active (recommended N = 5), OR lesson skipped/dismissed
soft_block:  Checklist panel — not a hard forbid
next:        trade_needs_reason (not implemented in pilot)
```

**What proves learning:** workflow events (Step counts, mode=REPLAY), **not** tooltip clicks alone.

---

## 3. Coaching rules

### Tone contract

| Avoid | Prefer |
|-------|--------|
| “Click Step because the tutorial says so.” | “You are attempting an order. Best practice is to observe context first.” |
| Fake celebration for empty actions | Acknowledge real Step / plan / review |
| Permanent modal prison | Soft panel + Continue / Review plan / Dismiss |
| Coaching that invents market outcomes | Coaching that references user intent + process |

### Soft-block pattern (canonical)

When trigger fires (example: Buy / place order while lesson active and success unmet):

```text
Before placing an order — process check

Have you defined / done:
□ Observed with Replay Step (context)
□ Thesis
□ Entry
□ Invalidation
□ Target

[Observe with Step]   [Review plan]   [Continue anyway]
```

Rules:

1. **Never forever-block** order placement in V1 — always offer Continue anyway (counts as dismiss for metrics).
2. Primary CTA routes to the **next best Terminal action** (e.g. Step), not a separate lesson page.
3. At most **one** coaching surface visible; queue or suppress duplicates (`impulse_prompts_shown` cap per session).
4. After success, show a short confirmation once, then quiet that lesson.
5. Copy names the **behavior**, not the UI chrome (“observe context” > “press the cyan button”).

### Event proof model

| Weak proof (insufficient alone) | Strong proof |
|---------------------------------|--------------|
| Dismissed coach | Replay Step × N |
| Opened tour | Active REPLAY mode + steps |
| Hovered plan | Plan fields meaningfully filled |
| Visited Journal empty | Journal open **with** real entry / Review after real close |

Pilot success leans on **Replay Step count**, not “clicked Continue.”

---

## 4. Experienced user escape path

### Decision: explicit mode + always-available quieting

```text
Beginner mode  →  guided coaching for incomplete lessons
Experienced mode → reduced prompts (path idle; optional tip on demand)
```

**Escape mechanisms (all required in any later implementation):**

| Control | Behavior |
|---------|----------|
| **Skip lesson** | Marks lesson dismissed; advances or idles; does not write fake progress as “completed” unless we explicitly allow “skipped” ≠ “completed” |
| **Continue anyway** | Allows action; records dismiss reason; may re-prompt with backoff |
| **Experienced mode** | Sets `mode=experienced`, `coaching_enabled` soft-off for curriculum prompts |
| **Quiet for session** | `quiet_until` / session flag — no coach until reload or user re-enables |
| **Tour vs Path** | UX-P1 Skip/Complete does not force UX-P2; optional handoff CTA only |

**Completed vs skipped:** keep distinct in storage so metrics stay honest.

**Default mode:** `beginner` until user chooses Experienced or completes pilot lesson. Users who already `COMPLETE`d UX-P1 still get beginner coaching **once** for the pilot unless they opt out — surfaces intro ≠ habit proof.

---

## 5. Success metrics

### Do not optimize

- Time spent in coach UI  
- Number of coach impressions  
- Tour completion alone  

### Do measure (product signals)

| Metric | Signal |
|--------|--------|
| First planned workflow | Real plan → order → close → Review path used |
| Replay before orders | Session: first Step/Replay activity precedes first order (or coach Continue rate falls) |
| Plans with reasoning | Thesis non-empty on linked plans |
| Return to Review/Journal | Visits after closes; journal entries from real trades |
| Fewer impulsive actions | Drop in Continue-anyway on `observe_before_trade` over sessions (local analytics later; V1 can log counters only in localStorage) |

V1 may only **instrument counters in localStorage**; no telemetry backend required to ship the pilot.

---

## 6. Implementation boundary & phases

### Out of scope for UX-P2 V1 pilot

- Lessons 2–8 UI  
- Adaptive / ML coaching  
- Backend learning profile  
- Mentor/Academy rewrite  
- Chart feature expansion  
- Fake market scenarios for “grades”  
- Weakening order_engine / session / journal contracts  

### Phased delivery (authorization gates)

```text
Phase 0  Boundary plan          ← THIS DOCUMENT (freeze before code)
Phase 1  Pilot lesson only      observe_before_trade (client module)
Phase 2  Browser QA on pilot    same discipline as UX-P1
Phase 3  Lesson 2–3             reason + invalidation
Phase 4  Workflow lessons       execute_from_plan → review → journal
Phase 5  Experienced polish     quieter defaults, backoff tuning
Phase 6  Optional backend sync  only after local model proven
```

### Module shape (when coding is later authorized)

```text
static/js/learning_path.js     # engine: state, triggers, success
static/css/learning_path.css   # coach panel (not tour clone)
terminal.html                  # bindHost events only; no engine rewrite
```

- **Do not** fold UX-P2 into `onboarding_tour.js` — keep tour and path separate.  
- **Do** init learning engine in the same decoupled boot path as onboarding (`finally` / independent of chart).  
- Host bindings: observe Step, order intent, Replay active — thin adapters only.

### Relationship to UX-P1 after COMPLETE

Optional single CTA: “Continue with Learning Path” → activates `observe_before_trade`.  
Never auto-chain a second full-screen tour.

---

## Boundary answers (summary)

| # | Question | Decision |
|---|----------|----------|
| 1 | Progress ownership | **Local-only V1** (`octomarket.learning.v1`); backend later |
| 2 | Lesson style | **Fixed curriculum** as content records; adaptive weak-area coaching is post-V1 |
| 3 | Proof of learning | **Completed workflows / real actions** (Step, plan fields, real review) — not tutorial clicks; no fake trades |
| 4 | Avoid annoyance | Soft-block + Continue anyway + Experienced mode + session quiet + prompt caps |
| 5 | First ship | **One lesson:** `observe_before_trade` |
| 6 | Code now? | **No** — freeze this plan; implement only under a separate gate |

---

## Freeze checklist

- [x] State ownership decided (local V1)  
- [x] Lesson model decided (data/triggers/success)  
- [x] Coaching behavior decided (soft, process-framed)  
- [x] Experienced escape decided  
- [x] Metrics decided (habit signals, not dwell time)  
- [x] Pilot scope = one lesson  
- [x] **Boundary plan frozen as product contract (2026-08-21)**  
- [ ] Pilot implementation gate (separate authorization — not open)  
- [ ] Browser QA gate after pilot code  

---

## Next implementation gate (NOT YET AUTHORIZED)

When separately authorized, the **only** allowed first ship is:

# UX-P2 Pilot: Lesson 1 — Observe Before Trade

```text
Lesson ID:   observe_before_trade
Goal:        Observe market context before making decisions
Trigger:     User enters Terminal / Replay context (per frozen rules)
Coach:       Why observation comes first (process-framed, soft)
Proof:       User completes Replay steps (real workflow)
Completion:  Mark lesson complete in localStorage only
Next:        Planning lesson later — not in pilot
```

**Pilot must not include:** all 8 lessons, adaptive AI, scoring, achievements, backend profiles, gamification, trading/session contract changes.

**Pilot success criteria (before expanding curriculum):**

1. Enter Terminal  
2. Understand why observe-first matters  
3. Use Replay  
4. Complete the lesson locally  
5. Return later without feeling interrupted  

---

## Roadmap position

```text
0f0c9aa          A1 CLOSED
→ 18A.3 COMPLETE
→ 6908614        UX-P1 COMMITTED
→ 0e1d2d5        UX-P1 repair + Browser QA PASS
→ THIS ARTIFACT  UX-P2 Learning Engine Boundary FROZEN (contract)
→ STOP

Next authorization (when ready):
  Open UX-P2 Pilot Implementation Gate —
  Lesson 1 only (observe_before_trade),
  no additional lessons, no backend changes, no trading contract changes.
```
