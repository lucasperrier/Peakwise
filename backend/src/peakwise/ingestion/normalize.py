from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta

from peakwise.ingestion.base import ParsedDailyRecord, ParsedManualInput, ParsedWorkoutRecord
from peakwise.models import (
    DailyFact,
    DailySourceCoverage,
    ManualDailyInput,
    RawEvent,
    WorkoutFact,
)

logger = logging.getLogger("peakwise.ingestion")

# ---------------------------------------------------------------------------
# Source-priority for field merging (higher wins when both have a value)
# ---------------------------------------------------------------------------

_DAILY_SOURCE_PRIORITY = {"garmin": 3, "apple_health": 2, "scale": 1}


def _pick(current: object, new: object, current_priority: int, new_priority: int) -> object:
    """Return the higher-priority non-None value."""
    if new is None:
        return current
    if current is None:
        return new
    return new if new_priority >= current_priority else current


# ---------------------------------------------------------------------------
# Build daily_fact rows from parsed daily records
# ---------------------------------------------------------------------------


def merge_daily_records(
    records: list[ParsedDailyRecord],
) -> list[DailyFact]:
    """Merge parsed daily records from multiple sources into DailyFact rows.

    When multiple sources provide the same field for the same date, the
    higher-priority source wins (Garmin > Apple Health > Scale).
    """
    by_date: dict[date, dict] = defaultdict(
        lambda: {
            "body_weight_kg": None,
            "body_fat_pct": None,
            "resting_hr_bpm": None,
            "hrv_ms": None,
            "sleep_duration_min": None,
            "sleep_score": None,
            "steps": None,
            "active_energy_kcal": None,
            "training_readiness": None,
            "stress_score": None,
            "body_battery": None,
            "_priority": defaultdict(int),
            "_sources": set(),
        }
    )

    fields = [
        "body_weight_kg",
        "body_fat_pct",
        "resting_hr_bpm",
        "hrv_ms",
        "sleep_duration_min",
        "sleep_score",
        "steps",
        "active_energy_kcal",
        "training_readiness",
        "stress_score",
        "body_battery",
    ]

    for rec in records:
        entry = by_date[rec.date]
        entry["_sources"].add(rec.source)
        src_pri = _DAILY_SOURCE_PRIORITY.get(rec.source, 0)

        for f in fields:
            val = getattr(rec, f, None)
            if val is not None:
                old_pri = entry["_priority"][f]
                entry[f] = _pick(entry[f], val, old_pri, src_pri)
                if src_pri >= old_pri:
                    entry["_priority"][f] = src_pri

    facts: list[DailyFact] = []
    for d, data in sorted(by_date.items()):
        sources = data.pop("_sources")
        data.pop("_priority")
        facts.append(
            DailyFact(
                date=d,
                **data,
                has_garmin_data="garmin" in sources,
                has_apple_health_data="apple_health" in sources,
                has_scale_data="scale" in sources,
            )
        )

    return facts


# ---------------------------------------------------------------------------
# Apply manual input overlays onto daily facts
# ---------------------------------------------------------------------------


def apply_manual_inputs(
    facts: list[DailyFact],
    manual_inputs: list[ParsedManualInput],
) -> list[ManualDailyInput]:
    """Overlay manual inputs onto existing DailyFact rows and return
    ManualDailyInput records for persistence."""
    facts_by_date = {f.date: f for f in facts}
    persisted: list[ManualDailyInput] = []

    for mi in manual_inputs:
        fact = facts_by_date.get(mi.date)
        if fact is None:
            # Create a sparse daily fact for this date
            fact = DailyFact(date=mi.date)
            facts.append(fact)
            facts_by_date[mi.date] = fact

        # Overlay subjective fields
        if mi.left_knee_pain_score is not None:
            fact.left_knee_pain_score = mi.left_knee_pain_score
        if mi.soreness_score is not None:
            fact.soreness_score = mi.soreness_score
        if mi.mood_score is not None:
            fact.mood_score = mi.mood_score
        if mi.motivation_score is not None:
            fact.motivation_score = mi.motivation_score
        if mi.illness_flag is not None:
            fact.illness_flag = mi.illness_flag
        if mi.stress_score is not None:
            fact.stress_score = mi.stress_score
        fact.has_manual_input = True

        persisted.append(
            ManualDailyInput(
                date=mi.date,
                left_knee_pain_score=mi.left_knee_pain_score,
                global_pain_score=mi.global_pain_score,
                soreness_score=mi.soreness_score,
                mood_score=mi.mood_score,
                motivation_score=mi.motivation_score,
                stress_score_subjective=mi.stress_score,
                illness_flag=mi.illness_flag,
                free_text_note=mi.free_text_note,
            )
        )

    return persisted


# ---------------------------------------------------------------------------
# Build workout_fact rows from parsed workout records
# ---------------------------------------------------------------------------


