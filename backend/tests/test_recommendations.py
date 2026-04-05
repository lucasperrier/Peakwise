"""Tests for Phase 5 — recommendation engine.

Covers rule-based mode selection, warning overrides, reason codes,
next-best alternatives, and the recommendation pipeline.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from peakwise.models import (
    Base,
    RecommendationMode,
    RecommendationSnapshot,
    ScoreSnapshot,
)
from peakwise.recommendations.pipeline import (
    RecommendationPipelineResult,
    compute_recommendation_for_date,
    run_recommendation_pipeline,
)
from peakwise.recommendations.rules import (
    RecommendationResult,
    determine_recommendation,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_DATE = date(2025, 7, 7)

NO_WARNINGS: dict[str, bool] = {
    "knee_pain_warning": False,
    "illness_warning": False,
    "sleep_debt_warning": False,
    "hrv_suppression_warning": False,
    "overload_warning": False,
}


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session


def _make_score(
    d: date,
    *,
    recovery: float = 70.0,
    race_readiness: float = 65.0,
    health: float = 75.0,
    load_balance: float = 70.0,
    warnings: dict[str, bool] | None = None,
) -> ScoreSnapshot:
    return ScoreSnapshot(
        date=d,
        score_engine_version="1.0.0",
        recovery_score=recovery,
        race_readiness_score=race_readiness,
        general_health_score=health,
        load_balance_score=load_balance,
        subcomponents_json={},
        warnings_json=warnings or dict(NO_WARNINGS),
    )


# ---------------------------------------------------------------------------
# Mode selection from recovery score
# ---------------------------------------------------------------------------


class TestRecoveryToMode:
    def test_full_go_high_recovery(self):
        """Recovery >= 80 with no warnings → full_go."""
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.full_go
        assert "recovery_high" in result.reason_codes

    def test_train_as_planned_acceptable_recovery(self):
        """Recovery 65-79 → train_as_planned."""
        result = determine_recommendation(70.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.train_as_planned
        assert "recovery_acceptable" in result.reason_codes

    def test_reduce_intensity_moderate_recovery(self):
        """Recovery 50-64 → reduce_intensity."""
        result = determine_recommendation(55.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.reduce_intensity
        assert "recovery_moderate" in result.reason_codes

    def test_recovery_focused_low_recovery(self):
        """Recovery 35-49 → recovery_focused."""
        result = determine_recommendation(40.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.recovery_focused
        assert "recovery_low" in result.reason_codes

    def test_full_rest_very_low_recovery(self):
        """Recovery < 35 → full_rest."""
        result = determine_recommendation(20.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.full_rest
        assert "recovery_very_low" in result.reason_codes

    def test_boundary_full_go_exact(self):
        """Recovery exactly 80 → full_go."""
        result = determine_recommendation(80.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.full_go


# ---------------------------------------------------------------------------
# Secondary score caps
# ---------------------------------------------------------------------------


class TestSecondaryScoreCaps:
    def test_low_load_balance_caps_to_reduce(self):
        """Load balance < 50 caps mode at reduce_intensity."""
        result = determine_recommendation(85.0, 70.0, 75.0, 40.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.reduce_intensity
        assert "load_balance_poor" in result.reason_codes

    def test_low_health_caps_to_reduce(self):
        """Health < 45 caps mode at reduce_intensity."""
        result = determine_recommendation(85.0, 70.0, 40.0, 75.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.reduce_intensity
        assert "health_caution" in result.reason_codes

    def test_both_low_caps_to_reduce(self):
        """Both health and load-balance low → still reduce_intensity, both codes."""
        result = determine_recommendation(85.0, 70.0, 40.0, 40.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.reduce_intensity
        assert "load_balance_poor" in result.reason_codes
        assert "health_caution" in result.reason_codes

    def test_low_recovery_already_below_cap(self):
        """Recovery already at full_rest, secondary caps don't loosen it."""
        result = determine_recommendation(20.0, 70.0, 40.0, 40.0, dict(NO_WARNINGS))
        assert result.mode == RecommendationMode.full_rest


# ---------------------------------------------------------------------------
# Warning overrides
# ---------------------------------------------------------------------------


