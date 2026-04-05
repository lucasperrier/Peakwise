# TASKS

## Goal
Build a V1 that can answer:

**What should I do today, and why?**

This task list is ordered so coding agents can work in bounded, testable increments.

---

## Phase 0 - Repository and planning
- [x] Initialize repository structure
- [x] Create `README.md`
- [x] Add `docs/v1_scope.md`
- [x] Add `docs/data_model.md`
- [x] Add `docs/scoring.md`
- [x] Add `docs/bedrock_spec.md`
- [x] Define coding conventions and agent guardrails
- [x] Choose stack and document the decision
- [x] Configure linting and formatting
- [x] Configure testing framework
- [x] Create `.env.example`

### Deliverable
A repo with clear docs, tooling, and a stable implementation target.

---

## Phase 1 - Warehouse foundation

### Database
- [x] Set up database project
- [x] Create migrations for `daily_fact`
- [x] Create migrations for `workout_fact`
- [x] Create migrations for `manual_daily_input`
- [x] Create migrations for `daily_source_coverage`
- [x] Create migrations for `daily_features`
- [x] Create migrations for `score_snapshot`
- [x] Create migrations for `recommendation_snapshot`

### Seed and fixture data
- [x] Create seed file for daily metrics
- [x] Create seed file for workouts
- [x] Create seed file for manual inputs
- [x] Create seed script to populate local database

### Validation
- [x] Add schema validation for inbound records
- [x] Add source lineage fields
- [x] Add data quality flags
- [x] Add tests for warehouse writes

### Deliverable
A local database containing realistic seeded historical data.

---

## Phase 2 - Ingestion layer

### File-based ingestion first
- [x] Implement Garmin import from export format or normalized CSV
- [x] Implement Apple Health import from export format or normalized CSV
- [x] Implement Strava import from export format or normalized CSV
- [x] Implement scale import from CSV
- [x] Implement manual input import and form handling

### Normalization
- [x] Map imported data into source-agnostic warehouse records
- [x] Deduplicate duplicate workout records across sources if needed
- [x] Mark partial or missing days explicitly
- [x] Log ingestion errors and skipped rows

### Deliverable
A repeatable ingestion pipeline that can rebuild the warehouse from exported data.

---

## Phase 3 - Feature engineering

### Daily features
- [x] Compute 7-day rolling averages
- [x] Compute 28-day baseline deviations
- [x] Compute 90-day baseline features where relevant
- [x] Compute sleep debt
- [x] Compute body-weight slope
- [x] Compute recovery trend
- [x] Compute steps consistency
- [x] Compute mood and stress trends

### Running features
- [x] Compute weekly km
- [x] Compute rolling 4-week km
- [x] Compute longest run in last 7 days
- [x] Compute easy-run efficiency at fixed HR band
- [x] Compute quality-session completion counts
- [x] Compute projected HM time placeholder logic
- [x] Compute plan adherence placeholder logic

### Hybrid features
- [x] Parse CrossFit notes into tags where available
- [x] Compute lower-body CrossFit density
- [x] Compute hard-day density
- [x] Compute session spacing quality
- [x] Compute interference risk score inputs
- [x] Compute long-run protection score inputs

### Deliverable
A populated `daily_features` layer that supports deterministic scoring.

---

## Phase 4 - Scoring engine

### Recovery score
- [x] Implement recovery score formula
- [x] Persist recovery subcomponents
- [x] Add tests for high, medium, low readiness days

### Race-readiness score
- [x] Implement race-readiness formula
- [x] Persist race-readiness subcomponents
- [x] Add tests for on-track vs off-track scenarios

### General-health score
- [x] Implement general-health formula
- [x] Persist general-health subcomponents
- [x] Add tests for stable vs drifting health scenarios

### Load-balance score
- [x] Implement load-balance formula
- [x] Persist load-balance subcomponents
- [x] Add tests for balanced vs interference-heavy weeks

### Warning logic
- [x] Implement knee pain warning
- [x] Implement illness warning
- [x] Implement sleep debt warning
- [x] Implement HRV suppression warning
- [x] Implement overload warning
- [x] Add tests for warning triggers

### Deliverable
A deterministic score engine with persisted outputs and test coverage.

---

## Phase 5 - Recommendation engine
- [x] Define recommendation rule config
- [x] Implement mapping from scores and warnings to recommendation mode
- [x] Implement mapping from recommendation mode to suggested action
- [x] Add reason codes
- [x] Add next-best alternative output
- [x] Persist recommendation snapshots
- [x] Add unit tests for recommendation outcomes

### Deliverable
The backend can answer: what should I do today, and why?

---

## Phase 6 - API contracts
- [x] Create `GET /api/today`
- [x] Create `GET /api/running`
- [x] Create `GET /api/health`
- [x] Create `GET /api/strength`
- [x] Create `GET /api/weekly-review`
- [x] Create `POST /api/manual-input`
- [x] Define typed response payloads
- [x] Add contract tests

### Deliverable
Stable application endpoints ready for the frontend.

---

## Phase 7 - Frontend MVP

### Today page
- [x] Build Today recommendation card
- [x] Build Recovery card
- [x] Build Half-marathon card
- [x] Build Health card
- [x] Build Training-balance card
- [x] Build short explanation panel

### Trend views
- [x] Running page with weekly km trend and long-run progression
- [x] Health page with weight, sleep, HRV, resting HR trends
- [x] Strength page with session timeline and lower-body load density
- [x] Weekly review page with key changes and flags

### Deliverable
A usable localhost dashboard centered on the Today screen.

---

## Phase 8 - LLM layer
- [x] Build structured context assembler from score and feature outputs
- [x] Define prompt for daily explanation
- [x] Define prompt for weekly review
- [x] Define prompt for question answering
- [x] Log structured context alongside LLM output
- [x] Add grounding guardrails so the model only explains explicit inputs
- [x] Add fallback behavior if LLM call fails

### Deliverable
The app produces grounded natural-language explanations of computed states.

---

## Phase 9 - Feedback loop and refinement
- [ ] Add recommendation feedback UI
- [ ] Store feedback events
- [ ] Build simple admin/debug view for score inspection
- [ ] Surface missing-data warnings in UI
- [ ] Tune thresholds using lived data
- [ ] Improve note parsing heuristics

### Deliverable
A V1 that can be iteratively improved from real usage.

---

## First milestone
- [ ] Given seeded historical data, the app computes scores
- [ ] Given those scores, the app produces a recommendation
- [ ] The Today screen renders the recommendation and score drivers
- [ ] The LLM explanation is grounded in structured context

When all four items above are true, the first milestone is complete.

---

## Agent guardrails
- [ ] Never invent score formulas outside documented rules
- [ ] Never bypass typed contracts
- [ ] Keep business logic out of UI components
- [ ] All score outputs must expose subcomponents
- [ ] Preserve source lineage in ingestion
- [ ] Keep thresholds in config, not hard-coded in multiple places
- [ ] Add tests for every scoring and recommendation module
- [ ] LLM outputs must be based on structured context only
