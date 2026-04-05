from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://peakwise:peakwise@localhost:5432/peakwise"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    debug: bool = False

    model_config = {"env_prefix": "PEAKWISE_", "env_file": ".env"}


# ---------------------------------------------------------------------------
# Feature engineering thresholds & constants
# ---------------------------------------------------------------------------

# Sleep target used for sleep debt calculation (minutes per night)
TARGET_SLEEP_MIN: float = 480.0

# Easy-run HR zone boundaries (bpm) for efficiency tracking
EASY_HR_ZONE_LOW: int = 130
EASY_HR_ZONE_HIGH: int = 150

# Minimum distance to classify as a long run (km)
LONG_RUN_MIN_KM: float = 15.0

# Weekly km target for plan adherence calculation
TARGET_WEEKLY_KM: float = 40.0

# Plan adherence: fraction of target that counts as "hitting the week"
PLAN_ADHERENCE_THRESHOLD: float = 0.95

# Number of weeks to evaluate plan adherence over
PLAN_ADHERENCE_WEEKS: int = 4

# Half-marathon distance (km)
HM_DISTANCE_KM: float = 21.0975

# Hard session types for load-balance calculation
HARD_SESSION_TYPES: frozenset[str] = frozenset({"run_quality", "run_long", "crossfit"})

# Run session types for running features
RUN_SESSION_TYPES: frozenset[str] = frozenset({"run_easy", "run_quality", "run_long"})

# Lower-body load score threshold (percentile proxy) for CF density
LOWER_BODY_LOAD_THRESHOLD: float = 3.0

# Minimum gap (days) before a long run to count as "protected"
LONG_RUN_PROTECTION_GAP_DAYS: int = 2

# Interference risk weights
INTERFERENCE_HARD_DAY_WEIGHT: float = 15.0
INTERFERENCE_LOWER_BODY_WEIGHT: float = 25.0
INTERFERENCE_SPACING_PENALTY: float = 20.0

# ---------------------------------------------------------------------------
# Scoring engine constants
# ---------------------------------------------------------------------------

SCORE_ENGINE_VERSION: str = "1.0.0"

# Default value for subcomponents when input data is missing
SCORE_MISSING_DEFAULT: float = 50.0

# --- Recovery score weights ---
RECOVERY_WEIGHTS: dict[str, float] = {
    "hrv": 0.20,
    "resting_hr": 0.15,
    "sleep": 0.20,
    "load": 0.15,
    "soreness": 0.10,
    "illness": 0.10,
    "subjective_fatigue": 0.05,
    "device_readiness": 0.05,
}

# HRV component: score = clamp(baseline + hrv_vs_28d_pct * scale, 0, 100)
RECOVERY_HRV_BASELINE_SCORE: float = 70.0
RECOVERY_HRV_SCALE: float = 3.0

# Resting HR: score = clamp(baseline - delta * scale, 0, 100)
RECOVERY_RHR_BASELINE_SCORE: float = 75.0
RECOVERY_RHR_SCALE: float = 8.0

# Sleep: average normalised from floor, debt penalty
RECOVERY_SLEEP_AVG_FLOOR: float = 300.0
RECOVERY_SLEEP_AVG_RANGE: float = 180.0
RECOVERY_SLEEP_DEBT_PENALTY_SCALE: float = 15.0

# Load: score = clamp(90 - load_3d * scale, 0, 100)
RECOVERY_LOAD_3D_SCALE: float = 0.175
RECOVERY_LOAD_7D_BLEND: float = 0.3  # 30% 7d, 70% 3d

# Soreness & fatigue: score = clamp(100 - value * scale, 0, 100)
RECOVERY_SORENESS_SCALE: float = 10.0
RECOVERY_FATIGUE_SCALE: float = 10.0

# --- Race-readiness score weights ---
RACE_READINESS_WEIGHTS: dict[str, float] = {
    "weekly_volume": 0.20,
    "long_run": 0.20,
    "easy_efficiency": 0.20,
    "quality_completion": 0.10,
    "projection": 0.15,
    "plan_adherence": 0.10,
    "trend": 0.05,
}

RACE_VOLUME_SCALE: float = 80.0
RACE_LONG_RUN_TARGET_KM: float = 18.0
RACE_EFFICIENCY_CEILING_SEC: float = 400.0
RACE_EFFICIENCY_RANGE_SEC: float = 150.0
RACE_QUALITY_TARGET_14D: int = 4
RACE_HM_TARGET_SEC: float = 5400.0   # 1 h 30 min
RACE_HM_CEILING_SEC: float = 7200.0  # 2 h
RACE_TREND_SCALE: float = 20.0

# --- General-health score weights ---
HEALTH_WEIGHTS: dict[str, float] = {
    "sleep_consistency": 0.20,
    "weight_trend": 0.15,
    "resting_hr_trend": 0.10,
    "hrv_stability": 0.10,
    "steps": 0.10,
    "pain": 0.15,
    "mood": 0.10,
    "stress": 0.10,
}

HEALTH_WEIGHT_LOSS_AGGRESSIVE: float = -0.05
HEALTH_WEIGHT_STABLE_RANGE: float = 0.02
HEALTH_PAIN_FREE_WINDOW: int = 14
HEALTH_TREND_SCALE: float = 30.0

# --- Load-balance score weights ---
LOAD_BALANCE_WEIGHTS: dict[str, float] = {
    "hard_day_density": 0.20,
    "lower_body_density": 0.20,
    "session_spacing": 0.15,
    "long_run_protection": 0.20,
    "run_distribution": 0.10,
    "interference": 0.15,
}

LOAD_BALANCE_HARD_DAY_IDEAL: int = 3
LOAD_BALANCE_HARD_DAY_MAX: int = 6
LOAD_BALANCE_EASY_TARGET_PCT: float = 0.80

# --- Warning thresholds ---
WARNING_KNEE_PAIN_THRESHOLD: float = 4.0
WARNING_SLEEP_DEBT_THRESHOLD: float = 300.0
WARNING_HRV_SUPPRESSION_PCT: float = -15.0
WARNING_RHR_SPIKE_DELTA: float = 5.0
WARNING_OVERLOAD_LOAD_7D: float = 700.0
WARNING_OVERLOAD_HARD_DAYS: int = 5

# ---------------------------------------------------------------------------
# Recommendation engine constants
# ---------------------------------------------------------------------------

RECOMMENDATION_ENGINE_VERSION: str = "1.0.0"

# Score thresholds for mode selection (applied to recovery score)
RECO_RECOVERY_FULL_GO: float = 80.0
RECO_RECOVERY_TRAIN_AS_PLANNED: float = 65.0
RECO_RECOVERY_REDUCE_INTENSITY: float = 50.0
RECO_RECOVERY_RECOVERY_FOCUSED: float = 35.0
# Below RECOVERY_FOCUSED → full_rest

# Load-balance threshold: below this, cap at reduce_intensity
RECO_LOAD_BALANCE_CAUTION: float = 50.0

# Health threshold: below this, cap at reduce_intensity
RECO_HEALTH_CAUTION: float = 45.0
