from __future__ import annotations

from pathlib import Path

from peakwise.ingestion.base import (
    IngestionResult,
    ParsedManualInput,
    parse_date,
    read_csv,
    safe_bool,
    safe_float,
)


def parse_manual_input_csv(
    path: Path,
) -> tuple[list[ParsedManualInput], IngestionResult]:
    """Parse manual daily input CSV.

    Expected columns: date, left_knee_pain_score, global_pain_score,
    soreness_score, mood_score, motivation_score, stress_score,
    illness_flag, note
    """
    result = IngestionResult(source="manual", file_name=path.name)
    records: list[ParsedManualInput] = []
    rows = read_csv(path)

    for i, row in enumerate(rows, start=2):
        result.rows_processed += 1
        try:
            d = parse_date(row["date"])
        except (ValueError, KeyError) as exc:
            result.add_error(str(exc), row_number=i, field_name="date")
            continue

        records.append(
            ParsedManualInput(
                date=d,
                left_knee_pain_score=safe_float(row.get("left_knee_pain_score")),
                global_pain_score=safe_float(row.get("global_pain_score")),
                soreness_score=safe_float(row.get("soreness_score")),
                mood_score=safe_float(row.get("mood_score")),
                motivation_score=safe_float(row.get("motivation_score")),
                stress_score=safe_float(row.get("stress_score")),
                illness_flag=safe_bool(row.get("illness_flag")),
                free_text_note=row.get("note", "").strip() or None,
            )
        )
        result.rows_imported += 1

    return records, result
