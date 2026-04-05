"""Warning logic for the scoring engine.

Evaluates hard warnings that can trigger recommendation overrides
regardless of total scores.
"""

from __future__ import annotations

from peakwise.config import (
    WARNING_HRV_SUPPRESSION_PCT,
    WARNING_KNEE_PAIN_THRESHOLD,
    WARNING_OVERLOAD_HARD_DAYS,
    WARNING_OVERLOAD_LOAD_7D,
    WARNING_RHR_SPIKE_DELTA,
    WARNING_SLEEP_DEBT_THRESHOLD,
)
from peakwise.models import DailyFact, DailyFeatures


def compute_knee_pain_warning(daily_fact: DailyFact) -> bool:
    if daily_fact.left_knee_pain_score is None:
        return False
    return daily_fact.left_knee_pain_score >= WARNING_KNEE_PAIN_THRESHOLD


def compute_illness_warning(daily_fact: DailyFact) -> bool:
    return daily_fact.illness_flag is True


def compute_sleep_debt_warning(features: DailyFeatures) -> bool:
    if features.sleep_debt_min is None:
        return False
    return features.sleep_debt_min >= WARNING_SLEEP_DEBT_THRESHOLD


def compute_hrv_suppression_warning(features: DailyFeatures) -> bool:
    if features.hrv_vs_28d_pct is None:
        return False
    return features.hrv_vs_28d_pct <= WARNING_HRV_SUPPRESSION_PCT


def compute_overload_warning(features: DailyFeatures) -> bool:
    load_triggered = (
        features.recent_load_7d is not None
        and features.recent_load_7d >= WARNING_OVERLOAD_LOAD_7D
    )
    hard_day_triggered = (
        features.hard_day_count_7d is not None
        and features.hard_day_count_7d >= WARNING_OVERLOAD_HARD_DAYS
    )
    return load_triggered or hard_day_triggered


def compute_all_warnings(
    features: DailyFeatures,
    daily_fact: DailyFact,
) -> dict[str, bool]:
    """Evaluate all warning conditions.

    Returns a dict mapping warning names to boolean active status.
    """
    return {
        "knee_pain_warning": compute_knee_pain_warning(daily_fact),
        "illness_warning": compute_illness_warning(daily_fact),
        "sleep_debt_warning": compute_sleep_debt_warning(features),
        "hrv_suppression_warning": compute_hrv_suppression_warning(features),
        "overload_warning": compute_overload_warning(features),
    }
