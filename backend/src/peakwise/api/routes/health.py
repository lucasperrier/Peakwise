"""GET /api/health — health features and trend."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.api.deps import get_db
from peakwise.api.schemas import (
    HealthFeatures,
    HealthResponse,
    HealthTrendPoint,
)
from peakwise.models import DailyFeatures, ScoreSnapshot

router = APIRouter()

_TREND_DAYS = 28


@router.get("/health", response_model=HealthResponse)
def get_health(
    target_date: date | None = Query(None, alias="date"),  # noqa: B008
    days: int = Query(_TREND_DAYS, ge=1, le=90),
    db: Session = Depends(get_db),  # noqa: B008
) -> HealthResponse:
    target = target_date or date.today()
    trend_start = target - timedelta(days=days - 1)

    feat: DailyFeatures | None = db.get(DailyFeatures, target)
    score: ScoreSnapshot | None = db.get(ScoreSnapshot, target)

    current = None
    if feat is not None:
        current = HealthFeatures(
            body_weight_7d_avg=feat.body_weight_7d_avg,
            body_weight_28d_slope=feat.body_weight_28d_slope,
            sleep_consistency_score=feat.sleep_consistency_score,
            hrv_7d_avg=feat.hrv_7d_avg,
            resting_hr_7d_avg=feat.resting_hr_7d_avg,
            sleep_7d_avg=feat.sleep_7d_avg,
            sleep_debt_min=feat.sleep_debt_min,
            mood_trend=feat.mood_trend,
            stress_trend=feat.stress_trend,
            steps_consistency_score=feat.steps_consistency_score,
            pain_free_days_last_14d=feat.pain_free_days_last_14d,
        )

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
        HealthTrendPoint(
            date=f.date,
            body_weight_7d_avg=f.body_weight_7d_avg,
            hrv_7d_avg=f.hrv_7d_avg,
            resting_hr_7d_avg=f.resting_hr_7d_avg,
            sleep_7d_avg=f.sleep_7d_avg,
            sleep_debt_min=f.sleep_debt_min,
            mood_trend=f.mood_trend,
            stress_trend=f.stress_trend,
        )
        for f in trend_rows
    ]

    return HealthResponse(
        date=target,
        current=current,
        general_health_score=score.general_health_score if score else None,
        trend=trend,
    )
