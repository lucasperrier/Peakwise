"""Daily / recovery feature computations.

Computes rolling averages, baseline deviations, sleep debt, and
subjective-metric trends from the curated daily_fact table.
"""

from __future__ import annotations

from datetime import date, timedelta

from peakwise.config import TARGET_SLEEP_MIN
from peakwise.features.helpers import (
    consistency_score,
    linear_slope,
    rolling_avg,
    rolling_sum,
)
from peakwise.models import DailyFact, WorkoutFact


def compute_hrv_7d_avg(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    values = [
        daily_facts[target_date - timedelta(days=i)].hrv_ms
        for i in range(6, -1, -1)
        if (target_date - timedelta(days=i)) in daily_facts
    ]
    return rolling_avg(values, 7)


def compute_hrv_vs_28d_pct(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    hrv_7d = compute_hrv_7d_avg(daily_facts, target_date)
    values_28d = [
        daily_facts[target_date - timedelta(days=i)].hrv_ms
        for i in range(27, -1, -1)
        if (target_date - timedelta(days=i)) in daily_facts
    ]
    hrv_28d = rolling_avg(values_28d, 28)
    if hrv_7d is None or hrv_28d is None or hrv_28d == 0:
        return None
    return (hrv_7d - hrv_28d) / hrv_28d * 100.0


def compute_resting_hr_7d_avg(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    values = [
        float(daily_facts[target_date - timedelta(days=i)].resting_hr_bpm)
        for i in range(6, -1, -1)
        if (target_date - timedelta(days=i)) in daily_facts
        and daily_facts[target_date - timedelta(days=i)].resting_hr_bpm is not None
    ]
    return rolling_avg(values, 7)


def compute_resting_hr_vs_28d_delta(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    hr_7d = compute_resting_hr_7d_avg(daily_facts, target_date)
    values_28d = [
        float(daily_facts[target_date - timedelta(days=i)].resting_hr_bpm)
        for i in range(27, -1, -1)
        if (target_date - timedelta(days=i)) in daily_facts
        and daily_facts[target_date - timedelta(days=i)].resting_hr_bpm is not None
    ]
    hr_28d = rolling_avg(values_28d, 28)
    if hr_7d is None or hr_28d is None:
        return None
    return hr_7d - hr_28d


def compute_sleep_7d_avg(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    values = [
        daily_facts[target_date - timedelta(days=i)].sleep_duration_min
        for i in range(6, -1, -1)
        if (target_date - timedelta(days=i)) in daily_facts
    ]
    return rolling_avg(values, 7)


def compute_sleep_debt_min(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float:
    total = rolling_sum(
        [
            daily_facts[target_date - timedelta(days=i)].sleep_duration_min
            for i in range(6, -1, -1)
            if (target_date - timedelta(days=i)) in daily_facts
        ],
        7,
    )
    target = TARGET_SLEEP_MIN * 7
    return max(0.0, target - total)


def compute_recent_load(
    workouts: list[WorkoutFact],
    target_date: date,
    days: int,
) -> float:
    start = target_date - timedelta(days=days - 1)
    return sum(
        w.training_load or 0.0
        for w in workouts
        if not w.is_duplicate and start <= w.session_date <= target_date
    )


def compute_recovery_trend(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    """Slope of training_readiness over the last 14 days as a proxy for
    recovery trend (positive = improving)."""
    values = [
        daily_facts[target_date - timedelta(days=i)].training_readiness
        if (target_date - timedelta(days=i)) in daily_facts
        else None
        for i in range(13, -1, -1)
    ]
    return linear_slope(values)


# --- Health features computed from daily_fact ---


def compute_body_weight_7d_avg(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    values = [
        daily_facts[target_date - timedelta(days=i)].body_weight_kg
        for i in range(6, -1, -1)
        if (target_date - timedelta(days=i)) in daily_facts
    ]
    return rolling_avg(values, 7)


def compute_body_weight_28d_slope(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    values = [
        daily_facts[target_date - timedelta(days=i)].body_weight_kg
        if (target_date - timedelta(days=i)) in daily_facts
        else None
        for i in range(27, -1, -1)
    ]
    return linear_slope(values)


def compute_sleep_consistency_score(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    values = [
        daily_facts[target_date - timedelta(days=i)].sleep_duration_min
        if (target_date - timedelta(days=i)) in daily_facts
        else None
        for i in range(13, -1, -1)
    ]
    return consistency_score(values, 14)


def compute_pain_free_days_last_14d(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> int:
    count = 0
    for i in range(14):
        d = target_date - timedelta(days=i)
        if d in daily_facts:
            pain = daily_facts[d].left_knee_pain_score
            if pain is None or pain <= 1.0:
                count += 1
        else:
            # Missing day: no data, not counted as pain but not counted as pain-free
            pass
    return count


def compute_mood_trend(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    values = [
        daily_facts[target_date - timedelta(days=i)].mood_score
        if (target_date - timedelta(days=i)) in daily_facts
        else None
        for i in range(13, -1, -1)
    ]
    return linear_slope(values)


def compute_stress_trend(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    values = [
        daily_facts[target_date - timedelta(days=i)].stress_score
        if (target_date - timedelta(days=i)) in daily_facts
        else None
        for i in range(13, -1, -1)
    ]
    return linear_slope(values)


def compute_steps_consistency_score(
    daily_facts: dict[date, DailyFact],
    target_date: date,
) -> float | None:
    values = [
        float(daily_facts[target_date - timedelta(days=i)].steps)
        if (target_date - timedelta(days=i)) in daily_facts
        and daily_facts[target_date - timedelta(days=i)].steps is not None
        else None
        for i in range(13, -1, -1)
    ]
    return consistency_score(values, 14)
