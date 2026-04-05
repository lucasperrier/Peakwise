"""LLM pipeline — orchestrates context assembly, prompt construction, and LLM calls.

Phase 2.5: All LLM calls are audited. The LLM receives only structured
inputs (scores, components, reason codes, recommendation, plan context,
confidence). Outputs are logged for trust and debugging.
"""

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
from peakwise.models import LLMAuditLog

logger = logging.getLogger("peakwise.llm")


def _audit_llm_call(
    result: LLMResult,
    prompt_type: str,
    target_date: date | None,
    db: Session | None,
) -> None:
    """Persist LLM call to audit log."""
    if db is None:
        return
    try:
        log = LLMAuditLog(
            date=target_date,
            prompt_type=prompt_type,
            context_json=result.context_sent,
            model=result.model,
            response_text=result.explanation,
            error=result.error,
        )
        db.add(log)
        db.flush()
    except Exception:
        logger.exception("Failed to persist LLM audit log")


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
            prompt_type="daily_explanation",
        )

    system_msg, user_msg = daily_explanation_prompt(context)
    result = generate(system_msg, user_msg, context, settings)
    result.prompt_type = "daily_explanation"
    _audit_llm_call(result, "daily_explanation", target_date, db)
    return result


def explain_weekly_review(
    current_week: dict[str, Any],
    previous_week: dict[str, Any] | None,
    score_changes: dict[str, Any] | None,
    flags: list[str],
    settings: Settings | None = None,
    db: Session | None = None,
) -> LLMResult:
    """Generate a natural-language summary for the weekly review."""
    context = assemble_weekly_review_context(
        current_week, previous_week, score_changes, flags
    )
    system_msg, user_msg = weekly_review_prompt(context)
    result = generate(system_msg, user_msg, context, settings)
    result.prompt_type = "weekly_review"
    _audit_llm_call(result, "weekly_review", None, db)
    return result


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
            prompt_type="qa",
        )

    system_msg, user_msg = qa_prompt(context, question)
    result = generate(system_msg, user_msg, context, settings)
    result.prompt_type = "qa"
    _audit_llm_call(result, "qa", target_date, db)
    return result
