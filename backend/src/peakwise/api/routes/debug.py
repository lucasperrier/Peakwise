"""GET /api/debug/day — single-date debug endpoint for threshold tuning."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.api.deps import get_db
from peakwise.models import (
    DailyFact,
    DailyFeatures,
    DailyReasonCode,
    DailyScoreComponent,
    DailyScoreSnapshot,
    DailySourceCoverage,
    RecommendationSnapshot,
    ScoreSnapshot,
    WorkoutFact,
)
from peakwise.trust import compute_decision_confidence, compute_field_provenance, compute_source_coverage

router = APIRouter()

_LOOKBACK_DAYS = 14


@router.get("/debug/day")
def debug_day(
    target_date: date = Query(..., alias="date"),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> dict:
    target = target_date
    lookback_start = target - timedelta(days=_LOOKBACK_DAYS)

    # Raw daily facts
    fact: DailyFact | None = db.get(DailyFact, target)
    fact_dict = None
    if fact:
        fact_dict = {
            c.key: getattr(fact, c.key)
            for c in fact.__table__.columns
            if getattr(fact, c.key) is not None
        }

    # Features
    feat: DailyFeatures | None = db.get(DailyFeatures, target)
    feat_dict = None
    if feat:
        feat_dict = {
            c.key: getattr(feat, c.key)
            for c in feat.__table__.columns
            if getattr(feat, c.key) is not None
        }

    # Workouts in lookback window
    workouts = list(
        db.scalars(
            select(WorkoutFact).where(
                WorkoutFact.session_date >= lookback_start,
                WorkoutFact.session_date <= target,
                WorkoutFact.is_duplicate.is_(False),
            ).order_by(WorkoutFact.session_date.desc())
        ).all()
    )
    workout_list = []
    for w in workouts:
        workout_list.append({
            "workout_id": w.workout_id,
            "session_date": str(w.session_date),
            "session_type": w.session_type,
            "duration_min": w.duration_min,
            "training_load": w.training_load,
            "distance_km": w.distance_km,
            "is_lower_body_dominant": w.is_lower_body_dominant,
            "raw_notes": w.raw_notes,
        })

    # Score snapshot
    score: ScoreSnapshot | None = db.get(ScoreSnapshot, target)
    score_dict = None
    if score:
        score_dict = {
            "recovery_score": score.recovery_score,
            "race_readiness_score": score.race_readiness_score,
            "general_health_score": score.general_health_score,
            "load_balance_score": score.load_balance_score,
            "subcomponents": score.subcomponents_json,
            "warnings": score.warnings_json,
            "score_engine_version": score.score_engine_version,
        }

    # Score components
    components = list(
        db.scalars(
            select(DailyScoreComponent).where(DailyScoreComponent.date == target)
        ).all()
    )
    component_list = [
        {
            "score_type": c.score_type,
            "component_name": c.component_name,
            "raw_input_value": c.raw_input_value,
            "normalized_value": c.normalized_value,
            "weighted_contribution": c.weighted_contribution,
            "direction": c.direction,
        }
        for c in components
    ]

    # Reason codes
    reason_codes = list(
        db.scalars(
            select(DailyReasonCode).where(DailyReasonCode.date == target)
        ).all()
    )
    reason_list = [
        {
            "code": r.code,
            "source": r.source,
            "severity": r.severity,
            "detail": r.detail,
        }
        for r in reason_codes
    ]

    # Recommendation
    rec: RecommendationSnapshot | None = db.get(RecommendationSnapshot, target)
    rec_dict = None
    if rec:
        rec_dict = {
            "mode": rec.mode,
            "recommended_action": rec.recommended_action,
            "intensity_modifier": rec.intensity_modifier,
            "duration_modifier": rec.duration_modifier,
            "reason_codes": rec.reason_codes_json,
            "risk_flags": rec.risk_flags_json,
            "next_best_alternative": rec.next_best_alternative,
            "recommendation_engine_version": rec.recommendation_engine_version,
        }

    # Confidence
    confidence_score, confidence_level = compute_decision_confidence(fact, target, db)

    # Source coverage
    coverage = compute_source_coverage(fact) if fact else {}

    # Field provenance
    provenance = compute_field_provenance(fact) if fact else {}

    # Daily score snapshot (Phase 2)
    dss: DailyScoreSnapshot | None = db.get(DailyScoreSnapshot, target)
    dss_dict = None
    if dss:
        dss_dict = {
            "score_version": dss.score_version,
            "recommendation_version": dss.recommendation_version,
            "confidence_level": dss.confidence_level,
            "decision_confidence_score": dss.decision_confidence_score,
        }

    # Baseline comparisons (from features)
    baselines = {}
    if feat:
        baselines = {
            "hrv_vs_28d_pct": feat.hrv_vs_28d_pct,
            "resting_hr_vs_28d_delta": feat.resting_hr_vs_28d_delta,
            "body_weight_28d_slope": feat.body_weight_28d_slope,
            "sleep_debt_min": feat.sleep_debt_min,
        }

    return {
        "date": str(target),
        "daily_facts": fact_dict,
        "features": feat_dict,
        "workouts_in_lookback": workout_list,
        "baselines": baselines,
        "score_snapshot": score_dict,
        "score_components": component_list,
        "reason_codes": reason_list,
        "recommendation": rec_dict,
        "confidence": {
            "score": confidence_score,
            "level": confidence_level,
        },
        "source_coverage": coverage,
        "field_provenance": provenance,
        "score_breakdown": dss_dict,
    }
