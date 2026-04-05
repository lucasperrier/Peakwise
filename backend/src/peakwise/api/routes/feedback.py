"""POST /api/feedback — daily recommendation feedback capture."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.api.deps import get_db
from peakwise.models import DailyFeedback

router = APIRouter()


class FeedbackRequest(BaseModel):
    date: date
    rating: str = Field(..., pattern="^(accurate|too_hard|too_easy|pain_increased|ignored)$")
    free_text_note: Optional[str] = Field(None, max_length=2000)
    actual_session_type: Optional[str] = Field(None, max_length=50)
    next_day_outcome: Optional[str] = Field(None, max_length=200)


class FeedbackResponse(BaseModel):
    id: int
    date: date
    rating: str
    created: bool


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
def post_feedback(
    body: FeedbackRequest,
    db: Session = Depends(get_db),  # noqa: B008
) -> FeedbackResponse:
    # Check if feedback already exists for this date
    existing: DailyFeedback | None = db.scalar(
        select(DailyFeedback).where(DailyFeedback.date == body.date).limit(1)
    )

    created = existing is None
    record = existing if existing is not None else DailyFeedback(date=body.date)

    record.rating = body.rating
    if body.free_text_note is not None:
        record.free_text_note = body.free_text_note
    if body.actual_session_type is not None:
        record.actual_session_type = body.actual_session_type
    if body.next_day_outcome is not None:
        record.next_day_outcome = body.next_day_outcome

    if created:
        db.add(record)
    db.flush()
    db.commit()

    return FeedbackResponse(
        id=record.id,
        date=record.date,
        rating=record.rating,
        created=created,
    )


@router.get("/feedback")
def get_feedback(
    start_date: date | None = Query(None, alias="start"),  # noqa: B008
    end_date: date | None = Query(None, alias="end"),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> list[dict]:
    """Simple feedback review endpoint for threshold tuning."""
    query = select(DailyFeedback).order_by(DailyFeedback.date.desc())

    if start_date:
        query = query.where(DailyFeedback.date >= start_date)
    if end_date:
        query = query.where(DailyFeedback.date <= end_date)

    rows = db.scalars(query.limit(100)).all()
    return [
        {
            "id": r.id,
            "date": str(r.date),
            "rating": r.rating,
            "free_text_note": r.free_text_note,
            "actual_session_type": r.actual_session_type,
            "next_day_outcome": r.next_day_outcome,
            "recommendation_version": r.recommendation_version,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in rows
    ]
