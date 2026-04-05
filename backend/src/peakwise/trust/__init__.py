"""Data trust layer.

Computes decision confidence based on source coverage, data freshness,
and field-level provenance. Reduces recommendation strength when
confidence is low.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.models import (
    DailyFact,
    DailyFieldProvenance,
    DailySourceCoverage,
    WorkoutFact,
)

logger = logging.getLogger("peakwise.trust")

# ---------------------------------------------------------------------------
# Source coverage check
# ---------------------------------------------------------------------------

_SOURCE_COVERAGE_FIELDS = [
    ("garmin_coverage", "has_garmin_data"),
    ("apple_health_coverage", "has_apple_health_data"),
    ("strava_coverage", "has_strava_data"),
    ("scale_coverage", "has_scale_data"),
    ("manual_input_coverage", "has_manual_input"),
]


def compute_source_coverage(
    daily_fact: DailyFact,
) -> dict[str, bool]:
    """Return a dict of which sources are present for the day."""
    return {
        "garmin": bool(daily_fact.has_garmin_data),
        "apple_health": bool(daily_fact.has_apple_health_data),
        "strava": bool(daily_fact.has_strava_data),
        "scale": bool(daily_fact.has_scale_data),
        "manual_input": bool(daily_fact.has_manual_input),
    }


# ---------------------------------------------------------------------------
# Field-level provenance
# ---------------------------------------------------------------------------

_FIELD_SOURCE_MAP: dict[str, list[tuple[str, str]]] = {
    "sleep": [("sleep_duration_min", "garmin"), ("sleep_score", "garmin")],
    "hrv": [("hrv_ms", "garmin")],
    "resting_hr": [("resting_hr_bpm", "garmin")],
    "weight": [("body_weight_kg", "scale")],
    "workout": [("has_strava_data", "strava"), ("has_garmin_data", "garmin")],
}


def compute_field_provenance(
    daily_fact: DailyFact,
) -> dict[str, str | None]:
    """Determine which source provided each key metric field."""
    provenance: dict[str, str | None] = {}

    # Sleep
    if daily_fact.sleep_duration_min is not None:
        provenance["sleep"] = "garmin" if daily_fact.has_garmin_data else "apple_health"
    else:
        provenance["sleep"] = None

    # HRV
    if daily_fact.hrv_ms is not None:
        provenance["hrv"] = "garmin" if daily_fact.has_garmin_data else "apple_health"
    else:
        provenance["hrv"] = None

    # Resting HR
    if daily_fact.resting_hr_bpm is not None:
        provenance["resting_hr"] = "garmin" if daily_fact.has_garmin_data else "apple_health"
    else:
        provenance["resting_hr"] = None

    # Weight
    if daily_fact.body_weight_kg is not None:
        provenance["weight"] = "scale"
    else:
        provenance["weight"] = None

    # Workout
    if daily_fact.has_strava_data or daily_fact.has_garmin_data:
        provenance["workout"] = "strava" if daily_fact.has_strava_data else "garmin"
    else:
        provenance["workout"] = None

    return provenance


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------

_FRESHNESS_THRESHOLDS: dict[str, int] = {
    "recovery": 2,   # no fresh recovery data (HRV, HR, sleep) within 2 days
    "weight": 7,     # no fresh weight data within 7 days
    "workout": 3,    # no fresh workout sync within 3 days
}


def detect_stale_data(
    target_date: date,
    session: Session,
) -> dict[str, int | None]:
    """Detect stale data fields.

    Returns a dict mapping field category to days since last fresh data.
    None means data is fresh (within threshold).
    """
    stale: dict[str, int | None] = {}

    # Recovery staleness: check for HRV within threshold
    for days_back in range(_FRESHNESS_THRESHOLDS["recovery"] + 1):
        d = target_date - timedelta(days=days_back)
        fact = session.get(DailyFact, d)
        if fact and fact.hrv_ms is not None:
            stale["recovery"] = None
            break
    else:
        stale["recovery"] = _FRESHNESS_THRESHOLDS["recovery"]

    # Weight staleness
    for days_back in range(_FRESHNESS_THRESHOLDS["weight"] + 1):
        d = target_date - timedelta(days=days_back)
        fact = session.get(DailyFact, d)
        if fact and fact.body_weight_kg is not None:
            stale["weight"] = None
            break
    else:
        stale["weight"] = _FRESHNESS_THRESHOLDS["weight"]

    # Workout staleness
    recent_workouts = session.scalars(
        select(WorkoutFact).where(
            WorkoutFact.session_date >= target_date - timedelta(days=_FRESHNESS_THRESHOLDS["workout"]),
            WorkoutFact.session_date <= target_date,
            WorkoutFact.is_duplicate.is_(False),
        )
    ).all()
    stale["workout"] = None if recent_workouts else _FRESHNESS_THRESHOLDS["workout"]

    return stale


# ---------------------------------------------------------------------------
# Decision confidence score
# ---------------------------------------------------------------------------


def compute_decision_confidence(
    daily_fact: DailyFact | None,
    target_date: date,
    session: Session,
) -> tuple[float, str]:
    """Compute a decision confidence score (0-100) and level.

    Returns (score, level) where level is one of:
    high, medium, low, insufficient.
    """
    if daily_fact is None:
        return 0.0, "insufficient"

    score = 0.0
    max_score = 0.0

    # Source coverage (up to 40 points)
    coverage = compute_source_coverage(daily_fact)
    source_weights = {
        "garmin": 15.0,
        "apple_health": 5.0,
        "strava": 5.0,
        "scale": 5.0,
        "manual_input": 10.0,
    }
    for source_name, weight in source_weights.items():
        max_score += weight
        if coverage.get(source_name):
            score += weight

    # Key metric availability (up to 40 points)
    metric_checks = [
        (daily_fact.hrv_ms is not None, 10.0),
        (daily_fact.resting_hr_bpm is not None, 5.0),
        (daily_fact.sleep_duration_min is not None, 10.0),
        (daily_fact.body_weight_kg is not None, 5.0),
        (daily_fact.soreness_score is not None, 5.0),
        (daily_fact.mood_score is not None, 5.0),
    ]
    for present, weight in metric_checks:
        max_score += weight
        if present:
            score += weight

    # Freshness penalty (up to 20 points)
    max_score += 20.0
    stale = detect_stale_data(target_date, session)
    freshness_score = 20.0
    for category, staleness_days in stale.items():
        if staleness_days is not None:
            freshness_score -= 7.0
    score += max(0.0, freshness_score)

    # Normalize to 0-100
    confidence = (score / max_score * 100.0) if max_score > 0 else 0.0
    confidence = max(0.0, min(100.0, confidence))

    # Map to level
    if confidence >= 75.0:
        level = "high"
    elif confidence >= 50.0:
        level = "medium"
    elif confidence >= 25.0:
        level = "low"
    else:
        level = "insufficient"

    return round(confidence, 1), level


# ---------------------------------------------------------------------------
# Persist provenance
# ---------------------------------------------------------------------------


def persist_field_provenance(
    target_date: date,
    daily_fact: DailyFact,
    session: Session,
    stale_data: dict[str, int | None] | None = None,
) -> list[DailyFieldProvenance]:
    """Persist field-level provenance records for the date."""
    provenance = compute_field_provenance(daily_fact)
    if stale_data is None:
        stale_data = detect_stale_data(target_date, session)

    # Delete existing for this date
    existing = session.scalars(
        select(DailyFieldProvenance).where(DailyFieldProvenance.date == target_date)
    ).all()
    for r in existing:
        session.delete(r)

    records: list[DailyFieldProvenance] = []
    for field_name, source in provenance.items():
        if source is not None:
            is_stale = False
            staleness_days = None
            # Check staleness
            if field_name in ("hrv", "resting_hr", "sleep") and stale_data.get("recovery") is not None:
                is_stale = True
                staleness_days = stale_data["recovery"]
            elif field_name == "weight" and stale_data.get("weight") is not None:
                is_stale = True
                staleness_days = stale_data["weight"]
            elif field_name == "workout" and stale_data.get("workout") is not None:
                is_stale = True
                staleness_days = stale_data["workout"]

            record = DailyFieldProvenance(
                date=target_date,
                field_name=field_name,
                source=source,
                is_stale=is_stale,
                staleness_days=staleness_days,
            )
            session.add(record)
            records.append(record)

    return records
