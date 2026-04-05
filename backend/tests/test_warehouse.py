"""Tests for warehouse writes — verifies that the ingestion pipeline correctly
persists data to the database and that upsert semantics work."""

from __future__ import annotations

import csv
import tempfile
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from peakwise.ingestion.pipeline import IngestionManifest, PipelineResult, run_ingestion
from peakwise.models import (
    Base,
    DailyFact,
    DailySourceCoverage,
    ManualDailyInput,
    RawEvent,
    WorkoutFact,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session


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


def _garmin_daily_csv(rows: list[dict]) -> Path:
    return _write_csv(rows, "garmin_daily.csv")


def _garmin_activities_csv(rows: list[dict]) -> Path:
    return _write_csv(rows, "garmin_activities.csv")


def _strava_csv(rows: list[dict]) -> Path:
    return _write_csv(rows, "strava_activities.csv")


def _scale_csv(rows: list[dict]) -> Path:
    return _write_csv(rows, "scale_data.csv")


def _manual_csv(rows: list[dict]) -> Path:
    return _write_csv(rows, "manual_inputs.csv")


def _apple_health_csv(rows: list[dict]) -> Path:
    return _write_csv(rows, "apple_health.csv")


# ---------------------------------------------------------------------------
# DailyFact persistence
# ---------------------------------------------------------------------------


class TestDailyFactPersistence:
    def test_single_day_write(self, db_session: Session):
        manifest = IngestionManifest(
            garmin_daily_csv=_garmin_daily_csv([
                {
                    "date": "2025-06-01",
                    "body_weight_kg": "75.5",
                    "resting_hr_bpm": "52",
                    "hrv_ms": "45",
                    "sleep_duration_min": "420",
                    "sleep_score": "82",
                    "steps": "8500",
                    "active_energy_kcal": "650",
                    "training_readiness": "70",
                    "stress_score": "30",
                    "body_battery": "75",
                },
            ]),
        )
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        assert result.daily_facts_count == 1
        fact = db_session.get(DailyFact, date(2025, 6, 1))
        assert fact is not None
        assert fact.body_weight_kg == pytest.approx(75.5)
        assert fact.resting_hr_bpm == 52
        assert fact.has_garmin_data is True

    def test_multiple_days_write(self, db_session: Session):
        manifest = IngestionManifest(
            garmin_daily_csv=_garmin_daily_csv([
                {"date": "2025-06-01", "steps": "8000"},
                {"date": "2025-06-02", "steps": "9000"},
                {"date": "2025-06-03", "steps": "10000"},
            ]),
        )
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        assert result.daily_facts_count == 3
        count = db_session.scalar(select(func.count()).select_from(DailyFact))
        assert count == 3

    def test_multi_source_merge(self, db_session: Session):
        manifest = IngestionManifest(
            garmin_daily_csv=_garmin_daily_csv([
                {"date": "2025-06-01", "resting_hr_bpm": "52", "steps": "8500"},
            ]),
            apple_health_csv=_apple_health_csv([
                {"date": "2025-06-01", "resting_hr_bpm": "55", "steps": "9000"},
            ]),
            scale_csv=_scale_csv([
                {"date": "2025-06-01", "body_weight_kg": "75.0", "body_fat_pct": "14.8"},
            ]),
        )
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        assert result.daily_facts_count == 1
        fact = db_session.get(DailyFact, date(2025, 6, 1))
        assert fact is not None
        # Garmin wins for resting_hr (higher priority)
        assert fact.resting_hr_bpm == 52
        assert fact.has_garmin_data is True
        assert fact.has_apple_health_data is True
        assert fact.has_scale_data is True

    def test_upsert_semantics(self, db_session: Session):
        """Re-running ingestion should update, not duplicate."""
        csv_path = _garmin_daily_csv([
            {"date": "2025-06-01", "steps": "8000", "resting_hr_bpm": "52"},
        ])
        manifest = IngestionManifest(garmin_daily_csv=csv_path)

        run_ingestion(manifest, db_session)
        db_session.commit()

        # Run again with updated data
        csv_path2 = _garmin_daily_csv([
            {"date": "2025-06-01", "steps": "9000", "resting_hr_bpm": "53"},
        ])
        manifest2 = IngestionManifest(garmin_daily_csv=csv_path2)
        run_ingestion(manifest2, db_session)
        db_session.commit()

        count = db_session.scalar(select(func.count()).select_from(DailyFact))
        assert count == 1
        fact = db_session.get(DailyFact, date(2025, 6, 1))
        assert fact.steps == 9000
        assert fact.resting_hr_bpm == 53


# ---------------------------------------------------------------------------
# WorkoutFact persistence
# ---------------------------------------------------------------------------


class TestWorkoutFactPersistence:
    def test_single_workout_write(self, db_session: Session):
        manifest = IngestionManifest(
            garmin_activities_csv=_garmin_activities_csv([
                {
                    "source_workout_id": "g100",
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
            ]),
        )
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        assert result.workout_facts_count == 1
        workouts = db_session.scalars(select(WorkoutFact)).all()
        assert len(workouts) == 1
        w = workouts[0]
        assert w.source == "garmin"
        assert w.session_type == "run_easy"
        assert w.distance_km == pytest.approx(8.5)
        assert w.session_date == date(2025, 6, 1)

    def test_deduplication_across_sources(self, db_session: Session):
        manifest = IngestionManifest(
            garmin_activities_csv=_garmin_activities_csv([
                {
                    "source_workout_id": "g100",
                    "session_date": "2025-06-01",
                    "start_time": "2025-06-01 07:00:00",
                    "end_time": "2025-06-01 07:45:00",
                    "session_type": "Running",
                    "duration_min": "45",
                    "avg_hr_bpm": "145",
                    "max_hr_bpm": "165",
                    "distance_km": "8.5",
                    "avg_pace_sec_per_km": "318",
                    "elevation_gain_m": "",
                    "calories_kcal": "",
                    "training_load": "",
                    "route_type": "",
                    "cadence_spm": "",
                    "notes": "",
                },
            ]),
            strava_csv=_strava_csv([
                {
                    "source_workout_id": "s200",
                    "session_date": "2025-06-01",
                    "start_time": "2025-06-01 07:00:00",
                    "session_type": "Running",
                    "duration_min": "44",
                    "distance_km": "8.4",
                    "avg_hr_bpm": "146",
                    "max_hr_bpm": "166",
                    "avg_pace_sec_per_km": "314",
                    "elevation_gain_m": "",
                    "calories_kcal": "",
                    "notes": "",
                },
            ]),
        )
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        assert result.duplicates_found == 1
        workouts = db_session.scalars(select(WorkoutFact)).all()
        assert len(workouts) == 2

        non_dup = [w for w in workouts if not w.is_duplicate]
        dups = [w for w in workouts if w.is_duplicate]
        assert len(non_dup) == 1
        assert len(dups) == 1
        assert non_dup[0].source == "garmin"
        assert dups[0].source == "strava"


# ---------------------------------------------------------------------------
# ManualDailyInput persistence
# ---------------------------------------------------------------------------


class TestManualInputPersistence:
    def test_manual_input_write(self, db_session: Session):
        manifest = IngestionManifest(
            garmin_daily_csv=_garmin_daily_csv([
                {"date": "2025-06-01", "steps": "8000"},
            ]),
            manual_input_csv=_manual_csv([
                {
                    "date": "2025-06-01",
                    "left_knee_pain_score": "3",
                    "global_pain_score": "2",
                    "soreness_score": "4",
                    "mood_score": "7",
                    "motivation_score": "8",
                    "stress_score": "5",
                    "illness_flag": "false",
                    "note": "Knee felt stiff",
                },
            ]),
        )
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        assert result.manual_inputs_count == 1

        # Check ManualDailyInput record
        inputs = db_session.scalars(select(ManualDailyInput)).all()
        assert len(inputs) == 1
        assert inputs[0].left_knee_pain_score == pytest.approx(3.0)
        assert inputs[0].free_text_note == "Knee felt stiff"

        # Check overlay on DailyFact
        fact = db_session.get(DailyFact, date(2025, 6, 1))
        assert fact is not None
        assert fact.soreness_score == pytest.approx(4.0)
        assert fact.mood_score == pytest.approx(7.0)
        assert fact.has_manual_input is True

    def test_manual_input_creates_sparse_fact(self, db_session: Session):
        """Manual input for a date with no other data creates a sparse DailyFact."""
        manifest = IngestionManifest(
            manual_input_csv=_manual_csv([
                {
                    "date": "2025-07-15",
                    "left_knee_pain_score": "5",
                    "global_pain_score": "",
                    "soreness_score": "6",
                    "mood_score": "4",
                    "motivation_score": "3",
                    "stress_score": "7",
                    "illness_flag": "true",
                    "note": "Feeling sick",
                },
            ]),
        )
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        fact = db_session.get(DailyFact, date(2025, 7, 15))
        assert fact is not None
        assert fact.left_knee_pain_score == pytest.approx(5.0)
        assert fact.illness_flag is True
        assert fact.has_manual_input is True
        assert fact.has_garmin_data is False


# ---------------------------------------------------------------------------
# DailySourceCoverage persistence
# ---------------------------------------------------------------------------


class TestCoveragePersistence:
    def test_coverage_records_created(self, db_session: Session):
        manifest = IngestionManifest(
            garmin_daily_csv=_garmin_daily_csv([
                {"date": "2025-06-01", "steps": "8000"},
                {"date": "2025-06-03", "steps": "9000"},
            ]),
        )
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        # Should have coverage for 6/1, 6/2 (gap), and 6/3
        assert result.coverage_records_count == 3
        cov_records = db_session.scalars(select(DailySourceCoverage)).all()
        dates = sorted(c.date for c in cov_records)
        assert date(2025, 6, 2) in dates

        gap = next(c for c in cov_records if c.date == date(2025, 6, 2))
        assert gap.is_partial_day is True
        assert gap.coverage_note == "No data for this date"


# ---------------------------------------------------------------------------
# RawEvent lineage
# ---------------------------------------------------------------------------


class TestRawEventPersistence:
    def test_raw_events_created(self, db_session: Session):
        manifest = IngestionManifest(
            garmin_daily_csv=_garmin_daily_csv([
                {"date": "2025-06-01", "steps": "8000"},
            ]),
            garmin_activities_csv=_garmin_activities_csv([
                {
                    "source_workout_id": "g100",
                    "session_date": "2025-06-01",
                    "start_time": "",
                    "end_time": "",
                    "session_type": "Running",
                    "duration_min": "45",
                    "avg_hr_bpm": "145",
                    "max_hr_bpm": "165",
                    "distance_km": "8.5",
                    "avg_pace_sec_per_km": "",
                    "elevation_gain_m": "",
                    "calories_kcal": "",
                    "training_load": "",
                    "route_type": "",
                    "cadence_spm": "",
                    "notes": "",
                },
            ]),
        )
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        assert result.raw_events_count >= 2
        events = db_session.scalars(select(RawEvent)).all()
        types = {e.record_type for e in events}
        assert "daily" in types
        assert "workout" in types


# ---------------------------------------------------------------------------
# Full pipeline integration
# ---------------------------------------------------------------------------


class TestFullPipelineIntegration:
    def test_all_sources_combined(self, db_session: Session):
        """End-to-end: all source types parsed, normalized, and persisted."""
        manifest = IngestionManifest(
            garmin_daily_csv=_garmin_daily_csv([
                {
                    "date": "2025-06-01",
                    "resting_hr_bpm": "52",
                    "hrv_ms": "45",
                    "sleep_duration_min": "420",
                    "sleep_score": "82",
                    "steps": "8500",
                    "active_energy_kcal": "650",
                    "training_readiness": "70",
                    "stress_score": "30",
                    "body_battery": "75",
                },
                {
                    "date": "2025-06-02",
                    "resting_hr_bpm": "54",
                    "hrv_ms": "42",
                    "sleep_duration_min": "390",
                    "sleep_score": "75",
                    "steps": "10000",
                    "active_energy_kcal": "700",
                    "training_readiness": "65",
                    "stress_score": "35",
                    "body_battery": "60",
                },
            ]),
            garmin_activities_csv=_garmin_activities_csv([
                {
                    "source_workout_id": "g100",
                    "session_date": "2025-06-01",
                    "start_time": "2025-06-01 07:00:00",
                    "end_time": "2025-06-01 07:45:00",
                    "session_type": "Running",
                    "duration_min": "45",
                    "avg_hr_bpm": "145",
                    "max_hr_bpm": "165",
                    "distance_km": "8.5",
                    "avg_pace_sec_per_km": "318",
                    "elevation_gain_m": "100",
                    "calories_kcal": "400",
                    "training_load": "80",
                    "route_type": "road",
                    "cadence_spm": "172",
                    "notes": "",
                },
                {
                    "source_workout_id": "g101",
                    "session_date": "2025-06-02",
                    "start_time": "2025-06-02 17:00:00",
                    "end_time": "2025-06-02 18:00:00",
                    "session_type": "CrossFit",
                    "duration_min": "60",
                    "avg_hr_bpm": "150",
                    "max_hr_bpm": "178",
                    "distance_km": "",
                    "avg_pace_sec_per_km": "",
                    "elevation_gain_m": "",
                    "calories_kcal": "500",
                    "training_load": "90",
                    "route_type": "",
                    "cadence_spm": "",
                    "notes": "Back squats 5x5, then AMRAP burpees and wall balls",
                },
            ]),
            apple_health_csv=_apple_health_csv([
                {
                    "date": "2025-06-01",
                    "resting_hr_bpm": "55",
                    "hrv_ms": "43",
                    "sleep_duration_min": "415",
                    "steps": "8800",
                    "active_energy_kcal": "660",
                },
            ]),
            scale_csv=_scale_csv([
                {"date": "2025-06-01", "body_weight_kg": "75.2", "body_fat_pct": "14.9"},
                {"date": "2025-06-02", "body_weight_kg": "75.0", "body_fat_pct": "14.8"},
            ]),
            strava_csv=_strava_csv([
                {
                    "source_workout_id": "s200",
                    "session_date": "2025-06-01",
                    "start_time": "2025-06-01 07:00:00",
                    "session_type": "Running",
                    "duration_min": "44",
                    "distance_km": "8.4",
                    "avg_hr_bpm": "146",
                    "max_hr_bpm": "166",
                    "avg_pace_sec_per_km": "314",
                    "elevation_gain_m": "95",
                    "calories_kcal": "410",
                    "notes": "",
                },
            ]),
            manual_input_csv=_manual_csv([
                {
                    "date": "2025-06-01",
                    "left_knee_pain_score": "2",
                    "global_pain_score": "1",
                    "soreness_score": "3",
                    "mood_score": "8",
                    "motivation_score": "9",
                    "stress_score": "3",
                    "illness_flag": "false",
                    "note": "",
                },
            ]),
        )

        result = run_ingestion(manifest, db_session)
        db_session.commit()

        # Verify counts
        assert result.daily_facts_count == 2
        assert result.workout_facts_count == 3  # 2 garmin + 1 strava (1 dup)
        assert result.manual_inputs_count == 1
        assert result.duplicates_found == 1

        # Verify DailyFact data integrity
        fact1 = db_session.get(DailyFact, date(2025, 6, 1))
        assert fact1 is not None
        assert fact1.resting_hr_bpm == 52  # Garmin wins
        assert fact1.body_weight_kg == pytest.approx(75.2)  # scale
        assert fact1.soreness_score == pytest.approx(3.0)  # manual overlay
        assert fact1.has_garmin_data is True
        assert fact1.has_apple_health_data is True
        assert fact1.has_scale_data is True
        assert fact1.has_manual_input is True

        # Verify WorkoutFact integrity
        workouts = db_session.scalars(
            select(WorkoutFact).where(WorkoutFact.session_date == date(2025, 6, 1))
        ).all()
        assert len(workouts) == 2  # garmin run + strava dup
        garmin_run = next(w for w in workouts if w.source == "garmin")
        assert garmin_run.session_type == "run_easy"

        # Verify coverage
        cov = db_session.scalars(select(DailySourceCoverage)).all()
        assert len(cov) >= 2

        # Verify raw events
        raw_count = db_session.scalar(select(func.count()).select_from(RawEvent))
        assert raw_count >= 5  # 2 daily + 2 workouts + 1 apple + 1 scale + 1 manual

    def test_empty_pipeline(self, db_session: Session):
        """Running with no files produces zero records."""
        manifest = IngestionManifest()
        result = run_ingestion(manifest, db_session)
        db_session.commit()

        assert result.daily_facts_count == 0
        assert result.workout_facts_count == 0
        assert result.manual_inputs_count == 0
