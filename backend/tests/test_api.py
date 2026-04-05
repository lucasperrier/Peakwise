"""Contract tests for Phase 6 — API endpoints.

Validates that all endpoints return typed response payloads matching
the defined schemas. Uses an in-memory SQLite database with seeded data.
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
from peakwise.api.schemas import (
    HealthResponse,
    ManualInputResponse,
    RunningResponse,
    StrengthResponse,
    TodayResponse,
    WeeklyReviewResponse,
)
from peakwise.models import (
    Base,
    DailyFact,
    DailyFeatures,
    ManualDailyInput,
    RecommendationSnapshot,
    ScoreSnapshot,
    WorkoutFact,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_DATE = date(2025, 7, 7)  # Monday


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
    }
    defaults.update(kwargs)
    record = DailyFact(date=d, **defaults)
    session.add(record)
    return record


def _seed_features(session: Session, d: date, **kwargs) -> DailyFeatures:
    defaults = {
        "hrv_7d_avg": 42.0,
        "hrv_vs_28d_pct": 5.0,
        "resting_hr_7d_avg": 58.0,
        "resting_hr_vs_28d_delta": -1.0,
        "sleep_7d_avg": 460.0,
        "sleep_debt_min": 80.0,
        "recent_load_3d": 200.0,
        "recent_load_7d": 450.0,
        "recovery_trend": 0.5,
        "weekly_km": 35.0,
        "rolling_4w_km": 140.0,
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
            "recovery": {"hrv": 75.0, "sleep": 70.0},
            "race_readiness": {"weekly_volume": 70.0},
            "general_health": {"sleep_consistency": 82.0},
            "load_balance": {"hard_day_density": 80.0},
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


def _seed_recommendation(session: Session, d: date, **kwargs) -> RecommendationSnapshot:
    defaults = {
        "recommendation_engine_version": "1.0.0",
        "mode": "train_as_planned",
        "recommended_action": "Follow today's plan at normal intensity",
        "intensity_modifier": None,
        "duration_modifier": None,
        "reason_codes_json": ["recovery_acceptable"],
        "next_best_alternative": "Reduce intensity if fatigue accumulates",
        "risk_flags_json": [],
    }
    defaults.update(kwargs)
    record = RecommendationSnapshot(date=d, **defaults)
    session.add(record)
    return record


def _seed_workout(
    session: Session,
    d: date,
    session_type: str = "crossfit",
    **kwargs,
) -> WorkoutFact:
    defaults = {
        "source": "garmin",
        "session_date": d,
        "session_type": session_type,
        "duration_min": 55.0,
        "training_load": 120.0,
        "is_duplicate": False,
    }
    defaults.update(kwargs)
    record = WorkoutFact(workout_id=str(uuid.uuid4()), **defaults)
    session.add(record)
    return record


def _seed_full_day(session: Session, d: date) -> None:
    _seed_daily_fact(session, d)
    _seed_features(session, d)
    _seed_score(session, d)
    _seed_recommendation(session, d)


def _seed_two_weeks(session: Session) -> None:
    """Seed 14 days of data ending on BASE_DATE (Monday)."""
    for i in range(14):
        d = BASE_DATE - timedelta(days=13 - i)
        _seed_full_day(session, d)
        if i % 3 == 0:
            _seed_workout(session, d, "crossfit")
        if i % 2 == 0:
            _seed_workout(session, d, "run_easy", distance_km=8.0)
    session.flush()


# ---------------------------------------------------------------------------
# GET /api/today
# ---------------------------------------------------------------------------


class TestTodayEndpoint:
    def test_returns_recommendation_and_scores(self, client: TestClient, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        db_session.flush()

        resp = client.get("/api/today", params={"date": str(BASE_DATE)})
        assert resp.status_code == 200

        data = TodayResponse.model_validate(resp.json())
        assert data.date == BASE_DATE
        assert data.recommendation is not None
        assert data.recommendation.mode == "train_as_planned"
        assert data.recommendation.recommended_action is not None
        assert len(data.recommendation.reason_codes) > 0
        assert data.scores is not None
        assert data.scores.recovery == 72.0
        assert data.scores.race_readiness == 65.0
        assert data.subcomponents is not None
        assert data.warnings is not None

    def test_missing_date_returns_empty_payload(self, client: TestClient):
        resp = client.get("/api/today", params={"date": "2099-01-01"})
        assert resp.status_code == 200

        data = TodayResponse.model_validate(resp.json())
        assert data.recommendation is None
        assert data.scores is None

    def test_scores_without_recommendation(self, client: TestClient, db_session: Session):
        _seed_score(db_session, BASE_DATE)
        db_session.flush()

        resp = client.get("/api/today", params={"date": str(BASE_DATE)})
        assert resp.status_code == 200

        data = TodayResponse.model_validate(resp.json())
        assert data.scores is not None
        assert data.recommendation is None


# ---------------------------------------------------------------------------
# GET /api/running
# ---------------------------------------------------------------------------


class TestRunningEndpoint:
    def test_returns_current_and_trend(self, client: TestClient, db_session: Session):
        _seed_two_weeks(db_session)

        resp = client.get("/api/running", params={"date": str(BASE_DATE), "days": "14"})
        assert resp.status_code == 200

        data = RunningResponse.model_validate(resp.json())
        assert data.date == BASE_DATE
        assert data.current is not None
        assert data.current.weekly_km == 35.0
        assert data.race_readiness_score == 65.0
        assert len(data.trend) == 14

    def test_empty_trend(self, client: TestClient):
        resp = client.get("/api/running", params={"date": "2099-01-01"})
        assert resp.status_code == 200

        data = RunningResponse.model_validate(resp.json())
        assert data.current is None
        assert data.trend == []

    def test_days_parameter_bounds(self, client: TestClient):
        resp = client.get("/api/running", params={"date": str(BASE_DATE), "days": "0"})
        assert resp.status_code == 422  # validation error


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_returns_current_and_trend(self, client: TestClient, db_session: Session):
        _seed_two_weeks(db_session)

        resp = client.get("/api/health", params={"date": str(BASE_DATE), "days": "14"})
        assert resp.status_code == 200

        data = HealthResponse.model_validate(resp.json())
        assert data.date == BASE_DATE
        assert data.current is not None
        assert data.current.hrv_7d_avg == 42.0
        assert data.current.sleep_debt_min == 80.0
        assert data.general_health_score == 78.0
        assert len(data.trend) == 14

    def test_empty_data(self, client: TestClient):
        resp = client.get("/api/health", params={"date": "2099-01-01"})
        assert resp.status_code == 200

        data = HealthResponse.model_validate(resp.json())
        assert data.current is None
        assert data.general_health_score is None


# ---------------------------------------------------------------------------
# GET /api/strength
# ---------------------------------------------------------------------------


class TestStrengthEndpoint:
    def test_returns_workouts_and_trend(self, client: TestClient, db_session: Session):
        _seed_two_weeks(db_session)

        resp = client.get("/api/strength", params={"date": str(BASE_DATE), "days": "14"})
        assert resp.status_code == 200

        data = StrengthResponse.model_validate(resp.json())
        assert data.date == BASE_DATE
        assert data.current is not None
        assert data.current.hard_day_count_7d == 3
        assert data.load_balance_score == 68.0
        assert len(data.trend) == 14
        # Only crossfit/strength workouts should appear
        for w in data.recent_workouts:
            assert w.session_type in {"crossfit", "strength"}

    def test_empty_data(self, client: TestClient):
        resp = client.get("/api/strength", params={"date": "2099-01-01"})
        assert resp.status_code == 200

        data = StrengthResponse.model_validate(resp.json())
        assert data.current is None
        assert data.recent_workouts == []


# ---------------------------------------------------------------------------
# GET /api/weekly-review
# ---------------------------------------------------------------------------


class TestWeeklyReviewEndpoint:
    def test_returns_two_weeks_comparison(self, client: TestClient, db_session: Session):
        _seed_two_weeks(db_session)

        resp = client.get("/api/weekly-review", params={"date": str(BASE_DATE)})
        assert resp.status_code == 200

        data = WeeklyReviewResponse.model_validate(resp.json())
        assert data.current_week.start_date == BASE_DATE  # Monday
        assert data.previous_week is not None
        assert data.score_changes is not None
        assert isinstance(data.flags, list)

    def test_empty_weeks(self, client: TestClient):
        resp = client.get("/api/weekly-review", params={"date": "2099-01-01"})
        assert resp.status_code == 200

        data = WeeklyReviewResponse.model_validate(resp.json())
        assert data.current_week.workout_count == 0

    def test_flag_sleep_below_7h(self, client: TestClient, db_session: Session):
        # Seed a week with low sleep
        monday = BASE_DATE
        for i in range(7):
            d = monday + timedelta(days=i)
            _seed_daily_fact(db_session, d, sleep_duration_min=380.0)
            _seed_features(db_session, d)
            _seed_score(db_session, d)
        db_session.flush()

        resp = client.get("/api/weekly-review", params={"date": str(monday)})
        data = WeeklyReviewResponse.model_validate(resp.json())
        assert "sleep_below_7h" in data.flags


# ---------------------------------------------------------------------------
# POST /api/manual-input
# ---------------------------------------------------------------------------


class TestManualInputEndpoint:
    def test_create_new_input(self, client: TestClient, db_session: Session):
        payload = {
            "date": str(BASE_DATE),
            "left_knee_pain_score": 2.0,
            "soreness_score": 3.0,
            "mood_score": 7.0,
            "illness_flag": False,
        }

        resp = client.post("/api/manual-input", json=payload)
        assert resp.status_code == 201

        data = ManualInputResponse.model_validate(resp.json())
        assert data.date == BASE_DATE
        assert data.created is True
        assert data.id > 0

        # Verify daily_fact was updated
        daily: DailyFact | None = db_session.get(DailyFact, BASE_DATE)
        assert daily is not None
        assert daily.left_knee_pain_score == 2.0
        assert daily.has_manual_input is True

    def test_update_existing_input(self, client: TestClient, db_session: Session):
        # First create
        payload = {
            "date": str(BASE_DATE),
            "mood_score": 6.0,
        }
        resp1 = client.post("/api/manual-input", json=payload)
        assert resp1.status_code == 201
        assert resp1.json()["created"] is True

        # Then update
        payload2 = {
            "date": str(BASE_DATE),
            "mood_score": 8.0,
            "soreness_score": 4.0,
        }
        resp2 = client.post("/api/manual-input", json=payload2)
        assert resp2.status_code == 201
        data = ManualInputResponse.model_validate(resp2.json())
        assert data.created is False

        # Check the record was updated
        record: ManualDailyInput | None = db_session.get(ManualDailyInput, data.id)
        assert record is not None
        assert record.mood_score == 8.0
        assert record.soreness_score == 4.0

    def test_validation_rejects_out_of_range(self, client: TestClient):
        payload = {
            "date": str(BASE_DATE),
            "mood_score": 15.0,  # exceeds max of 10
        }
        resp = client.post("/api/manual-input", json=payload)
        assert resp.status_code == 422

    def test_validation_rejects_missing_date(self, client: TestClient):
        payload = {"mood_score": 7.0}
        resp = client.post("/api/manual-input", json=payload)
        assert resp.status_code == 422

    def test_free_text_note_stored(self, client: TestClient, db_session: Session):
        payload = {
            "date": str(BASE_DATE),
            "free_text_note": "Feeling good after rest day",
        }
        resp = client.post("/api/manual-input", json=payload)
        assert resp.status_code == 201

        record_id = resp.json()["id"]
        record: ManualDailyInput | None = db_session.get(ManualDailyInput, record_id)
        assert record is not None
        assert record.free_text_note == "Feeling good after rest day"


# ---------------------------------------------------------------------------
# Response schema validation
# ---------------------------------------------------------------------------


class TestResponseSchemaContracts:
    """Verify that all response payloads can be validated by their Pydantic models."""

    def test_today_schema_fields(self, client: TestClient, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        db_session.flush()

        resp = client.get("/api/today", params={"date": str(BASE_DATE)})
        body = resp.json()

        # All top-level keys must be present
        assert "date" in body
        assert "recommendation" in body
        assert "scores" in body
        assert "subcomponents" in body
        assert "warnings" in body

        # Recommendation sub-fields
        rec = body["recommendation"]
        assert "mode" in rec
        assert "recommended_action" in rec
        assert "reason_codes" in rec
        assert "risk_flags" in rec

    def test_running_schema_fields(self, client: TestClient, db_session: Session):
        _seed_features(db_session, BASE_DATE)
        _seed_score(db_session, BASE_DATE)
        db_session.flush()

        resp = client.get("/api/running", params={"date": str(BASE_DATE)})
        body = resp.json()

        assert "date" in body
        assert "current" in body
        assert "race_readiness_score" in body
        assert "trend" in body

        current = body["current"]
        for field in [
            "weekly_km",
            "rolling_4w_km",
            "longest_run_last_7d_km",
            "easy_pace_fixed_hr_sec_per_km",
            "quality_sessions_last_14d",
            "projected_hm_time_sec",
            "plan_adherence_pct",
        ]:
            assert field in current

    def test_health_schema_fields(self, client: TestClient, db_session: Session):
        _seed_features(db_session, BASE_DATE)
        _seed_score(db_session, BASE_DATE)
        db_session.flush()

        resp = client.get("/api/health", params={"date": str(BASE_DATE)})
        body = resp.json()

        assert "date" in body
        assert "current" in body
        assert "general_health_score" in body
        assert "trend" in body

    def test_strength_schema_fields(self, client: TestClient, db_session: Session):
        _seed_features(db_session, BASE_DATE)
        _seed_score(db_session, BASE_DATE)
        db_session.flush()

        resp = client.get("/api/strength", params={"date": str(BASE_DATE)})
        body = resp.json()

        assert "date" in body
        assert "current" in body
        assert "load_balance_score" in body
        assert "recent_workouts" in body
        assert "trend" in body

    def test_weekly_review_schema_fields(self, client: TestClient, db_session: Session):
        _seed_two_weeks(db_session)

        resp = client.get("/api/weekly-review", params={"date": str(BASE_DATE)})
        body = resp.json()

        assert "current_week" in body
        assert "previous_week" in body
        assert "score_changes" in body
        assert "flags" in body

        week = body["current_week"]
        for field in [
            "start_date",
            "end_date",
            "avg_recovery_score",
            "total_km",
            "workout_count",
        ]:
            assert field in week
