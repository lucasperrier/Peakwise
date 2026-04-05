# Data Model

## Overview
The app should normalize all incoming information into a common warehouse with two primary grains:
- daily records
- workout-session records

This allows the scoring engine and recommendation layer to operate independently of source-specific schemas.

---

## Design principles
- Preserve raw source lineage
- Store coverage flags explicitly
- Prefer append-only raw ingestion plus curated transformations
- Keep deterministic feature generation separate from raw storage
- Make warehouse design friendly to both analytics and application queries

---

## Recommended schema layers

### 1. Raw layer
Purpose: preserve original source payloads and allow debugging.

Suggested tables:
- `raw_garmin_events`
- `raw_apple_health_events`
- `raw_strava_events`
- `raw_scale_events`
- `raw_manual_inputs`

Common fields:
- `id`
- `source`
- `source_record_id`
- `ingested_at`
- `event_timestamp`
- `payload_json`
- `user_timezone`
- `source_file_name` or `sync_job_id`
- `quality_flag`

### 2. Curated warehouse layer
Purpose: source-agnostic business objects used by the app.

Core tables:
- `daily_fact`
- `workout_fact`
- `baseline_snapshot`
- `score_snapshot`
- `recommendation_snapshot`
- `manual_daily_input`
- `daily_source_coverage`

### 3. Feature layer
Purpose: precomputed derived values for scoring and UI.

Suggested tables or materialized views:
- `daily_features`
- `workout_features`
- `weekly_training_summary`
- `historical_best_blocks`

---

## Core table definitions

## `daily_fact`
One row per calendar date.

### Primary key
- `date`

### Core fields
- `date`
- `body_weight_kg`
- `body_fat_pct`
- `resting_hr_bpm`
- `hrv_ms`
- `sleep_duration_min`
- `sleep_score`
- `steps`
- `active_energy_kcal`
- `training_readiness`
- `stress_score`
- `body_battery`

### Subjective fields
- `soreness_score`
- `left_knee_pain_score`
- `motivation_score`
- `mood_score`
- `illness_flag`
- `perceived_fatigue_score`

### Coverage / quality fields
- `has_garmin_data`
- `has_apple_health_data`
- `has_strava_data`
- `has_scale_data`
- `has_manual_input`
- `data_quality_flag`
- `notes`

### Audit fields
- `created_at`
- `updated_at`

---

## `workout_fact`
One row per workout session.

### Primary key
- `workout_id`

### Core fields
- `workout_id`
- `source`
- `source_workout_id`
- `start_time`
- `end_time`
- `session_date`
- `session_type`
- `duration_min`
- `avg_hr_bpm`
- `max_hr_bpm`
- `training_load`
- `distance_km`
- `avg_pace_sec_per_km`
- `elevation_gain_m`
- `calories_kcal`

### Run-specific fields
- `route_type`
- `cadence_spm`
- `splits_json`
- `time_in_zones_json`
- `weather_json`

### CrossFit-specific parsed fields
- `is_strength`
- `is_engine`
- `is_metcon`
- `has_squats`
- `has_hinges`
- `has_jumps`
- `has_oly_lifts`
- `is_upper_body_dominant`
- `is_lower_body_dominant`
- `session_rpe`
- `local_muscular_stress_tag`
- `raw_notes`

### Derived scheduling / interference fields
- `lower_body_load_score`
- `interference_contribution`
- `next_day_soreness_linked`
- `training_phase_label`

### Audit fields
- `created_at`
- `updated_at`

---

## `manual_daily_input`
User-entered context that wearables do not capture well.

### Fields
- `date`
- `left_knee_pain_score`
- `global_pain_score`
- `soreness_score`
- `mood_score`
- `motivation_score`
- `stress_score_subjective`
- `illness_flag`
- `free_text_note`
- `created_at`
- `updated_at`

---

## `daily_source_coverage`
Tracks which sources contributed to a day and whether the day is incomplete.

### Fields
- `date`
- `garmin_coverage`
- `apple_health_coverage`
- `strava_coverage`
- `scale_coverage`
- `manual_input_coverage`
- `is_partial_day`
- `coverage_note`

---

## `daily_features`
Precomputed features used by scoring and UI.

### Recovery-related features
- `hrv_7d_avg`
- `hrv_vs_28d_pct`
- `resting_hr_7d_avg`
- `resting_hr_vs_28d_delta`
- `sleep_7d_avg`
- `sleep_debt_min`
- `recent_load_3d`
- `recent_load_7d`
- `recovery_trend`

### Running-related features
- `weekly_km`
- `rolling_4w_km`
- `longest_run_last_7d_km`
- `easy_pace_fixed_hr_sec_per_km`
- `quality_sessions_last_14d`
- `projected_hm_time_sec`
- `plan_adherence_pct`

### Health-related features
- `body_weight_7d_avg`
- `body_weight_28d_slope`
- `sleep_consistency_score`
- `pain_free_days_last_14d`
- `mood_trend`
- `stress_trend`
- `steps_consistency_score`

### Hybrid-balance features
- `hard_day_count_7d`
- `run_intensity_distribution_json`
- `lower_body_crossfit_density_7d`
- `long_run_protection_score`
- `interference_risk_score`

---

## `baseline_snapshot`
Stores baseline windows used for comparison.

### Fields
- `date`
- `window_type`  
  Examples: `7d`, `28d`, `90d`, `seasonal`, `best_4w_run_block`
- `metric_name`
- `baseline_value`
- `sample_size`
- `baseline_start_date`
- `baseline_end_date`
- `computed_at`

---

## `historical_best_blocks`
Stores historically best periods to compare against current training.

### Fields
- `block_id`
- `block_type`
- `start_date`
- `end_date`
- `label`
- `metric_summary_json`
- `notes`

Examples:
- best 4-week running consistency block
- best recovery block
- best weight-to-performance window

---

## `score_snapshot`
Daily persisted score outputs for inspection and versioning.

### Fields
- `date`
- `score_engine_version`
- `recovery_score`
- `race_readiness_score`
- `general_health_score`
- `load_balance_score`
- `subcomponents_json`
- `warnings_json`
- `computed_at`

---

## `recommendation_snapshot`
Daily recommendation result.

### Fields
- `date`
- `recommendation_engine_version`
- `mode`
- `recommended_action`
- `intensity_modifier`
- `duration_modifier`
- `reason_codes_json`
- `next_best_alternative`
- `risk_flags_json`
- `computed_at`

---

## Suggested enums

### `session_type`
- `run_easy`
- `run_quality`
- `run_long`
- `crossfit`
- `strength`
- `walk`
- `mobility`
- `bike`
- `other`

### `recommendation_mode`
- `full_go`
- `train_as_planned`
- `reduce_intensity`
- `recovery_focused`
- `full_rest`
- `injury_watch`

---

## Minimal API-facing payloads
The UI should generally consume these aggregates:
- `TodayPayload`
- `RunningOverviewPayload`
- `HealthOverviewPayload`
- `StrengthOverviewPayload`
- `WeeklyReviewPayload`

These payloads should be assembled from warehouse and feature tables, not directly from raw source tables.

---

## Data quality rules
- Never silently overwrite raw data
- Preserve source record identifiers
- Mark missing or partial days explicitly
- Make source availability visible to the scoring engine
- Do not impute important health metrics without explicit flags
- Log parsing confidence for CrossFit workout notes

---

## First implementation recommendation
Implement these tables first:
1. `daily_fact`
2. `workout_fact`
3. `manual_daily_input`
4. `daily_features`
5. `score_snapshot`
6. `recommendation_snapshot`

That is enough to power the first functional Today screen.
