"""Race-readiness score computation.

Estimates progression toward the half-marathon target based on weekly
volume, long-run completion, easy-run efficiency, quality sessions,
projected HM time, plan adherence, and trend direction.
"""

from __future__ import annotations

from peakwise.config import (
    RACE_EFFICIENCY_CEILING_SEC,
    RACE_EFFICIENCY_RANGE_SEC,
    RACE_HM_CEILING_SEC,
    RACE_HM_TARGET_SEC,
    RACE_LONG_RUN_TARGET_KM,
    RACE_QUALITY_TARGET_14D,
    RACE_READINESS_WEIGHTS,
    RACE_TREND_SCALE,
    RACE_VOLUME_SCALE,
    SCORE_MISSING_DEFAULT,
    TARGET_WEEKLY_KM,
)
from peakwise.models import DailyFeatures


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _weekly_volume_component(features: DailyFeatures) -> float | None:
    if features.weekly_km is None:
        return None
    return _clamp(features.weekly_km / TARGET_WEEKLY_KM * RACE_VOLUME_SCALE)


def _long_run_component(features: DailyFeatures) -> float | None:
    if features.longest_run_last_7d_km is None:
        return None
    if features.longest_run_last_7d_km == 0.0:
        return 40.0  # no long run this week, partial credit
    return _clamp(features.longest_run_last_7d_km / RACE_LONG_RUN_TARGET_KM * 100.0)


def _easy_efficiency_component(features: DailyFeatures) -> float | None:
    if features.easy_pace_fixed_hr_sec_per_km is None:
        return None
    return _clamp(
        (RACE_EFFICIENCY_CEILING_SEC - features.easy_pace_fixed_hr_sec_per_km)
        / RACE_EFFICIENCY_RANGE_SEC
        * 100.0
    )


def _quality_completion_component(features: DailyFeatures) -> float | None:
    if features.quality_sessions_last_14d is None:
        return None
    return _clamp(features.quality_sessions_last_14d / RACE_QUALITY_TARGET_14D * 100.0)


def _projection_component(features: DailyFeatures) -> float | None:
    if features.projected_hm_time_sec is None:
        return None
    return _clamp(
        (RACE_HM_CEILING_SEC - features.projected_hm_time_sec)
        / (RACE_HM_CEILING_SEC - RACE_HM_TARGET_SEC)
        * 100.0
    )


def _plan_adherence_component(features: DailyFeatures) -> float | None:
    if features.plan_adherence_pct is None:
        return None
    return _clamp(features.plan_adherence_pct)


def _trend_component(features: DailyFeatures) -> float | None:
    if features.recovery_trend is None:
        return None
    return _clamp(50.0 + features.recovery_trend * RACE_TREND_SCALE)


def compute_race_readiness_score(
    features: DailyFeatures,
) -> tuple[float, dict[str, float | None]]:
    """Compute the race-readiness score and its subcomponents.

    Returns a tuple of (score, subcomponents_dict).
    """
    subcomponents: dict[str, float | None] = {
        "weekly_volume_component": _weekly_volume_component(features),
        "long_run_component": _long_run_component(features),
        "easy_efficiency_component": _easy_efficiency_component(features),
        "quality_completion_component": _quality_completion_component(features),
        "projection_component": _projection_component(features),
        "plan_adherence_component": _plan_adherence_component(features),
        "trend_component": _trend_component(features),
    }

    weights = RACE_READINESS_WEIGHTS
    key_map = {
        "weekly_volume": "weekly_volume_component",
        "long_run": "long_run_component",
        "easy_efficiency": "easy_efficiency_component",
        "quality_completion": "quality_completion_component",
        "projection": "projection_component",
        "plan_adherence": "plan_adherence_component",
        "trend": "trend_component",
    }

    score = 0.0
    for weight_key, comp_key in key_map.items():
        value = subcomponents[comp_key]
        if value is None:
            value = SCORE_MISSING_DEFAULT
        score += value * weights[weight_key]

    return _clamp(score), subcomponents