def build_workout_facts(records: list[ParsedWorkoutRecord]) -> list[WorkoutFact]:
    """Convert parsed workout records into WorkoutFact model instances."""
    facts: list[WorkoutFact] = []
    for rec in records:
        facts.append(
            WorkoutFact(
                source=rec.source,
                source_workout_id=rec.source_workout_id,
                start_time=rec.start_time,
                end_time=rec.end_time,
                session_date=rec.session_date,
                session_type=rec.session_type,
                duration_min=rec.duration_min,
                avg_hr_bpm=rec.avg_hr_bpm,
                max_hr_bpm=rec.max_hr_bpm,
                training_load=rec.training_load,
                distance_km=rec.distance_km,
                avg_pace_sec_per_km=rec.avg_pace_sec_per_km,
                elevation_gain_m=rec.elevation_gain_m,
                calories_kcal=rec.calories_kcal,
                route_type=rec.route_type,
                cadence_spm=rec.cadence_spm,
                raw_notes=rec.raw_notes,
            )
        )
    return facts


# ---------------------------------------------------------------------------
# Build source coverage
# ---------------------------------------------------------------------------


def build_source_coverage(
    daily_facts: list[DailyFact],
    workout_facts: list[WorkoutFact],
    manual_inputs: list[ManualDailyInput],
) -> list[DailySourceCoverage]:
    """Build daily_source_coverage rows for every date that has any data."""
    all_dates: set[date] = set()

    garmin_dates: set[date] = set()
    apple_dates: set[date] = set()
    strava_dates: set[date] = set()
    scale_dates: set[date] = set()
    manual_dates: set[date] = set()

    for f in daily_facts:
        all_dates.add(f.date)
        if f.has_garmin_data:
            garmin_dates.add(f.date)
        if f.has_apple_health_data:
            apple_dates.add(f.date)
        if f.has_scale_data:
            scale_dates.add(f.date)
        if f.has_manual_input:
            manual_dates.add(f.date)

    for w in workout_facts:
        all_dates.add(w.session_date)
        if w.source == "strava":
            strava_dates.add(w.session_date)
        elif w.source == "garmin":
            garmin_dates.add(w.session_date)

    for m in manual_inputs:
        all_dates.add(m.date)
        manual_dates.add(m.date)

    coverage: list[DailySourceCoverage] = []
    for d in sorted(all_dates):
        has_garmin = d in garmin_dates
        has_apple = d in apple_dates
        has_strava = d in strava_dates
        has_scale = d in scale_dates
        has_manual = d in manual_dates

        source_count = sum([has_garmin, has_apple, has_strava, has_scale, has_manual])
        is_partial = source_count < 2  # consider partial if fewer than 2 sources

        coverage.append(
            DailySourceCoverage(
                date=d,
                garmin_coverage=has_garmin,
                apple_health_coverage=has_apple,
                strava_coverage=has_strava,
                scale_coverage=has_scale,
                manual_input_coverage=has_manual,
                is_partial_day=is_partial,
            )
        )

    return coverage


# ---------------------------------------------------------------------------
# Mark missing days explicitly
# ---------------------------------------------------------------------------


def mark_missing_days(
    daily_facts: list[DailyFact],
    coverage: list[DailySourceCoverage],
) -> list[DailySourceCoverage]:
    """Identify gaps in the date range and create explicit coverage records
    for missing days."""
    if not daily_facts:
        return coverage

    existing_dates = {c.date for c in coverage}
    all_fact_dates = {f.date for f in daily_facts}
    all_dates = existing_dates | all_fact_dates

    min_date = min(all_dates)
    max_date = max(all_dates)

    added: list[DailySourceCoverage] = []
    current = min_date
    while current <= max_date:
        if current not in existing_dates:
            added.append(
                DailySourceCoverage(
                    date=current,
                    is_partial_day=True,
                    coverage_note="No data for this date",
                )
            )
        current += timedelta(days=1)

    return coverage + added


# ---------------------------------------------------------------------------
# Build raw events for lineage
# ---------------------------------------------------------------------------


def build_raw_events(
    daily_records: list[ParsedDailyRecord],
    workout_records: list[ParsedWorkoutRecord],
    manual_inputs: list[ParsedManualInput],
    file_name: str | None = None,
) -> list[RawEvent]:
    """Create RawEvent records for source lineage preservation."""
    events: list[RawEvent] = []

    for rec in daily_records:
        events.append(
            RawEvent(
                source=rec.source,
                event_date=rec.date,
                record_type="daily",
                payload_json=rec.raw_payload,
                source_file_name=file_name,
            )
        )

    for rec in workout_records:
        events.append(
            RawEvent(
                source=rec.source,
                source_record_id=rec.source_workout_id,
                event_date=rec.session_date,
                event_timestamp=rec.start_time,
                record_type="workout",
                payload_json=rec.raw_payload,
                source_file_name=file_name,
            )
        )

    for rec in manual_inputs:
        events.append(
            RawEvent(
                source="manual",
                event_date=rec.date,
                record_type="manual_input",
                payload_json={
                    "left_knee_pain_score": rec.left_knee_pain_score,
                    "global_pain_score": rec.global_pain_score,
                    "soreness_score": rec.soreness_score,
                    "mood_score": rec.mood_score,
                    "motivation_score": rec.motivation_score,
                    "stress_score": rec.stress_score,
                    "illness_flag": rec.illness_flag,
                    "free_text_note": rec.free_text_note,
                },
                source_file_name=file_name,
            )
        )

    return events
