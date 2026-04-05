"""Hybrid / load-balance feature computations.

Computes hard-day density, CrossFit lower-body density, session spacing,
interference risk, and long-run protection scores.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from peakwise.config import (
    HARD_SESSION_TYPES,
    INTERFERENCE_HARD_DAY_WEIGHT,
    INTERFERENCE_LOWER_BODY_WEIGHT,
    INTERFERENCE_SPACING_PENALTY,
    LONG_RUN_PROTECTION_GAP_DAYS,
    LOWER_BODY_LOAD_THRESHOLD,
)
from peakwise.models import WorkoutFact


def _non_dup_workouts(
    workouts: list[WorkoutFact],
    start: date,
    end: date,
) -> list[WorkoutFact]:
    return [
        w
        for w in workouts
        if not w.is_duplicate and start <= w.session_date <= end
    ]


def compute_hard_day_count_7d(
    workouts: list[WorkoutFact],
    target_date: date,
) -> int:
    start = target_date - timedelta(days=6)
    relevant = _non_dup_workouts(workouts, start, target_date)
    hard_dates = {w.session_date for w in relevant if w.session_type in HARD_SESSION_TYPES}
    return len(hard_dates)


def compute_run_intensity_distribution(
    workouts: list[WorkoutFact],
    target_date: date,
) -> dict[str, int]:
    """Count of easy / quality / long runs in the last 7 days."""
    start = target_date - timedelta(days=6)
    relevant = _non_dup_workouts(workouts, start, target_date)
    dist: dict[str, int] = {"easy": 0, "quality": 0, "long": 0}
    for w in relevant:
        if w.session_type == "run_easy":
            dist["easy"] += 1
        elif w.session_type == "run_quality":
            dist["quality"] += 1
        elif w.session_type == "run_long":
            dist["long"] += 1
    return dist


def compute_lower_body_crossfit_density_7d(
    workouts: list[WorkoutFact],
    target_date: date,
) -> float:
    """Fraction of days in the last 7 with a lower-body-heavy CrossFit session."""
    start = target_date - timedelta(days=6)
    relevant = _non_dup_workouts(workouts, start, target_date)
    cf_sessions = [w for w in relevant if w.session_type == "crossfit"]
    lower_body_dates: set[date] = set()
    for w in cf_sessions:
        is_lower = w.is_lower_body_dominant or (
            w.lower_body_load_score is not None
            and w.lower_body_load_score > LOWER_BODY_LOAD_THRESHOLD
        )
        if is_lower:
            lower_body_dates.add(w.session_date)
    return len(lower_body_dates) / 7.0


def compute_long_run_protection_score(
    workouts: list[WorkoutFact],
    target_date: date,
) -> float:
    """Score 0-100 indicating whether the most recent long run was adequately
    protected (preceded by enough rest/easy days)."""
    start = target_date - timedelta(days=13)
    relevant = _non_dup_workouts(workouts, start, target_date)
    long_runs = sorted(
        [w for w in relevant if w.session_type == "run_long"],
        key=lambda w: w.session_date,
        reverse=True,
    )
    if not long_runs:
        return 100.0  # no long run → no protection needed

    last_long = long_runs[0]
    # Check days before the long run for hard sessions
    for gap in range(1, LONG_RUN_PROTECTION_GAP_DAYS + 1):
        check_date = last_long.session_date - timedelta(days=gap)
        hard_before = [
            w
            for w in relevant
            if w.session_date == check_date and w.session_type in HARD_SESSION_TYPES
        ]
        if hard_before:
            # Penalty proportional to how close the hard session was
            return max(0.0, 100.0 - (LONG_RUN_PROTECTION_GAP_DAYS - gap + 1) * 40.0)
    return 100.0


def _count_back_to_back_hard_days(
    workouts: list[WorkoutFact],
    target_date: date,
) -> int:
    """Count pairs of consecutive days that both have hard sessions."""
    start = target_date - timedelta(days=6)
    relevant = _non_dup_workouts(workouts, start, target_date)
    hard_dates = sorted({w.session_date for w in relevant if w.session_type in HARD_SESSION_TYPES})
    pairs = 0
    for i in range(len(hard_dates) - 1):
        if (hard_dates[i + 1] - hard_dates[i]).days == 1:
            pairs += 1
    return pairs


def compute_interference_risk_score(
    workouts: list[WorkoutFact],
    target_date: date,
) -> float:
    """Composite interference risk (0-100, >70 = risky).

    Heuristic combining:
    - Hard-day count (too many = bad)
    - Lower-body CF density (too close to quality runs)
    - Back-to-back hard days (poor spacing)
    """
    hard_days = compute_hard_day_count_7d(workouts, target_date)
    lb_density = compute_lower_body_crossfit_density_7d(workouts, target_date)
    b2b = _count_back_to_back_hard_days(workouts, target_date)

    score = 0.0
    # Hard day component: each hard day above 3 adds risk
    score += max(0, hard_days - 3) * INTERFERENCE_HARD_DAY_WEIGHT
    # Lower-body density component
    score += lb_density * 100.0 * (INTERFERENCE_LOWER_BODY_WEIGHT / 100.0)
    # Spacing component: each back-to-back pair adds penalty
    score += b2b * INTERFERENCE_SPACING_PENALTY

    return min(100.0, max(0.0, score))


def compute_crossfit_tags(workout: WorkoutFact) -> dict[str, bool]:
    """Parse raw_notes into CrossFit movement tags.

    Returns a dict of boolean flags based on keyword matching in the notes.
    """
    notes = (workout.raw_notes or "").lower()
    keywords: dict[str, list[str]] = {
        "has_squats": ["squat", "front squat", "back squat", "goblet squat", "air squat",
                       "pistol", "wall ball"],
        "has_hinges": ["deadlift", "clean", "snatch", "swing", "rdl", "good morning",
                       "hip hinge"],
        "has_jumps": ["jump", "box jump", "burpee", "double under", "tuck jump"],
        "has_oly_lifts": ["clean", "snatch", "jerk", "clean and jerk", "c&j"],
        "is_upper_body_dominant": ["press", "push-up", "pull-up", "handstand", "dip",
                                   "ring", "muscle-up", "bench"],
        "is_lower_body_dominant": ["squat", "deadlift", "lunge", "wall ball", "pistol",
                                   "box jump", "thruster"],
    }
    result: dict[str, bool] = {}
    for tag, words in keywords.items():
        result[tag] = any(w in notes for w in words)
    return result
