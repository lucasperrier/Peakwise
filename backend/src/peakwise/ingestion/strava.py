from __future__ import annotations

import contextlib
from pathlib import Path

from peakwise.ingestion.base import (
    IngestionResult,
    ParsedWorkoutRecord,
    map_activity_type,
    parse_date,
    parse_datetime,
    read_csv,
    safe_float,
    safe_int,
)


def parse_strava_csv(
    path: Path,
) -> tuple[list[ParsedWorkoutRecord], IngestionResult]:
    """Parse Strava activities CSV.

    Supports two formats:

    1. Normalized CSV with columns: source_workout_id, session_date, start_time,
       session_type, duration_min, distance_km, avg_hr_bpm, max_hr_bpm,
       avg_pace_sec_per_km, elevation_gain_m, calories_kcal, notes
    2. Native Strava bulk-export ``activities.csv`` with columns such as
       Activity ID, Activity Date, Activity Type, Elapsed Time, Distance, etc.
    """
    result = IngestionResult(source="strava", file_name=path.name)
    records: list[ParsedWorkoutRecord] = []
    rows = read_csv(path)

    if not rows:
        return records, result

    # Detect format by checking header keys
    first_keys = set(rows[0].keys())
    is_native = "Activity ID" in first_keys or "Activity Type" in first_keys

    for i, row in enumerate(rows, start=2):
        result.rows_processed += 1

        if is_native:
            rec = _parse_native_row(row, i, result)
        else:
            rec = _parse_normalized_row(row, i, result)

        if rec is not None:
            records.append(rec)
            result.rows_imported += 1

    return records, result


def _parse_native_row(
    row: dict[str, str], row_num: int, result: IngestionResult
) -> ParsedWorkoutRecord | None:
    date_str = row.get("Activity Date", "").strip()
    if not date_str:
        result.add_error("Missing Activity Date", row_number=row_num, field_name="Activity Date")
        return None

    try:
        dt = parse_datetime(date_str)
        d = dt.date()
    except ValueError:
        try:
            d = parse_date(date_str)
            dt = None
        except ValueError as exc:
            result.add_error(str(exc), row_number=row_num, field_name="Activity Date")
            return None

    raw_type = row.get("Activity Type", "other")
    # Strava distance is in km by default in bulk export
    distance = safe_float(row.get("Distance"))
    # Strava elapsed time is in seconds in bulk export
    elapsed_sec = safe_float(row.get("Elapsed Time"))
    duration = elapsed_sec / 60.0 if elapsed_sec else None
    notes = row.get("Activity Name", "")
    session_type = map_activity_type(raw_type, distance, duration, notes)

    source_id = row.get("Activity ID", "").strip()
    if not source_id:
        source_id = f"strava_{d.isoformat()}_{row_num}"

    avg_pace = None
    if distance and distance > 0 and duration:
        avg_pace = (duration * 60.0) / distance  # seconds per km

    return ParsedWorkoutRecord(
        source="strava",
        source_workout_id=source_id,
        session_date=d,
        session_type=session_type,
        start_time=dt if isinstance(dt, type(None)) is False else None,
        duration_min=duration,
        avg_hr_bpm=safe_int(row.get("Average Heart Rate")),
        max_hr_bpm=safe_int(row.get("Max Heart Rate")),
        distance_km=distance,
        avg_pace_sec_per_km=avg_pace,
        elevation_gain_m=safe_float(row.get("Elevation Gain")),
        calories_kcal=safe_float(row.get("Calories")),
        raw_notes=notes or None,
        raw_payload=dict(row),
    )


def _parse_normalized_row(
    row: dict[str, str], row_num: int, result: IngestionResult
) -> ParsedWorkoutRecord | None:
    try:
        d = parse_date(row["session_date"])
    except (ValueError, KeyError) as exc:
        result.add_error(str(exc), row_number=row_num, field_name="session_date")
        return None

    raw_type = row.get("session_type", "other")
    distance = safe_float(row.get("distance_km"))
    duration = safe_float(row.get("duration_min"))
    notes = row.get("notes", "")
    session_type = map_activity_type(raw_type, distance, duration, notes)

    source_id = row.get("source_workout_id", "").strip()
    if not source_id:
        source_id = f"strava_{d.isoformat()}_{row_num}"

    start = None
    if row.get("start_time"):
        with contextlib.suppress(ValueError):
            start = parse_datetime(row["start_time"])

    return ParsedWorkoutRecord(
        source="strava",
        source_workout_id=source_id,
        session_date=d,
        session_type=session_type,
        start_time=start,
        duration_min=duration,
        avg_hr_bpm=safe_int(row.get("avg_hr_bpm")),
        max_hr_bpm=safe_int(row.get("max_hr_bpm")),
        distance_km=distance,
        avg_pace_sec_per_km=safe_float(row.get("avg_pace_sec_per_km")),
        elevation_gain_m=safe_float(row.get("elevation_gain_m")),
        calories_kcal=safe_float(row.get("calories_kcal")),
        raw_notes=notes or None,
        raw_payload=dict(row),
    )