class TestWarningOverrides:
    def test_illness_caps_at_recovery_focused(self):
        """Illness warning → capped at recovery_focused."""
        warnings = {**NO_WARNINGS, "illness_warning": True}
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, warnings)
        assert result.mode == RecommendationMode.recovery_focused
        assert "illness_active" in result.reason_codes
        assert "illness_warning" in result.risk_flags

    def test_knee_pain_caps_at_injury_watch(self):
        """Knee pain warning → capped at injury_watch."""
        warnings = {**NO_WARNINGS, "knee_pain_warning": True}
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, warnings)
        assert result.mode == RecommendationMode.injury_watch
        assert "knee_pain_elevated" in result.reason_codes
        assert "knee_pain_warning" in result.risk_flags

    def test_overload_caps_at_reduce_intensity(self):
        """Overload warning → capped at reduce_intensity."""
        warnings = {**NO_WARNINGS, "overload_warning": True}
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, warnings)
        assert result.mode == RecommendationMode.reduce_intensity
        assert "overload_detected" in result.reason_codes

    def test_sleep_debt_caps_at_reduce_intensity(self):
        """Sleep debt warning → capped at reduce_intensity."""
        warnings = {**NO_WARNINGS, "sleep_debt_warning": True}
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, warnings)
        assert result.mode == RecommendationMode.reduce_intensity
        assert "sleep_debt_high" in result.reason_codes

    def test_hrv_suppression_caps_at_reduce_intensity(self):
        """HRV suppression warning → capped at reduce_intensity."""
        warnings = {**NO_WARNINGS, "hrv_suppression_warning": True}
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, warnings)
        assert result.mode == RecommendationMode.reduce_intensity
        assert "hrv_suppressed" in result.reason_codes

    def test_multiple_warnings_most_restrictive_wins(self):
        """Knee pain + illness → injury_watch (more restrictive than recovery_focused)."""
        warnings = {
            **NO_WARNINGS,
            "knee_pain_warning": True,
            "illness_warning": True,
        }
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, warnings)
        assert result.mode == RecommendationMode.injury_watch
        assert "knee_pain_elevated" in result.reason_codes
        assert "illness_active" in result.reason_codes

    def test_warning_doesnt_loosen_already_restrictive(self):
        """Recovery at full_rest + overload warning → stays full_rest."""
        warnings = {**NO_WARNINGS, "overload_warning": True}
        result = determine_recommendation(20.0, 70.0, 75.0, 75.0, warnings)
        assert result.mode == RecommendationMode.full_rest


# ---------------------------------------------------------------------------
# Reason codes and result shape
# ---------------------------------------------------------------------------


