from __future__ import annotations

import csv
import tempfile
from datetime import date
from pathlib import Path

import pytest

from peakwise.ingestion.apple_health import parse_apple_health_csv
from peakwise.ingestion.base import (
    ParsedDailyRecord,
    ParsedManualInput,
    ParsedWorkoutRecord,
    classify_run_type,
    map_activity_type,
    parse_date,
    safe_bool,
    safe_float,
    safe_int,
)
from peakwise.ingestion.dedup import deduplicate_workouts
from peakwise.ingestion.garmin import parse_garmin_activities_csv, parse_garmin_daily_csv
from peakwise.ingestion.manual import parse_manual_input_csv
from peakwise.ingestion.normalize import (
    apply_manual_inputs,
    build_source_coverage,
    build_workout_facts,
    mark_missing_days,
    merge_daily_records,
)
from peakwise.ingestion.scale import parse_scale_csv
from peakwise.ingestion.strava import parse_strava_csv
from peakwise.models import DailyFact, WorkoutFact

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(rows: list[dict], filename: str = "test.csv") -> Path:
    tmp = Path(tempfile.mkdtemp()) / filename
    if not rows:
        tmp.write_text("")
        return tmp
    fieldnames = list(rows[0].keys())
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return tmp


# ---------------------------------------------------------------------------
# Base helpers
# ---------------------------------------------------------------------------


class TestParseDate:
    def test_iso_format(self):
        assert parse_date("2025-06-15") == date(2025, 6, 15)

    def test_us_format(self):
        assert parse_date("06/15/2025") == date(2025, 6, 15)

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_date("not-a-date")


class TestSafeFloat:
    def test_valid(self):
        assert safe_float("3.14") == pytest.approx(3.14)

    def test_with_comma(self):
        assert safe_float("1,234.5") == pytest.approx(1234.5)

    def test_empty(self):
        assert safe_float("") is None

    def test_none(self):
        assert safe_float(None) is None

    def test_invalid(self):
        assert safe_float("abc") is None


class TestSafeInt:
    def test_valid(self):
        assert safe_int("42") == 42

    def test_from_float(self):
        assert safe_int("42.6") == 43

    def test_empty(self):
        assert safe_int("") is None


class TestSafeBool:
    def test_true_values(self):
        for v in ("1", "true", "yes", "True", "YES", "y"):
            assert safe_bool(v) is True

    def test_false_values(self):
        for v in ("0", "false", "no", "False", "NO", "n"):
            assert safe_bool(v) is False

    def test_empty(self):
        assert safe_bool("") is None


class TestClassifyRunType:
    def test_long_by_distance(self):
        assert classify_run_type(16.0, 90.0) == "run_long"

    def test_easy_default(self):
        assert classify_run_type(8.0, 45.0) == "run_easy"

    def test_quality_from_notes(self):
        assert classify_run_type(10.0, 50.0, "Tempo intervals") == "run_quality"

    def test_long_from_notes(self):
        assert classify_run_type(12.0, 70.0, "long run Sunday") == "run_long"


class TestMapActivityType:
    def test_direct_match(self):
        assert map_activity_type("run_easy") == "run_easy"

    def test_running(self):
        assert map_activity_type("Running") in {"run_easy", "run_quality", "run_long"}

    def test_crossfit(self):
        assert map_activity_type("CrossFit") == "crossfit"

    def test_cycling(self):
        assert map_activity_type("Cycling") == "bike"

    def test_yoga(self):
        assert map_activity_type("Yoga") == "mobility"

    def test_unknown(self):
        assert map_activity_type("Underwater basket weaving") == "other"


# ---------------------------------------------------------------------------
# Garmin parser
# ---------------------------------------------------------------------------


