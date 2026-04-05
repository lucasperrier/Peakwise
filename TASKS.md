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
- [ ] Create seed file for daily metrics
- [ ] Create seed file for workouts
- [ ] Create seed file for manual inputs
- [ ] Create seed script to populate local database

### Validation
- [x] Add schema validation for inbound records
- [x] Add source lineage fields
- [x] Add data quality flags
- [ ] Add tests for warehouse writes

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
- [ ] Compute 7-day rolling averages
- [ ] Compute 28-day baseline deviations
- [ ] Compute 90-day baseline features where relevant
- [ ] Compute sleep debt
- [ ] Compute body-weight slope
- [ ] Compute recovery trend
- [ ] Compute steps consistency
- [ ] Compute mood and stress trends

### Running features
- [ ] Compute weekly km
- [ ] Compute rolling 4-week km
- [ ] Compute longest run in last 7 days
- [ ] Compute easy-run efficiency at fixed HR band
- [ ] Compute quality-session completion counts
- [ ] Compute projected HM time placeholder logic
- [ ] Compute plan adherence placeholder logic

### Hybrid features
- [ ] Parse CrossFit notes into tags where available
- [ ] Compute lower-body CrossFit density
- [ ] Compute hard-day density
- [ ] Compute session spacing quality
- [ ] Compute interference risk score inputs
- [ ] Compute long-run protection score inputs

### Deliverable
A populated `daily_features` layer that supports deterministic scoring.

---

## Phase 4 - Scoring engine

### Recovery score
- [ ] Implement recovery score formula
- [ ] Persist recovery subcomponents
- [ ] Add tests for high, medium, low readiness days

### Race-readiness score
- [ ] Implement race-readiness formula
- [ ] Persist race-readiness subcomponents
- [ ] Add tests for on-track vs off-track scenarios

### General-health score
- [ ] Implement general-health formula
- [ ] Persist general-health subcomponents
- [ ] Add tests for stable vs drifting health scenarios

### Load-balance score
- [ ] Implement load-balance formula
- [ ] Persist load-balance subcomponents
- [ ] Add tests for balanced vs interference-heavy weeks

### Warning logic
- [ ] Implement knee pain warning
- [ ] Implement illness warning
- [ ] Implement sleep debt warning
- [ ] Implement HRV suppression warning
- [ ] Implement overload warning
- [ ] Add tests for warning triggers

### Deliverable
A deterministic score engine with persisted outputs and test coverage.

---

## Phase 5 - Recommendation engine
- [ ] Define recommendation rule config
- [ ] Implement mapping from scores and warnings to recommendation mode
- [ ] Implement mapping from recommendation mode to suggested action
- [ ] Add reason codes
- [ ] Add next-best alternative output
- [ ] Persist recommendation snapshots
- [ ] Add unit tests for recommendation outcomes

### Deliverable
The backend can answer: what should I do today, and why?

---

## Phase 6 - API contracts
- [ ] Create `GET /api/today`
- [ ] Create `GET /api/running`
- [ ] Create `GET /api/health`
- [ ] Create `GET /api/strength`
- [ ] Create `GET /api/weekly-review`
- [ ] Create `POST /api/manual-input`
- [ ] Define typed response payloads
- [ ] Add contract tests

### Deliverable
Stable application endpoints ready for the frontend.

---

## Phase 7 - Frontend MVP

### Today page
- [ ] Build Today recommendation card
- [ ] Build Recovery card
- [ ] Build Half-marathon card
- [ ] Build Health card
- [ ] Build Training-balance card
- [ ] Build short explanation panel

### Trend views
- [ ] Running page with weekly km trend and long-run progression
- [ ] Health page with weight, sleep, HRV, resting HR trends
- [ ] Strength page with session timeline and lower-body load density
- [ ] Weekly review page with key changes and flags

### Deliverable
A usable localhost dashboard centered on the Today screen.

---

## Phase 8 - LLM layer
- [ ] Build structured context assembler from score and feature outputs
- [ ] Define prompt for daily explanation
- [ ] Define prompt for weekly review
- [ ] Define prompt for question answering
- [ ] Log structured context alongside LLM output
- [ ] Add grounding guardrails so the model only explains explicit inputs
- [ ] Add fallback behavior if LLM call fails

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
