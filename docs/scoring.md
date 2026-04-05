# Scoring

## Overview
The scoring system converts normalized health and training data into four deterministic headline scores:
- Recovery score
- Race-readiness score
- General-health score
- Load-balance score

Each score must be:
- deterministic
- interpretable
- decomposable
- versioned
- testable

The LLM does not generate scores. It only explains them.

---

## General scoring framework
Each score should be represented on a 0-100 scale.

Recommended interpretation:
- 85-100: strong / green
- 70-84: stable / light green
- 55-69: caution / yellow
- 40-54: high caution / orange
- below 40: poor / red

Suggested implementation pattern:
1. Compute normalized subcomponent values
2. Weight them deterministically
3. Apply bounded penalties for risk flags
4. Clamp final score to 0-100
5. Persist subcomponents for explainability

---

## 1. Recovery score

### Purpose
Estimate whether the user is ready to absorb training today.

### Inputs
- HRV versus baseline
- resting HR deviation from baseline
- sleep duration
- sleep debt
- recent training load
- soreness
- illness flag
- training readiness if available
- subjective fatigue

### Recommended subcomponents
- `hrv_component`
- `resting_hr_component`
- `sleep_component`
- `load_component`
- `soreness_component`
- `illness_component`
- `subjective_fatigue_component`
- `device_readiness_component`

### Suggested weights
- HRV: 0.20
- resting HR: 0.15
- sleep: 0.20
- recent load: 0.15
- soreness: 0.10
- illness: 0.10
- subjective fatigue: 0.05
- training readiness: 0.05

### Example heuristics
- HRV significantly below 28-day baseline reduces readiness
- resting HR above baseline reduces readiness
- sleep debt accumulates a penalty
- high 3-day or 7-day load reduces readiness if not matched by stable recovery
- high soreness or illness heavily suppresses readiness

### Output interpretation
- High recovery score supports normal or hard training if no injury warning is active
- Mid recovery score supports normal training with caution or reduced intensity
- Low recovery score supports recovery-focused work or full rest

---

## 2. Race-readiness score

### Purpose
Estimate progression toward the half-marathon target.

### Inputs
- weekly running distance
- rolling distance consistency
- long-run completion and progression
- easy-run efficiency at fixed HR band
- quality-session completion
- projected HM time
- plan adherence
- trend direction

### Recommended subcomponents
- `weekly_volume_component`
- `long_run_component`
- `easy_efficiency_component`
- `quality_completion_component`
- `projection_component`
- `plan_adherence_component`
- `trend_component`

### Suggested weights
- weekly volume: 0.20
- long run: 0.20
- easy-run efficiency: 0.20
- quality completion: 0.10
- projected time: 0.15
- plan adherence: 0.10
- trend direction: 0.05

### Example heuristics
- weekly km close to plan target increases readiness
- missing long runs reduces readiness strongly
- improved pace at a fixed easy HR increases readiness
- better projected HM time increases readiness
- repeated plan non-compliance lowers readiness even if isolated workouts were strong

### Output interpretation
- High score indicates the HM build is progressing well
- Mid score indicates progress but with gaps or uncertainty
- Low score indicates stagnation, regression, or insufficient build consistency

---

## 3. General-health score

### Purpose
Track long-term health rather than performance alone.

### Inputs
- sleep consistency
- body-weight trend
- resting HR trend
- HRV stability
- steps consistency
- pain trend
- mood trend
- stress trend
- illness flags

### Recommended subcomponents
- `sleep_consistency_component`
- `weight_trend_component`
- `resting_hr_trend_component`
- `hrv_stability_component`
- `steps_component`
- `pain_component`
- `mood_component`
- `stress_component`

### Suggested weights
- sleep consistency: 0.20
- weight trend: 0.15
- resting HR trend: 0.10
- HRV stability: 0.10
- steps consistency: 0.10
- pain: 0.15
- mood: 0.10
- stress: 0.10

### Example heuristics
- stable sleep and low volatility improve score
- aggressive body-weight loss can reduce score even if performance improves
- recurring knee pain suppresses score materially
- chronic stress or declining mood reduces score
- persistent resting HR elevation over baseline may indicate health drift

### Output interpretation
- High score suggests the broader system is healthy and sustainable
- Mid score suggests mixed signals or manageable drift
- Low score suggests hidden deterioration or unstable health patterns

---

## 4. Load-balance score

### Purpose
Measure whether running and CrossFit are balanced coherently.

### Inputs
- hard-day density
- lower-body CrossFit density
- spacing between demanding sessions
- long-run protection
- intensity distribution
- interference score

### Recommended subcomponents
- `hard_day_density_component`
- `lower_body_density_component`
- `session_spacing_component`
- `long_run_protection_component`
- `run_distribution_component`
- `interference_component`

### Suggested weights
- hard-day density: 0.20
- lower-body density: 0.20
- session spacing: 0.15
- long-run protection: 0.20
- intensity distribution: 0.10
- interference: 0.15

### Example heuristics
- too many hard days in 7 days lowers score
- lower-body-dominant CrossFit close to key run sessions lowers score
- insufficient spacing between quality run and hard CrossFit lowers score
- preserving long-run freshness increases score
- excessive mid-intensity stacking lowers score

### Output interpretation
- High score suggests running and CrossFit are reinforcing rather than colliding
- Mid score suggests moderate interference risk
- Low score suggests overload or poor scheduling logic

---

## Warning and override logic
Some conditions should trigger warnings or recommendation overrides regardless of total score.

### Suggested hard warnings
- `knee_pain_warning`
- `illness_warning`
- `sleep_debt_warning`
- `hrv_suppression_warning`
- `resting_hr_spike_warning`
- `aggressive_weight_loss_warning`
- `overload_warning`

### Example override rules
- If knee pain exceeds threshold, recommendation cannot be `full_go`
- If illness flag is true, recommendation is at most `recovery_focused`
- If HRV is severely suppressed and resting HR elevated, suppress hard training
- If recent lower-body load and pain both elevated, prefer low-impact recovery or rest

---

## Recommendation mode mapping
The recommendation engine should use the four scores plus warning logic.

### Example rule pattern
- `full_go`: recovery high, load-balance stable, no warnings
- `train_as_planned`: recovery acceptable, race-readiness stable, no major warnings
- `reduce_intensity`: moderate recovery or moderate overload risk
- `recovery_focused`: low recovery, health caution, or accumulating stress
- `full_rest`: very low recovery or illness
- `injury_watch`: pain-triggered suppression

This should remain rule-based in V1.

---

## Explainability requirements
Every score output should expose:
- final score
- subcomponent values
- top positive drivers
- top negative drivers
- any triggered warnings
- scoring engine version

The LLM layer can then explain:
- why a day is green, yellow, or red
- what changed versus recent baseline
- what the user should do today
- what variable most influenced the recommendation

---

## Versioning
Persist score and recommendation versions explicitly.

Suggested fields:
- `score_engine_version`
- `recommendation_engine_version`
- `llm_prompt_version`

This allows threshold tuning without losing reproducibility.

---

## Testing requirements
Each score must have:
- unit tests for expected inputs and outputs
- edge-case tests for missing data
- warning trigger tests
- recommendation override tests
- snapshot tests for structured explanation context if desired

---

## First implementation recommendation
For the first working version:
1. Implement simple weighted subcomponent formulas
2. Add hard warning overrides
3. Persist all subcomponents
4. Keep all thresholds in config
5. Tune only after observing real user data