class TestReasonCodesAndShape:
    def test_result_has_all_fields(self):
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert isinstance(result, RecommendationResult)
        assert isinstance(result.mode, RecommendationMode)
        assert isinstance(result.recommended_action, str)
        assert isinstance(result.reason_codes, list)
        assert isinstance(result.risk_flags, list)
        assert result.next_best_alternative is not None

    def test_full_go_no_modifiers(self):
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.intensity_modifier is None
        assert result.duration_modifier is None

    def test_reduce_intensity_has_modifiers(self):
        result = determine_recommendation(55.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.intensity_modifier is not None
        assert result.duration_modifier is not None

    def test_no_warnings_empty_risk_flags(self):
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.risk_flags == []

    def test_reason_codes_accumulate(self):
        """Multiple caps produce multiple reason codes."""
        warnings = {**NO_WARNINGS, "overload_warning": True, "sleep_debt_warning": True}
        result = determine_recommendation(85.0, 70.0, 40.0, 40.0, warnings)
        assert len(result.reason_codes) >= 4  # recovery + health + load_balance + warnings


# ---------------------------------------------------------------------------
# Next-best alternative
# ---------------------------------------------------------------------------


class TestNextBestAlternative:
    def test_full_go_alternative(self):
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.next_best_alternative is not None
        assert "fatigue" in result.next_best_alternative.lower()

    def test_full_rest_alternative(self):
        result = determine_recommendation(20.0, 70.0, 75.0, 75.0, dict(NO_WARNINGS))
        assert result.next_best_alternative is not None
        assert "walk" in result.next_best_alternative.lower()

    def test_injury_watch_alternative(self):
        warnings = {**NO_WARNINGS, "knee_pain_warning": True}
        result = determine_recommendation(85.0, 70.0, 75.0, 75.0, warnings)
        assert result.next_best_alternative is not None
        assert "professional" in result.next_best_alternative.lower()


# ---------------------------------------------------------------------------
# Pipeline: compute_recommendation_for_date
# ---------------------------------------------------------------------------


class TestComputeRecommendationForDate:
    def test_produces_snapshot(self):
        score = _make_score(BASE_DATE, recovery=85.0)
        snap = compute_recommendation_for_date(score)
        assert snap is not None
        assert snap.date == BASE_DATE
        assert snap.mode == RecommendationMode.full_go.value
        assert snap.recommended_action != ""
        assert snap.recommendation_engine_version == "1.0.0"

    def test_missing_recovery_returns_none(self):
        score = _make_score(BASE_DATE, recovery=70.0)
        score.recovery_score = None
        snap = compute_recommendation_for_date(score)
        assert snap is None

    def test_reason_codes_persisted(self):
        score = _make_score(BASE_DATE, recovery=55.0)
        snap = compute_recommendation_for_date(score)
        assert snap is not None
        assert isinstance(snap.reason_codes_json, list)
        assert "recovery_moderate" in snap.reason_codes_json

    def test_warnings_reflected_in_snapshot(self):
        score = _make_score(
            BASE_DATE,
            recovery=85.0,
            warnings={"illness_warning": True, **{k: False for k in NO_WARNINGS if k != "illness_warning"}},
        )
        snap = compute_recommendation_for_date(score)
        assert snap is not None
        assert snap.mode == RecommendationMode.recovery_focused.value
        assert "illness_warning" in snap.risk_flags_json

    def test_next_best_alternative_persisted(self):
        score = _make_score(BASE_DATE, recovery=70.0)
        snap = compute_recommendation_for_date(score)
        assert snap is not None
        assert snap.next_best_alternative is not None


# ---------------------------------------------------------------------------
# Pipeline: run_recommendation_pipeline
# ---------------------------------------------------------------------------


class TestRunRecommendationPipeline:
    def test_persists_recommendations(self, db_session: Session):
        for i in range(3):
            d = BASE_DATE + timedelta(days=i)
            db_session.add(_make_score(d, recovery=75.0))
        db_session.flush()

        result = run_recommendation_pipeline(db_session)
        assert result.dates_recommended == 3
        assert result.dates_skipped == 0
        assert result.errors == []

        rows = db_session.scalars(select(RecommendationSnapshot)).all()
        assert len(rows) == 3

    def test_skips_dates_without_scores(self, db_session: Session):
        # Only add score for first day of a 3-day range
        db_session.add(_make_score(BASE_DATE, recovery=75.0))
        db_session.flush()

        result = run_recommendation_pipeline(db_session, BASE_DATE, BASE_DATE + timedelta(days=2))
        assert result.dates_recommended == 1
        assert result.dates_skipped == 2

    def test_upsert_no_duplicates(self, db_session: Session):
        db_session.add(_make_score(BASE_DATE, recovery=85.0))
        db_session.flush()

        r1 = run_recommendation_pipeline(db_session)
        assert r1.dates_recommended == 1

        r2 = run_recommendation_pipeline(db_session)
        assert r2.dates_recommended == 1

        rows = db_session.scalars(select(RecommendationSnapshot)).all()
        assert len(rows) == 1

    def test_empty_score_table(self, db_session: Session):
        result = run_recommendation_pipeline(db_session)
        assert result.dates_recommended == 0
        assert result.dates_skipped == 0

    def test_date_range_filtering(self, db_session: Session):
        for i in range(5):
            d = BASE_DATE + timedelta(days=i)
            db_session.add(_make_score(d, recovery=75.0))
        db_session.flush()

        result = run_recommendation_pipeline(
            db_session, BASE_DATE + timedelta(days=1), BASE_DATE + timedelta(days=3)
        )
        assert result.dates_recommended == 3
        assert result.dates_skipped == 0

    def test_recommendation_content_correct(self, db_session: Session):
        db_session.add(_make_score(BASE_DATE, recovery=85.0, load_balance=80.0))
        db_session.flush()

        run_recommendation_pipeline(db_session)
        snap = db_session.get(RecommendationSnapshot, BASE_DATE)
        assert snap is not None
        assert snap.mode == RecommendationMode.full_go.value
        assert "recovery_high" in snap.reason_codes_json
        assert snap.risk_flags_json == []

    def test_warning_override_persisted(self, db_session: Session):
        warnings = {**NO_WARNINGS, "knee_pain_warning": True}
        db_session.add(_make_score(BASE_DATE, recovery=85.0, warnings=warnings))
        db_session.flush()

        run_recommendation_pipeline(db_session)
        snap = db_session.get(RecommendationSnapshot, BASE_DATE)
        assert snap is not None
        assert snap.mode == RecommendationMode.injury_watch.value
        assert "knee_pain_warning" in snap.risk_flags_json
