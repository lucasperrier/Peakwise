"""General-health score computation.

Tracks long-term health sustainability based on sleep consistency,
body-weight trend, resting HR trend, HRV stability, steps consistency,
pain status, mood, and stress.
"""

from __future__ import annotations

from peakwise.config import (
    HEALTH_PAIN_FREE_WINDOW,
    HEALTH_TREND_SCALE,
    HEALTH_WEIGHT_LOSS_AGGRESSIVE,
    HEALTH_WEIGHT_STABLE_RANGE,
    HEALTH_WEIGHTS,
    SCORE_MISSING_DEFAULT,
)
from peakwise.models import DailyFeatures


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _sleep_consistency_component(features: DailyFeatures) -> float | None:
    if features.sleep_consistency_score is None:
        return None
    return _clamp(features.sleep_consistency_score)


def _weight_trend_component(features: DailyFeatures) -> float | None:
    if features.body_weight_28d_slope is None:
        return None
    slope = features.body_weight_28d_slope
    # Stable weight → high score; aggressive loss or gain → lower score
    if abs(slope) <= HEALTH_WEIGHT_STABLE_RANGE:
        return 90.0
    if slope < HEALTH_WEIGHT_LOSS_AGGRESSIVE:
        # Aggressive loss: score drops linearly
        return _clamp(90.0 + (slope - HEALTH_WEIGHT_LOSS_AGGRESSIVE) * 500.0)
    if slope < -HEALTH_WEIGHT_STABLE_RANGE:
        # Moderate loss: mild concern
        return 75.0
    # Weight gain beyond stable range
    return _clamp(90.0 - (slope - HEALTH_WEIGHT_STABLE_RANGE) * 300.0)


def _resting_hr_trend_component(features: DailyFeatures) -> float | None:
    if features.resting_hr_vs_28d_delta is None:
        return None
    # Lower delta (or negative) is better
    return _clamp(80.0 - features.resting_hr_vs_28d_delta * 8.0)


def _hrv_stability_component(features: DailyFeatures) -> float | None:
    if features.hrv_vs_28d_pct is None:
        return None
    # HRV at or above baseline is good; large drops are bad
    return _clamp(70.0 + features.hrv_vs_28d_pct * 2.0)


def _steps_component(features: DailyFeatures) -> float | None:
    if features.steps_consistency_score is None:
        return None
    return _clamp(features.steps_consistency_score)


def _pain_component(features: DailyFeatures) -> float | None:
    if features.pain_free_days_last_14d is None:
        return None
    return _clamp(features.pain_free_days_last_14d / HEALTH_PAIN_FREE_WINDOW * 100.0)


def _mood_component(features: DailyFeatures) -> float | None:
    if features.mood_trend is None:
        return None
    # Positive slope = improving mood → higher score
    return _clamp(60.0 + features.mood_trend * HEALTH_TREND_SCALE)


def _stress_component(features: DailyFeatures) -> float | None:
    if features.stress_trend is None:
        return None
    # Positive slope = worsening stress → lower score
    return _clamp(60.0 - features.stress_trend * HEALTH_TREND_SCALE)


def compute_general_health_score(
    features: DailyFeatures,
) -> tuple[float, dict[str, float | None]]:
    """Compute the general-health score and its subcomponents.

    Returns a tuple of (score, subcomponents_dict).
    """
    subcomponents: dict[str, float | None] = {
        "sleep_consistency_component": _sleep_consistency_component(features),
        "weight_trend_component": _weight_trend_component(features),
        "resting_hr_trend_component": _resting_hr_trend_component(features),
        "hrv_stability_component": _hrv_stability_component(features),
        "steps_component": _steps_component(features),
        "pain_component": _pain_component(features),
        "mood_component": _mood_component(features),
        "stress_component": _stress_component(features),
    }

    weights = HEALTH_WEIGHTS
    key_map = {
        "sleep_consistency": "sleep_consistency_component",
        "weight_trend": "weight_trend_component",
        "resting_hr_trend": "resting_hr_trend_component",
        "hrv_stability": "hrv_stability_component",
        "steps": "steps_component",
        "pain": "pain_component",
        "mood": "mood_component",
        "stress": "stress_component",
    }

    score = 0.0
    for weight_key, comp_key in key_map.items():
        value = subcomponents[comp_key]
        if value is None:
            value = SCORE_MISSING_DEFAULT
        score += value * weights[weight_key]

    return _clamp(score), subcomponents
