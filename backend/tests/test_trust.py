"""Tests for the data trust layer.

Covers source coverage, field provenance, staleness detection,
decision confidence scoring, and provenance persistence.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from peakwise.models import Base, DailyFact, WorkoutFact
from peakwise.trust import (
    compute_decision_confidence,
    compute_field_provenance,
    compute_source_coverage,
    detect_stale_data,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_DATE = date(2025, 7, 7)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session


def _make_daily(d: date, **kwargs) -> DailyFact:
    defaults = {
        "body_weight_kg": 75.0,
        "resting_hr_bpm": 52,
        "hrv_ms": 48.0,
        "sleep_duration_min": 420.0,
        "sleep_score": 80.0,
        "steps": 8500,
        "soreness_score": 2.0,
        "mood_score": 7.0,
        "illness_flag": False,
        "has_garmin_data": True,
        "has_apple_health_data": False,
        "has_strava_data": False,
        "has_scale_data": True,
        "has_manual_input": True,
    }
    defaults.update(kwargs)
    return DailyFact(date=d, **defaults)


# ---------------------------------------------------------------------------
# Source coverage tests
# ---------------------------------------------------------------------------


class TestSourceCoverage:
    def test_full_coverage(self):
        fact = _make_daily(
            BASE_DATE,
            has_garmin_data=True,
            has_apple_health_data=True,
            has_strava_data=True,
            has_scale_data=True,
            has_manual_input=True,
        )
        coverage = compute_source_coverage(fact)
        assert coverage["garmin"] is True
        assert coverage["apple_health"] is True
        assert coverage["strava"] is True
        assert coverage["scale"] is True
        assert coverage["manual_input"] is True

    def test_partial_coverage(self):
        fact = _make_daily(
            BASE_DATE,
            has_garmin_data=True,
            has_apple_health_data=False,
            has_strava_data=False,
            has_scale_data=False,
            has_manual_input=False,
        )
        coverage = compute_source_coverage(fact)
        assert coverage["garmin"] is True
        assert coverage["apple_health"] is False
        assert coverage["strava"] is False
        assert coverage["scale"] is False
        assert coverage["manual_input"] is False

    def test_no_coverage(self):
        fact = _make_daily(
            BASE_DATE,
            has_garmin_data=False,
            has_apple_health_data=False,
            has_strava_data=False,
            has_scale_data=False,
            has_manual_input=False,
        )
        coverage = compute_source_coverage(fact)
        assert all(v is False for v in coverage.values())


# ---------------------------------------------------------------------------
# Field provenance tests
# ---------------------------------------------------------------------------


class TestFieldProvenance:
    def test_garmin_sleep_source(self):
        fact = _make_daily(BASE_DATE, has_garmin_data=True, sleep_duration_min=420.0)
        prov = compute_field_provenance(fact)
        assert prov["sleep"] == "garmin"

    def test_missing_sleep(self):
        fact = _make_daily(BASE_DATE, sleep_duration_min=None)
        prov = compute_field_provenance(fact)
        assert prov["sleep"] is None

    def test_garmin_hrv(self):
        fact = _make_daily(BASE_DATE, has_garmin_data=True, hrv_ms=48.0)
        prov = compute_field_provenance(fact)
        assert prov["hrv"] == "garmin"

    def test_missing_hrv(self):
        fact = _make_daily(BASE_DATE, hrv_ms=None)
        prov = compute_field_provenance(fact)
        assert prov["hrv"] is None

    def test_weight_from_scale(self):
        fact = _make_daily(BASE_DATE, body_weight_kg=75.0)
        prov = compute_field_provenance(fact)
        assert prov["weight"] == "scale"

    def test_missing_weight(self):
        fact = _make_daily(BASE_DATE, body_weight_kg=None)
        prov = compute_field_provenance(fact)
        assert prov["weight"] is None

    def test_strava_workout(self):
        fact = _make_daily(BASE_DATE, has_strava_data=True)
        prov = compute_field_provenance(fact)
        assert prov["workout"] == "strava"

    def test_garmin_workout_fallback(self):
        fact = _make_daily(BASE_DATE, has_strava_data=False, has_garmin_data=True)
        prov = compute_field_provenance(fact)
        assert prov["workout"] == "garmin"

    def test_no_workout_source(self):
        fact = _make_daily(BASE_DATE, has_strava_data=False, has_garmin_data=False)
        prov = compute_field_provenance(fact)
        assert prov["workout"] is None


# ---------------------------------------------------------------------------
# Staleness detection tests
# ---------------------------------------------------------------------------


class TestStalenessDetection:
    def test_fresh_recovery_data(self, db_session: Session):
        """HRV present today → recovery is fresh."""
        db_session.add(_make_daily(BASE_DATE, hrv_ms=48.0))
        db_session.flush()
        stale = detect_stale_data(BASE_DATE, db_session)
        assert stale["recovery"] is None

    def test_stale_recovery_data(self, db_session: Session):
        """HRV only 5 days ago → recovery is stale."""
        db_session.add(_make_daily(BASE_DATE - timedelta(days=5), hrv_ms=48.0))
        db_session.flush()
        stale = detect_stale_data(BASE_DATE, db_session)
        assert stale["recovery"] is not None

    def test_fresh_weight_data(self, db_session: Session):
        db_session.add(_make_daily(BASE_DATE, body_weight_kg=75.0))
        db_session.flush()
        stale = detect_stale_data(BASE_DATE, db_session)
        assert stale["weight"] is None

    def test_stale_weight_data(self, db_session: Session):
        """Weight only 10 days ago → stale."""
        db_session.add(_make_daily(BASE_DATE - timedelta(days=10), body_weight_kg=75.0))
        db_session.flush()
        stale = detect_stale_data(BASE_DATE, db_session)
        assert stale["weight"] is not None

    def test_workout_freshness(self, db_session: Session):
        """Recent workout exists → fresh."""
        import uuid

        db_session.add(
            WorkoutFact(
                workout_id=str(uuid.uuid4()),
                session_date=BASE_DATE,
                session_type="running",
                source="strava",
                is_duplicate=False,
            )
        )
        db_session.flush()
        stale = detect_stale_data(BASE_DATE, db_session)
        assert stale["workout"] is None


# ---------------------------------------------------------------------------
# Decision confidence tests
# ---------------------------------------------------------------------------


class TestDecisionConfidence:
    def test_no_fact_returns_zero(self, db_session: Session):
        score, level = compute_decision_confidence(None, BASE_DATE, db_session)
        assert score == 0.0
        assert level == "insufficient"

    def test_full_data_high_confidence(self, db_session: Session):
        """Full data coverage → high confidence."""
        fact = _make_daily(
            BASE_DATE,
            has_garmin_data=True,
            has_apple_health_data=True,
            has_strava_data=True,
            has_scale_data=True,
            has_manual_input=True,
            hrv_ms=48.0,
            resting_hr_bpm=52,
            sleep_duration_min=420.0,
            body_weight_kg=75.0,
            soreness_score=2.0,
            mood_score=7.0,
        )
        db_session.add(fact)
        db_session.flush()
        score, level = compute_decision_confidence(fact, BASE_DATE, db_session)
        assert score >= 75.0
        assert level == "high"

    def test_minimal_data_low_confidence(self, db_session: Session):
        """Only garmin, no other sources, missing key metrics."""
        fact = _make_daily(
            BASE_DATE,
            has_garmin_data=True,
            has_apple_health_data=False,
            has_strava_data=False,
            has_scale_data=False,
            has_manual_input=False,
            hrv_ms=None,
            resting_hr_bpm=None,
            sleep_duration_min=None,
            body_weight_kg=None,
            soreness_score=None,
            mood_score=None,
        )
        db_session.add(fact)
        db_session.flush()
        score, level = compute_decision_confidence(fact, BASE_DATE, db_session)
        assert score < 50.0
        assert level in ("low", "insufficient")

    def test_confidence_score_in_range(self, db_session: Session):
        fact = _make_daily(BASE_DATE)
        db_session.add(fact)
        db_session.flush()
        score, level = compute_decision_confidence(fact, BASE_DATE, db_session)
        assert 0.0 <= score <= 100.0
        assert level in ("high", "medium", "low", "insufficient")
