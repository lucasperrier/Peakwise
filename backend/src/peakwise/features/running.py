"""Running-specific feature computations.

Computes weekly volume, long-run tracking, easy-run efficiency,
quality-session counts, projected HM time, and plan adherence.
"""

from __future__ import annotations

from datetime import date, timedelta

from peakwise.config import (
    EASY_HR_ZONE_HIGH,
    EASY_HR_ZONE_LOW,
    HM_DISTANCE_KM,
    PLAN_ADHERENCE_THRESHOLD,
    PLAN_ADHERENCE_WEEKS,
    RUN_SESSION_TYPES,
    TARGET_WEEKLY_KM,
)
from peakwise.features.helpers import rolling_avg
from peakwise.models import WorkoutFact


def _filter_runs(
    workouts: list[WorkoutFact],
    start: date,
    end: date,
) -> list[WorkoutFact]:
    """Return non-duplicate runs within [start, end]."""
    return [
        w
        for w in workouts
        if not w.is_duplicate
        and w.session_type in RUN_SESSION_TYPES
        and start <= w.session_date <= end
    ]


def compute_weekly_km(
    workouts: list[WorkoutFact],
    target_date: date,
) -> float:
    """Sum distance_km for all runs in the calendar week containing *target_date*
    (ISO week: Monday to Sunday)."""
    # Monday of the target date's week
    week_start = target_date - timedelta(days=target_date.weekday())
    runs = _filter_runs(workouts, week_start, target_date)
    return sum(r.distance_km or 0.0 for r in runs)


def compute_rolling_4w_km(
    workouts: list[WorkoutFact],
    target_date: date,
) -> float:
    start = target_date - timedelta(days=27)
    runs = _filter_runs(workouts, start, target_date)
    return sum(r.distance_km or 0.0 for r in runs)


def compute_longest_run_last_7d_km(
    workouts: list[WorkoutFact],
    target_date: date,
) -> float:
    start = target_date - timedelta(days=6)
    runs = _filter_runs(workouts, start, target_date)
    distances = [r.distance_km for r in runs if r.distance_km is not None]
    return max(distances) if distances else 0.0


def compute_easy_pace_fixed_hr(
    workouts: list[WorkoutFact],
    target_date: date,
) -> float | None:
    """Average pace (sec/km) for easy runs within the target HR zone over the
    last 28 days.  Returns ``None`` if no qualifying runs exist."""
    start = target_date - timedelta(days=27)
    runs = _filter_runs(workouts, start, target_date)
    paces: list[float] = []
    for r in runs:
        if (
            r.avg_hr_bpm is not None
            and EASY_HR_ZONE_LOW <= r.avg_hr_bpm <= EASY_HR_ZONE_HIGH
            and r.avg_pace_sec_per_km is not None
        ):
            paces.append(r.avg_pace_sec_per_km)
    return rolling_avg(paces, len(paces)) if paces else None


def compute_quality_sessions_last_14d(
    workouts: list[WorkoutFact],
    target_date: date,
) -> int:
    start = target_date - timedelta(days=13)
    return len([
        w
        for w in workouts
        if not w.is_duplicate
        and w.session_type in {"run_quality", "run_long"}
        and start <= w.session_date <= target_date
    ])


def compute_projected_hm_time_sec(
    workouts: list[WorkoutFact],
    target_date: date,
) -> float | None:
    """Estimate HM finish time using recent easy-pace efficiency as anchor.

    Uses a simplified Riegel formula: T_hm = T_easy × (21.0975 / D_easy)^1.06
    where D_easy / T_easy come from the most recent easy run in the HR zone.
    """
    start = target_date - timedelta(days=27)
    runs = _filter_runs(workouts, start, target_date)
    # Find most recent qualifying easy run
    qualifying = [
        r
        for r in runs
        if r.avg_hr_bpm is not None
        and EASY_HR_ZONE_LOW <= r.avg_hr_bpm <= EASY_HR_ZONE_HIGH
        and r.distance_km is not None
        and r.distance_km > 0
        and r.avg_pace_sec_per_km is not None
    ]
    if not qualifying:
        return None
    qualifying.sort(key=lambda r: r.session_date, reverse=True)
    best = qualifying[0]
    d_easy = best.distance_km  # type: ignore[assignment]
    t_easy_sec = best.avg_pace_sec_per_km * d_easy  # type: ignore[operator]
    return t_easy_sec * (HM_DISTANCE_KM / d_easy) ** 1.06


def compute_plan_adherence_pct(
    workouts: list[WorkoutFact],
    target_date: date,
) -> float | None:
    """Fraction of the last N weeks where actual weekly km ≥ threshold × target."""
    weeks_hit = 0
    for w in range(PLAN_ADHERENCE_WEEKS):
        week_end = target_date - timedelta(weeks=w)
        week_start = week_end - timedelta(days=week_end.weekday())
        runs = _filter_runs(workouts, week_start, week_end)
        weekly = sum(r.distance_km or 0.0 for r in runs)
        if weekly >= PLAN_ADHERENCE_THRESHOLD * TARGET_WEEKLY_KM:
            weeks_hit += 1
    return (weeks_hit / PLAN_ADHERENCE_WEEKS) * 100.0
