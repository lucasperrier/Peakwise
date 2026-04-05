"""Tests for Phase 3 — feature engineering.

Covers daily/recovery features, running features, hybrid/load-balance
features, and the full feature pipeline.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from peakwise.features.daily import (
    compute_body_weight_28d_slope,
    compute_body_weight_7d_avg,
    compute_hrv_7d_avg,
    compute_hrv_vs_28d_pct,
    compute_mood_trend,
    compute_pain_free_days_last_14d,
    compute_recent_load,
    compute_recovery_trend,
    compute_resting_hr_7d_avg,
    compute_resting_hr_vs_28d_delta,
    compute_sleep_7d_avg,
    compute_sleep_consistency_score,
    compute_sleep_debt_min,
    compute_steps_consistency_score,
    compute_stress_trend,
)
from peakwise.features.helpers import consistency_score, linear_slope, rolling_avg, rolling_sum
from peakwise.features.hybrid import (
    compute_crossfit_tags,
    compute_hard_day_count_7d,
    compute_interference_risk_score,
    compute_long_run_protection_score,
    compute_lower_body_crossfit_density_7d,
    compute_run_intensity_distribution,
)
from peakwise.features.pipeline import (
    FeaturePipelineResult,
    compute_features_for_date,
    run_feature_pipeline,
)
from peakwise.features.running import (
    compute_easy_pace_fixed_hr,
    compute_longest_run_last_7d_km,
    compute_plan_adherence_pct,
    compute_projected_hm_time_sec,
    compute_quality_sessions_last_14d,
    compute_rolling_4w_km,
    compute_weekly_km,
)
from peakwise.models import Base, DailyFact, DailyFeatures, WorkoutFact


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_DATE = date(2025, 7, 7)  # a Monday


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
        "has_garmin_data": True,
    }
    defaults.update(kwargs)
    return DailyFact(date=d, **defaults)


def _make_workout(
    d: date,
    session_type: str = "run_easy",
    distance_km: float | None = 8.0,
    avg_hr_bpm: int | None = 140,
    avg_pace_sec_per_km: float | None = 330.0,
    duration_min: float = 45.0,
    training_load: float = 80.0,
    is_duplicate: bool = False,
    **kwargs,
) -> WorkoutFact:
    return WorkoutFact(
        workout_id=str(uuid.uuid4()),
        source="garmin",
        session_date=d,
        session_type=session_type,
        distance_km=distance_km,
        avg_hr_bpm=avg_hr_bpm,
        avg_pace_sec_per_km=avg_pace_sec_per_km,
        duration_min=duration_min,
        training_load=training_load,
        is_duplicate=is_duplicate,
        **kwargs,
    )


def _build_daily_facts(n: int, base: date = BASE_DATE, **overrides) -> dict[date, DailyFact]:
    """Create *n* days of daily facts ending on *base*."""
    return {
        base - timedelta(days=i): _make_daily(base - timedelta(days=i), **overrides)
        for i in range(n)
    }


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_rolling_avg_basic(self):
        assert rolling_avg([1.0, 2.0, 3.0, 4.0, 5.0], 3) == pytest.approx(4.0)

    def test_rolling_avg_with_none(self):
        assert rolling_avg([1.0, None, 3.0], 3) == pytest.approx(2.0)

    def test_rolling_avg_all_none(self):
        assert rolling_avg([None, None], 2) is None

    def test_rolling_sum(self):
        assert rolling_sum([10.0, None, 20.0, 30.0], 3) == pytest.approx(50.0)

    def test_linear_slope_increasing(self):
        slope = linear_slope([1.0, 2.0, 3.0, 4.0])
        assert slope is not None
        assert slope == pytest.approx(1.0)

    def test_linear_slope_flat(self):
        slope = linear_slope([5.0, 5.0, 5.0])
        assert slope == pytest.approx(0.0)

    def test_linear_slope_insufficient(self):
        assert linear_slope([5.0]) is None
        assert linear_slope([None, None]) is None

    def test_consistency_score_perfect(self):
        score = consistency_score([60.0, 60.0, 60.0, 60.0], 4)
        assert score == pytest.approx(100.0)

    def test_consistency_score_variable(self):
        score = consistency_score([60.0, 80.0, 60.0, 80.0], 4)
        assert score is not None
        assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# Daily / Recovery feature tests
# ---------------------------------------------------------------------------


class TestDailyFeatures:
    def test_hrv_7d_avg(self):
        facts = _build_daily_facts(7, hrv_ms=50.0)
        result = compute_hrv_7d_avg(facts, BASE_DATE)
        assert result == pytest.approx(50.0)

    def test_hrv_7d_avg_partial(self):
        """Only 3 days of data available."""
        facts = _build_daily_facts(3, hrv_ms=45.0)
        result = compute_hrv_7d_avg(facts, BASE_DATE)
        assert result == pytest.approx(45.0)

    def test_hrv_vs_28d_pct_above_baseline(self):
        # 28 days at 40ms, last 7 days at 48ms
        facts: dict[date, DailyFact] = {}
        for i in range(28):
            d = BASE_DATE - timedelta(days=i)
            hrv = 48.0 if i < 7 else 40.0
            facts[d] = _make_daily(d, hrv_ms=hrv)
        result = compute_hrv_vs_28d_pct(facts, BASE_DATE)
        assert result is not None
        assert result > 0  # 7d avg is above 28d avg

    def test_resting_hr_7d_avg(self):
        facts = _build_daily_facts(7, resting_hr_bpm=55)
        result = compute_resting_hr_7d_avg(facts, BASE_DATE)
        assert result == pytest.approx(55.0)

    def test_resting_hr_vs_28d_delta(self):
        facts: dict[date, DailyFact] = {}
        for i in range(28):
            d = BASE_DATE - timedelta(days=i)
            hr = 55 if i < 7 else 50
            facts[d] = _make_daily(d, resting_hr_bpm=hr)
        result = compute_resting_hr_vs_28d_delta(facts, BASE_DATE)
        assert result is not None
        assert result > 0  # 7d is higher than 28d

    def test_sleep_7d_avg(self):
        facts = _build_daily_facts(7, sleep_duration_min=420.0)
        assert compute_sleep_7d_avg(facts, BASE_DATE) == pytest.approx(420.0)

    def test_sleep_debt_no_debt(self):
        """7 × 480 min = 3360 target; 7 × 490 = 3430 actual → 0 debt."""
        facts = _build_daily_facts(7, sleep_duration_min=490.0)
        assert compute_sleep_debt_min(facts, BASE_DATE) == pytest.approx(0.0)

    def test_sleep_debt_deficit(self):
        """7 × 480 = 3360 target; 7 × 400 = 2800 actual → 560 debt."""
        facts = _build_daily_facts(7, sleep_duration_min=400.0)
        assert compute_sleep_debt_min(facts, BASE_DATE) == pytest.approx(560.0)

    def test_recent_load_3d(self):
        workouts = [
            _make_workout(BASE_DATE, training_load=100.0),
            _make_workout(BASE_DATE - timedelta(days=1), training_load=80.0),
            _make_workout(BASE_DATE - timedelta(days=2), training_load=60.0),
            _make_workout(BASE_DATE - timedelta(days=5), training_load=200.0),
        ]
        assert compute_recent_load(workouts, BASE_DATE, 3) == pytest.approx(240.0)

    def test_recent_load_excludes_duplicates(self):
        workouts = [
            _make_workout(BASE_DATE, training_load=100.0),
            _make_workout(BASE_DATE, training_load=90.0, is_duplicate=True),
        ]
        assert compute_recent_load(workouts, BASE_DATE, 3) == pytest.approx(100.0)

    def test_recovery_trend_improving(self):
        facts: dict[date, DailyFact] = {}
        for i in range(14):
            d = BASE_DATE - timedelta(days=13 - i)
            facts[d] = _make_daily(d, training_readiness=50.0 + i * 2)
        slope = compute_recovery_trend(facts, BASE_DATE)
        assert slope is not None
        assert slope > 0

    def test_body_weight_7d_avg(self):
        facts = _build_daily_facts(7, body_weight_kg=76.0)
        assert compute_body_weight_7d_avg(facts, BASE_DATE) == pytest.approx(76.0)

    def test_body_weight_28d_slope_losing(self):
        facts: dict[date, DailyFact] = {}
        for i in range(28):
            d = BASE_DATE - timedelta(days=27 - i)
            facts[d] = _make_daily(d, body_weight_kg=78.0 - i * 0.05)
        slope = compute_body_weight_28d_slope(facts, BASE_DATE)
        assert slope is not None
        assert slope < 0  # losing weight

    def test_sleep_consistency_stable(self):
        facts = _build_daily_facts(14, sleep_duration_min=420.0)
        score = compute_sleep_consistency_score(facts, BASE_DATE)
        assert score is not None
        assert score == pytest.approx(100.0)

    def test_sleep_consistency_variable(self):
        facts: dict[date, DailyFact] = {}
        for i in range(14):
            d = BASE_DATE - timedelta(days=i)
            sleep = 360.0 if i % 2 == 0 else 480.0
            facts[d] = _make_daily(d, sleep_duration_min=sleep)
        score = compute_sleep_consistency_score(facts, BASE_DATE)
        assert score is not None
        assert score < 100.0

    def test_pain_free_days(self):
        facts: dict[date, DailyFact] = {}
        for i in range(14):
            d = BASE_DATE - timedelta(days=i)
            pain = 3.0 if i < 3 else 0.0  # 3 pain days, 11 pain-free
            facts[d] = _make_daily(d, left_knee_pain_score=pain)
        assert compute_pain_free_days_last_14d(facts, BASE_DATE) == 11

    def test_mood_trend_improving(self):
        facts: dict[date, DailyFact] = {}
        for i in range(14):
            d = BASE_DATE - timedelta(days=13 - i)
            facts[d] = _make_daily(d, mood_score=5.0 + i * 0.3)
        slope = compute_mood_trend(facts, BASE_DATE)
        assert slope is not None
        assert slope > 0

    def test_stress_trend_worsening(self):
        facts: dict[date, DailyFact] = {}
        for i in range(14):
            d = BASE_DATE - timedelta(days=13 - i)
            facts[d] = _make_daily(d, stress_score=20.0 + i * 1.0)
        slope = compute_stress_trend(facts, BASE_DATE)
        assert slope is not None
        assert slope > 0  # stress increasing = worsening

    def test_steps_consistency(self):
        facts = _build_daily_facts(14, steps=8500)
        score = compute_steps_consistency_score(facts, BASE_DATE)
        assert score is not None
        assert score == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Running feature tests
# ---------------------------------------------------------------------------


class TestRunningFeatures:
    def test_weekly_km(self):
        # BASE_DATE is Monday. Add runs Mon-Wed.
        workouts = [
            _make_workout(BASE_DATE, distance_km=8.0),
            _make_workout(BASE_DATE + timedelta(days=1), distance_km=10.0),
            _make_workout(BASE_DATE + timedelta(days=2), distance_km=6.0),
        ]
        # Compute for Wednesday
        assert compute_weekly_km(workouts, BASE_DATE + timedelta(days=2)) == pytest.approx(24.0)

    def test_weekly_km_excludes_non_runs(self):
        workouts = [
            _make_workout(BASE_DATE, distance_km=8.0, session_type="run_easy"),
            _make_workout(BASE_DATE, distance_km=0.0, session_type="crossfit"),
        ]
        assert compute_weekly_km(workouts, BASE_DATE) == pytest.approx(8.0)

    def test_rolling_4w_km(self):
        workouts = [
            _make_workout(BASE_DATE - timedelta(days=i), distance_km=10.0)
            for i in range(0, 28, 3)
        ]
        expected = 10.0 * len(workouts)
        assert compute_rolling_4w_km(workouts, BASE_DATE) == pytest.approx(expected)

    def test_longest_run_last_7d(self):
        workouts = [
            _make_workout(BASE_DATE, distance_km=8.0),
            _make_workout(BASE_DATE - timedelta(days=2), distance_km=15.0),
            _make_workout(BASE_DATE - timedelta(days=5), distance_km=12.0),
        ]
        assert compute_longest_run_last_7d_km(workouts, BASE_DATE) == pytest.approx(15.0)

    def test_longest_run_no_runs(self):
        assert compute_longest_run_last_7d_km([], BASE_DATE) == pytest.approx(0.0)

    def test_easy_pace_fixed_hr(self):
        workouts = [
            _make_workout(
                BASE_DATE,
                avg_hr_bpm=140,
                avg_pace_sec_per_km=340.0,
            ),
            _make_workout(
                BASE_DATE - timedelta(days=3),
                avg_hr_bpm=142,
                avg_pace_sec_per_km=335.0,
            ),
            # Outside easy zone — should be excluded
            _make_workout(
                BASE_DATE - timedelta(days=5),
                avg_hr_bpm=160,
                avg_pace_sec_per_km=290.0,
            ),
        ]
        result = compute_easy_pace_fixed_hr(workouts, BASE_DATE)
        assert result is not None
        assert result == pytest.approx(337.5)

    def test_easy_pace_no_qualifying(self):
        workouts = [
            _make_workout(BASE_DATE, avg_hr_bpm=160, avg_pace_sec_per_km=290.0),
        ]
        assert compute_easy_pace_fixed_hr(workouts, BASE_DATE) is None

    def test_quality_sessions_last_14d(self):
        workouts = [
            _make_workout(BASE_DATE, session_type="run_quality"),
            _make_workout(BASE_DATE - timedelta(days=3), session_type="run_long"),
            _make_workout(BASE_DATE - timedelta(days=7), session_type="run_easy"),
            _make_workout(BASE_DATE - timedelta(days=10), session_type="run_quality"),
            # Outside 14d window
            _make_workout(BASE_DATE - timedelta(days=20), session_type="run_quality"),
        ]
        assert compute_quality_sessions_last_14d(workouts, BASE_DATE) == 3

    def test_projected_hm_time(self):
        workouts = [
            _make_workout(
                BASE_DATE,
                avg_hr_bpm=140,
                distance_km=10.0,
                avg_pace_sec_per_km=330.0,
            ),
        ]
        result = compute_projected_hm_time_sec(workouts, BASE_DATE)
        assert result is not None
        # 330 * 10 = 3300s for 10km → project to 21.0975km
        assert result > 3300

    def test_projected_hm_time_no_data(self):
        assert compute_projected_hm_time_sec([], BASE_DATE) is None

    def test_plan_adherence_all_hit(self):
        # BASE_DATE is Monday 2025-07-07. Place runs within each ISO week.
        workouts: list[WorkoutFact] = []
        for w in range(4):
            # Monday of each week going backwards
            monday = BASE_DATE - timedelta(weeks=w)
            for r in range(4):
                workouts.append(
                    _make_workout(
                        monday + timedelta(days=r),  # Mon-Thu of each week
                        distance_km=10.0,
                    )
                )
        result = compute_plan_adherence_pct(workouts, BASE_DATE + timedelta(days=3))
        assert result is not None
        assert result == pytest.approx(100.0)

    def test_plan_adherence_none_hit(self):
        workouts = [_make_workout(BASE_DATE, distance_km=5.0)]
        result = compute_plan_adherence_pct(workouts, BASE_DATE)
        assert result is not None
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Hybrid / load-balance feature tests
# ---------------------------------------------------------------------------


class TestHybridFeatures:
    def test_hard_day_count_7d(self):
        workouts = [
            _make_workout(BASE_DATE, session_type="run_quality"),
            _make_workout(BASE_DATE - timedelta(days=1), session_type="crossfit"),
            _make_workout(BASE_DATE - timedelta(days=2), session_type="run_long"),
            _make_workout(BASE_DATE - timedelta(days=3), session_type="run_easy"),
            _make_workout(BASE_DATE - timedelta(days=4), session_type="crossfit"),
            # Outside 7d window
            _make_workout(BASE_DATE - timedelta(days=10), session_type="crossfit"),
        ]
        assert compute_hard_day_count_7d(workouts, BASE_DATE) == 4

    def test_hard_day_count_same_day(self):
        """Two hard sessions on the same day count as one hard day."""
        workouts = [
            _make_workout(BASE_DATE, session_type="crossfit"),
            _make_workout(BASE_DATE, session_type="run_quality"),
        ]
        assert compute_hard_day_count_7d(workouts, BASE_DATE) == 1

    def test_run_intensity_distribution(self):
        workouts = [
            _make_workout(BASE_DATE, session_type="run_easy"),
            _make_workout(BASE_DATE - timedelta(days=1), session_type="run_easy"),
            _make_workout(BASE_DATE - timedelta(days=2), session_type="run_quality"),
            _make_workout(BASE_DATE - timedelta(days=4), session_type="run_long"),
        ]
        dist = compute_run_intensity_distribution(workouts, BASE_DATE)
        assert dist == {"easy": 2, "quality": 1, "long": 1}

    def test_lower_body_cf_density(self):
        workouts = [
            _make_workout(
                BASE_DATE,
                session_type="crossfit",
                is_lower_body_dominant=True,
            ),
            _make_workout(
                BASE_DATE - timedelta(days=2),
                session_type="crossfit",
                is_lower_body_dominant=False,
                lower_body_load_score=5.0,  # above threshold
            ),
            _make_workout(
                BASE_DATE - timedelta(days=4),
                session_type="crossfit",
                is_lower_body_dominant=False,
                lower_body_load_score=1.0,  # below threshold
            ),
        ]
        density = compute_lower_body_crossfit_density_7d(workouts, BASE_DATE)
        assert density == pytest.approx(2.0 / 7.0)

    def test_long_run_protection_good(self):
        """Long run with 3+ easy/rest days before it."""
        workouts = [
            _make_workout(BASE_DATE - timedelta(days=1), session_type="run_long"),
            _make_workout(BASE_DATE - timedelta(days=5), session_type="run_easy"),
        ]
        score = compute_long_run_protection_score(workouts, BASE_DATE)
        assert score == pytest.approx(100.0)

    def test_long_run_protection_bad(self):
        """Hard session immediately before long run."""
        workouts = [
            _make_workout(BASE_DATE, session_type="run_long"),
            _make_workout(BASE_DATE - timedelta(days=1), session_type="crossfit"),
        ]
        score = compute_long_run_protection_score(workouts, BASE_DATE)
        assert score < 100.0

    def test_interference_risk_low(self):
        """Very light week → low interference."""
        workouts = [
            _make_workout(BASE_DATE, session_type="run_easy"),
            _make_workout(BASE_DATE - timedelta(days=3), session_type="run_easy"),
        ]
        score = compute_interference_risk_score(workouts, BASE_DATE)
        assert score < 30.0

    def test_interference_risk_high(self):
        """Packed week with back-to-back hard days."""
        workouts = [
            _make_workout(BASE_DATE, session_type="crossfit", is_lower_body_dominant=True),
            _make_workout(BASE_DATE - timedelta(days=1), session_type="run_quality"),
            _make_workout(BASE_DATE - timedelta(days=2), session_type="crossfit",
                          is_lower_body_dominant=True),
            _make_workout(BASE_DATE - timedelta(days=3), session_type="run_long"),
            _make_workout(BASE_DATE - timedelta(days=4), session_type="crossfit",
                          is_lower_body_dominant=True),
        ]
        score = compute_interference_risk_score(workouts, BASE_DATE)
        assert score > 50.0

    def test_crossfit_tags_squats(self):
        w = _make_workout(BASE_DATE, session_type="crossfit", raw_notes="Back squat 5x5, pull-ups")
        tags = compute_crossfit_tags(w)
        assert tags["has_squats"] is True
        assert tags["is_lower_body_dominant"] is True
        assert tags["is_upper_body_dominant"] is True  # pull-ups

    def test_crossfit_tags_empty_notes(self):
        w = _make_workout(BASE_DATE, session_type="crossfit", raw_notes="")
        tags = compute_crossfit_tags(w)
        assert all(v is False for v in tags.values())


# ---------------------------------------------------------------------------
# Full pipeline integration
# ---------------------------------------------------------------------------


class TestFeaturePipeline:
    def test_compute_features_for_date(self):
        facts = _build_daily_facts(30)
        workouts = [
            _make_workout(BASE_DATE - timedelta(days=i), session_type="run_easy")
            for i in range(0, 21, 3)
        ]
        features = compute_features_for_date(BASE_DATE, facts, workouts)
        assert features.date == BASE_DATE
        assert features.hrv_7d_avg is not None
        assert features.sleep_7d_avg is not None
        assert features.weekly_km is not None
        assert features.hard_day_count_7d is not None
        assert features.interference_risk_score is not None

    def test_run_feature_pipeline_persists(self, db_session: Session):
        """Pipeline reads from DB and writes DailyFeatures rows."""
        # Seed 30 days of daily facts + workouts
        for i in range(30):
            d = BASE_DATE - timedelta(days=i)
            db_session.add(_make_daily(d))
            if i % 2 == 0:
                db_session.add(_make_workout(d))
        db_session.flush()

        result = run_feature_pipeline(db_session)
        db_session.commit()

        assert result.dates_computed == 30
        rows = db_session.scalars(select(DailyFeatures)).all()
        assert len(rows) == 30

        # Spot-check one row
        feat = db_session.get(DailyFeatures, BASE_DATE)
        assert feat is not None
        assert feat.hrv_7d_avg is not None
        assert feat.weekly_km is not None

    def test_run_feature_pipeline_date_range(self, db_session: Session):
        for i in range(30):
            db_session.add(_make_daily(BASE_DATE - timedelta(days=i)))
        db_session.flush()

        start = BASE_DATE - timedelta(days=5)
        result = run_feature_pipeline(db_session, start_date=start, end_date=BASE_DATE)
        db_session.commit()

        assert result.dates_computed == 6  # 5 days + BASE_DATE

    def test_run_feature_pipeline_skips_missing_dates(self, db_session: Session):
        # Only add dates 0, 2, 4 (skip 1, 3)
        for i in [0, 2, 4]:
            db_session.add(_make_daily(BASE_DATE - timedelta(days=i)))
        db_session.flush()

        start = BASE_DATE - timedelta(days=4)
        result = run_feature_pipeline(db_session, start_date=start, end_date=BASE_DATE)
        db_session.commit()

        assert result.dates_computed == 3
        assert result.dates_skipped == 2

    def test_pipeline_upsert_semantics(self, db_session: Session):
        """Re-running the pipeline updates existing features, not duplicates."""
        for i in range(7):
            db_session.add(_make_daily(BASE_DATE - timedelta(days=i)))
        db_session.flush()

        run_feature_pipeline(db_session)
        db_session.commit()

        rows_first = db_session.scalars(select(DailyFeatures)).all()
        assert len(rows_first) == 7

        # Run again
        run_feature_pipeline(db_session)
        db_session.commit()

        rows_second = db_session.scalars(select(DailyFeatures)).all()
        assert len(rows_second) == 7  # no duplicates
