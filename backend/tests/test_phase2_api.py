"""Tests for Phase 2 API endpoints: debug and feedback.

Uses the same in-memory SQLite pattern as test_api.py.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from peakwise.api import create_app
from peakwise.api.deps import get_db
from peakwise.models import (
    Base,
    DailyFact,
    DailyFeatures,
    DailyFeedback,
    DailyReasonCode,
    DailyScoreComponent,
    DailyScoreSnapshot,
    RecommendationSnapshot,
    ScoreSnapshot,
    WorkoutFact,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_DATE = date(2025, 7, 7)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session


@pytest.fixture()
def client(db_session: Session):
    app = create_app()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _seed_daily_fact(session: Session, d: date, **kwargs) -> DailyFact:
    defaults = {
        "body_weight_kg": 78.0,
        "resting_hr_bpm": 58,
        "hrv_ms": 42.0,
        "sleep_duration_min": 460.0,
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
    record = DailyFact(date=d, **defaults)
    session.add(record)
    return record


def _seed_features(session: Session, d: date, **kwargs) -> DailyFeatures:
    defaults = {
        "hrv_7d_avg": 44.0,
        "hrv_vs_28d_pct": 3.0,
        "resting_hr_7d_avg": 57.0,
        "resting_hr_vs_28d_delta": 0.5,
        "sleep_7d_avg": 440.0,
        "sleep_debt_min": 80.0,
        "recent_load_3d": 200.0,
        "recent_load_7d": 420.0,
        "recovery_trend": 0.2,
        "weekly_km": 32.0,
        "rolling_4w_km": 125.0,
        "longest_run_last_7d_km": 16.0,
        "easy_pace_fixed_hr_sec_per_km": 355.0,
        "quality_sessions_last_14d": 3,
        "projected_hm_time_sec": 5700.0,
        "plan_adherence_pct": 0.80,
        "body_weight_7d_avg": 78.0,
        "body_weight_28d_slope": -0.01,
        "sleep_consistency_score": 82.0,
        "pain_free_days_last_14d": 12,
        "mood_trend": 0.3,
        "stress_trend": -0.1,
        "steps_consistency_score": 75.0,
        "hard_day_count_7d": 3,
        "lower_body_crossfit_density_7d": 0.3,
        "long_run_protection_score": 80.0,
        "interference_risk_score": 25.0,
    }
    defaults.update(kwargs)
    record = DailyFeatures(date=d, **defaults)
    session.add(record)
    return record


def _seed_score(session: Session, d: date, **kwargs) -> ScoreSnapshot:
    defaults = {
        "score_engine_version": "1.0.0",
        "recovery_score": 72.0,
        "race_readiness_score": 65.0,
        "general_health_score": 78.0,
        "load_balance_score": 68.0,
        "subcomponents_json": {
            "recovery": {"hrv_component": 75.0, "sleep_component": 70.0},
        },
        "warnings_json": {
            "knee_pain_warning": False,
            "illness_warning": False,
            "sleep_debt_warning": False,
            "hrv_suppression_warning": False,
            "overload_warning": False,
        },
    }
    defaults.update(kwargs)
    record = ScoreSnapshot(date=d, **defaults)
    session.add(record)
    return record


def _seed_recommendation(session: Session, d: date) -> RecommendationSnapshot:
    record = RecommendationSnapshot(
        date=d,
        recommendation_engine_version="1.0.0",
        mode="train_as_planned",
        recommended_action="Follow today's plan",
        reason_codes_json=["recovery_acceptable"],
        risk_flags_json=[],
    )
    session.add(record)
    return record


def _seed_full_day(session: Session, d: date) -> None:
    _seed_daily_fact(session, d)
    _seed_features(session, d)
    _seed_score(session, d)
    _seed_recommendation(session, d)


# ---------------------------------------------------------------------------
# Debug endpoint tests
# ---------------------------------------------------------------------------


class TestDebugEndpoint:
    def test_debug_day_success(self, client: TestClient, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        db_session.commit()

        resp = client.get(f"/api/debug/day?date={BASE_DATE}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == str(BASE_DATE)
        assert data["daily_facts"] is not None
        assert data["features"] is not None
        assert data["confidence"]["level"] in ("high", "medium", "low", "insufficient")
        assert 0.0 <= data["confidence"]["score"] <= 100.0
        assert isinstance(data["source_coverage"], dict)
        assert isinstance(data["field_provenance"], dict)
        assert isinstance(data["workouts_in_lookback"], list)

    def test_debug_day_no_data(self, client: TestClient, db_session: Session):
        resp = client.get(f"/api/debug/day?date={BASE_DATE}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["daily_facts"] is None
        assert data["features"] is None
        assert data["confidence"]["level"] == "insufficient"

    def test_debug_day_includes_workouts(self, client: TestClient, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        db_session.add(
            WorkoutFact(
                workout_id=str(uuid.uuid4()),
                session_date=BASE_DATE,
                session_type="running",
                source="strava",
                is_duplicate=False,
            )
        )
        db_session.commit()

        resp = client.get(f"/api/debug/day?date={BASE_DATE}")
        data = resp.json()
        assert len(data["workouts_in_lookback"]) >= 1


# ---------------------------------------------------------------------------
# Feedback endpoint tests
# ---------------------------------------------------------------------------


class TestFeedbackEndpoint:
    def test_submit_feedback(self, client: TestClient, db_session: Session):
        resp = client.post(
            "/api/feedback",
            json={
                "date": str(BASE_DATE),
                "rating": "accurate",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["date"] == str(BASE_DATE)
        assert data["rating"] == "accurate"
        assert data["created"] is True

    def test_submit_feedback_with_note(self, client: TestClient, db_session: Session):
        resp = client.post(
            "/api/feedback",
            json={
                "date": str(BASE_DATE),
                "rating": "too_hard",
                "free_text_note": "Legs were very tired from yesterday's CrossFit",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] == "too_hard"

        # Verify persisted
        fb = db_session.query(DailyFeedback).filter_by(date=BASE_DATE).first()
        assert fb is not None
        assert fb.free_text_note == "Legs were very tired from yesterday's CrossFit"

    def test_update_feedback(self, client: TestClient, db_session: Session):
        """Submitting feedback for the same date updates the rating."""
        client.post(
            "/api/feedback",
            json={"date": str(BASE_DATE), "rating": "accurate"},
        )
        resp = client.post(
            "/api/feedback",
            json={"date": str(BASE_DATE), "rating": "too_easy"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] == "too_easy"
        assert data["created"] is False

    def test_get_feedback(self, client: TestClient, db_session: Session):
        # Submit a few feedback entries
        for i, rating in enumerate(["accurate", "too_hard", "too_easy"]):
            d = BASE_DATE - timedelta(days=i)
            client.post("/api/feedback", json={"date": str(d), "rating": rating})

        resp = client.get("/api/feedback")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_invalid_rating(self, client: TestClient):
        resp = client.post(
            "/api/feedback",
            json={"date": str(BASE_DATE), "rating": "invalid_rating"},
        )
        assert resp.status_code == 422
