from __future__ import annotations

import contextlib
from pathlib import Path

from peakwise.ingestion.base import (
    IngestionResult,
    ParsedDailyRecord,
    ParsedWorkoutRecord,
    map_activity_type,
    parse_date,
    parse_datetime,
    read_csv,
    safe_float,
    safe_int,
)


def parse_garmin_daily_csv(
    path: Path,
) -> tuple[list[ParsedDailyRecord], IngestionResult]:
    """Parse Garmin daily summary CSV.

    Expected columns: date, body_weight_kg, body_fat_pct, resting_hr_bpm,
    hrv_ms, sleep_duration_min, sleep_score, steps, active_energy_kcal,
    training_readiness, stress_score, body_battery
    """
    result = IngestionResult(source="garmin", file_name=path.name)
    records: list[ParsedDailyRecord] = []
    rows = read_csv(path)

    for i, row in enumerate(rows, start=2):
        result.rows_processed += 1
        try:
            d = parse_date(row["date"])
        except (ValueError, KeyError) as exc:
            result.add_error(str(exc), row_number=i, field_name="date")
            continue

        records.append(
            ParsedDailyRecord(
                source="garmin",
                date=d,
                body_weight_kg=safe_float(row.get("body_weight_kg")),
                body_fat_pct=safe_float(row.get("body_fat_pct")),
                resting_hr_bpm=safe_int(row.get("resting_hr_bpm")),
                hrv_ms=safe_float(row.get("hrv_ms")),
                sleep_duration_min=safe_float(row.get("sleep_duration_min")),
                sleep_score=safe_float(row.get("sleep_score")),
                steps=safe_int(row.get("steps")),
                active_energy_kcal=safe_float(row.get("active_energy_kcal")),
                training_readiness=safe_float(row.get("training_readiness")),
                stress_score=safe_float(row.get("stress_score")),
                body_battery=safe_float(row.get("body_battery")),
                raw_payload=dict(row),
            )
        )
        result.rows_imported += 1

    return records, result


def parse_garmin_activities_csv(
    path: Path,
) -> tuple[list[ParsedWorkoutRecord], IngestionResult]:
    """Parse Garmin activities CSV.

    Expected columns: source_workout_id, session_date, start_time, end_time,
    session_type, duration_min, avg_hr_bpm, max_hr_bpm, distance_km,
    avg_pace_sec_per_km, elevation_gain_m, calories_kcal, training_load,
    route_type, cadence_spm, notes
    """
    result = IngestionResult(source="garmin", file_name=path.name)
    records: list[ParsedWorkoutRecord] = []
    rows = read_csv(path)

    for i, row in enumerate(rows, start=2):
        result.rows_processed += 1
        try:
            d = parse_date(row["session_date"])
        except (ValueError, KeyError) as exc:
            result.add_error(str(exc), row_number=i, field_name="session_date")
            continue

        raw_type = row.get("session_type", "other")
        distance = safe_float(row.get("distance_km"))
        duration = safe_float(row.get("duration_min"))
        notes = row.get("notes", "")
        session_type = map_activity_type(raw_type, distance, duration, notes)

        source_id = row.get("source_workout_id", "").strip()
        if not source_id:
            source_id = f"garmin_{d.isoformat()}_{i}"

        start = None
        if row.get("start_time"):
            with contextlib.suppress(ValueError):
                start = parse_datetime(row["start_time"])

        end = None
        if row.get("end_time"):
            with contextlib.suppress(ValueError):
                end = parse_datetime(row["end_time"])

        records.append(
            ParsedWorkoutRecord(
                source="garmin",
                source_workout_id=source_id,
                session_date=d,
                session_type=session_type,
                start_time=start,
                end_time=end,
                duration_min=duration,
                avg_hr_bpm=safe_int(row.get("avg_hr_bpm")),
                max_hr_bpm=safe_int(row.get("max_hr_bpm")),
                training_load=safe_float(row.get("training_load")),
                distance_km=distance,
                avg_pace_sec_per_km=safe_float(row.get("avg_pace_sec_per_km")),
                elevation_gain_m=safe_float(row.get("elevation_gain_m")),
                calories_kcal=safe_float(row.get("calories_kcal")),
                route_type=row.get("route_type", "").strip() or None,
                cadence_spm=safe_int(row.get("cadence_spm")),
                raw_notes=notes or None,
                raw_payload=dict(row),
            )
        )
        result.rows_imported += 1

    return records, result
