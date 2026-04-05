"""Structured context assembler for LLM consumption.

Builds typed context dictionaries from score, feature, and recommendation
snapshots. The LLM receives only these structured contexts — never raw
database rows — so it can only explain what the system has computed.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from peakwise.models import (
    DailyFact,
    DailyFeatures,
    RecommendationSnapshot,
    ScoreSnapshot,
)


def _round_or_none(val: float | None, ndigits: int = 1) -> float | None:
    return round(val, ndigits) if val is not None else None


def _safe_dict(obj: Any, keys: list[str]) -> dict[str, Any]:
    """Extract a subset of attributes from an ORM object, skipping None."""
    result: dict[str, Any] = {}
    for k in keys:
        v = getattr(obj, k, None)
        if v is not None:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Daily "today" context
# ---------------------------------------------------------------------------

_FACT_KEYS = [
    "body_weight_kg",
    "resting_hr_bpm",
    "hrv_ms",
    "sleep_duration_min",
    "sleep_score",
    "steps",
    "soreness_score",
    "left_knee_pain_score",
    "mood_score",
    "illness_flag",
    "perceived_fatigue_score",
    "training_readiness",
]

_FEATURE_KEYS = [
    # Recovery
    "hrv_7d_avg",
    "hrv_vs_28d_pct",
    "resting_hr_7d_avg",
    "resting_hr_vs_28d_delta",
    "sleep_7d_avg",
    "sleep_debt_min",
    "recent_load_3d",
    "recent_load_7d",
    "recovery_trend",
    # Running
    "weekly_km",
    "rolling_4w_km",
    "longest_run_last_7d_km",
    "easy_pace_fixed_hr_sec_per_km",
    "quality_sessions_last_14d",
    "projected_hm_time_sec",
    "plan_adherence_pct",
    # Health
    "body_weight_7d_avg",
    "body_weight_28d_slope",
    "sleep_consistency_score",
    "pain_free_days_last_14d",
    "mood_trend",
    "stress_trend",
    "steps_consistency_score",
    # Hybrid
    "hard_day_count_7d",
    "lower_body_crossfit_density_7d",
    "long_run_protection_score",
    "interference_risk_score",
]


def assemble_today_context(
    target_date: date,
    session: Session,
) -> dict[str, Any] | None:
    """Build a structured context dict for the daily explanation.

    Returns ``None`` if no score snapshot exists for the date.
    """
    score: ScoreSnapshot | None = session.get(ScoreSnapshot, target_date)
    if score is None:
        return None

    rec: RecommendationSnapshot | None = session.get(RecommendationSnapshot, target_date)
    feat: DailyFeatures | None = session.get(DailyFeatures, target_date)
    fact: DailyFact | None = session.get(DailyFact, target_date)

    ctx: dict[str, Any] = {"date": target_date.isoformat()}

    # Scores
    ctx["scores"] = {
        "recovery": _round_or_none(score.recovery_score),
        "race_readiness": _round_or_none(score.race_readiness_score),
        "general_health": _round_or_none(score.general_health_score),
        "load_balance": _round_or_none(score.load_balance_score),
    }

    # Subcomponents
    if score.subcomponents_json:
        ctx["subcomponents"] = score.subcomponents_json

    # Warnings
    active_warnings = {
        k: v for k, v in (score.warnings_json or {}).items() if v is True
    }
    if active_warnings:
        ctx["active_warnings"] = list(active_warnings.keys())

    # Recommendation
    if rec is not None:
        ctx["recommendation"] = {
            "mode": rec.mode,
            "action": rec.recommended_action,
            "reason_codes": rec.reason_codes_json or [],
            "risk_flags": rec.risk_flags_json or [],
        }
        if rec.intensity_modifier:
            ctx["recommendation"]["intensity_modifier"] = rec.intensity_modifier
        if rec.duration_modifier:
            ctx["recommendation"]["duration_modifier"] = rec.duration_modifier
        if rec.next_best_alternative:
            ctx["recommendation"]["alternative"] = rec.next_best_alternative

    # Features (non-null only)
    if feat is not None:
        ctx["features"] = _safe_dict(feat, _FEATURE_KEYS)

    # Daily facts (non-null only)
    if fact is not None:
        ctx["daily_metrics"] = _safe_dict(fact, _FACT_KEYS)

    return ctx


# ---------------------------------------------------------------------------
# Weekly review context
# ---------------------------------------------------------------------------


def assemble_weekly_review_context(
    current_week: dict[str, Any],
    previous_week: dict[str, Any] | None,
    score_changes: dict[str, Any] | None,
    flags: list[str],
) -> dict[str, Any]:
    """Build a structured context dict for the weekly review explanation.

    Accepts the already-serialised API payloads so duplication is avoided.
    """
    ctx: dict[str, Any] = {"current_week": current_week}
    if previous_week is not None:
        ctx["previous_week"] = previous_week
    if score_changes is not None:
        ctx["score_changes"] = score_changes
    if flags:
        ctx["flags"] = flags
    return ctx


# ---------------------------------------------------------------------------
# Question-answering context
# ---------------------------------------------------------------------------


def assemble_qa_context(
    target_date: date,
    session: Session,
) -> dict[str, Any] | None:
    """Build a context dict for follow-up Q&A.

    Reuses the today context and adds a note about what data is available.
    """
    today_ctx = assemble_today_context(target_date, session)
    if today_ctx is None:
        return None
    today_ctx["context_type"] = "qa"
    return today_ctx
