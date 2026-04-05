"""POST /api/manual-input — submit manual daily input."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.api.deps import get_db
from peakwise.api.schemas import ManualInputRequest, ManualInputResponse
from peakwise.models import DailyFact, ManualDailyInput

router = APIRouter()


@router.post("/manual-input", response_model=ManualInputResponse, status_code=201)
def post_manual_input(
    body: ManualInputRequest,
    db: Session = Depends(get_db),  # noqa: B008
) -> ManualInputResponse:
    # Upsert: check for existing entry on same date
    existing: ManualDailyInput | None = db.scalar(
        select(ManualDailyInput).where(ManualDailyInput.date == body.date).limit(1)
    )

    created = existing is None

    record = existing if existing is not None else ManualDailyInput(date=body.date)

    # Apply fields from request
    if body.left_knee_pain_score is not None:
        record.left_knee_pain_score = body.left_knee_pain_score
    if body.global_pain_score is not None:
        record.global_pain_score = body.global_pain_score
    if body.soreness_score is not None:
        record.soreness_score = body.soreness_score
    if body.mood_score is not None:
        record.mood_score = body.mood_score
    if body.motivation_score is not None:
        record.motivation_score = body.motivation_score
    if body.stress_score_subjective is not None:
        record.stress_score_subjective = body.stress_score_subjective
    if body.illness_flag is not None:
        record.illness_flag = body.illness_flag
    if body.free_text_note is not None:
        record.free_text_note = body.free_text_note

    if created:
        db.add(record)
    db.flush()

    # Propagate to daily_fact subjective fields
    daily: DailyFact | None = db.get(DailyFact, body.date)
    if daily is None:
        daily = DailyFact(date=body.date)
        db.add(daily)

    daily.left_knee_pain_score = record.left_knee_pain_score
    daily.soreness_score = record.soreness_score
    daily.mood_score = record.mood_score
    daily.motivation_score = record.motivation_score
    daily.illness_flag = record.illness_flag
    daily.has_manual_input = True

    db.commit()

    return ManualInputResponse(
        id=record.id,
        date=record.date,
        created=created,
    )
