"""Score breakdown persistence.

Writes DailyScoreSnapshot, DailyScoreComponent, and DailyReasonCode rows
from the scoring and recommendation pipeline outputs.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from peakwise.config import (
    HEALTH_WEIGHTS,
    LOAD_BALANCE_WEIGHTS,
    RACE_READINESS_WEIGHTS,
    RECOMMENDATION_ENGINE_VERSION,
    RECOVERY_WEIGHTS,
    SCORE_ENGINE_VERSION,
)
from peakwise.models import (
    DailyReasonCode,
    DailyScoreComponent,
    DailyScoreSnapshot,
    RecommendationSnapshot,
    ScoreSnapshot,
)

logger = logging.getLogger("peakwise.scoring.breakdowns")


def _direction(value: float | None) -> str:
    """Classify component direction."""
    if value is None:
        return "neutral"
    if value >= 60.0:
        return "positive"
    if value < 40.0:
        return "negative"
    return "neutral"


_WEIGHT_MAPS: dict[str, dict[str, float]] = {
    "recovery": RECOVERY_WEIGHTS,
    "race_readiness": RACE_READINESS_WEIGHTS,
    "general_health": HEALTH_WEIGHTS,
    "load_balance": LOAD_BALANCE_WEIGHTS,
}

# Maps config weight key → subcomponent JSON key
_COMPONENT_KEY_MAPS: dict[str, dict[str, str]] = {
    "recovery": {
        "hrv": "hrv_component",
        "resting_hr": "resting_hr_component",
        "sleep": "sleep_component",
        "load": "load_component",
        "soreness": "soreness_component",
        "illness": "illness_component",
        "subjective_fatigue": "subjective_fatigue_component",
        "device_readiness": "device_readiness_component",
    },
    "race_readiness": {
        "weekly_volume": "weekly_volume_component",
        "long_run": "long_run_component",
        "easy_efficiency": "easy_efficiency_component",
        "quality_completion": "quality_completion_component",
        "projection": "projection_component",
        "plan_adherence": "plan_adherence_component",
        "trend": "trend_component",
    },
    "general_health": {
        "sleep_consistency": "sleep_consistency_component",
        "weight_trend": "weight_trend_component",
        "resting_hr_trend": "resting_hr_trend_component",
        "hrv_stability": "hrv_stability_component",
        "steps": "steps_component",
        "pain": "pain_component",
        "mood": "mood_component",
        "stress": "stress_component",
    },
    "load_balance": {
        "hard_day_density": "hard_day_density_component",
        "lower_body_density": "lower_body_density_component",
        "session_spacing": "session_spacing_component",
        "long_run_protection": "long_run_protection_component",
        "run_distribution": "run_distribution_component",
        "interference": "interference_component",
    },
}


def persist_score_breakdown(
    target_date: date,
    score_snapshot: ScoreSnapshot,
    rec_snapshot: RecommendationSnapshot | None,
    confidence_score: float | None,
    confidence_level: str | None,
    session: Session,
) -> DailyScoreSnapshot:
    """Persist the full score breakdown for one date.

    Creates/updates DailyScoreSnapshot, DailyScoreComponent rows,
    and DailyReasonCode rows.
    """
    # Upsert DailyScoreSnapshot
    dss = DailyScoreSnapshot(
        date=target_date,
        recovery_score=score_snapshot.recovery_score,
        race_readiness_score=score_snapshot.race_readiness_score,
        general_health_score=score_snapshot.general_health_score,
        load_balance_score=score_snapshot.load_balance_score,
        recommendation_mode=rec_snapshot.mode if rec_snapshot else None,
        recommended_action=rec_snapshot.recommended_action if rec_snapshot else None,
        score_version=SCORE_ENGINE_VERSION,
        recommendation_version=RECOMMENDATION_ENGINE_VERSION,
        confidence_level=confidence_level,
        decision_confidence_score=confidence_score,
    )
    session.merge(dss)

    # Clear old components for this date
    session.execute(
        delete(DailyScoreComponent).where(DailyScoreComponent.date == target_date)
    )

    # Persist score components
    subcomponents = score_snapshot.subcomponents_json or {}
    for score_type, comp_key_map in _COMPONENT_KEY_MAPS.items():
        subs = subcomponents.get(score_type, {})
        weights = _WEIGHT_MAPS.get(score_type, {})

        for weight_key, comp_key in comp_key_map.items():
            raw_value = subs.get(comp_key)
            weight = weights.get(weight_key, 0.0)
            normalized = raw_value if raw_value is not None else None
            weighted = round(raw_value * weight, 2) if raw_value is not None else None

            session.add(DailyScoreComponent(
                date=target_date,
                score_type=score_type,
                component_name=comp_key,
                raw_input_value=raw_value,
                normalized_value=normalized,
                weighted_contribution=weighted,
                direction=_direction(raw_value),
            ))

    # Clear old reason codes for this date
    session.execute(
        delete(DailyReasonCode).where(DailyReasonCode.date == target_date)
    )

    # Persist reason codes from warnings
    warnings = score_snapshot.warnings_json or {}
    warning_code_map = {
        "knee_pain_warning": ("knee_pain_flag", "warning", "Knee pain score elevated"),
        "illness_warning": ("illness_active", "warning", "Illness flag active"),
        "sleep_debt_warning": ("sleep_debt_high", "warning", "Accumulated sleep debt high"),
        "hrv_suppression_warning": ("hrv_below_baseline", "warning", "HRV suppressed vs baseline"),
        "overload_warning": ("lower_body_density_high", "warning", "Training overload detected"),
    }
    for warning_key, (code, severity, detail) in warning_code_map.items():
        if warnings.get(warning_key):
            session.add(DailyReasonCode(
                date=target_date,
                code=code,
                source="scoring",
                severity=severity,
                detail=detail,
            ))

    # Persist reason codes from recommendation
    if rec_snapshot and rec_snapshot.reason_codes_json:
        for code in rec_snapshot.reason_codes_json:
            session.add(DailyReasonCode(
                date=target_date,
                code=code,
                source="recommendation",
                severity="info",
                detail=None,
            ))

    # Data coverage low flag
    if confidence_level in ("low", "insufficient"):
        session.add(DailyReasonCode(
            date=target_date,
            code="data_coverage_low",
            source="trust",
            severity="warning",
            detail=f"Decision confidence: {confidence_score}%",
        ))

    session.flush()
    return dss
