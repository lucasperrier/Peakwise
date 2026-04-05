"""GET /api/strength — CrossFit / strength features, recent workouts, and trend."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.api.deps import get_db
from peakwise.api.schemas import (
    RecentWorkout,
    StrengthFeatures,
    StrengthResponse,
    StrengthTrendPoint,
)
from peakwise.models import DailyFeatures, ScoreSnapshot, WorkoutFact

router = APIRouter()

_TREND_DAYS = 28
_RECENT_WORKOUT_DAYS = 14
_CF_SESSION_TYPES = {"crossfit", "strength"}


@router.get("/strength", response_model=StrengthResponse)
def get_strength(
    target_date: date | None = Query(None, alias="date"),  # noqa: B008
    days: int = Query(_TREND_DAYS, ge=1, le=90),
    db: Session = Depends(get_db),  # noqa: B008
) -> StrengthResponse:
    target = target_date or date.today()
    trend_start = target - timedelta(days=days - 1)
    workout_start = target - timedelta(days=_RECENT_WORKOUT_DAYS - 1)

    feat: DailyFeatures | None = db.get(DailyFeatures, target)
    score: ScoreSnapshot | None = db.get(ScoreSnapshot, target)

    current = None
    if feat is not None:
        current = StrengthFeatures(
            hard_day_count_7d=feat.hard_day_count_7d,
            lower_body_crossfit_density_7d=feat.lower_body_crossfit_density_7d,
            long_run_protection_score=feat.long_run_protection_score,
            interference_risk_score=feat.interference_risk_score,
            run_intensity_distribution=feat.run_intensity_distribution_json,
        )

    # Recent CrossFit / strength workouts
    workout_rows: list[WorkoutFact] = list(
        db.scalars(
            select(WorkoutFact)
            .where(
                WorkoutFact.session_date >= workout_start,
                WorkoutFact.session_date <= target,
                WorkoutFact.session_type.in_(_CF_SESSION_TYPES),
                WorkoutFact.is_duplicate.is_(False),
            )
            .order_by(WorkoutFact.session_date.desc())
        ).all()
    )
    recent_workouts = [
        RecentWorkout(
            workout_id=w.workout_id,
            session_date=w.session_date,
            session_type=w.session_type,
            duration_min=w.duration_min,
            training_load=w.training_load,
            is_lower_body_dominant=w.is_lower_body_dominant,
            raw_notes=w.raw_notes,
        )
        for w in workout_rows
    ]

    # Trend
    trend_rows: list[DailyFeatures] = list(
        db.scalars(
            select(DailyFeatures)
            .where(
                DailyFeatures.date >= trend_start,
                DailyFeatures.date <= target,
            )
            .order_by(DailyFeatures.date)
        ).all()
    )
    trend = [
        StrengthTrendPoint(
            date=f.date,
            hard_day_count_7d=f.hard_day_count_7d,
            lower_body_crossfit_density_7d=f.lower_body_crossfit_density_7d,
            interference_risk_score=f.interference_risk_score,
        )
        for f in trend_rows
    ]

    return StrengthResponse(
        date=target,
        current=current,
        load_balance_score=score.load_balance_score if score else None,
        recent_workouts=recent_workouts,
        trend=trend,
    )
