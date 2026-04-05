from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SessionType(enum.StrEnum):
    run_easy = "run_easy"
    run_quality = "run_quality"
    run_long = "run_long"
    crossfit = "crossfit"
    strength = "strength"
    walk = "walk"
    mobility = "mobility"
    bike = "bike"
    other = "other"


class RecommendationMode(enum.StrEnum):
    full_go = "full_go"
    train_as_planned = "train_as_planned"
    reduce_intensity = "reduce_intensity"
    recovery_focused = "recovery_focused"
    full_rest = "full_rest"
    injury_watch = "injury_watch"


# ---------------------------------------------------------------------------
# Raw layer - preserves original source payloads
# ---------------------------------------------------------------------------


class RawEvent(Base):
    __tablename__ = "raw_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(255))
    ingested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    event_date: Mapped[date | None] = mapped_column(Date)
    event_timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    record_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    source_file_name: Mapped[str | None] = mapped_column(String(500))
    quality_flag: Mapped[str | None] = mapped_column(String(50))


# ---------------------------------------------------------------------------
# Curated warehouse layer
# ---------------------------------------------------------------------------


class DailyFact(Base):
    __tablename__ = "daily_fact"

    date: Mapped[date] = mapped_column(Date, primary_key=True)

    # Core metrics
    body_weight_kg: Mapped[float | None] = mapped_column(Float)
    body_fat_pct: Mapped[float | None] = mapped_column(Float)
    resting_hr_bpm: Mapped[int | None] = mapped_column(Integer)
    hrv_ms: Mapped[float | None] = mapped_column(Float)
    sleep_duration_min: Mapped[float | None] = mapped_column(Float)
    sleep_score: Mapped[float | None] = mapped_column(Float)
    steps: Mapped[int | None] = mapped_column(Integer)
    active_energy_kcal: Mapped[float | None] = mapped_column(Float)
    training_readiness: Mapped[float | None] = mapped_column(Float)
    stress_score: Mapped[float | None] = mapped_column(Float)
    body_battery: Mapped[float | None] = mapped_column(Float)

    # Subjective
    soreness_score: Mapped[float | None] = mapped_column(Float)
    left_knee_pain_score: Mapped[float | None] = mapped_column(Float)
    motivation_score: Mapped[float | None] = mapped_column(Float)
    mood_score: Mapped[float | None] = mapped_column(Float)
    illness_flag: Mapped[bool | None] = mapped_column(Boolean)
    perceived_fatigue_score: Mapped[float | None] = mapped_column(Float)

    # Coverage
    has_garmin_data: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    has_apple_health_data: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    has_strava_data: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    has_scale_data: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    has_manual_input: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    data_quality_flag: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class WorkoutFact(Base):
    __tablename__ = "workout_fact"

    workout_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_workout_id: Mapped[str | None] = mapped_column(String(255))
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String(30), nullable=False)
    duration_min: Mapped[float | None] = mapped_column(Float)
    avg_hr_bpm: Mapped[int | None] = mapped_column(Integer)
    max_hr_bpm: Mapped[int | None] = mapped_column(Integer)
    training_load: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float | None] = mapped_column(Float)
    avg_pace_sec_per_km: Mapped[float | None] = mapped_column(Float)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float)
    calories_kcal: Mapped[float | None] = mapped_column(Float)

    # Run-specific
    route_type: Mapped[str | None] = mapped_column(String(50))
    cadence_spm: Mapped[int | None] = mapped_column(Integer)
    splits_json: Mapped[dict | None] = mapped_column(JSON)
    time_in_zones_json: Mapped[dict | None] = mapped_column(JSON)
    weather_json: Mapped[dict | None] = mapped_column(JSON)

    # CrossFit-specific
    is_strength: Mapped[bool | None] = mapped_column(Boolean)
    is_engine: Mapped[bool | None] = mapped_column(Boolean)
    is_metcon: Mapped[bool | None] = mapped_column(Boolean)
    has_squats: Mapped[bool | None] = mapped_column(Boolean)
    has_hinges: Mapped[bool | None] = mapped_column(Boolean)
    has_jumps: Mapped[bool | None] = mapped_column(Boolean)
    has_oly_lifts: Mapped[bool | None] = mapped_column(Boolean)
    is_upper_body_dominant: Mapped[bool | None] = mapped_column(Boolean)
    is_lower_body_dominant: Mapped[bool | None] = mapped_column(Boolean)
    session_rpe: Mapped[float | None] = mapped_column(Float)
    local_muscular_stress_tag: Mapped[str | None] = mapped_column(String(50))
    raw_notes: Mapped[str | None] = mapped_column(Text)

    # Derived scheduling / interference
    lower_body_load_score: Mapped[float | None] = mapped_column(Float)
    interference_contribution: Mapped[float | None] = mapped_column(Float)
    next_day_soreness_linked: Mapped[bool | None] = mapped_column(Boolean)
    training_phase_label: Mapped[str | None] = mapped_column(String(50))

    # Deduplication
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    duplicate_of_id: Mapped[str | None] = mapped_column(String(36))

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ManualDailyInput(Base):
    __tablename__ = "manual_daily_input"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    left_knee_pain_score: Mapped[float | None] = mapped_column(Float)
    global_pain_score: Mapped[float | None] = mapped_column(Float)
    soreness_score: Mapped[float | None] = mapped_column(Float)
    mood_score: Mapped[float | None] = mapped_column(Float)
    motivation_score: Mapped[float | None] = mapped_column(Float)
    stress_score_subjective: Mapped[float | None] = mapped_column(Float)
    illness_flag: Mapped[bool | None] = mapped_column(Boolean)
    free_text_note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class DailySourceCoverage(Base):
    __tablename__ = "daily_source_coverage"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    garmin_coverage: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    apple_health_coverage: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    strava_coverage: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    scale_coverage: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    manual_input_coverage: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    is_partial_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    coverage_note: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Feature layer