class TestGarminDailyParser:
    def test_basic_parse(self):
        path = _write_csv(
            [
                {
                    "date": "2025-06-01",
                    "body_weight_kg": "75.5",
                    "body_fat_pct": "15.2",
                    "resting_hr_bpm": "52",
                    "hrv_ms": "45.3",
                    "sleep_duration_min": "420",
                    "sleep_score": "82",
                    "steps": "8500",
                    "active_energy_kcal": "650",
                    "training_readiness": "70",
                    "stress_score": "30",
                    "body_battery": "75",
                },
            ]
        )
        records, result = parse_garmin_daily_csv(path)
        assert result.ok
        assert len(records) == 1
        r = records[0]
        assert r.source == "garmin"
        assert r.date == date(2025, 6, 1)
        assert r.body_weight_kg == pytest.approx(75.5)
        assert r.resting_hr_bpm == 52
        assert r.steps == 8500

    def test_missing_optional_fields(self):
        path = _write_csv(
            [
                {"date": "2025-06-01", "steps": "10000"},
            ]
        )
        records, result = parse_garmin_daily_csv(path)
        assert result.ok
        assert records[0].body_weight_kg is None
        assert records[0].steps == 10000

    def test_bad_date_skips_row(self):
        path = _write_csv(
            [
                {"date": "bad-date", "steps": "10000"},
                {"date": "2025-06-01", "steps": "5000"},
            ]
        )
        records, result = parse_garmin_daily_csv(path)
        assert len(records) == 1
        assert result.rows_skipped == 1
        assert len(result.errors) == 1


class TestGarminActivitiesParser:
    def test_basic_parse(self):
        path = _write_csv(
            [
                {
                    "source_workout_id": "g123",
                    "session_date": "2025-06-01",
                    "start_time": "2025-06-01 07:00:00",
                    "end_time": "2025-06-01 07:45:00",
                    "session_type": "Running",
                    "duration_min": "45",
                    "avg_hr_bpm": "145",
                    "max_hr_bpm": "165",
                    "distance_km": "8.5",
                    "avg_pace_sec_per_km": "318",
                    "elevation_gain_m": "120",
                    "calories_kcal": "450",
                    "training_load": "85",
                    "route_type": "road",
                    "cadence_spm": "170",
                    "notes": "",
                },
            ]
        )
        records, result = parse_garmin_activities_csv(path)
        assert result.ok
        assert len(records) == 1
        r = records[0]
        assert r.source == "garmin"
        assert r.session_type == "run_easy"
        assert r.distance_km == pytest.approx(8.5)

    def test_long_run_classification(self):
        path = _write_csv(
            [
                {
                    "source_workout_id": "g456",
                    "session_date": "2025-06-01",
                    "start_time": "",
                    "end_time": "",
                    "session_type": "Running",
                    "duration_min": "95",
                    "avg_hr_bpm": "140",
                    "max_hr_bpm": "155",
                    "distance_km": "18",
                    "avg_pace_sec_per_km": "",
                    "elevation_gain_m": "",
                    "calories_kcal": "",
                    "training_load": "",
                    "route_type": "",
                    "cadence_spm": "",
                    "notes": "",
                },
            ]
        )
        records, _ = parse_garmin_activities_csv(path)
        assert records[0].session_type == "run_long"


# ---------------------------------------------------------------------------
# Apple Health parser
# ---------------------------------------------------------------------------


class TestAppleHealthParser:
    def test_basic_parse(self):
        path = _write_csv(
            [
                {
                    "date": "2025-06-01",
                    "resting_hr_bpm": "55",
                    "hrv_ms": "40",
                    "sleep_duration_min": "400",
                    "steps": "9000",
                    "active_energy_kcal": "600",
                },
            ]
        )
        records, result = parse_apple_health_csv(path)
        assert result.ok
        assert len(records) == 1
        assert records[0].source == "apple_health"
        assert records[0].hrv_ms == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# Strava parser
# ---------------------------------------------------------------------------


class TestStravaParser:
    def test_normalized_format(self):
        path = _write_csv(
            [
                {
                    "source_workout_id": "s100",
                    "session_date": "2025-06-01",
                    "start_time": "2025-06-01 06:30:00",
                    "session_type": "Running",
                    "duration_min": "50",
                    "distance_km": "10",
                    "avg_hr_bpm": "150",
                    "max_hr_bpm": "170",
                    "avg_pace_sec_per_km": "300",
                    "elevation_gain_m": "80",
                    "calories_kcal": "500",
                    "notes": "",
                },
            ]
        )
        records, result = parse_strava_csv(path)
        assert result.ok
        assert len(records) == 1
        assert records[0].source == "strava"

    def test_native_format(self):
        path = _write_csv(
            [
                {
                    "Activity ID": "12345678",
                    "Activity Date": "2025-06-01 07:30:00",
                    "Activity Name": "Morning Run",
                    "Activity Type": "Run",
                    "Elapsed Time": "2700",
                    "Distance": "8.0",
                    "Average Heart Rate": "148",
                    "Max Heart Rate": "168",
                    "Elevation Gain": "50",
                    "Calories": "400",
                },
            ]
        )
        records, result = parse_strava_csv(path)
        assert result.ok
        assert len(records) == 1
        r = records[0]
        assert r.source == "strava"
        assert r.source_workout_id == "12345678"
        assert r.duration_min == pytest.approx(45.0)
        assert r.distance_km == pytest.approx(8.0)


