# PHASE_2_CHECKLIST.md

# Peakwise — Phase 2 Checklist
## Trust, scoring, and daily decision layer

Phase 2 goal: make Peakwise able to answer, for any given day:

- what should I do today
- why
- how confident is the system
- which exact inputs drove that result

This phase turns the current MVP into a trustworthy decision system, consistent with the bedrock spec. :contentReference[oaicite:0]{index=0}

---

## 1. Freeze the decision contract

### Outputs for one date
- [x] `recovery_score`
- [x] `race_readiness_score`
- [x] `general_health_score`
- [x] `load_balance_score`
- [x] `recommendation_mode`
- [x] `recommended_action`
- [x] `reason_codes`
- [x] `confidence_level`

### Allowed recommendation modes
- [x] `full_go`
- [x] `train_as_planned`
- [x] `reduce_intensity`
- [x] `recovery_focused`
- [x] `full_rest`
- [x] `injury_watch`

### Allowed action labels
- [x] `easy_run`
- [x] `quality_run`
- [x] `long_run`
- [x] `crossfit_only`
- [x] `crossfit_plus_easy_run`
- [x] `mobility_walk`
- [x] `rest`

### Versioning
- [x] Add `score_version`
- [x] Add `recommendation_version`

---

## 2. Persist score breakdowns

### Tables
- [x] Create `daily_score_snapshots`
- [x] Create `daily_score_components`
- [x] Create `daily_reason_codes`

### `daily_score_snapshots`
- [x] Store one row per user per date
- [x] Persist final scores
- [x] Persist recommendation mode
- [x] Persist recommended action
- [x] Persist score version
- [x] Persist recommendation version
- [x] Persist generated timestamp

### `daily_score_components`
- [x] Persist component name
- [x] Persist raw input value
- [x] Persist normalized value
- [x] Persist weighted contribution
- [x] Persist direction: `positive`, `negative`, `neutral`

### `daily_reason_codes`
- [x] Store structured warning / explanation codes
- [x] Initial codes:
  - [x] `sleep_debt_high`
  - [x] `hrv_below_baseline`
  - [x] `resting_hr_elevated`
  - [x] `long_run_protected`
  - [x] `lower_body_density_high`
  - [x] `knee_pain_flag`
  - [x] `data_coverage_low`

---

## 3. Build the data trust layer

### Daily source coverage
- [x] Garmin present
- [x] Apple Health present
- [x] Strava present
- [x] Scale present
- [x] Manual input present

### Field-level provenance
- [x] Sleep source
- [x] HRV source
- [x] Resting HR source
- [x] Weight source
- [x] Workout source

### Data quality rules
- [x] Detect duplicate workout imports across sources
- [x] Define deduplication strategy for overlapping sessions
- [x] Mark partial days explicitly
- [x] Add stale-data detection
  - [x] no fresh recovery data
  - [x] no fresh weight data
  - [x] no fresh workout sync

### Trust output
- [x] Compute `decision_confidence_score`
- [x] Reduce recommendation strength when confidence is low

---

## 4. Formalize each score

### Recovery score
#### Inputs
- [x] HRV vs 28-day baseline
- [x] Resting HR vs baseline
- [x] Sleep duration
- [x] Sleep debt
- [x] Recent load
- [x] Soreness
- [x] Illness
- [x] Device readiness if available

#### Logic
- [x] Finalize weights
- [x] Finalize caps
- [x] Add hard overrides:
  - [x] illness reduces ceiling
  - [x] severe sleep debt reduces ceiling
  - [x] high soreness reduces ceiling

### Race readiness score
#### Inputs
- [x] Weekly km
- [x] Rolling 4-week km
- [x] Longest run
- [x] Easy pace at fixed HR
- [x] Quality session completion
- [x] Plan adherence
- [x] Projected HM time
- [x] Trend direction

#### Logic
- [x] Define projection fallback when data is insufficient
- [x] Define when race-readiness is withheld due to missing running data

### General health score
#### Inputs
- [x] Sleep consistency
- [x] Weight trend
- [x] Resting HR trend
- [x] HRV stability
- [x] Pain-free days
- [x] Mood trend
- [x] Stress trend
- [x] Steps consistency

#### Logic
- [x] Define safe weight trend band
- [x] Add penalty rules for aggressive weight loss
- [x] Add penalty rules for worsening pain

### Load balance score
#### Inputs
- [x] Hard-day density
- [x] Lower-body CrossFit density
- [x] Session spacing
- [x] Long-run protection
- [x] Interference risk

