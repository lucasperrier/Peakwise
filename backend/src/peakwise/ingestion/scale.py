from __future__ import annotations

from pathlib import Path

from peakwise.ingestion.base import (
    IngestionResult,
    ParsedDailyRecord,
    parse_date,
    read_csv,
    safe_float,
)


def parse_scale_csv(
    path: Path,
) -> tuple[list[ParsedDailyRecord], IngestionResult]:
    """Parse scale measurements CSV.

    Expected columns: date, body_weight_kg, body_fat_pct
    """
    result = IngestionResult(source="scale", file_name=path.name)
    records: list[ParsedDailyRecord] = []
    rows = read_csv(path)

    for i, row in enumerate(rows, start=2):
        result.rows_processed += 1
        try:
            d = parse_date(row["date"])
        except (ValueError, KeyError) as exc:
            result.add_error(str(exc), row_number=i, field_name="date")
            continue

        weight = safe_float(row.get("body_weight_kg"))
        if weight is None:
            result.add_error("Missing body_weight_kg", row_number=i, field_name="body_weight_kg")
            continue

        records.append(
            ParsedDailyRecord(
                source="scale",
                date=d,
                body_weight_kg=weight,
                body_fat_pct=safe_float(row.get("body_fat_pct")),
                raw_payload=dict(row),
            )
        )
        result.rows_imported += 1

    return records, result
