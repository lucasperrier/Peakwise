"""Tests for score breakdown persistence."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from peakwise.models import (
    Base,
    DailyReasonCode,
    DailyScoreComponent,
    DailyScoreSnapshot,
    RecommendationSnapshot,
    ScoreSnapshot,
)
from peakwise.scoring.breakdowns import persist_score_breakdown

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


def _make_score(d: date) -> ScoreSnapshot:
    return ScoreSnapshot(
        date=d,
        score_engine_version="1.0.0",
        recovery_score=72.0,
        race_readiness_score=65.0,
        general_health_score=80.0,
        load_balance_score=70.0,
        subcomponents_json={
            "recovery": {
                "hrv_component": 75.0,
                "resting_hr_component": 80.0,
                "sleep_component": 70.0,
                "load_component": 60.0,
                "soreness_component": 85.0,
                "illness_component": 100.0,
                "subjective_fatigue_component": 65.0,
                "device_readiness_component": 70.0,
            },
            "race_readiness": {
                "weekly_volume_component": 70.0,
                "long_run_component": 60.0,
                "easy_efficiency_component": 65.0,
                "quality_completion_component": 80.0,
                "projection_component": 55.0,
                "plan_adherence_component": 75.0,
                "trend_component": 50.0,
            },
            "general_health": {
                "sleep_consistency_component": 85.0,
                "weight_trend_component": 90.0,
                "resting_hr_trend_component": 80.0,
                "hrv_stability_component": 75.0,
                "steps_component": 70.0,
                "pain_component": 95.0,
                "mood_component": 80.0,
                "stress_component": 75.0,
            },
            "load_balance": {
                "hard_day_density_component": 80.0,
                "lower_body_density_component": 70.0,
                "session_spacing_component": 75.0,
                "long_run_protection_component": 60.0,
                "run_distribution_component": 65.0,
                "interference_component": 55.0,
            },
        },
        warnings_json={
            "knee_pain_warning": False,
            "illness_warning": False,
            "sleep_debt_warning": True,
            "hrv_suppression_warning": False,
            "overload_warning": False,
        },
    )


def _make_rec(d: date) -> RecommendationSnapshot:
    return RecommendationSnapshot(
        date=d,
        recommendation_engine_version="1.0.0",
        mode="train_as_planned",
        recommended_action="quality_run",
        reason_codes_json=["recovery_acceptable", "sleep_debt_high"],
        risk_flags_json=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPersistScoreBreakdown:
    def test_creates_snapshot(self, db_session: Session):
        score = _make_score(BASE_DATE)
        rec = _make_rec(BASE_DATE)
        dss = persist_score_breakdown(BASE_DATE, score, rec, 72.5, "medium", db_session)
        assert dss.date == BASE_DATE
        assert dss.recovery_score == 72.0
        assert dss.recommendation_mode == "train_as_planned"
        assert dss.confidence_level == "medium"
        assert dss.decision_confidence_score == 72.5

    def test_creates_components(self, db_session: Session):
        score = _make_score(BASE_DATE)
        persist_score_breakdown(BASE_DATE, score, None, 60.0, "medium", db_session)
        components = db_session.scalars(
            select(DailyScoreComponent).where(DailyScoreComponent.date == BASE_DATE)
        ).all()
        # 8 recovery + 7 race_readiness + 8 general_health + 6 load_balance = 29
        assert len(components) == 29

    def test_component_directions(self, db_session: Session):
        score = _make_score(BASE_DATE)
        persist_score_breakdown(BASE_DATE, score, None, 60.0, "medium", db_session)
        components = db_session.scalars(
            select(DailyScoreComponent).where(DailyScoreComponent.date == BASE_DATE)
        ).all()
        directions = {c.direction for c in components}
        assert directions.issubset({"positive", "negative", "neutral"})

    def test_creates_reason_codes_from_warnings(self, db_session: Session):
        score = _make_score(BASE_DATE)
        persist_score_breakdown(BASE_DATE, score, None, 60.0, "medium", db_session)
        codes = db_session.scalars(
            select(DailyReasonCode).where(DailyReasonCode.date == BASE_DATE)
        ).all()
        code_names = [c.code for c in codes]
        assert "sleep_debt_high" in code_names

    def test_creates_reason_codes_from_recommendation(self, db_session: Session):
        score = _make_score(BASE_DATE)
        rec = _make_rec(BASE_DATE)
        persist_score_breakdown(BASE_DATE, score, rec, 60.0, "medium", db_session)
        codes = db_session.scalars(
            select(DailyReasonCode).where(DailyReasonCode.date == BASE_DATE)
        ).all()
        code_names = [c.code for c in codes]
        assert "recovery_acceptable" in code_names

    def test_low_confidence_adds_data_coverage_code(self, db_session: Session):
        score = _make_score(BASE_DATE)
        persist_score_breakdown(BASE_DATE, score, None, 20.0, "low", db_session)
        codes = db_session.scalars(
            select(DailyReasonCode).where(DailyReasonCode.date == BASE_DATE)
        ).all()
        code_names = [c.code for c in codes]
        assert "data_coverage_low" in code_names

    def test_high_confidence_no_data_coverage_code(self, db_session: Session):
        score = _make_score(BASE_DATE)
        persist_score_breakdown(BASE_DATE, score, None, 80.0, "high", db_session)
        codes = db_session.scalars(
            select(DailyReasonCode).where(DailyReasonCode.date == BASE_DATE)
        ).all()
        code_names = [c.code for c in codes]
        assert "data_coverage_low" not in code_names

    def test_upsert_clears_old_components(self, db_session: Session):
        """Re-running for the same date replaces old components."""
        score = _make_score(BASE_DATE)
        persist_score_breakdown(BASE_DATE, score, None, 60.0, "medium", db_session)
        db_session.commit()

        count1 = len(
            db_session.scalars(
                select(DailyScoreComponent).where(DailyScoreComponent.date == BASE_DATE)
            ).all()
        )

        persist_score_breakdown(BASE_DATE, score, None, 60.0, "medium", db_session)
        db_session.commit()

        count2 = len(
            db_session.scalars(
                select(DailyScoreComponent).where(DailyScoreComponent.date == BASE_DATE)
            ).all()
        )
        assert count1 == count2

    def test_no_recommendation(self, db_session: Session):
        """Works fine without a recommendation snapshot."""
        score = _make_score(BASE_DATE)
        dss = persist_score_breakdown(BASE_DATE, score, None, 50.0, "medium", db_session)
        assert dss.recommendation_mode is None
        assert dss.recommended_action is None
