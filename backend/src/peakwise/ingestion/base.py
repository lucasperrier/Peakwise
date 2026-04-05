from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger("peakwise.ingestion")


# ---------------------------------------------------------------------------
# Ingestion result tracking
# ---------------------------------------------------------------------------


@dataclass
class IngestionError:
    source: str
    file_name: str
    row_number: int | None
    field: str | None
    message: str


@dataclass
class IngestionResult:
    source: str
    file_name: str
    rows_processed: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    errors: list[IngestionError] = field(default_factory=list)

    def add_error(
        self,
        message: str,
        row_number: int | None = None,
        field_name: str | None = None,
    ) -> None:
        self.errors.append(
            IngestionError(
                source=self.source,
                file_name=self.file_name,
                row_number=row_number,
                field=field_name,
                message=message,
            )
        )
        self.rows_skipped += 1
        logger.warning(
            "Ingestion error [%s/%s] row=%s field=%s: %s",
            self.source,
            self.file_name,
            row_number,
            field_name,
            message,
        )

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Parsed record types
# ---------------------------------------------------------------------------


@dataclass
class ParsedDailyRecord:
    source: str
    date: date
    body_weight_kg: float | None = None
    body_fat_pct: float | None = None
    resting_hr_bpm: int | None = None
    hrv_ms: float | None = None
    sleep_duration_min: float | None = None
    sleep_score: float | None = None
    steps: int | None = None
    active_energy_kcal: float | None = None
    training_readiness: float | None = None
    stress_score: float | None = None
    body_battery: float | None = None
    raw_payload: dict | None = None


@dataclass
class ParsedWorkoutRecord:
    source: str
    source_workout_id: str
    session_date: date
    session_type: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_min: float | None = None
    avg_hr_bpm: int | None = None
    max_hr_bpm: int | None = None
    training_load: float | None = None
    distance_km: float | None = None
    avg_pace_sec_per_km: float | None = None
    elevation_gain_m: float | None = None
    calories_kcal: float | None = None
    route_type: str | None = None
    cadence_spm: int | None = None
    raw_notes: str | None = None
    raw_payload: dict | None = None


@dataclass
class ParsedManualInput:
    date: date
    left_knee_pain_score: float | None = None
    global_pain_score: float | None = None
    soreness_score: float | None = None
    mood_score: float | None = None
    motivation_score: float | None = None
    stress_score: float | None = None
    illness_flag: bool | None = None
    free_text_note: str | None = None


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

VALID_SESSION_TYPES = {
    "run_easy",
    "run_quality",
    "run_long",
    "crossfit",
    "strength",
    "walk",
    "mobility",
    "bike",
    "other",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {value!r}")


def parse_datetime(value: str) -> datetime:
    value = value.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {value!r}")


def safe_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value.strip().replace(",", ""))
    except ValueError:
        return None


def safe_int(value: str | None) -> int | None:
    f = safe_float(value)
    if f is None:
        return None
    return round(f)


def safe_bool(value: str | None) -> bool | None:
    if value is None or value.strip() == "":
        return None
    v = value.strip().lower()
    if v in ("1", "true", "yes", "y"):
        return True
    if v in ("0", "false", "no", "n"):
        return False
    return None


def classify_run_type(
    distance_km: float | None,
    duration_min: float | None,
    notes: str | None = None,
) -> str:
    if notes:
        lower = notes.lower()
        if any(w in lower for w in ("interval", "tempo", "threshold", "quality", "speed")):
            return "run_quality"
        if any(w in lower for w in ("long run", "long_run", "long-run")):
            return "run_long"
    if distance_km is not None and distance_km >= 15.0:
        return "run_long"
    if distance_km is not None and distance_km >= 10.0 and duration_min is not None:
        pace = duration_min / distance_km if distance_km > 0 else 99
        if pace < 5.0:
            return "run_quality"
    return "run_easy"


def map_activity_type(
    raw_type: str,
    distance_km: float | None = None,
    duration_min: float | None = None,
    notes: str | None = None,
) -> str:
    t = raw_type.strip().lower()
    if t in VALID_SESSION_TYPES:
        return t
    run_keywords = ("run", "running", "trail run", "trail running", "treadmill")
    if any(k in t for k in run_keywords):
        return classify_run_type(distance_km, duration_min, notes)
    if "crossfit" in t or "cross fit" in t or "functional" in t:
        return "crossfit"
    if "strength" in t or "weight" in t or "gym" in t:
        return "strength"
    if "walk" in t or "hike" in t or "hiking" in t:
        return "walk"
    if "yoga" in t or "stretch" in t or "mobility" in t or "pilates" in t:
        return "mobility"
    if "bike" in t or "cycling" in t or "ride" in t:
        return "bike"
    return "other"
