from __future__ import annotations

import logging

from peakwise.models import WorkoutFact

logger = logging.getLogger("peakwise.ingestion")


def deduplicate_workouts(workouts: list[WorkoutFact]) -> list[WorkoutFact]:
    """Identify and mark duplicate workout records across sources.

    Two workouts are considered duplicates when they share the same session
    date, have overlapping time windows (or similar duration), and similar
    distance.  When a duplicate is found, the Garmin record is preferred,
    then Strava, then others.  The lower-priority duplicate is marked with
    ``is_duplicate=True`` and ``duplicate_of_id`` pointing to the kept record.
    """
    source_priority = {"garmin": 3, "strava": 2}

    # Group by session_date
    by_date: dict[str, list[WorkoutFact]] = {}
    for w in workouts:
        key = w.session_date.isoformat()
        by_date.setdefault(key, []).append(w)

    for date_key, group in by_date.items():
        if len(group) < 2:
            continue

        # Sort by source priority descending so the preferred record comes first
        group.sort(key=lambda w: source_priority.get(w.source, 0), reverse=True)

        seen: list[WorkoutFact] = []
        for w in group:
            if w.is_duplicate:
                continue
            match = _find_match(w, seen)
            if match is not None:
                w.is_duplicate = True
                w.duplicate_of_id = match.workout_id
                logger.info(
                    "Marked workout %s (%s) as duplicate of %s (%s) on %s",
                    w.workout_id,
                    w.source,
                    match.workout_id,
                    match.source,
                    date_key,
                )
            else:
                seen.append(w)

    return workouts


def _find_match(candidate: WorkoutFact, seen: list[WorkoutFact]) -> WorkoutFact | None:
    """Check if *candidate* matches any workout already in *seen*."""
    for existing in seen:
        if _is_likely_same(candidate, existing):
            return existing
    return None


def _is_likely_same(a: WorkoutFact, b: WorkoutFact) -> bool:
    """Heuristic: same date, similar session type category, and overlapping
    duration or distance."""
    if a.session_date != b.session_date:
        return False

    # Must be broadly the same kind of activity
    if not _same_activity_category(a.session_type, b.session_type):
        return False

    # Check duration similarity (within 20%)
    if a.duration_min and b.duration_min:
        ratio = min(a.duration_min, b.duration_min) / max(a.duration_min, b.duration_min)
        if ratio < 0.8:
            return False

    # Check distance similarity (within 20%) if both have it
    if a.distance_km and b.distance_km:
        ratio = min(a.distance_km, b.distance_km) / max(a.distance_km, b.distance_km)
        if ratio < 0.8:
            return False

    # Check time overlap if both have start times
    if a.start_time and b.start_time:
        diff = abs((a.start_time - b.start_time).total_seconds())
        if diff > 3600:  # more than 1 hour apart → different sessions
            return False

    return True


_RUN_TYPES = {"run_easy", "run_quality", "run_long"}
_STRENGTH_TYPES = {"crossfit", "strength"}


def _same_activity_category(a: str, b: str) -> bool:
    if a == b:
        return True
    if a in _RUN_TYPES and b in _RUN_TYPES:
        return True
    return bool(a in _STRENGTH_TYPES and b in _STRENGTH_TYPES)
