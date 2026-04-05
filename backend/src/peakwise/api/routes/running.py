"""GET /api/running — running features and trend."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.api.deps import get_db
from peakwise.api.schemas import (
    RunningFeatures,
    RunningResponse,
    RunningTrendPoint,
)
from peakwise.models import DailyFeatures, ScoreSnapshot

router = APIRouter()

_TREND_DAYS = 28


@router.get("/running", response_model=RunningResponse)
def get_running(
    target_date: date | None = Query(None, alias="date"),  # noqa: B008
    days: int = Query(_TREND_DAYS, ge=1, le=90),
    db: Session = Depends(get_db),  # noqa: B008
) -> RunningResponse:
    target = target_date or date.today()
    trend_start = target - timedelta(days=days - 1)

    # Current day features
    feat: DailyFeatures | None = db.get(DailyFeatures, target)
    score: ScoreSnapshot | None = db.get(ScoreSnapshot, target)

    current = None
    if feat is not None:
        current = RunningFeatures(
            weekly_km=feat.weekly_km,
            rolling_4w_km=feat.rolling_4w_km,
            longest_run_last_7d_km=feat.longest_run_last_7d_km,
            easy_pace_fixed_hr_sec_per_km=feat.easy_pace_fixed_hr_sec_per_km,
            quality_sessions_last_14d=feat.quality_sessions_last_14d,
            projected_hm_time_sec=feat.projected_hm_time_sec,
            plan_adherence_pct=feat.plan_adherence_pct,
        )

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
        RunningTrendPoint(
            date=f.date,
            weekly_km=f.weekly_km,
            rolling_4w_km=f.rolling_4w_km,
            longest_run_last_7d_km=f.longest_run_last_7d_km,
            easy_pace_fixed_hr_sec_per_km=f.easy_pace_fixed_hr_sec_per_km,
            quality_sessions_last_14d=f.quality_sessions_last_14d,
        )
        for f in trend_rows
    ]

    return RunningResponse(
        date=target,
        current=current,
        race_readiness_score=score.race_readiness_score if score else None,
        trend=trend,
    )
