"""Typed response and request payloads for all API endpoints."""

from __future__ import annotations

from datetime import date
from datetime import date as DateType
from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class ScoresPayload(BaseModel):
    recovery: float | None = None
    race_readiness: float | None = None
    general_health: float | None = None
    load_balance: float | None = None


# ---------------------------------------------------------------------------
# GET /api/today
# ---------------------------------------------------------------------------


class RecommendationPayload(BaseModel):
    mode: str
    recommended_action: str
    intensity_modifier: str | None = None
    duration_modifier: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    next_best_alternative: str | None = None
    risk_flags: list[str] = Field(default_factory=list)


class TodayResponse(BaseModel):
    date: date
    recommendation: RecommendationPayload | None = None
    scores: ScoresPayload | None = None
    subcomponents: dict[str, dict[str, float | None]] | None = None
    warnings: dict[str, bool] | None = None
    explanation: str | None = None


# ---------------------------------------------------------------------------
# GET /api/running
# ---------------------------------------------------------------------------


class RunningFeatures(BaseModel):
    weekly_km: float | None = None
    rolling_4w_km: float | None = None
    longest_run_last_7d_km: float | None = None
    easy_pace_fixed_hr_sec_per_km: float | None = None
    quality_sessions_last_14d: int | None = None
    projected_hm_time_sec: float | None = None
    plan_adherence_pct: float | None = None


class RunningTrendPoint(BaseModel):
    date: date
    weekly_km: float | None = None
    rolling_4w_km: float | None = None
    longest_run_last_7d_km: float | None = None
    easy_pace_fixed_hr_sec_per_km: float | None = None
    quality_sessions_last_14d: int | None = None


class RunningResponse(BaseModel):
    date: date
    current: RunningFeatures | None = None
    race_readiness_score: float | None = None
    trend: list[RunningTrendPoint] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


class HealthFeatures(BaseModel):
    body_weight_7d_avg: float | None = None
    body_weight_28d_slope: float | None = None
    sleep_consistency_score: float | None = None
    hrv_7d_avg: float | None = None
    resting_hr_7d_avg: float | None = None
    sleep_7d_avg: float | None = None
    sleep_debt_min: float | None = None
    mood_trend: float | None = None
    stress_trend: float | None = None
    steps_consistency_score: float | None = None
    pain_free_days_last_14d: int | None = None


class HealthTrendPoint(BaseModel):
    date: date
    body_weight_7d_avg: float | None = None
    hrv_7d_avg: float | None = None
    resting_hr_7d_avg: float | None = None
    sleep_7d_avg: float | None = None
    sleep_debt_min: float | None = None
    mood_trend: float | None = None
    stress_trend: float | None = None


class HealthResponse(BaseModel):
    date: date
    current: HealthFeatures | None = None
    general_health_score: float | None = None
    trend: list[HealthTrendPoint] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GET /api/strength
# ---------------------------------------------------------------------------


class StrengthFeatures(BaseModel):
    hard_day_count_7d: int | None = None
    lower_body_crossfit_density_7d: float | None = None
    long_run_protection_score: float | None = None
    interference_risk_score: float | None = None
    run_intensity_distribution: dict | None = None


class RecentWorkout(BaseModel):
    workout_id: str
    session_date: date
    session_type: str
    duration_min: float | None = None
    training_load: float | None = None
    is_lower_body_dominant: bool | None = None
    raw_notes: str | None = None


class StrengthTrendPoint(BaseModel):
    date: date
    hard_day_count_7d: int | None = None
    lower_body_crossfit_density_7d: float | None = None
    interference_risk_score: float | None = None


class StrengthResponse(BaseModel):
    date: date
    current: StrengthFeatures | None = None
    load_balance_score: float | None = None
    recent_workouts: list[RecentWorkout] = Field(default_factory=list)
    trend: list[StrengthTrendPoint] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GET /api/weekly-review
# ---------------------------------------------------------------------------


class WeekSummary(BaseModel):
    start_date: date
    end_date: date
    avg_recovery_score: float | None = None
    avg_race_readiness_score: float | None = None
    avg_general_health_score: float | None = None
    avg_load_balance_score: float | None = None
    total_km: float | None = None
    workout_count: int = 0
    avg_sleep_duration_min: float | None = None
    avg_hrv_ms: float | None = None
    avg_resting_hr_bpm: float | None = None


class ScoreChange(BaseModel):
    previous: float | None = None
    current: float | None = None
    delta: float | None = None


class ScoreChanges(BaseModel):
    recovery: ScoreChange | None = None
    race_readiness: ScoreChange | None = None
    general_health: ScoreChange | None = None
    load_balance: ScoreChange | None = None


class WeeklyReviewResponse(BaseModel):
    current_week: WeekSummary
    previous_week: WeekSummary | None = None
    score_changes: ScoreChanges | None = None
    flags: list[str] = Field(default_factory=list)
    explanation: str | None = None


# ---------------------------------------------------------------------------
# POST /api/ask
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    date: Optional[DateType] = None


class AskResponse(BaseModel):
    answer: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# POST /api/manual-input
# ---------------------------------------------------------------------------


class ManualInputRequest(BaseModel):
    date: date
    left_knee_pain_score: float | None = Field(None, ge=0, le=10)
    global_pain_score: float | None = Field(None, ge=0, le=10)
    soreness_score: float | None = Field(None, ge=0, le=10)
    mood_score: float | None = Field(None, ge=0, le=10)
    motivation_score: float | None = Field(None, ge=0, le=10)
    stress_score_subjective: float | None = Field(None, ge=0, le=10)
    illness_flag: bool | None = None
    free_text_note: str | None = Field(None, max_length=2000)


class ManualInputResponse(BaseModel):
    id: int
    date: date
    created: bool
