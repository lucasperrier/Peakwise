"""OpenAI client wrapper with logging, grounding validation, and fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAI, OpenAIError

from peakwise.config import Settings

logger = logging.getLogger("peakwise.llm")

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class LLMResult:
    """Structured return from an LLM call."""

    explanation: str | None
    context_sent: dict[str, Any]
    model: str
    error: str | None = None
    prompt_type: str | None = None


# ---------------------------------------------------------------------------
# Grounding check
# ---------------------------------------------------------------------------

_HALLUCINATION_MARKERS = [
    "I don't have access to",
    "I cannot determine",
    "based on my training data",
    "as an AI language model",
]


def _passes_grounding_check(text: str) -> bool:
    """Basic sanity check that the response stays grounded.

    Returns False if the response contains markers suggesting the model
    is inventing context or disclaiming access to data it was given.
    """
    lowered = text.lower()
    for marker in _HALLUCINATION_MARKERS:
        if marker.lower() in lowered:
            return False
    return True


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def _get_client(settings: Settings) -> OpenAI | None:
    """Return an OpenAI client or None if the API key is not configured."""
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)


def generate(
    system_message: str,
    user_message: str,
    context: dict[str, Any],
    settings: Settings | None = None,
) -> LLMResult:
    """Call the LLM and return a structured result with logging.

    Handles:
    - Missing API key (returns fallback)
    - API errors (returns fallback with error message)
    - Grounding check failure (logs warning, still returns text)
    """
    if settings is None:
        settings = Settings()

    model = settings.openai_model

    client = _get_client(settings)
    if client is None:
        logger.warning("OpenAI API key not configured; returning fallback")
        return LLMResult(
            explanation=None,
            context_sent=context,
            model=model,
            error="openai_api_key not configured",
        )

    try:
        logger.info("LLM request: model=%s, context_keys=%s", model, list(context.keys()))

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=800,
        )

        text = (response.choices[0].message.content or "").strip()

        if not _passes_grounding_check(text):
            logger.warning("LLM response failed grounding check; returning anyway")

        logger.info(
            "LLM response: model=%s, tokens=%s, length=%d",
            model,
            getattr(response.usage, "total_tokens", "?"),
            len(text),
        )

        return LLMResult(
            explanation=text if text else None,
            context_sent=context,
            model=model,
        )

    except OpenAIError as exc:
        logger.error("OpenAI API error: %s", exc)
        return LLMResult(
            explanation=None,
            context_sent=context,
            model=model,
            error=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected LLM error: %s", exc)
        return LLMResult(
            explanation=None,
            context_sent=context,
            model=model,
            error=str(exc),
        )
