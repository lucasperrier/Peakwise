"""GET /api/today — daily recommendation and score snapshot."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from peakwise.api.deps import get_db
from peakwise.api.schemas import (
    RecommendationPayload,
    ScoresPayload,
    TodayResponse,
)
from peakwise.config import RECOMMENDATION_ENGINE_VERSION, SCORE_ENGINE_VERSION, Settings
from peakwise.llm.pipeline import explain_today
from peakwise.models import DailyFact, RecommendationSnapshot, ScoreSnapshot
from peakwise.trust import compute_decision_confidence

logger = logging.getLogger("peakwise.api.today")

router = APIRouter()


@router.get("/today", response_model=TodayResponse)
def get_today(
    target_date: date | None = Query(None, alias="date"),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> TodayResponse:
    target = target_date or date.today()

    score: ScoreSnapshot | None = db.get(ScoreSnapshot, target)
    rec: RecommendationSnapshot | None = db.get(RecommendationSnapshot, target)

    recommendation = None
    if rec is not None:
        recommendation = RecommendationPayload(
            mode=rec.mode,
            recommended_action=rec.recommended_action,
            intensity_modifier=rec.intensity_modifier,
            duration_modifier=rec.duration_modifier,
            reason_codes=rec.reason_codes_json or [],
            next_best_alternative=rec.next_best_alternative,
            risk_flags=rec.risk_flags_json or [],
        )

    scores = None
    subcomponents = None
    warnings = None
    if score is not None:
        scores = ScoresPayload(
            recovery=score.recovery_score,
            race_readiness=score.race_readiness_score,
            general_health=score.general_health_score,
            load_balance=score.load_balance_score,
        )
        subcomponents = score.subcomponents_json
        warnings = score.warnings_json

    # Decision confidence
    fact: DailyFact | None = db.get(DailyFact, target)
    confidence_score, confidence_level = compute_decision_confidence(fact, target, db)

    # LLM explanation (best-effort)
    explanation = None
    if score is not None:
        try:
            result = explain_today(target, db, Settings())
            explanation = result.explanation
        except Exception:
            logger.exception("Failed to generate daily explanation")

    return TodayResponse(
        date=target,
        recommendation=recommendation,
        scores=scores,
        subcomponents=subcomponents,
        warnings=warnings,
        explanation=explanation,
        confidence_score=confidence_score,
        confidence_level=confidence_level,
        score_version=SCORE_ENGINE_VERSION,
        recommendation_version=RECOMMENDATION_ENGINE_VERSION,
    )
