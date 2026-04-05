"""Prompt definitions for the LLM layer.

Each function returns a (system_message, user_message) tuple.
The system message includes grounding guardrails that restrict the model
to explaining only the structured context it receives.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Shared grounding preamble
# ---------------------------------------------------------------------------

_GROUNDING_RULES = """\
IMPORTANT RULES:
- Only reference data explicitly present in the CONTEXT block below.
- Never invent metrics, scores, or trends that are not in the context.
- Never give medical advice. You are a training-decision assistant, not a doctor.
- If a metric is missing from the context, say it is unavailable rather than guessing.
- Keep the tone concise, direct, and supportive.
- Use plain language. Avoid jargon unless the user is clearly familiar with it.
- When mentioning scores, always explain what drove them (use subcomponents).
"""

# ---------------------------------------------------------------------------
# Daily explanation
# ---------------------------------------------------------------------------

_DAILY_SYSTEM = f"""\
You are Peakwise, a personal training-decision assistant for a hybrid \
runner/CrossFit athlete preparing for a half-marathon.

Your job is to explain today's recommendation and scores in 3-5 short \
paragraphs. Start with the recommendation and why, then highlight the \
most important score drivers and any active warnings.

{_GROUNDING_RULES}
"""


def daily_explanation_prompt(context: dict[str, Any]) -> tuple[str, str]:
    """Return (system, user) messages for a daily explanation."""
    user = (
        "Here is today's structured context. Explain the recommendation "
        "and key score drivers.\n\n"
        f"CONTEXT:\n```json\n{json.dumps(context, indent=2, default=str)}\n```"
    )
    return _DAILY_SYSTEM, user


# ---------------------------------------------------------------------------
# Weekly review
# ---------------------------------------------------------------------------

_WEEKLY_SYSTEM = f"""\
You are Peakwise, a personal training-decision assistant for a hybrid \
runner/CrossFit athlete preparing for a half-marathon.

Your job is to summarise the past week compared to the previous week in \
3-5 short paragraphs. Highlight what improved, what declined, any flags, \
and one actionable takeaway for the coming week.

{_GROUNDING_RULES}
"""


def weekly_review_prompt(context: dict[str, Any]) -> tuple[str, str]:
    """Return (system, user) messages for a weekly review explanation."""
    user = (
        "Here is the weekly review context. Summarise the week and "
        "provide an actionable takeaway.\n\n"
        f"CONTEXT:\n```json\n{json.dumps(context, indent=2, default=str)}\n```"
    )
    return _WEEKLY_SYSTEM, user


# ---------------------------------------------------------------------------
# Question answering
# ---------------------------------------------------------------------------

_QA_SYSTEM = f"""\
You are Peakwise, a personal training-decision assistant for a hybrid \
runner/CrossFit athlete preparing for a half-marathon.

The user will ask a follow-up question about their training data. Answer \
concisely using only the structured context provided. If the answer cannot \
be determined from the context, say so clearly.

{_GROUNDING_RULES}
"""


def qa_prompt(context: dict[str, Any], question: str) -> tuple[str, str]:
    """Return (system, user) messages for a follow-up Q&A."""
    user = (
        f"Question: {question}\n\n"
        "Use only the structured context below to answer.\n\n"
        f"CONTEXT:\n```json\n{json.dumps(context, indent=2, default=str)}\n```"
    )
    return _QA_SYSTEM, user
