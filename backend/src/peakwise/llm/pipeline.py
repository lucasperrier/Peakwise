"""LLM pipeline — orchestrates context assembly, prompt construction, and LLM calls."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from peakwise.config import Settings
from peakwise.llm.client import LLMResult, generate
from peakwise.llm.context import (
    assemble_qa_context,
    assemble_today_context,
    assemble_weekly_review_context,
)
from peakwise.llm.prompts import (
    daily_explanation_prompt,
    qa_prompt,
    weekly_review_prompt,
)

logger = logging.getLogger("peakwise.llm")


def explain_today(
    target_date: date,
    db: Session,
    settings: Settings | None = None,
) -> LLMResult:
    """Generate a natural-language explanation for the daily recommendation."""
    context = assemble_today_context(target_date, db)
    if context is None:
        return LLMResult(
            explanation=None,
            context_sent={},
            model=(settings or Settings()).openai_model,
            error="no score data for date",
        )

    system_msg, user_msg = daily_explanation_prompt(context)
    return generate(system_msg, user_msg, context, settings)


def explain_weekly_review(
    current_week: dict[str, Any],
    previous_week: dict[str, Any] | None,
    score_changes: dict[str, Any] | None,
    flags: list[str],
    settings: Settings | None = None,
) -> LLMResult:
    """Generate a natural-language summary for the weekly review."""
    context = assemble_weekly_review_context(
        current_week, previous_week, score_changes, flags
    )
    system_msg, user_msg = weekly_review_prompt(context)
    return generate(system_msg, user_msg, context, settings)


def answer_question(
    question: str,
    target_date: date,
    db: Session,
    settings: Settings | None = None,
) -> LLMResult:
    """Answer a follow-up question grounded in the day's context."""
    context = assemble_qa_context(target_date, db)
    if context is None:
        return LLMResult(
            explanation=None,
            context_sent={},
            model=(settings or Settings()).openai_model,
            error="no score data for date",
        )

    system_msg, user_msg = qa_prompt(context, question)
    return generate(system_msg, user_msg, context, settings)
