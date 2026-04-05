"""Tests for Phase 4 — scoring engine.

Covers recovery score, race-readiness score, general-health score,
load-balance score, warning logic, and the full scoring pipeline.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from peakwise.models import Base, DailyFact, DailyFeatures, ScoreSnapshot, WorkoutFact
from peakwise.scoring.health import compute_general_health_score
from peakwise.scoring.load_balance import compute_load_balance_score
from peakwise.scoring.pipeline import (
    ScoringPipelineResult,
    compute_scores_for_date,
    run_scoring_pipeline,
)
from peakwise.scoring.race_readiness import compute_race_readiness_score
from peakwise.scoring.recovery import compute_recovery_score
from peakwise.scoring.warnings import (
    compute_all_warnings,
    compute_hrv_suppression_warning,
    compute_illness_warning,
    compute_knee_pain_warning,
    compute_overload_warning,
    compute_sleep_debt_warning,
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
        "active_energy_kcal": 600.0,
        "training_readiness": 65.0,
        "stress_score": 30.0,
        "body_battery": 70.0,
        "soreness_score": 2.0,
        "left_knee_pain_score": 0.0,
        "mood_score": 7.0,
        "illness_flag": False,
        "perceived_fatigue_score": 3.0,
        "has_garmin_data": True,
    }
    defaults.update(kwargs)
    return DailyFact(date=d, **defaults)


def _make_features(d: date, **kwargs) -> DailyFeatures:
    """Create DailyFeatures with sensible defaults for a healthy, well-rested day."""
    defaults = {
        # Recovery
        "hrv_7d_avg": 48.0,
        "hrv_vs_28d_pct": 5.0,
        "resting_hr_7d_avg": 52.0,
        "resting_hr_vs_28d_delta": -1.0,
        "sleep_7d_avg": 450.0,
        "sleep_debt_min": 60.0,
        "recent_load_3d": 180.0,
        "recent_load_7d": 400.0,
        "recovery_trend": 0.5,
        # Running
        "weekly_km": 35.0,
        "rolling_4w_km": 140.0,
        "longest_run_last_7d_km": 16.0,
        "easy_pace_fixed_hr_sec_per_km": 330.0,
        "quality_sessions_last_14d": 3,
        "projected_hm_time_sec": 6000.0,
        "plan_adherence_pct": 75.0,
        # Health
        "body_weight_7d_avg": 75.0,
        "body_weight_28d_slope": -0.01,
        "sleep_consistency_score": 85.0,
        "pain_free_days_last_14d": 12,
        "mood_trend": 0.3,
        "stress_trend": -0.1,
        "steps_consistency_score": 80.0,
        # Hybrid balance
        "hard_day_count_7d": 3,
        "run_intensity_distribution_json": {"easy": 3, "quality": 1, "long": 1},
        "lower_body_crossfit_density_7d": 0.14,
        "long_run_protection_score": 100.0,
        "interference_risk_score": 20.0,
    }
    defaults.update(kwargs)
    return DailyFeatures(date=d, **defaults)


# ---------------------------------------------------------------------------
# Recovery score tests
# ---------------------------------------------------------------------------


class TestRecoveryScore:
    def test_high_readiness(self):
        """Well-rested day with good metrics → high recovery."""
        features = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=10.0,
            resting_hr_vs_28d_delta=-2.0,
            sleep_7d_avg=480.0,
            sleep_debt_min=0.0,
            recent_load_3d=100.0,
            recent_load_7d=250.0,
        )
        fact = _make_daily(
            BASE_DATE,
            soreness_score=1.0,
            illness_flag=False,
            perceived_fatigue_score=2.0,
            training_readiness=80.0,
        )
        score, subs = compute_recovery_score(features, fact)
        assert 75.0 <= score <= 100.0
        assert subs["illness_component"] == 100.0

    def test_medium_readiness(self):
        """Moderate sleep debt, some soreness → mid recovery."""
        features = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=0.0,
            resting_hr_vs_28d_delta=1.0,
            sleep_7d_avg=400.0,
            sleep_debt_min=200.0,
            recent_load_3d=250.0,
            recent_load_7d=500.0,
        )
        fact = _make_daily(
            BASE_DATE,
            soreness_score=4.0,
            illness_flag=False,
            perceived_fatigue_score=5.0,
            training_readiness=55.0,
        )
        score, subs = compute_recovery_score(features, fact)
        assert 40.0 <= score <= 75.0

    def test_low_readiness(self):
        """Illness, poor sleep, high load → low recovery."""
        features = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=-20.0,
            resting_hr_vs_28d_delta=6.0,
            sleep_7d_avg=340.0,
            sleep_debt_min=500.0,
            recent_load_3d=400.0,
            recent_load_7d=800.0,
        )
        fact = _make_daily(
            BASE_DATE,
            soreness_score=7.0,
            illness_flag=True,
            perceived_fatigue_score=8.0,
            training_readiness=30.0,
        )
        score, subs = compute_recovery_score(features, fact)
        assert score < 40.0
        assert subs["illness_component"] == 0.0

    def test_missing_data_uses_default(self):
        """Missing HRV and fatigue data should still produce a valid score."""
        features = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=None,
            resting_hr_vs_28d_delta=0.0,
            sleep_7d_avg=450.0,
            sleep_debt_min=60.0,
            recent_load_3d=150.0,
            recent_load_7d=350.0,
        )
        fact = _make_daily(
            BASE_DATE,
            soreness_score=2.0,
            illness_flag=False,
            perceived_fatigue_score=None,
            training_readiness=None,
        )
        score, subs = compute_recovery_score(features, fact)
        assert 0.0 <= score <= 100.0
        assert subs["hrv_component"] is None
        assert subs["subjective_fatigue_component"] is None
        assert subs["device_readiness_component"] is None

    def test_subcomponents_returned(self):
        features = _make_features(BASE_DATE)
        fact = _make_daily(BASE_DATE)
        score, subs = compute_recovery_score(features, fact)
        expected_keys = {
            "hrv_component",
            "resting_hr_component",
            "sleep_component",
            "load_component",
            "soreness_component",
            "illness_component",
            "subjective_fatigue_component",
            "device_readiness_component",
        }
        assert set(subs.keys()) == expected_keys

    def test_score_clamped_0_100(self):
        features = _make_features(BASE_DATE, hrv_vs_28d_pct=50.0)
        fact = _make_daily(BASE_DATE, soreness_score=0.0, perceived_fatigue_score=0.0)
        score, _ = compute_recovery_score(features, fact)
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# Race-readiness score tests
# ---------------------------------------------------------------------------


class TestRaceReadinessScore:
    def test_on_track(self):
        """Good volume, long run, efficiency → high race readiness."""
        features = _make_features(
            BASE_DATE,
            weekly_km=42.0,
            longest_run_last_7d_km=18.0,
            easy_pace_fixed_hr_sec_per_km=310.0,
            quality_sessions_last_14d=4,
            projected_hm_time_sec=5600.0,
            plan_adherence_pct=100.0,
            recovery_trend=1.0,
        )
        score, subs = compute_race_readiness_score(features)
        assert score >= 70.0

    def test_off_track(self):
        """Low volume, no long run, slow efficiency → low race readiness."""
        features = _make_features(
            BASE_DATE,
            weekly_km=15.0,
            longest_run_last_7d_km=0.0,
            easy_pace_fixed_hr_sec_per_km=380.0,
            quality_sessions_last_14d=0,
            projected_hm_time_sec=7100.0,
            plan_adherence_pct=25.0,
            recovery_trend=-0.5,
        )
        score, subs = compute_race_readiness_score(features)
        assert score < 55.0

    def test_missing_projection(self):
        """Missing projected HM time uses default."""
        features = _make_features(BASE_DATE, projected_hm_time_sec=None)
        score, subs = compute_race_readiness_score(features)
        assert 0.0 <= score <= 100.0
        assert subs["projection_component"] is None

    def test_subcomponents_returned(self):
        features = _make_features(BASE_DATE)
        score, subs = compute_race_readiness_score(features)
        expected_keys = {
            "weekly_volume_component",
            "long_run_component",
            "easy_efficiency_component",
            "quality_completion_component",
            "projection_component",
            "plan_adherence_component",
            "trend_component",
        }
        assert set(subs.keys()) == expected_keys


# ---------------------------------------------------------------------------
# General-health score tests
# ---------------------------------------------------------------------------


class TestGeneralHealthScore:
    def test_stable_health(self):
        """Stable sleep, weight, low pain → high health score."""
        features = _make_features(
            BASE_DATE,
            sleep_consistency_score=95.0,
            body_weight_28d_slope=0.0,
            resting_hr_vs_28d_delta=-1.0,
            hrv_vs_28d_pct=3.0,
            steps_consistency_score=90.0,
            pain_free_days_last_14d=14,
            mood_trend=0.5,
            stress_trend=-0.2,
        )
        score, subs = compute_general_health_score(features)
        assert score >= 75.0

    def test_drifting_health(self):
        """Poor sleep, increasing stress, pain → low health score."""
        features = _make_features(
            BASE_DATE,
            sleep_consistency_score=40.0,
            body_weight_28d_slope=-0.08,
            resting_hr_vs_28d_delta=4.0,
            hrv_vs_28d_pct=-12.0,
            steps_consistency_score=30.0,
            pain_free_days_last_14d=5,
            mood_trend=-1.0,
            stress_trend=1.5,
        )
        score, subs = compute_general_health_score(features)
        assert score < 55.0

    def test_weight_stable_range(self):
        features = _make_features(BASE_DATE, body_weight_28d_slope=0.01)
        _, subs = compute_general_health_score(features)
        assert subs["weight_trend_component"] == pytest.approx(90.0)

    def test_subcomponents_returned(self):
        features = _make_features(BASE_DATE)
        score, subs = compute_general_health_score(features)
        expected_keys = {
            "sleep_consistency_component",
            "weight_trend_component",
            "resting_hr_trend_component",
            "hrv_stability_component",
            "steps_component",
            "pain_component",
            "mood_component",
            "stress_component",
        }
        assert set(subs.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Load-balance score tests
# ---------------------------------------------------------------------------


class TestLoadBalanceScore:
    def test_balanced_week(self):
        """Light hard-day count, good spacing, protected long run → high score."""
        features = _make_features(
            BASE_DATE,
            hard_day_count_7d=2,
            lower_body_crossfit_density_7d=0.0,
            long_run_protection_score=100.0,
            interference_risk_score=10.0,
            run_intensity_distribution_json={"easy": 4, "quality": 1, "long": 0},
        )
        score, subs = compute_load_balance_score(features)
        assert score >= 75.0

    def test_interference_heavy_week(self):
        """Too many hard days, high interference → low score."""
        features = _make_features(
            BASE_DATE,
            hard_day_count_7d=6,
            lower_body_crossfit_density_7d=0.43,
            long_run_protection_score=30.0,
            interference_risk_score=80.0,
            run_intensity_distribution_json={"easy": 1, "quality": 3, "long": 1},
        )
        score, subs = compute_load_balance_score(features)
        assert score < 45.0

    def test_no_runs_distribution(self):
        """No runs in the distribution → default."""
        features = _make_features(
            BASE_DATE,
            run_intensity_distribution_json={"easy": 0, "quality": 0, "long": 0},
        )
        _, subs = compute_load_balance_score(features)
        assert subs["run_distribution_component"] == pytest.approx(50.0)

    def test_subcomponents_returned(self):
        features = _make_features(BASE_DATE)
        score, subs = compute_load_balance_score(features)
        expected_keys = {
            "hard_day_density_component",
            "lower_body_density_component",
            "session_spacing_component",
            "long_run_protection_component",
            "run_distribution_component",
            "interference_component",
        }
        assert set(subs.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Warning tests
# ---------------------------------------------------------------------------


class TestWarnings:
    def test_knee_pain_warning_triggered(self):
        fact = _make_daily(BASE_DATE, left_knee_pain_score=5.0)
        assert compute_knee_pain_warning(fact) is True

    def test_knee_pain_warning_not_triggered(self):
        fact = _make_daily(BASE_DATE, left_knee_pain_score=2.0)
        assert compute_knee_pain_warning(fact) is False

    def test_knee_pain_warning_none(self):
        fact = _make_daily(BASE_DATE, left_knee_pain_score=None)
        assert compute_knee_pain_warning(fact) is False

    def test_illness_warning_triggered(self):
        fact = _make_daily(BASE_DATE, illness_flag=True)
        assert compute_illness_warning(fact) is True

    def test_illness_warning_not_triggered(self):
        fact = _make_daily(BASE_DATE, illness_flag=False)
        assert compute_illness_warning(fact) is False

    def test_sleep_debt_warning_triggered(self):
        features = _make_features(BASE_DATE, sleep_debt_min=350.0)
        assert compute_sleep_debt_warning(features) is True

    def test_sleep_debt_warning_not_triggered(self):
        features = _make_features(BASE_DATE, sleep_debt_min=100.0)
        assert compute_sleep_debt_warning(features) is False

    def test_hrv_suppression_warning_triggered(self):
        features = _make_features(BASE_DATE, hrv_vs_28d_pct=-18.0)
        assert compute_hrv_suppression_warning(features) is True

    def test_hrv_suppression_warning_not_triggered(self):
        features = _make_features(BASE_DATE, hrv_vs_28d_pct=-5.0)
        assert compute_hrv_suppression_warning(features) is False

    def test_overload_warning_high_load(self):
        features = _make_features(BASE_DATE, recent_load_7d=750.0, hard_day_count_7d=3)
        assert compute_overload_warning(features) is True

    def test_overload_warning_many_hard_days(self):
        features = _make_features(BASE_DATE, recent_load_7d=400.0, hard_day_count_7d=6)
        assert compute_overload_warning(features) is True

    def test_overload_warning_not_triggered(self):
        features = _make_features(BASE_DATE, recent_load_7d=400.0, hard_day_count_7d=3)
        assert compute_overload_warning(features) is False

    def test_compute_all_warnings(self):
        features = _make_features(
            BASE_DATE,
            sleep_debt_min=350.0,
            hrv_vs_28d_pct=-18.0,
            recent_load_7d=400.0,
            hard_day_count_7d=3,
        )
        fact = _make_daily(BASE_DATE, left_knee_pain_score=5.0, illness_flag=True)
        warnings = compute_all_warnings(features, fact)

        assert warnings["knee_pain_warning"] is True
        assert warnings["illness_warning"] is True
        assert warnings["sleep_debt_warning"] is True
        assert warnings["hrv_suppression_warning"] is True
        assert warnings["overload_warning"] is False

    def test_no_warnings(self):
        features = _make_features(
            BASE_DATE,
            sleep_debt_min=50.0,
            hrv_vs_28d_pct=5.0,
            recent_load_7d=350.0,
            hard_day_count_7d=3,
        )
        fact = _make_daily(
            BASE_DATE, left_knee_pain_score=1.0, illness_flag=False
        )
        warnings = compute_all_warnings(features, fact)
        assert all(v is False for v in warnings.values())


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


class TestScoringPipeline:
    def test_compute_scores_for_date(self):
        features = {BASE_DATE: _make_features(BASE_DATE)}
        daily_facts = {BASE_DATE: _make_daily(BASE_DATE)}
        snapshot = compute_scores_for_date(BASE_DATE, daily_facts, features)
        assert snapshot is not None
        assert snapshot.date == BASE_DATE
        assert 0.0 <= snapshot.recovery_score <= 100.0
        assert 0.0 <= snapshot.race_readiness_score <= 100.0
        assert 0.0 <= snapshot.general_health_score <= 100.0
        assert 0.0 <= snapshot.load_balance_score <= 100.0
        assert "recovery" in snapshot.subcomponents_json
        assert "race_readiness" in snapshot.subcomponents_json
        assert "general_health" in snapshot.subcomponents_json
        assert "load_balance" in snapshot.subcomponents_json
        assert isinstance(snapshot.warnings_json, dict)

    def test_compute_scores_missing_data(self):
        features: dict[date, DailyFeatures] = {}
        daily_facts = {BASE_DATE: _make_daily(BASE_DATE)}
        snapshot = compute_scores_for_date(BASE_DATE, daily_facts, features)
        assert snapshot is None

    def test_run_scoring_pipeline_persists(self, db_session: Session):
        """Pipeline persists ScoreSnapshot rows."""
        for i in range(10):
            d = BASE_DATE - timedelta(days=i)
            db_session.add(_make_daily(d))
            db_session.add(_make_features(d))
        db_session.flush()

        result = run_scoring_pipeline(db_session)
        db_session.commit()

        assert result.dates_scored == 10
        assert result.dates_skipped == 0
        rows = db_session.scalars(select(ScoreSnapshot)).all()
        assert len(rows) == 10

        # Spot-check
        snap = db_session.get(ScoreSnapshot, BASE_DATE)
        assert snap is not None
        assert snap.recovery_score is not None
        assert snap.score_engine_version == "1.0.0"

    def test_run_scoring_pipeline_date_range(self, db_session: Session):
        for i in range(10):
            d = BASE_DATE - timedelta(days=i)
            db_session.add(_make_daily(d))
            db_session.add(_make_features(d))
        db_session.flush()

        start = BASE_DATE - timedelta(days=3)
        result = run_scoring_pipeline(db_session, start_date=start, end_date=BASE_DATE)
        db_session.commit()

        assert result.dates_scored == 4

    def test_run_scoring_pipeline_skips_missing(self, db_session: Session):
        """Days without features are skipped."""
        for i in [0, 2, 4]:
            d = BASE_DATE - timedelta(days=i)
            db_session.add(_make_daily(d))
            db_session.add(_make_features(d))
        # Add daily_facts without features for days 1, 3
        for i in [1, 3]:
            db_session.add(_make_daily(BASE_DATE - timedelta(days=i)))
        db_session.flush()

        start = BASE_DATE - timedelta(days=4)
        result = run_scoring_pipeline(db_session, start_date=start, end_date=BASE_DATE)
        db_session.commit()

        assert result.dates_scored == 3
        assert result.dates_skipped == 2

    def test_pipeline_upsert(self, db_session: Session):
        """Re-running the pipeline updates, not duplicates."""
        for i in range(5):
            d = BASE_DATE - timedelta(days=i)
            db_session.add(_make_daily(d))
            db_session.add(_make_features(d))
        db_session.flush()

        run_scoring_pipeline(db_session)
        db_session.commit()
        assert len(db_session.scalars(select(ScoreSnapshot)).all()) == 5

        run_scoring_pipeline(db_session)
        db_session.commit()
        assert len(db_session.scalars(select(ScoreSnapshot)).all()) == 5

    def test_pipeline_warnings_persisted(self, db_session: Session):
        """Warnings dict is persisted in the snapshot."""
        d = BASE_DATE
        db_session.add(_make_daily(d, illness_flag=True, left_knee_pain_score=6.0))
        db_session.add(_make_features(d, sleep_debt_min=400.0, hrv_vs_28d_pct=-20.0))
        db_session.flush()

        run_scoring_pipeline(db_session)
        db_session.commit()

        snap = db_session.get(ScoreSnapshot, d)
        assert snap is not None
        warnings = snap.warnings_json
        assert warnings["knee_pain_warning"] is True
        assert warnings["illness_warning"] is True
        assert warnings["sleep_debt_warning"] is True
        assert warnings["hrv_suppression_warning"] is True
