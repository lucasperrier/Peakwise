"""Recommendation pipeline.

Orchestrates the mapping from score snapshots to recommendation snapshots
and persists results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.config import RECOMMENDATION_ENGINE_VERSION
from peakwise.models import DailyFact, RecommendationSnapshot, ScoreSnapshot
from peakwise.recommendations.rules import determine_recommendation
from peakwise.trust import compute_decision_confidence

logger = logging.getLogger("peakwise.recommendations")


@dataclass
class RecommendationPipelineResult:
    dates_recommended: int = 0
    dates_skipped: int = 0
    errors: list[str] = field(default_factory=list)


def compute_recommendation_for_date(
    score: ScoreSnapshot,
    session: Session | None = None,
) -> RecommendationSnapshot | None:
    """Compute a recommendation from a persisted score snapshot.

    Returns ``None`` if required score data is missing.
    """
    if score.recovery_score is None:
        return None

    warnings: dict[str, bool] = score.warnings_json or {}

    # Compute decision confidence for the recommendation
    confidence_score: float | None = None
    if session is not None:
        fact: DailyFact | None = session.get(DailyFact, score.date)
        confidence_score, _ = compute_decision_confidence(fact, score.date, session)

    result = determine_recommendation(
        recovery_score=score.recovery_score,
        race_readiness_score=score.race_readiness_score or 50.0,
        general_health_score=score.general_health_score or 50.0,
        load_balance_score=score.load_balance_score or 50.0,
        warnings=warnings,
        confidence_score=confidence_score,
    )

    return RecommendationSnapshot(
        date=score.date,
        recommendation_engine_version=RECOMMENDATION_ENGINE_VERSION,
        mode=result.mode.value,
        recommended_action=result.recommended_action,
        intensity_modifier=result.intensity_modifier,
        duration_modifier=result.duration_modifier,
        reason_codes_json=result.reason_codes,
        next_best_alternative=result.next_best_alternative,
        risk_flags_json=result.risk_flags,
    )


def run_recommendation_pipeline(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> RecommendationPipelineResult:
    """Compute and persist recommendations for a date range.

    Requires the scoring layer (score_snapshot) to already be populated.
    """
    result = RecommendationPipelineResult()

    # Determine date range from score_snapshot
    all_score_dates: list[date] = [
        row[0]
        for row in session.execute(
            select(ScoreSnapshot.date).order_by(ScoreSnapshot.date)
        ).all()
    ]
    if not all_score_dates:
        return result

    effective_start = start_date or all_score_dates[0]
    effective_end = end_date or all_score_dates[-1]

    # Load scores
    score_rows: list[ScoreSnapshot] = list(
        session.scalars(
            select(ScoreSnapshot).where(
                ScoreSnapshot.date >= effective_start,
                ScoreSnapshot.date <= effective_end,
            )
        ).all()
    )
    scores: dict[date, ScoreSnapshot] = {s.date: s for s in score_rows}

    # Recommend each date
    current = effective_start
    while current <= effective_end:
        score = scores.get(current)
        if score is None:
            result.dates_skipped += 1
            current += timedelta(days=1)
            continue
        try:
            snapshot = compute_recommendation_for_date(score, session=session)
            if snapshot is None:
                result.dates_skipped += 1
            else:
                session.merge(snapshot)
                result.dates_recommended += 1
        except Exception as exc:
            msg = f"Error recommending {current}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
        current += timedelta(days=1)

    session.flush()
    logger.info(
        "Recommendation pipeline complete: %d recommended, %d skipped, %d errors",
        result.dates_recommended,
        result.dates_skipped,
        len(result.errors),
    )
    return result
