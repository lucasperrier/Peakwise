from __future__ import annotations

from pathlib import Path

from peakwise.ingestion.base import (
    IngestionResult,
    ParsedDailyRecord,
    parse_date,
    read_csv,
    safe_float,
    safe_int,
)


def parse_apple_health_csv(
    path: Path,
) -> tuple[list[ParsedDailyRecord], IngestionResult]:
    """Parse Apple Health daily summary CSV.

    Expected columns: date, resting_hr_bpm, hrv_ms, sleep_duration_min,
    steps, active_energy_kcal
    """
    result = IngestionResult(source="apple_health", file_name=path.name)
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
                source="apple_health",
                date=d,
                resting_hr_bpm=safe_int(row.get("resting_hr_bpm")),
                hrv_ms=safe_float(row.get("hrv_ms")),
                sleep_duration_min=safe_float(row.get("sleep_duration_min")),
                steps=safe_int(row.get("steps")),
                active_energy_kcal=safe_float(row.get("active_energy_kcal")),
                raw_payload=dict(row),
            )
        )
        result.rows_imported += 1

    return records, result
