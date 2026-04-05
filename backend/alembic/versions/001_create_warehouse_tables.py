"""create warehouse tables

Revision ID: 001
Revises:
Create Date: 2026-04-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- raw_event ---
    op.create_table(
        "raw_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_record_id", sa.String(255)),
        sa.Column("ingested_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("event_date", sa.Date),
        sa.Column("event_timestamp", sa.DateTime),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("payload_json", sa.JSON),
        sa.Column("source_file_name", sa.String(500)),
        sa.Column("quality_flag", sa.String(50)),
    )

    # --- daily_fact ---
    op.create_table(
        "daily_fact",
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("body_weight_kg", sa.Float),
        sa.Column("body_fat_pct", sa.Float),
        sa.Column("resting_hr_bpm", sa.Integer),
        sa.Column("hrv_ms", sa.Float),
        sa.Column("sleep_duration_min", sa.Float),
        sa.Column("sleep_score", sa.Float),
        sa.Column("steps", sa.Integer),
        sa.Column("active_energy_kcal", sa.Float),
        sa.Column("training_readiness", sa.Float),
        sa.Column("stress_score", sa.Float),
        sa.Column("body_battery", sa.Float),
        sa.Column("soreness_score", sa.Float),
        sa.Column("left_knee_pain_score", sa.Float),
        sa.Column("motivation_score", sa.Float),
        sa.Column("mood_score", sa.Float),
        sa.Column("illness_flag", sa.Boolean),
        sa.Column("perceived_fatigue_score", sa.Float),
        sa.Column("has_garmin_data", sa.Boolean, server_default="false"),
        sa.Column("has_apple_health_data", sa.Boolean, server_default="false"),
        sa.Column("has_strava_data", sa.Boolean, server_default="false"),
        sa.Column("has_scale_data", sa.Boolean, server_default="false"),
        sa.Column("has_manual_input", sa.Boolean, server_default="false"),
        sa.Column("data_quality_flag", sa.String(50)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- workout_fact ---
    op.create_table(
        "workout_fact",
        sa.Column("workout_id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_workout_id", sa.String(255)),
        sa.Column("start_time", sa.DateTime),
        sa.Column("end_time", sa.DateTime),
        sa.Column("session_date", sa.Date, nullable=False, index=True),
        sa.Column("session_type", sa.String(30), nullable=False),
        sa.Column("duration_min", sa.Float),
        sa.Column("avg_hr_bpm", sa.Integer),
        sa.Column("max_hr_bpm", sa.Integer),
        sa.Column("training_load", sa.Float),
        sa.Column("distance_km", sa.Float),
        sa.Column("avg_pace_sec_per_km", sa.Float),
        sa.Column("elevation_gain_m", sa.Float),
        sa.Column("calories_kcal", sa.Float),
        sa.Column("route_type", sa.String(50)),
        sa.Column("cadence_spm", sa.Integer),
        sa.Column("splits_json", sa.JSON),
        sa.Column("time_in_zones_json", sa.JSON),
        sa.Column("weather_json", sa.JSON),
        sa.Column("is_strength", sa.Boolean),
        sa.Column("is_engine", sa.Boolean),
        sa.Column("is_metcon", sa.Boolean),
        sa.Column("has_squats", sa.Boolean),
        sa.Column("has_hinges", sa.Boolean),
        sa.Column("has_jumps", sa.Boolean),
        sa.Column("has_oly_lifts", sa.Boolean),
        sa.Column("is_upper_body_dominant", sa.Boolean),
        sa.Column("is_lower_body_dominant", sa.Boolean),
        sa.Column("session_rpe", sa.Float),
        sa.Column("local_muscular_stress_tag", sa.String(50)),
        sa.Column("raw_notes", sa.Text),
        sa.Column("lower_body_load_score", sa.Float),
        sa.Column("interference_contribution", sa.Float),
        sa.Column("next_day_soreness_linked", sa.Boolean),
        sa.Column("training_phase_label", sa.String(50)),
        sa.Column("is_duplicate", sa.Boolean, server_default="false"),
        sa.Column("duplicate_of_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- manual_daily_input ---
    op.create_table(
        "manual_daily_input",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("left_knee_pain_score", sa.Float),
        sa.Column("global_pain_score", sa.Float),
        sa.Column("soreness_score", sa.Float),
        sa.Column("mood_score", sa.Float),
        sa.Column("motivation_score", sa.Float),
        sa.Column("stress_score_subjective", sa.Float),
        sa.Column("illness_flag", sa.Boolean),
        sa.Column("free_text_note", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- daily_source_coverage ---
    op.create_table(
        "daily_source_coverage",
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("garmin_coverage", sa.Boolean, server_default="false"),
        sa.Column("apple_health_coverage", sa.Boolean, server_default="false"),
        sa.Column("strava_coverage", sa.Boolean, server_default="false"),
        sa.Column("scale_coverage", sa.Boolean, server_default="false"),
        sa.Column("manual_input_coverage", sa.Boolean, server_default="false"),
        sa.Column("is_partial_day", sa.Boolean, server_default="false"),
        sa.Column("coverage_note", sa.Text),
    )

    # --- daily_features ---
    op.create_table(
        "daily_features",
        sa.Column("date", sa.Date, primary_key=True),
        # Recovery
        sa.Column("hrv_7d_avg", sa.Float),
        sa.Column("hrv_vs_28d_pct", sa.Float),
        sa.Column("resting_hr_7d_avg", sa.Float),
        sa.Column("resting_hr_vs_28d_delta", sa.Float),
        sa.Column("sleep_7d_avg", sa.Float),
        sa.Column("sleep_debt_min", sa.Float),
        sa.Column("recent_load_3d", sa.Float),
        sa.Column("recent_load_7d", sa.Float),
        sa.Column("recovery_trend", sa.Float),
        # Running
        sa.Column("weekly_km", sa.Float),
        sa.Column("rolling_4w_km", sa.Float),
        sa.Column("longest_run_last_7d_km", sa.Float),
        sa.Column("easy_pace_fixed_hr_sec_per_km", sa.Float),
        sa.Column("quality_sessions_last_14d", sa.Integer),
        sa.Column("projected_hm_time_sec", sa.Float),
        sa.Column("plan_adherence_pct", sa.Float),
        # Health
        sa.Column("body_weight_7d_avg", sa.Float),
        sa.Column("body_weight_28d_slope", sa.Float),
        sa.Column("sleep_consistency_score", sa.Float),
        sa.Column("pain_free_days_last_14d", sa.Integer),
        sa.Column("mood_trend", sa.Float),
        sa.Column("stress_trend", sa.Float),
        sa.Column("steps_consistency_score", sa.Float),
        # Hybrid balance
        sa.Column("hard_day_count_7d", sa.Integer),
        sa.Column("run_intensity_distribution_json", sa.JSON),
        sa.Column("lower_body_crossfit_density_7d", sa.Float),
        sa.Column("long_run_protection_score", sa.Float),
        sa.Column("interference_risk_score", sa.Float),
    )

    # --- score_snapshot ---
    op.create_table(
        "score_snapshot",
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("score_engine_version", sa.String(20), nullable=False),
        sa.Column("recovery_score", sa.Float),
        sa.Column("race_readiness_score", sa.Float),
        sa.Column("general_health_score", sa.Float),
        sa.Column("load_balance_score", sa.Float),
        sa.Column("subcomponents_json", sa.JSON),
        sa.Column("warnings_json", sa.JSON),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- recommendation_snapshot ---
    op.create_table(
        "recommendation_snapshot",
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("recommendation_engine_version", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("recommended_action", sa.String(100), nullable=False),
        sa.Column("intensity_modifier", sa.String(50)),
        sa.Column("duration_modifier", sa.String(50)),
        sa.Column("reason_codes_json", sa.JSON),
        sa.Column("next_best_alternative", sa.String(100)),
        sa.Column("risk_flags_json", sa.JSON),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- baseline_snapshot ---
    op.create_table(
        "baseline_snapshot",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("window_type", sa.String(30), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("baseline_value", sa.Float),
        sa.Column("sample_size", sa.Integer),
        sa.Column("baseline_start_date", sa.Date),
        sa.Column("baseline_end_date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- historical_best_block ---
    op.create_table(
        "historical_best_block",
        sa.Column("block_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("block_type", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("label", sa.String(200)),
        sa.Column("metric_summary_json", sa.JSON),
        sa.Column("notes", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("historical_best_block")
    op.drop_table("baseline_snapshot")
    op.drop_table("recommendation_snapshot")
    op.drop_table("score_snapshot")
    op.drop_table("daily_features")
    op.drop_table("daily_source_coverage")
    op.drop_table("manual_daily_input")
    op.drop_table("workout_fact")
    op.drop_table("daily_fact")
    op.drop_table("raw_event")