# ---------------------------------------------------------------------------
# Scale parser
# ---------------------------------------------------------------------------


class TestScaleParser:
    def test_basic_parse(self):
        path = _write_csv(
            [
                {"date": "2025-06-01", "body_weight_kg": "75.0", "body_fat_pct": "14.8"},
                {"date": "2025-06-02", "body_weight_kg": "74.8", "body_fat_pct": "14.7"},
            ]
        )
        records, result = parse_scale_csv(path)
        assert result.ok
        assert len(records) == 2

    def test_missing_weight_skips_row(self):
        path = _write_csv(
            [
                {"date": "2025-06-01", "body_weight_kg": "", "body_fat_pct": "14.8"},
            ]
        )
        records, result = parse_scale_csv(path)
        assert len(records) == 0
        assert result.rows_skipped == 1


# ---------------------------------------------------------------------------
# Manual input parser
# ---------------------------------------------------------------------------


class TestManualInputParser:
    def test_basic_parse(self):
        path = _write_csv(
            [
                {
                    "date": "2025-06-01",
                    "left_knee_pain_score": "3",
                    "global_pain_score": "2",
                    "soreness_score": "4",
                    "mood_score": "7",
                    "motivation_score": "8",
                    "stress_score": "5",
                    "illness_flag": "false",
                    "note": "Knee felt stiff after yesterday",
                },
            ]
        )
        records, result = parse_manual_input_csv(path)
        assert result.ok
        assert len(records) == 1
        r = records[0]
        assert r.left_knee_pain_score == pytest.approx(3.0)
        assert r.illness_flag is False
        assert r.free_text_note == "Knee felt stiff after yesterday"


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestMergeDailyRecords:
    def test_single_source(self):
        records = [
            ParsedDailyRecord(
                source="garmin",
                date=date(2025, 6, 1),
                resting_hr_bpm=52,
                steps=8000,
            ),
        ]
        facts = merge_daily_records(records)
        assert len(facts) == 1
        assert facts[0].resting_hr_bpm == 52
        assert facts[0].has_garmin_data is True

    def test_multi_source_priority(self):
        records = [
            ParsedDailyRecord(
                source="apple_health",
                date=date(2025, 6, 1),
                resting_hr_bpm=55,
                steps=9000,
            ),
            ParsedDailyRecord(
                source="garmin",
                date=date(2025, 6, 1),
                resting_hr_bpm=52,
                steps=8500,
            ),
        ]
        facts = merge_daily_records(records)
        assert len(facts) == 1
        # Garmin has higher priority
        assert facts[0].resting_hr_bpm == 52
        assert facts[0].steps == 8500
        assert facts[0].has_garmin_data is True
        assert facts[0].has_apple_health_data is True

    def test_fill_gaps_from_lower_priority(self):
        records = [
            ParsedDailyRecord(
                source="garmin",
                date=date(2025, 6, 1),
                resting_hr_bpm=52,
            ),
            ParsedDailyRecord(
                source="apple_health",
                date=date(2025, 6, 1),
                steps=9000,
            ),
        ]
        facts = merge_daily_records(records)
        assert facts[0].resting_hr_bpm == 52
        assert facts[0].steps == 9000

    def test_multiple_dates(self):
        records = [
            ParsedDailyRecord(source="garmin", date=date(2025, 6, 1), steps=8000),
            ParsedDailyRecord(source="garmin", date=date(2025, 6, 2), steps=10000),
        ]
        facts = merge_daily_records(records)
        assert len(facts) == 2


class TestApplyManualInputs:
    def test_overlay_on_existing(self):
        facts = [DailyFact(date=date(2025, 6, 1), resting_hr_bpm=52)]
        inputs = [ParsedManualInput(date=date(2025, 6, 1), soreness_score=4.0, mood_score=7.0)]
        manual_models = apply_manual_inputs(facts, inputs)
        assert facts[0].soreness_score == pytest.approx(4.0)
        assert facts[0].mood_score == pytest.approx(7.0)
        assert facts[0].has_manual_input is True
        assert len(manual_models) == 1

    def test_creates_sparse_fact_for_missing_date(self):
        facts: list[DailyFact] = []
        inputs = [ParsedManualInput(date=date(2025, 6, 5), soreness_score=2.0)]
        apply_manual_inputs(facts, inputs)
        assert len(facts) == 1
        assert facts[0].date == date(2025, 6, 5)
        assert facts[0].soreness_score == pytest.approx(2.0)


