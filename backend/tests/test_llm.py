"""Tests for Phase 8 — LLM layer.

Tests cover context assembly, prompt construction, grounding guardrails,
fallback behavior, and the /api/ask endpoint.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from peakwise.api import create_app
from peakwise.api.deps import get_db
from peakwise.llm.client import LLMResult, _passes_grounding_check, generate
from peakwise.llm.context import (
    assemble_qa_context,
    assemble_today_context,
    assemble_weekly_review_context,
)
from peakwise.llm.prompts import daily_explanation_prompt, qa_prompt, weekly_review_prompt
from peakwise.models import (
    Base,
    DailyFact,
    DailyFeatures,
    RecommendationSnapshot,
    ScoreSnapshot,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_DATE = date(2025, 7, 7)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session


@pytest.fixture()
def client(db_session: Session):
    app = create_app()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _seed_score(session: Session, d: date) -> ScoreSnapshot:
    record = ScoreSnapshot(
        date=d,
        score_engine_version="1.0.0",
        recovery_score=72.0,
        race_readiness_score=65.0,
        general_health_score=78.0,
        load_balance_score=68.0,
        subcomponents_json={
            "recovery": {"hrv": 75.0, "sleep": 70.0},
            "race_readiness": {"weekly_volume": 70.0},
            "general_health": {"sleep_consistency": 82.0},
            "load_balance": {"hard_day_density": 80.0},
        },
        warnings_json={
            "knee_pain_warning": False,
            "illness_warning": False,
            "sleep_debt_warning": True,
        },
    )
    session.add(record)
    return record


def _seed_recommendation(session: Session, d: date) -> RecommendationSnapshot:
    record = RecommendationSnapshot(
        date=d,
        recommendation_engine_version="1.0.0",
        mode="train_as_planned",
        recommended_action="Follow today's plan at normal intensity",
        reason_codes_json=["recovery_acceptable"],
        risk_flags_json=[],
    )
    session.add(record)
    return record


def _seed_features(session: Session, d: date) -> DailyFeatures:
    record = DailyFeatures(
        date=d,
        hrv_7d_avg=42.0,
        sleep_debt_min=120.0,
        weekly_km=35.0,
        hard_day_count_7d=3,
    )
    session.add(record)
    return record


def _seed_fact(session: Session, d: date) -> DailyFact:
    record = DailyFact(
        date=d,
        resting_hr_bpm=58,
        hrv_ms=42.0,
        sleep_duration_min=460.0,
        mood_score=7.0,
    )
    session.add(record)
    return record


def _seed_full_day(session: Session, d: date) -> None:
    _seed_score(session, d)
    _seed_recommendation(session, d)
    _seed_features(session, d)
    _seed_fact(session, d)
    session.flush()


# ---------------------------------------------------------------------------
# Context assembler tests
# ---------------------------------------------------------------------------


class TestContextAssembler:
    def test_today_context_returns_none_without_score(self, db_session: Session):
        ctx = assemble_today_context(BASE_DATE, db_session)
        assert ctx is None

    def test_today_context_includes_scores(self, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        ctx = assemble_today_context(BASE_DATE, db_session)
        assert ctx is not None
        assert ctx["date"] == BASE_DATE.isoformat()
        assert ctx["scores"]["recovery"] == 72.0
        assert ctx["scores"]["race_readiness"] == 65.0

    def test_today_context_includes_active_warnings(self, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        ctx = assemble_today_context(BASE_DATE, db_session)
        assert "active_warnings" in ctx
        assert "sleep_debt_warning" in ctx["active_warnings"]
        assert "knee_pain_warning" not in ctx["active_warnings"]

    def test_today_context_includes_recommendation(self, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        ctx = assemble_today_context(BASE_DATE, db_session)
        assert ctx["recommendation"]["mode"] == "train_as_planned"
        assert "recovery_acceptable" in ctx["recommendation"]["reason_codes"]

    def test_today_context_includes_features(self, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        ctx = assemble_today_context(BASE_DATE, db_session)
        assert ctx["features"]["hrv_7d_avg"] == 42.0
        assert ctx["features"]["weekly_km"] == 35.0

    def test_today_context_includes_daily_metrics(self, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        ctx = assemble_today_context(BASE_DATE, db_session)
        assert ctx["daily_metrics"]["resting_hr_bpm"] == 58
        assert ctx["daily_metrics"]["sleep_duration_min"] == 460.0

    def test_weekly_review_context_structure(self):
        current = {"start_date": "2025-07-07", "avg_recovery_score": 72.0}
        previous = {"start_date": "2025-06-30", "avg_recovery_score": 68.0}
        changes = {"recovery": {"delta": 4.0}}
        flags = ["volume_spike"]
        ctx = assemble_weekly_review_context(current, previous, changes, flags)
        assert ctx["current_week"] == current
        assert ctx["previous_week"] == previous
        assert ctx["flags"] == ["volume_spike"]

    def test_qa_context_sets_type(self, db_session: Session):
        _seed_full_day(db_session, BASE_DATE)
        ctx = assemble_qa_context(BASE_DATE, db_session)
        assert ctx is not None
        assert ctx["context_type"] == "qa"


# ---------------------------------------------------------------------------
# Prompt construction tests
# ---------------------------------------------------------------------------


class TestPrompts:
    def test_daily_prompt_contains_context_json(self):
        ctx = {"date": "2025-07-07", "scores": {"recovery": 72.0}}
        system, user = daily_explanation_prompt(ctx)
        assert "Peakwise" in system
        assert "CONTEXT" in user
        assert '"recovery": 72.0' in user

    def test_weekly_prompt_contains_context(self):
        ctx = {"current_week": {"avg_recovery_score": 72.0}}
        system, user = weekly_review_prompt(ctx)
        assert "summarise" in system.lower() or "Summarise" in system
        assert "CONTEXT" in user

    def test_qa_prompt_includes_question(self):
        ctx = {"date": "2025-07-07", "scores": {"recovery": 72.0}}
        system, user = qa_prompt(ctx, "Why is my recovery low?")
        assert "Why is my recovery low?" in user
        assert "CONTEXT" in user

    def test_grounding_rules_in_all_prompts(self):
        ctx = {"date": "2025-07-07"}
        for fn in [daily_explanation_prompt, weekly_review_prompt]:
            system, _ = fn(ctx)
            assert "Never invent" in system
            assert "Never give medical advice" in system


# ---------------------------------------------------------------------------
# Grounding check tests
# ---------------------------------------------------------------------------


class TestGroundingCheck:
    def test_passes_normal_text(self):
        assert _passes_grounding_check("Your recovery score is 72, driven by good sleep.") is True

    def test_fails_on_disclaimer(self):
        assert _passes_grounding_check("As an AI language model, I cannot...") is False

    def test_fails_on_access_disclaimer(self):
        assert _passes_grounding_check("I don't have access to your data") is False


# ---------------------------------------------------------------------------
# Client fallback tests
# ---------------------------------------------------------------------------


class TestClientFallback:
    def test_returns_fallback_without_api_key(self):
        from peakwise.config import Settings

        settings = Settings(openai_api_key="")
        result = generate("system", "user", {"k": "v"}, settings)
        assert result.explanation is None
        assert result.error == "openai_api_key not configured"
        assert result.context_sent == {"k": "v"}

    @patch("peakwise.llm.client._get_client")
    def test_returns_fallback_on_api_error(self, mock_get_client):
        from openai import OpenAIError

        from peakwise.config import Settings

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = OpenAIError("rate_limit")
        mock_get_client.return_value = mock_client

        settings = Settings(openai_api_key="test-key")
        result = generate("system", "user", {"k": "v"}, settings)
        assert result.explanation is None
        assert "rate_limit" in (result.error or "")

    @patch("peakwise.llm.client._get_client")
    def test_returns_text_on_success(self, mock_get_client):
        from peakwise.config import Settings

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Your recovery is good."
        mock_response.usage.total_tokens = 100

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        settings = Settings(openai_api_key="test-key")
        result = generate("system", "user", {"k": "v"}, settings)
        assert result.explanation == "Your recovery is good."
        assert result.error is None


# ---------------------------------------------------------------------------
# API endpoint tests (LLM mocked)
# ---------------------------------------------------------------------------


class TestTodayExplanation:
    @patch("peakwise.api.routes.today.explain_today")
    def test_today_includes_explanation(self, mock_explain, client, db_session):
        mock_explain.return_value = LLMResult(
            explanation="Recovery is solid today.",
            context_sent={},
            model="gpt-4o",
        )
        _seed_full_day(db_session, BASE_DATE)

        resp = client.get("/api/today", params={"date": str(BASE_DATE)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] == "Recovery is solid today."

    @patch("peakwise.api.routes.today.explain_today")
    def test_today_explanation_none_on_failure(self, mock_explain, client, db_session):
        mock_explain.side_effect = RuntimeError("LLM down")
        _seed_full_day(db_session, BASE_DATE)

        resp = client.get("/api/today", params={"date": str(BASE_DATE)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] is None

    def test_today_explanation_none_without_score(self, client):
        resp = client.get("/api/today", params={"date": "2099-01-01"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] is None


class TestAskEndpoint:
    @patch("peakwise.api.routes.ask.answer_question")
    def test_ask_returns_answer(self, mock_answer, client, db_session):
        mock_answer.return_value = LLMResult(
            explanation="Your sleep debt is 120 minutes.",
            context_sent={},
            model="gpt-4o",
        )
        _seed_full_day(db_session, BASE_DATE)

        resp = client.post(
            "/api/ask",
            json={"question": "Why is my sleep debt high?", "date": str(BASE_DATE)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Your sleep debt is 120 minutes."

    @patch("peakwise.api.routes.ask.answer_question")
    def test_ask_returns_error_on_failure(self, mock_answer, client):
        mock_answer.side_effect = RuntimeError("boom")

        resp = client.post(
            "/api/ask",
            json={"question": "test question"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == "internal_error"

    def test_ask_validates_empty_question(self, client):
        resp = client.post("/api/ask", json={"question": ""})
        assert resp.status_code == 422
