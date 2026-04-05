"""Recovery score computation.

Estimates whether the user is ready to absorb training today, based on
HRV, resting HR, sleep, recent load, soreness, illness, subjective
fatigue, and device readiness.
"""

from __future__ import annotations

from peakwise.config import (
    RECOVERY_FATIGUE_SCALE,
    RECOVERY_HRV_BASELINE_SCORE,
    RECOVERY_HRV_SCALE,
    RECOVERY_LOAD_3D_SCALE,
    RECOVERY_LOAD_7D_BLEND,
    RECOVERY_RHR_BASELINE_SCORE,
    RECOVERY_RHR_SCALE,
    RECOVERY_SLEEP_AVG_FLOOR,
    RECOVERY_SLEEP_AVG_RANGE,
    RECOVERY_SLEEP_DEBT_PENALTY_SCALE,
    RECOVERY_SORENESS_SCALE,
    RECOVERY_WEIGHTS,
    SCORE_MISSING_DEFAULT,
)
from peakwise.models import DailyFact, DailyFeatures


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _hrv_component(features: DailyFeatures) -> float | None:
    if features.hrv_vs_28d_pct is None:
        return None
    return _clamp(RECOVERY_HRV_BASELINE_SCORE + features.hrv_vs_28d_pct * RECOVERY_HRV_SCALE)


def _resting_hr_component(features: DailyFeatures) -> float | None:
    if features.resting_hr_vs_28d_delta is None:
        return None
    return _clamp(RECOVERY_RHR_BASELINE_SCORE - features.resting_hr_vs_28d_delta * RECOVERY_RHR_SCALE)


def _sleep_component(features: DailyFeatures) -> float | None:
    if features.sleep_7d_avg is None:
        return None
    avg_score = _clamp((features.sleep_7d_avg - RECOVERY_SLEEP_AVG_FLOOR) / RECOVERY_SLEEP_AVG_RANGE * 100.0)
    debt_penalty = _clamp((features.sleep_debt_min or 0.0) / RECOVERY_SLEEP_DEBT_PENALTY_SCALE, 0.0, 40.0)
    return _clamp(avg_score - debt_penalty)


def _load_component(features: DailyFeatures) -> float | None:
    load_3d = features.recent_load_3d
    load_7d = features.recent_load_7d
    if load_3d is None and load_7d is None:
        return None
    score_3d = _clamp(90.0 - (load_3d or 0.0) * RECOVERY_LOAD_3D_SCALE)
    score_7d = _clamp(90.0 - (load_7d or 0.0) * RECOVERY_LOAD_3D_SCALE * 0.5)
    return score_3d * (1 - RECOVERY_LOAD_7D_BLEND) + score_7d * RECOVERY_LOAD_7D_BLEND


def _soreness_component(daily_fact: DailyFact) -> float | None:
    if daily_fact.soreness_score is None:
        return None
    return _clamp(100.0 - daily_fact.soreness_score * RECOVERY_SORENESS_SCALE)


def _illness_component(daily_fact: DailyFact) -> float:
    if daily_fact.illness_flag is True:
        return 0.0
    return 100.0


def _subjective_fatigue_component(daily_fact: DailyFact) -> float | None:
    if daily_fact.perceived_fatigue_score is None:
        return None
    return _clamp(100.0 - daily_fact.perceived_fatigue_score * RECOVERY_FATIGUE_SCALE)


def _device_readiness_component(daily_fact: DailyFact) -> float | None:
    if daily_fact.training_readiness is None:
        return None
    return _clamp(daily_fact.training_readiness)


def compute_recovery_score(
    features: DailyFeatures,
    daily_fact: DailyFact,
) -> tuple[float, dict[str, float | None]]:
    """Compute the recovery score and its subcomponents.

    Returns a tuple of (score, subcomponents_dict).
    """
    subcomponents: dict[str, float | None] = {
        "hrv_component": _hrv_component(features),
        "resting_hr_component": _resting_hr_component(features),
        "sleep_component": _sleep_component(features),
        "load_component": _load_component(features),
        "soreness_component": _soreness_component(daily_fact),
        "illness_component": _illness_component(daily_fact),
        "subjective_fatigue_component": _subjective_fatigue_component(daily_fact),
        "device_readiness_component": _device_readiness_component(daily_fact),
    }

    weights = RECOVERY_WEIGHTS
    key_map = {
        "hrv": "hrv_component",
        "resting_hr": "resting_hr_component",
        "sleep": "sleep_component",
        "load": "load_component",
        "soreness": "soreness_component",
        "illness": "illness_component",
        "subjective_fatigue": "subjective_fatigue_component",
        "device_readiness": "device_readiness_component",
    }

    score = 0.0
    for weight_key, comp_key in key_map.items():
        value = subcomponents[comp_key]
        if value is None:
            value = SCORE_MISSING_DEFAULT
        score += value * weights[weight_key]

    return _clamp(score), subcomponents
