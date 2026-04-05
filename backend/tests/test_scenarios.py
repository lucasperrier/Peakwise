"""Phase 2 scenario tests — 5 representative days.

Each fixture represents a real-world scenario that validates the end-to-end
scoring → recommendation → confidence pipeline.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from peakwise.models import Base, DailyFact, DailyFeatures, RecommendationMode
from peakwise.recommendations.rules import determine_recommendation
from peakwise.scoring.health import compute_general_health_score
from peakwise.scoring.load_balance import compute_load_balance_score
from peakwise.scoring.pipeline import compute_scores_for_date
from peakwise.scoring.race_readiness import compute_race_readiness_score
from peakwise.scoring.recovery import compute_recovery_score
from peakwise.scoring.warnings import compute_all_warnings
from peakwise.trust import compute_decision_confidence

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
        "has_apple_health_data": False,
        "has_strava_data": True,
        "has_scale_data": True,
        "has_manual_input": True,
    }
    defaults.update(kwargs)
    return DailyFact(date=d, **defaults)


def _make_features(d: date, **kwargs) -> DailyFeatures:
    defaults = {
        "hrv_7d_avg": 48.0,
        "hrv_vs_28d_pct": 5.0,
        "resting_hr_7d_avg": 52.0,
        "resting_hr_vs_28d_delta": -1.0,
        "sleep_7d_avg": 450.0,
        "sleep_debt_min": 60.0,
        "recent_load_3d": 180.0,
        "recent_load_7d": 400.0,
        "recovery_trend": 0.5,
        "weekly_km": 35.0,
        "rolling_4w_km": 140.0,
        "longest_run_last_7d_km": 16.0,
        "easy_pace_fixed_hr_sec_per_km": 330.0,
        "quality_sessions_last_14d": 3,
        "projected_hm_time_sec": 6000.0,
        "plan_adherence_pct": 75.0,
        "body_weight_7d_avg": 75.0,
        "body_weight_28d_slope": -0.01,
        "sleep_consistency_score": 85.0,
        "pain_free_days_last_14d": 12,
        "mood_trend": 0.3,
        "stress_trend": -0.1,
        "steps_consistency_score": 80.0,
        "hard_day_count_7d": 3,
        "run_intensity_distribution_json": {"easy": 3, "quality": 1, "long": 1},
        "lower_body_crossfit_density_7d": 0.14,
        "long_run_protection_score": 100.0,
        "interference_risk_score": 20.0,
    }
    defaults.update(kwargs)
    return DailyFeatures(date=d, **defaults)


# ---------------------------------------------------------------------------
# Scenario 1: Ideal training day
# ---------------------------------------------------------------------------


class TestIdealTrainingDay:
    """Everything looks good — full data, well rested, well trained."""

    def _build(self, db_session: Session):
        fact = _make_daily(
            BASE_DATE,
            hrv_ms=52.0,
            resting_hr_bpm=50,
            sleep_duration_min=480.0,
            soreness_score=1.0,
            mood_score=8.0,
            illness_flag=False,
            perceived_fatigue_score=2.0,
            training_readiness=80.0,
        )
        features = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=10.0,
            resting_hr_vs_28d_delta=-2.0,
            sleep_7d_avg=470.0,
            sleep_debt_min=0.0,
            recent_load_3d=120.0,
            recent_load_7d=280.0,
            hard_day_count_7d=2,
            lower_body_crossfit_density_7d=0.14,
            long_run_protection_score=100.0,
            interference_risk_score=10.0,
        )
        db_session.add(fact)
        db_session.flush()
        return fact, features

    def test_high_recovery(self, db_session):
        fact, feat = self._build(db_session)
        score, _ = compute_recovery_score(feat, fact)
        assert score >= 75.0

    def test_full_go_recommendation(self, db_session):
        fact, feat = self._build(db_session)
        score, _ = compute_recovery_score(feat, fact)
        warnings = compute_all_warnings(feat, fact)
        result = determine_recommendation(score, 70.0, 80.0, 80.0, warnings)
        assert result.mode == RecommendationMode.full_go

    def test_high_confidence(self, db_session):
        fact, _ = self._build(db_session)
        conf, level = compute_decision_confidence(fact, BASE_DATE, db_session)
        assert conf >= 70.0
        assert level in ("high", "medium")


# ---------------------------------------------------------------------------
# Scenario 2: Overload day
# ---------------------------------------------------------------------------


class TestOverloadDay:
    """Too many hard sessions, high training load, HRV suppressed."""

    def _build(self, db_session: Session):
        fact = _make_daily(
            BASE_DATE,
            hrv_ms=35.0,
            resting_hr_bpm=60,
            sleep_duration_min=380.0,
            soreness_score=6.0,
            mood_score=5.0,
            perceived_fatigue_score=7.0,
            training_readiness=35.0,
        )
        features = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=-18.0,
            resting_hr_vs_28d_delta=5.0,
            sleep_7d_avg=380.0,
            sleep_debt_min=300.0,
            recent_load_3d=350.0,
            recent_load_7d=750.0,
            hard_day_count_7d=6,
            lower_body_crossfit_density_7d=0.43,
            long_run_protection_score=30.0,
            interference_risk_score=80.0,
        )
        db_session.add(fact)
        db_session.flush()
        return fact, features

    def test_low_recovery(self, db_session):
        fact, feat = self._build(db_session)
        score, _ = compute_recovery_score(feat, fact)
        assert score < 50.0

    def test_recommendation_restricted(self, db_session):
        fact, feat = self._build(db_session)
        recovery, _ = compute_recovery_score(feat, fact)
        warnings = compute_all_warnings(feat, fact)
        _, load_subs = compute_load_balance_score(feat)
        load_score, _ = compute_load_balance_score(feat)
        result = determine_recommendation(recovery, 60.0, 60.0, load_score, warnings)
        # Should be at most reduce_intensity, probably recovery_focused or lower
        restricted_modes = {
            RecommendationMode.reduce_intensity,
            RecommendationMode.recovery_focused,
            RecommendationMode.full_rest,
        }
        assert result.mode in restricted_modes

    def test_warnings_triggered(self, db_session):
        fact, feat = self._build(db_session)
        warnings = compute_all_warnings(feat, fact)
        assert warnings["hrv_suppression_warning"] is True
        assert warnings["overload_warning"] is True


# ---------------------------------------------------------------------------
# Scenario 3: Poor sleep day
# ---------------------------------------------------------------------------


class TestPoorSleepDay:
    """Severe sleep debt, poor sleep consistency."""

    def _build(self, db_session: Session):
        fact = _make_daily(
            BASE_DATE,
            hrv_ms=38.0,
            resting_hr_bpm=56,
            sleep_duration_min=300.0,
            sleep_score=40.0,
            soreness_score=3.0,
            mood_score=5.0,
            perceived_fatigue_score=6.0,
            training_readiness=40.0,
        )
        features = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=-8.0,
            resting_hr_vs_28d_delta=3.0,
            sleep_7d_avg=340.0,
            sleep_debt_min=450.0,
            sleep_consistency_score=35.0,
            recent_load_3d=150.0,
            recent_load_7d=350.0,
        )
        db_session.add(fact)
        db_session.flush()
        return fact, features

    def test_recovery_suppressed(self, db_session):
        fact, feat = self._build(db_session)
        score, _ = compute_recovery_score(feat, fact)
        # Severe sleep debt ceiling at 50
        assert score <= 55.0

    def test_sleep_debt_warning(self, db_session):
        fact, feat = self._build(db_session)
        warnings = compute_all_warnings(feat, fact)
        assert warnings["sleep_debt_warning"] is True

    def test_recommendation_reduced(self, db_session):
        fact, feat = self._build(db_session)
        recovery, _ = compute_recovery_score(feat, fact)
        warnings = compute_all_warnings(feat, fact)
        result = determine_recommendation(recovery, 65.0, 60.0, 70.0, warnings)
        allowed = {
            RecommendationMode.reduce_intensity,
            RecommendationMode.recovery_focused,
            RecommendationMode.full_rest,
        }
        assert result.mode in allowed


# ---------------------------------------------------------------------------
# Scenario 4: Injury watch day
# ---------------------------------------------------------------------------


class TestInjuryWatchDay:
    """Knee pain elevated, everything else is fine."""

    def _build(self, db_session: Session):
        fact = _make_daily(
            BASE_DATE,
            hrv_ms=50.0,
            resting_hr_bpm=52,
            sleep_duration_min=460.0,
            soreness_score=5.0,
            left_knee_pain_score=6.0,
            mood_score=6.0,
            perceived_fatigue_score=4.0,
            training_readiness=60.0,
        )
        features = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=3.0,
            resting_hr_vs_28d_delta=0.0,
            sleep_7d_avg=450.0,
            sleep_debt_min=30.0,
            pain_free_days_last_14d=5,
        )
        db_session.add(fact)
        db_session.flush()
        return fact, features

    def test_knee_pain_warning(self, db_session):
        fact, feat = self._build(db_session)
        warnings = compute_all_warnings(feat, fact)
        assert warnings["knee_pain_warning"] is True

    def test_injury_watch_mode(self, db_session):
        fact, feat = self._build(db_session)
        recovery, _ = compute_recovery_score(feat, fact)
        warnings = compute_all_warnings(feat, fact)
        result = determine_recommendation(recovery, 70.0, 75.0, 75.0, warnings)
        assert result.mode == RecommendationMode.injury_watch
        assert "knee_pain_elevated" in result.reason_codes

    def test_risk_flag_set(self, db_session):
        fact, feat = self._build(db_session)
        recovery, _ = compute_recovery_score(feat, fact)
        warnings = compute_all_warnings(feat, fact)
        result = determine_recommendation(recovery, 70.0, 75.0, 75.0, warnings)
        assert "knee_pain_warning" in result.risk_flags


# ---------------------------------------------------------------------------
# Scenario 5: Incomplete data day
# ---------------------------------------------------------------------------


class TestIncompleteDataDay:
    """Garmin only, no scale, no manual, no strava, missing key metrics."""

    def _build(self, db_session: Session):
        fact = _make_daily(
            BASE_DATE,
            hrv_ms=None,
            resting_hr_bpm=54,
            sleep_duration_min=None,
            sleep_score=None,
            body_weight_kg=None,
            soreness_score=None,
            mood_score=None,
            perceived_fatigue_score=None,
            training_readiness=None,
            has_garmin_data=True,
            has_apple_health_data=False,
            has_strava_data=False,
            has_scale_data=False,
            has_manual_input=False,
        )
        features = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=None,
            resting_hr_vs_28d_delta=0.0,
            sleep_7d_avg=None,
            sleep_debt_min=None,
        )
        db_session.add(fact)
        db_session.flush()
        return fact, features

    def test_low_confidence(self, db_session):
        fact, _ = self._build(db_session)
        conf, level = compute_decision_confidence(fact, BASE_DATE, db_session)
        assert conf < 50.0
        assert level in ("low", "insufficient")

    def test_recommendation_capped_by_confidence(self, db_session):
        """With low confidence, recommendation should be conservative."""
        fact, feat = self._build(db_session)
        # Even if the available metrics suggest OK recovery, low confidence
        # should cap the recommendation
        recovery, _ = compute_recovery_score(feat, fact)
        warnings = compute_all_warnings(feat, fact)
        conf, _ = compute_decision_confidence(fact, BASE_DATE, db_session)
        result = determine_recommendation(
            recovery, 70.0, 70.0, 70.0, warnings, confidence_score=conf
        )
        restricted_modes = {
            RecommendationMode.reduce_intensity,
            RecommendationMode.recovery_focused,
            RecommendationMode.full_rest,
        }
        assert result.mode in restricted_modes

    def test_scores_still_compute(self, db_session):
        """Missing data should produce valid (if uncertain) scores."""
        fact, feat = self._build(db_session)
        daily_facts = {BASE_DATE: fact}
        features = {BASE_DATE: feat}
        snapshot = compute_scores_for_date(BASE_DATE, daily_facts, features)
        assert snapshot is not None
        assert 0.0 <= snapshot.recovery_score <= 100.0


# ---------------------------------------------------------------------------
# Snapshot regression tests
# ---------------------------------------------------------------------------


class TestScoreSnapshots:
    """Ensure score outputs don't silently regress."""

    def test_ideal_day_score_range(self, db_session):
        """Ideal training day produces consistent score ranges."""
        fact = _make_daily(
            BASE_DATE,
            hrv_ms=52.0,
            resting_hr_bpm=50,
            sleep_duration_min=480.0,
            soreness_score=1.0,
            illness_flag=False,
            perceived_fatigue_score=2.0,
            training_readiness=80.0,
        )
        feat = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=10.0,
            resting_hr_vs_28d_delta=-2.0,
            sleep_7d_avg=470.0,
            sleep_debt_min=0.0,
            recent_load_3d=120.0,
            recent_load_7d=280.0,
        )
        daily_facts = {BASE_DATE: fact}
        features = {BASE_DATE: feat}
        snap = compute_scores_for_date(BASE_DATE, daily_facts, features)
        assert snap is not None
        # Expected ranges for ideal day
        assert 70.0 <= snap.recovery_score <= 100.0
        assert 50.0 <= snap.race_readiness_score <= 100.0
        assert 60.0 <= snap.general_health_score <= 100.0
        assert 60.0 <= snap.load_balance_score <= 100.0

    def test_overload_day_score_range(self, db_session):
        fact = _make_daily(
            BASE_DATE,
            hrv_ms=35.0,
            resting_hr_bpm=60,
            sleep_duration_min=380.0,
            soreness_score=6.0,
            perceived_fatigue_score=7.0,
            training_readiness=35.0,
        )
        feat = _make_features(
            BASE_DATE,
            hrv_vs_28d_pct=-18.0,
            resting_hr_vs_28d_delta=5.0,
            sleep_7d_avg=380.0,
            sleep_debt_min=300.0,
            recent_load_3d=350.0,
            recent_load_7d=750.0,
            hard_day_count_7d=6,
            interference_risk_score=80.0,
        )
        daily_facts = {BASE_DATE: fact}
        features = {BASE_DATE: feat}
        snap = compute_scores_for_date(BASE_DATE, daily_facts, features)
        assert snap is not None
        # Overload day should have low recovery and load balance
        assert snap.recovery_score < 50.0
        assert snap.load_balance_score < 50.0
