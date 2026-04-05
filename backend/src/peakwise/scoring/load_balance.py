"""Load-balance score computation.

Measures whether running and CrossFit are balanced coherently, based on
hard-day density, lower-body CrossFit density, session spacing, long-run
protection, run intensity distribution, and interference risk.
"""

from __future__ import annotations

from peakwise.config import (
    LOAD_BALANCE_EASY_TARGET_PCT,
    LOAD_BALANCE_HARD_DAY_IDEAL,
    LOAD_BALANCE_HARD_DAY_MAX,
    LOAD_BALANCE_WEIGHTS,
    SCORE_MISSING_DEFAULT,
)
from peakwise.models import DailyFeatures


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _hard_day_density_component(features: DailyFeatures) -> float | None:
    if features.hard_day_count_7d is None:
        return None
    count = features.hard_day_count_7d
    if count <= LOAD_BALANCE_HARD_DAY_IDEAL:
        return 100.0
    # Linear decay from 100 at ideal to 0 at max
    span = LOAD_BALANCE_HARD_DAY_MAX - LOAD_BALANCE_HARD_DAY_IDEAL
    return _clamp(100.0 - (count - LOAD_BALANCE_HARD_DAY_IDEAL) / span * 100.0)


def _lower_body_density_component(features: DailyFeatures) -> float | None:
    if features.lower_body_crossfit_density_7d is None:
        return None
    # density is a fraction 0-1; lower is better
    return _clamp(100.0 - features.lower_body_crossfit_density_7d * 200.0)


def _session_spacing_component(features: DailyFeatures) -> float | None:
    """Approximate session-spacing quality from hard-day count.

    Fewer hard days implies more rest days between sessions.
    """
    if features.hard_day_count_7d is None:
        return None
    count = features.hard_day_count_7d
    if count <= 2:
        return 100.0
    if count == 3:
        return 85.0
    if count == 4:
        return 60.0
    return _clamp(60.0 - (count - 4) * 20.0)


def _long_run_protection_component(features: DailyFeatures) -> float | None:
    if features.long_run_protection_score is None:
        return None
    return _clamp(features.long_run_protection_score)


def _run_distribution_component(features: DailyFeatures) -> float | None:
    dist = features.run_intensity_distribution_json
    if not dist or not isinstance(dist, dict):
        return None
    easy = dist.get("easy", 0)
    quality = dist.get("quality", 0)
    long = dist.get("long", 0)
    total = easy + quality + long
    if total == 0:
        return SCORE_MISSING_DEFAULT
    easy_pct = easy / total
    # Closer to target → higher score
    deviation = abs(easy_pct - LOAD_BALANCE_EASY_TARGET_PCT)
    return _clamp(100.0 - deviation * 200.0)


def _interference_component(features: DailyFeatures) -> float | None:
    if features.interference_risk_score is None:
        return None
    # interference_risk_score: 0-100 where higher = worse; invert for component
    return _clamp(100.0 - features.interference_risk_score)


def compute_load_balance_score(
    features: DailyFeatures,
) -> tuple[float, dict[str, float | None]]:
    """Compute the load-balance score and its subcomponents.

    Returns a tuple of (score, subcomponents_dict).
    """
    subcomponents: dict[str, float | None] = {
        "hard_day_density_component": _hard_day_density_component(features),
        "lower_body_density_component": _lower_body_density_component(features),
        "session_spacing_component": _session_spacing_component(features),
        "long_run_protection_component": _long_run_protection_component(features),
        "run_distribution_component": _run_distribution_component(features),
        "interference_component": _interference_component(features),
    }

    weights = LOAD_BALANCE_WEIGHTS
    key_map = {
        "hard_day_density": "hard_day_density_component",
        "lower_body_density": "lower_body_density_component",
        "session_spacing": "session_spacing_component",
        "long_run_protection": "long_run_protection_component",
        "run_distribution": "run_distribution_component",
        "interference": "interference_component",
    }

    score = 0.0
    for weight_key, comp_key in key_map.items():
        value = subcomponents[comp_key]
        if value is None:
            value = SCORE_MISSING_DEFAULT
        score += value * weights[weight_key]

    return _clamp(score), subcomponents