class TestBuildWorkoutFacts:
    def test_basic(self):
        records = [
            ParsedWorkoutRecord(
                source="garmin",
                source_workout_id="g100",
                session_date=date(2025, 6, 1),
                session_type="run_easy",
                duration_min=45.0,
                distance_km=8.5,
            ),
        ]
        facts = build_workout_facts(records)
        assert len(facts) == 1
        assert facts[0].source == "garmin"
        assert facts[0].session_type == "run_easy"


class TestBuildSourceCoverage:
    def test_coverage(self):
        daily_facts = [
            DailyFact(date=date(2025, 6, 1), has_garmin_data=True, has_apple_health_data=True),
        ]
        coverage = build_source_coverage(daily_facts, [], [])
        assert len(coverage) == 1
        assert coverage[0].garmin_coverage is True
        assert coverage[0].apple_health_coverage is True


class TestMarkMissingDays:
    def test_fills_gaps(self):
        facts = [
            DailyFact(date=date(2025, 6, 1)),
            DailyFact(date=date(2025, 6, 3)),
        ]
        coverage = build_source_coverage(facts, [], [])
        full = mark_missing_days(facts, coverage)
        dates = sorted(c.date for c in full)
        assert date(2025, 6, 2) in dates
        gap_record = next(c for c in full if c.date == date(2025, 6, 2))
        assert gap_record.is_partial_day is True
        assert gap_record.coverage_note == "No data for this date"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplicateWorkouts:
    def test_marks_duplicate(self):
        w1 = WorkoutFact(
            workout_id="aaa",
            source="garmin",
            source_workout_id="g100",
            session_date=date(2025, 6, 1),
            session_type="run_easy",
            duration_min=45.0,
            distance_km=8.5,
        )
        w2 = WorkoutFact(
            workout_id="bbb",
            source="strava",
            source_workout_id="s200",
            session_date=date(2025, 6, 1),
            session_type="run_easy",
            duration_min=44.0,
            distance_km=8.4,
        )
        workouts = [w1, w2]
        deduplicate_workouts(workouts)
        # Strava should be marked as duplicate of Garmin (higher priority)
        assert w2.is_duplicate is True
        assert w2.duplicate_of_id == "aaa"
        assert not w1.is_duplicate

    def test_no_false_positive_different_types(self):
        w1 = WorkoutFact(
            workout_id="aaa",
            source="garmin",
            source_workout_id="g100",
            session_date=date(2025, 6, 1),
            session_type="run_easy",
            duration_min=45.0,
            distance_km=8.5,
        )
        w2 = WorkoutFact(
            workout_id="bbb",
            source="garmin",
            source_workout_id="g101",
            session_date=date(2025, 6, 1),
            session_type="crossfit",
            duration_min=60.0,
        )
        workouts = [w1, w2]
        deduplicate_workouts(workouts)
        assert not w1.is_duplicate
        assert not w2.is_duplicate

    def test_no_false_positive_different_duration(self):
        w1 = WorkoutFact(
            workout_id="aaa",
            source="garmin",
            source_workout_id="g100",
            session_date=date(2025, 6, 1),
            session_type="run_easy",
            duration_min=45.0,
            distance_km=8.5,
        )
        w2 = WorkoutFact(
            workout_id="bbb",
            source="strava",
            source_workout_id="s200",
            session_date=date(2025, 6, 1),
            session_type="run_easy",
            duration_min=90.0,
            distance_km=16.0,
        )
        workouts = [w1, w2]
        deduplicate_workouts(workouts)
        assert not w1.is_duplicate
        assert not w2.is_duplicate


# ---------------------------------------------------------------------------
# Ingestion result tracking
# ---------------------------------------------------------------------------


class TestIngestionResult:
    def test_error_tracking(self):
        from peakwise.ingestion.base import IngestionResult

        result = IngestionResult(source="test", file_name="test.csv")
        result.rows_processed = 5
        result.rows_imported = 3
        result.add_error("bad row", row_number=2)
        result.add_error("another bad row", row_number=4)
        assert not result.ok
        assert result.rows_skipped == 2
        assert len(result.errors) == 2
        assert result.errors[0].row_number == 2