#### Logic
- [x] Define what counts as a hard day
- [x] Define lower-body dominant CrossFit tags
- [x] Define protected windows around quality runs and long runs

---

## 5. Build the recommendation rules engine

### Core engine
- [x] Create a pure deterministic recommendation service
- [x] Input = score bundle + warnings + plan context
- [x] Output = recommendation mode + action + reason codes

### Priority order
- [x] Illness override
- [x] Injury / pain override
- [x] Severe recovery suppression
- [x] Overload / load-balance suppression
- [x] Normal plan execution

### Intensity modifiers
- [x] Shorten session
- [x] Swap quality for easy
- [x] Remove second session
- [x] Replace with mobility

### Test cases
- [x] Good race-readiness but terrible recovery
- [x] Good recovery but knee pain
- [x] Strong running metrics but poor load balance
- [x] Partial missing data

---

## 6. Build a single-date debug endpoint

### Backend
- [x] Add `/api/debug/day?date=YYYY-MM-DD`

### Response should include
- [x] Raw normalized daily facts
- [x] Relevant workouts in lookback window
- [x] Baseline comparisons
- [x] Score components
- [x] Reason codes
- [x] Recommendation result
- [x] Confidence result

### Frontend
- [x] Add a simple admin/debug page
- [x] Use it as the main threshold-tuning tool

---

## 7. Make the UI uncertainty-aware

### Today page and cards
- [x] Add data confidence badge
- [x] Add partial-data state to major cards
- [x] Show score drivers
- [x] Show warnings above recommendation

### UX distinctions
- [x] Distinguish low score + strong confidence
- [x] Distinguish low score + weak confidence

### Inspectability
- [x] Add expandable component breakdowns on score cards
- [x] Add a “why today?” drawer using structured reasons, not LLM-only text

---

## 8. Improve workout tagging for Strength

### CrossFit parser
- [x] Build lightweight parser for Strava notes / manual logs

### Tag vocabulary
- [x] squat
- [x] hinge
- [x] lunge
- [x] jump
- [x] olympic_lift
- [x] upper_push
- [x] upper_pull
- [x] engine
- [x] metcon

### Derived outputs
- [x] Infer lower-body stress score per session
- [x] Infer interference risk for next 24–48h
- [x] Store parsed tags
- [x] Store parsing confidence
- [x] Add manual override for bad parses

---

## 9. Add feedback capture

### Daily recommendation feedback
- [x] `accurate`
- [x] `too_hard`
- [x] `too_easy`
- [x] `pain_increased`
- [x] `ignored`

### Extra note
- [x] Optional free-text note

### Persist feedback with
- [x] date
- [x] recommendation version
- [x] actual completed session
- [x] subjective next-day outcome

### Review tooling
- [x] Add simple feedback review page for threshold tuning

---

## 10. Test and validate

### Unit tests
- [x] Test every score calculation
- [x] Test every recommendation override

### Fixtures
- [x] Ideal training day
- [x] Overload day
- [x] Poor sleep day
- [x] Injury-watch day
- [x] Incomplete-data day

### Regression
- [x] Add snapshot tests for score outputs
- [x] Ensure explanations never require missing fields
- [x] Validate one year of historical data can recompute prior daily decisions consistently, as required by the bedrock spec. :contentReference[oaicite:1]{index=1}

---

## 11. Only after that: Phase 2.5 LLM layer

### Structured input only
- [x] Final scores
- [x] Component summaries
- [x] Reason codes
- [x] Recommendation mode
- [x] Plan context
- [x] Confidence level

### Outputs
- [x] One daily explanation paragraph
- [x] One weekly review summary

### Trust controls
- [x] Log prompt context
- [x] Log model output
- [x] Prevent unsupported claims by grounding on reason codes

---

## Definition of done for Phase 2

- [x] Any score on screen can be traced to stored components
- [x] Any recommendation can be explained with explicit rules
- [x] Missing or conflicting data lowers confidence visibly
- [x] The app can debug one day end-to-end
- [x] Feedback on recommendation quality is stored
- [x] The system answers “what should I do today and why?” without relying on the LLM for the decision itself, matching the bedrock design. :contentReference[oaicite:2]{index=2}

---

## Recommended execution order

1. [x] Freeze decision contract
2. [x] Persist score breakdowns
3. [x] Build data trust layer
4. [x] Finalize score formulas
5. [x] Build deterministic recommendation engine
6. [x] Add debug endpoint/page
7. [x] Make UI uncertainty-aware
8. [x] Improve workout tagging
9. [x] Add feedback capture
10. [x] Test and validate
11. [x] Add LLM explanations last