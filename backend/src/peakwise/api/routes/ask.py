"""POST /api/ask — follow-up question answering."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from peakwise.api.deps import get_db
from peakwise.api.schemas import AskRequest, AskResponse
from peakwise.config import Settings
from peakwise.llm.pipeline import answer_question

logger = logging.getLogger("peakwise.api.ask")

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def post_ask(
    body: AskRequest,
    db: Session = Depends(get_db),  # noqa: B008
) -> AskResponse:
    target = body.date or date.today()

    try:
        result = answer_question(body.question, target, db, Settings())
        return AskResponse(answer=result.explanation, error=result.error)
    except Exception:
        logger.exception("Failed to answer question")
        return AskResponse(answer=None, error="internal_error")
