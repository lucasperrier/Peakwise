"""GET /api/weekly-review — week-over-week comparison."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.api.deps import get_db
from peakwise.api.schemas import (
    ScoreChange,
    ScoreChanges,
    WeeklyReviewResponse,
    WeekSummary,
)
from peakwise.config import Settings
from peakwise.llm.pipeline import explain_weekly_review
from peakwise.models import DailyFact, ScoreSnapshot, WorkoutFact

logger = logging.getLogger("peakwise.api.weekly_review")

router = APIRouter()


def _week_bounds(ref: date) -> tuple[date, date]:
    """Return (Monday, Sunday) of the ISO week containing *ref*."""
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _build_week_summary(
    start: date,
    end: date,
    scores: list[ScoreSnapshot],
    facts: list[DailyFact],
    workouts: list[WorkoutFact],
) -> WeekSummary:
    def _avg(values: list[float | None]) -> float | None:
        nums = [v for v in values if v is not None]
        return round(sum(nums) / len(nums), 2) if nums else None

    total_km = sum(
        w.distance_km for w in workouts if w.distance_km is not None and not w.is_duplicate
    )

    return WeekSummary(
        start_date=start,
        end_date=end,
        avg_recovery_score=_avg([s.recovery_score for s in scores]),
        avg_race_readiness_score=_avg([s.race_readiness_score for s in scores]),
        avg_general_health_score=_avg([s.general_health_score for s in scores]),
        avg_load_balance_score=_avg([s.load_balance_score for s in scores]),
        total_km=round(total_km, 2) if total_km else None,
        workout_count=sum(1 for w in workouts if not w.is_duplicate),
        avg_sleep_duration_min=_avg([f.sleep_duration_min for f in facts]),
        avg_hrv_ms=_avg([f.hrv_ms for f in facts]),
        avg_resting_hr_bpm=_avg(
            [float(f.resting_hr_bpm) for f in facts if f.resting_hr_bpm is not None]
        ),
    )


def _score_change(prev: float | None, curr: float | None) -> ScoreChange | None:
    if curr is None and prev is None:
        return None
    delta = None
    if curr is not None and prev is not None:
        delta = round(curr - prev, 2)
    return ScoreChange(previous=prev, current=curr, delta=delta)


@router.get("/weekly-review", response_model=WeeklyReviewResponse)
def get_weekly_review(
    target_date: date | None = Query(None, alias="date"),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> WeeklyReviewResponse:
    ref = target_date or date.today()
    curr_start, curr_end = _week_bounds(ref)
    prev_start = curr_start - timedelta(days=7)
    prev_end = curr_start - timedelta(days=1)

    # Load data for both weeks
    all_start = prev_start
    all_end = curr_end

    scores: list[ScoreSnapshot] = list(
        db.scalars(
            select(ScoreSnapshot)
            .where(ScoreSnapshot.date >= all_start, ScoreSnapshot.date <= all_end)
            .order_by(ScoreSnapshot.date)
        ).all()
    )
    facts: list[DailyFact] = list(
        db.scalars(
            select(DailyFact)
            .where(DailyFact.date >= all_start, DailyFact.date <= all_end)
            .order_by(DailyFact.date)
        ).all()
    )
    workouts: list[WorkoutFact] = list(
        db.scalars(
            select(WorkoutFact)
            .where(WorkoutFact.session_date >= all_start, WorkoutFact.session_date <= all_end)
            .order_by(WorkoutFact.session_date)
        ).all()
    )

    def _in_range(d: date, s: date, e: date) -> bool:
        return s <= d <= e

    curr_scores = [s for s in scores if _in_range(s.date, curr_start, curr_end)]
    curr_facts = [f for f in facts if _in_range(f.date, curr_start, curr_end)]
    curr_workouts = [w for w in workouts if _in_range(w.session_date, curr_start, curr_end)]

    prev_scores = [s for s in scores if _in_range(s.date, prev_start, prev_end)]
    prev_facts = [f for f in facts if _in_range(f.date, prev_start, prev_end)]
    prev_workouts = [w for w in workouts if _in_range(w.session_date, prev_start, prev_end)]

    current_week = _build_week_summary(curr_start, curr_end, curr_scores, curr_facts, curr_workouts)
    previous_week = _build_week_summary(prev_start, prev_end, prev_scores, prev_facts, prev_workouts)

    # Score changes
    score_changes = ScoreChanges(
        recovery=_score_change(previous_week.avg_recovery_score, current_week.avg_recovery_score),
        race_readiness=_score_change(
            previous_week.avg_race_readiness_score, current_week.avg_race_readiness_score
        ),
        general_health=_score_change(
            previous_week.avg_general_health_score, current_week.avg_general_health_score
        ),
        load_balance=_score_change(
            previous_week.avg_load_balance_score, current_week.avg_load_balance_score
        ),
    )

    # Flags
    flags: list[str] = []
    if (
        current_week.avg_recovery_score is not None
        and previous_week.avg_recovery_score is not None
        and current_week.avg_recovery_score < previous_week.avg_recovery_score - 10
    ):
        flags.append("recovery_declining")
    if (
        current_week.total_km is not None
        and previous_week.total_km is not None
        and previous_week.total_km > 0
        and current_week.total_km > previous_week.total_km * 1.15
    ):
        flags.append("volume_spike")
    if (
        current_week.avg_sleep_duration_min is not None
        and current_week.avg_sleep_duration_min < 420
    ):
        flags.append("sleep_below_7h")

    # LLM explanation (best-effort)
    explanation = None
    try:
        result = explain_weekly_review(
            current_week=current_week.model_dump(mode="json"),
            previous_week=previous_week.model_dump(mode="json"),
            score_changes=score_changes.model_dump(mode="json") if score_changes else None,
            flags=flags,
            settings=Settings(),
        )
        explanation = result.explanation
    except Exception:
        logger.exception("Failed to generate weekly review explanation")

    return WeeklyReviewResponse(
        current_week=current_week,
        previous_week=previous_week,
        score_changes=score_changes,
        flags=flags,
        explanation=explanation,
    )
