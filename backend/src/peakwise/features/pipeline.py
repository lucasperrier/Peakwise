"""Feature engineering pipeline.

Orchestrates the computation of all daily features from the curated
warehouse layer (daily_fact + workout_fact) and persists the results
to the daily_features table.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.features.daily import (
    compute_body_weight_28d_slope,
    compute_body_weight_7d_avg,
    compute_hrv_7d_avg,
    compute_hrv_vs_28d_pct,
    compute_mood_trend,
    compute_pain_free_days_last_14d,
    compute_recent_load,
    compute_recovery_trend,
    compute_resting_hr_7d_avg,
    compute_resting_hr_vs_28d_delta,
    compute_sleep_7d_avg,
    compute_sleep_consistency_score,
    compute_sleep_debt_min,
    compute_steps_consistency_score,
    compute_stress_trend,
)
from peakwise.features.running import (
    compute_easy_pace_fixed_hr,
    compute_longest_run_last_7d_km,
    compute_plan_adherence_pct,
    compute_projected_hm_time_sec,
    compute_quality_sessions_last_14d,
    compute_rolling_4w_km,
    compute_weekly_km,
)
from peakwise.features.hybrid import (
    compute_hard_day_count_7d,
    compute_interference_risk_score,
    compute_long_run_protection_score,
    compute_lower_body_crossfit_density_7d,
    compute_run_intensity_distribution,
)
from peakwise.models import DailyFact, DailyFeatures, WorkoutFact

logger = logging.getLogger("peakwise.features")


@dataclass
class FeaturePipelineResult:
    dates_computed: int = 0
    dates_skipped: int = 0
    errors: list[str] | None = None


def compute_features_for_date(
    target_date: date,
    daily_facts: dict[date, DailyFact],
    workouts: list[WorkoutFact],
) -> DailyFeatures:
    """Compute all features for a single date and return a DailyFeatures model."""
    features = DailyFeatures(date=target_date)

    # --- Recovery features ---
    features.hrv_7d_avg = compute_hrv_7d_avg(daily_facts, target_date)
    features.hrv_vs_28d_pct = compute_hrv_vs_28d_pct(daily_facts, target_date)
    features.resting_hr_7d_avg = compute_resting_hr_7d_avg(daily_facts, target_date)
    features.resting_hr_vs_28d_delta = compute_resting_hr_vs_28d_delta(
        daily_facts, target_date
    )
    features.sleep_7d_avg = compute_sleep_7d_avg(daily_facts, target_date)
    features.sleep_debt_min = compute_sleep_debt_min(daily_facts, target_date)
    features.recent_load_3d = compute_recent_load(workouts, target_date, 3)
    features.recent_load_7d = compute_recent_load(workouts, target_date, 7)
    features.recovery_trend = compute_recovery_trend(daily_facts, target_date)

    # --- Running features ---
    features.weekly_km = compute_weekly_km(workouts, target_date)
    features.rolling_4w_km = compute_rolling_4w_km(workouts, target_date)
    features.longest_run_last_7d_km = compute_longest_run_last_7d_km(
        workouts, target_date
    )
    features.easy_pace_fixed_hr_sec_per_km = compute_easy_pace_fixed_hr(
        workouts, target_date
    )
    features.quality_sessions_last_14d = compute_quality_sessions_last_14d(
        workouts, target_date
    )
    features.projected_hm_time_sec = compute_projected_hm_time_sec(
        workouts, target_date
    )
    features.plan_adherence_pct = compute_plan_adherence_pct(workouts, target_date)

    # --- Health features ---
    features.body_weight_7d_avg = compute_body_weight_7d_avg(daily_facts, target_date)
    features.body_weight_28d_slope = compute_body_weight_28d_slope(
        daily_facts, target_date
    )
    features.sleep_consistency_score = compute_sleep_consistency_score(
        daily_facts, target_date
    )
    features.pain_free_days_last_14d = compute_pain_free_days_last_14d(
        daily_facts, target_date
    )
    features.mood_trend = compute_mood_trend(daily_facts, target_date)
    features.stress_trend = compute_stress_trend(daily_facts, target_date)
    features.steps_consistency_score = compute_steps_consistency_score(
        daily_facts, target_date
    )

    # --- Hybrid / load-balance features ---
    features.hard_day_count_7d = compute_hard_day_count_7d(workouts, target_date)
    features.run_intensity_distribution_json = compute_run_intensity_distribution(
        workouts, target_date
    )
    features.lower_body_crossfit_density_7d = compute_lower_body_crossfit_density_7d(
        workouts, target_date
    )
    features.long_run_protection_score = compute_long_run_protection_score(
        workouts, target_date
    )
    features.interference_risk_score = compute_interference_risk_score(
        workouts, target_date
    )

    return features


def run_feature_pipeline(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> FeaturePipelineResult:
    """Compute and persist features for a date range.

    If *start_date* / *end_date* are omitted the pipeline processes all dates
    present in daily_fact.  We load a buffer of 90 days before *start_date* so
    that rolling windows have enough data.
    """
    result = FeaturePipelineResult(errors=[])

    # Determine date range from daily_fact
    all_dates: list[date] = [
        row[0]
        for row in session.execute(
            select(DailyFact.date).order_by(DailyFact.date)
        ).all()
    ]
    if not all_dates:
        return result

    effective_start = start_date or all_dates[0]
    effective_end = end_date or all_dates[-1]

    # Load data with a 90-day lookback buffer
    buffer_start = effective_start - timedelta(days=90)
    daily_rows: list[DailyFact] = list(
        session.scalars(
            select(DailyFact).where(DailyFact.date >= buffer_start)
        ).all()
    )
    daily_facts: dict[date, DailyFact] = {f.date: f for f in daily_rows}

    workout_rows: list[WorkoutFact] = list(
        session.scalars(
            select(WorkoutFact).where(WorkoutFact.session_date >= buffer_start)
        ).all()
    )

    # Compute features for each target date
    current = effective_start
    while current <= effective_end:
        if current not in daily_facts:
            result.dates_skipped += 1
            current += timedelta(days=1)
            continue
        try:
            features = compute_features_for_date(current, daily_facts, workout_rows)
            session.merge(features)
            result.dates_computed += 1
        except Exception as exc:
            msg = f"Error computing features for {current}: {exc}"
            logger.error(msg)
            result.errors.append(msg)  # type: ignore[union-attr]
        current += timedelta(days=1)

    session.flush()
    logger.info(
        "Feature pipeline complete: %d dates computed, %d skipped, %d errors",
        result.dates_computed,
        result.dates_skipped,
        len(result.errors or []),
    )
    return result
