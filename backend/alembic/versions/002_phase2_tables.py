"""Phase 2: score breakdowns, provenance, feedback, LLM audit, workout tags

Revision ID: 002
Revises: 001
Create Date: 2026-04-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- daily_score_snapshot ---
    op.create_table(
        "daily_score_snapshot",
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("recovery_score", sa.Float),
        sa.Column("race_readiness_score", sa.Float),
        sa.Column("general_health_score", sa.Float),
        sa.Column("load_balance_score", sa.Float),
        sa.Column("recommendation_mode", sa.String(30)),
        sa.Column("recommended_action", sa.String(100)),
        sa.Column("score_version", sa.String(20), nullable=False),
        sa.Column("recommendation_version", sa.String(20), nullable=False),
        sa.Column("confidence_level", sa.String(20)),
        sa.Column("decision_confidence_score", sa.Float),
        sa.Column("generated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- daily_score_component ---
    op.create_table(
        "daily_score_component",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("score_type", sa.String(30), nullable=False),
        sa.Column("component_name", sa.String(100), nullable=False),
        sa.Column("raw_input_value", sa.Float),
        sa.Column("normalized_value", sa.Float),
        sa.Column("weighted_contribution", sa.Float),
        sa.Column("direction", sa.String(10), nullable=False),
    )

    # --- daily_reason_code ---
    op.create_table(
        "daily_reason_code",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20)),
        sa.Column("detail", sa.String(500)),
    )

    # --- daily_field_provenance ---
    op.create_table(
        "daily_field_provenance",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("is_stale", sa.Boolean, server_default="false"),
        sa.Column("staleness_days", sa.Integer),
    )

    # --- daily_feedback ---
    op.create_table(
        "daily_feedback",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("rating", sa.String(30), nullable=False),
        sa.Column("free_text_note", sa.Text),
        sa.Column("recommendation_version", sa.String(20)),
        sa.Column("actual_session_type", sa.String(50)),
        sa.Column("next_day_outcome", sa.String(200)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- llm_audit_log ---
    op.create_table(
        "llm_audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date),
        sa.Column("prompt_type", sa.String(30), nullable=False),
        sa.Column("context_json", sa.JSON),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("response_text", sa.Text),
        sa.Column("error", sa.String(500)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- workout_tag ---
    op.create_table(
        "workout_tag",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workout_id", sa.String(36), nullable=False, index=True),
        sa.Column("tag", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("is_manual_override", sa.Boolean, server_default="false"),
    )


def downgrade() -> None:
    op.drop_table("workout_tag")
    op.drop_table("llm_audit_log")
    op.drop_table("daily_feedback")
    op.drop_table("daily_field_provenance")
    op.drop_table("daily_reason_code")
    op.drop_table("daily_score_component")
    op.drop_table("daily_score_snapshot")