# ---------------------------------------------------------------------------


class DailyFeatures(Base):
    __tablename__ = "daily_features"

    date: Mapped[date] = mapped_column(Date, primary_key=True)

    # Recovery
    hrv_7d_avg: Mapped[float | None] = mapped_column(Float)
    hrv_vs_28d_pct: Mapped[float | None] = mapped_column(Float)
    resting_hr_7d_avg: Mapped[float | None] = mapped_column(Float)
    resting_hr_vs_28d_delta: Mapped[float | None] = mapped_column(Float)
    sleep_7d_avg: Mapped[float | None] = mapped_column(Float)
    sleep_debt_min: Mapped[float | None] = mapped_column(Float)
    recent_load_3d: Mapped[float | None] = mapped_column(Float)
    recent_load_7d: Mapped[float | None] = mapped_column(Float)
    recovery_trend: Mapped[float | None] = mapped_column(Float)

    # Running
    weekly_km: Mapped[float | None] = mapped_column(Float)
    rolling_4w_km: Mapped[float | None] = mapped_column(Float)
    longest_run_last_7d_km: Mapped[float | None] = mapped_column(Float)
    easy_pace_fixed_hr_sec_per_km: Mapped[float | None] = mapped_column(Float)
    quality_sessions_last_14d: Mapped[int | None] = mapped_column(Integer)
    projected_hm_time_sec: Mapped[float | None] = mapped_column(Float)
    plan_adherence_pct: Mapped[float | None] = mapped_column(Float)

    # Health
    body_weight_7d_avg: Mapped[float | None] = mapped_column(Float)
    body_weight_28d_slope: Mapped[float | None] = mapped_column(Float)
    sleep_consistency_score: Mapped[float | None] = mapped_column(Float)
    pain_free_days_last_14d: Mapped[int | None] = mapped_column(Integer)
    mood_trend: Mapped[float | None] = mapped_column(Float)
    stress_trend: Mapped[float | None] = mapped_column(Float)
    steps_consistency_score: Mapped[float | None] = mapped_column(Float)

    # Hybrid balance
    hard_day_count_7d: Mapped[int | None] = mapped_column(Integer)
    run_intensity_distribution_json: Mapped[dict | None] = mapped_column(JSON)
    lower_body_crossfit_density_7d: Mapped[float | None] = mapped_column(Float)
    long_run_protection_score: Mapped[float | None] = mapped_column(Float)
    interference_risk_score: Mapped[float | None] = mapped_column(Float)


# ---------------------------------------------------------------------------
# Score & recommendation snapshots
# ---------------------------------------------------------------------------


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshot"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    score_engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    recovery_score: Mapped[float | None] = mapped_column(Float)
    race_readiness_score: Mapped[float | None] = mapped_column(Float)
    general_health_score: Mapped[float | None] = mapped_column(Float)
    load_balance_score: Mapped[float | None] = mapped_column(Float)
    subcomponents_json: Mapped[dict | None] = mapped_column(JSON)
    warnings_json: Mapped[dict | None] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RecommendationSnapshot(Base):
    __tablename__ = "recommendation_snapshot"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    recommendation_engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(100), nullable=False)
    intensity_modifier: Mapped[str | None] = mapped_column(String(50))
    duration_modifier: Mapped[str | None] = mapped_column(String(50))
    reason_codes_json: Mapped[dict | None] = mapped_column(JSON)
    next_best_alternative: Mapped[str | None] = mapped_column(String(100))
    risk_flags_json: Mapped[dict | None] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Baseline & historical best blocks
# ---------------------------------------------------------------------------


class BaselineSnapshot(Base):
    __tablename__ = "baseline_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    window_type: Mapped[str] = mapped_column(String(30), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    baseline_value: Mapped[float | None] = mapped_column(Float)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    baseline_start_date: Mapped[date | None] = mapped_column(Date)
    baseline_end_date: Mapped[date | None] = mapped_column(Date)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class HistoricalBestBlock(Base):
    __tablename__ = "historical_best_block"

    block_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    block_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))
    metric_summary_json: Mapped[dict | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
