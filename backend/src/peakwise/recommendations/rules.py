"""Recommendation rules engine.

Maps scores + warnings → recommendation mode → suggested action.
All logic is deterministic and rule-based.
"""

from __future__ import annotations

from dataclasses import dataclass

from peakwise.config import (
    RECO_HEALTH_CAUTION,
    RECO_LOAD_BALANCE_CAUTION,
    RECO_RECOVERY_FULL_GO,
    RECO_RECOVERY_RECOVERY_FOCUSED,
    RECO_RECOVERY_REDUCE_INTENSITY,
    RECO_RECOVERY_TRAIN_AS_PLANNED,
)
from peakwise.models import RecommendationMode


@dataclass
class RecommendationResult:
    mode: RecommendationMode
    recommended_action: str
    intensity_modifier: str | None
    duration_modifier: str | None
    reason_codes: list[str]
    next_best_alternative: str | None
    risk_flags: list[str]


# ---------------------------------------------------------------------------
# Mode → action mapping
# ---------------------------------------------------------------------------

_MODE_ACTIONS: dict[RecommendationMode, str] = {
    RecommendationMode.full_go: "Train as planned, including hard sessions",
    RecommendationMode.train_as_planned: "Follow today's plan at normal intensity",
    RecommendationMode.reduce_intensity: "Train but reduce intensity or volume",
    RecommendationMode.recovery_focused: "Light movement only: walk, mobility, or easy spin",
    RecommendationMode.full_rest: "Full rest day — skip training",
    RecommendationMode.injury_watch: "Rest or pain-free movement only; monitor symptoms",
}

_MODE_INTENSITY: dict[RecommendationMode, str | None] = {
    RecommendationMode.full_go: None,
    RecommendationMode.train_as_planned: None,
    RecommendationMode.reduce_intensity: "Cap effort at moderate; avoid quality sessions",
    RecommendationMode.recovery_focused: "Very easy only; HR below zone 2",
    RecommendationMode.full_rest: None,
    RecommendationMode.injury_watch: "Zero impact if pain present",
}

_MODE_DURATION: dict[RecommendationMode, str | None] = {
    RecommendationMode.full_go: None,
    RecommendationMode.train_as_planned: None,
    RecommendationMode.reduce_intensity: "Shorten session by ~20-30%",
    RecommendationMode.recovery_focused: "Keep under 30-40 minutes",
    RecommendationMode.full_rest: None,
    RecommendationMode.injury_watch: None,
}

# Next-best fallback: what to do if the primary recommendation feels too
# conservative or too aggressive.
_MODE_ALTERNATIVES: dict[RecommendationMode, str | None] = {
    RecommendationMode.full_go: "If fatigue appears mid-session, drop to easy pace",
    RecommendationMode.train_as_planned: "Reduce intensity if fatigue accumulates",
    RecommendationMode.reduce_intensity: "Switch to recovery-focused if discomfort rises",
    RecommendationMode.recovery_focused: "Full rest if even light movement feels taxing",
    RecommendationMode.full_rest: "Gentle walk if stiffness improves later in the day",
    RecommendationMode.injury_watch: "Consult a professional if pain persists or worsens",
}

# Ordered from most restrictive to least (used for capping)
_MODE_ORDER: list[RecommendationMode] = [
    RecommendationMode.full_rest,
    RecommendationMode.injury_watch,
    RecommendationMode.recovery_focused,
    RecommendationMode.reduce_intensity,
    RecommendationMode.train_as_planned,
    RecommendationMode.full_go,
]


def _cap_mode(current: RecommendationMode, ceiling: RecommendationMode) -> RecommendationMode:
    """Return the more restrictive of *current* and *ceiling*."""
    current_idx = _MODE_ORDER.index(current)
    ceiling_idx = _MODE_ORDER.index(ceiling)
    return _MODE_ORDER[min(current_idx, ceiling_idx)]


# ---------------------------------------------------------------------------
# Warning → mode overrides
# ---------------------------------------------------------------------------


def _apply_warning_overrides(
    mode: RecommendationMode,
    warnings: dict[str, bool],
    reason_codes: list[str],
    risk_flags: list[str],
) -> RecommendationMode:
    """Apply hard-warning overrides that cap the recommendation mode."""

    if warnings.get("illness_warning"):
        mode = _cap_mode(mode, RecommendationMode.recovery_focused)
        reason_codes.append("illness_active")
        risk_flags.append("illness_warning")

    if warnings.get("knee_pain_warning"):
        mode = _cap_mode(mode, RecommendationMode.injury_watch)
        reason_codes.append("knee_pain_elevated")
        risk_flags.append("knee_pain_warning")

    if warnings.get("overload_warning"):
        mode = _cap_mode(mode, RecommendationMode.reduce_intensity)
        reason_codes.append("overload_detected")
        risk_flags.append("overload_warning")

    if warnings.get("sleep_debt_warning"):
        mode = _cap_mode(mode, RecommendationMode.reduce_intensity)
        reason_codes.append("sleep_debt_high")
        risk_flags.append("sleep_debt_warning")

    if warnings.get("hrv_suppression_warning"):
        mode = _cap_mode(mode, RecommendationMode.reduce_intensity)
        reason_codes.append("hrv_suppressed")
        risk_flags.append("hrv_suppression_warning")

    return mode


# ---------------------------------------------------------------------------
# Score → mode mapping
# ---------------------------------------------------------------------------


def _recovery_to_base_mode(
    recovery: float,
    reason_codes: list[str],
) -> RecommendationMode:
    """Determine the base recommendation mode from recovery score."""
    if recovery >= RECO_RECOVERY_FULL_GO:
        reason_codes.append("recovery_high")
        return RecommendationMode.full_go
    if recovery >= RECO_RECOVERY_TRAIN_AS_PLANNED:
        reason_codes.append("recovery_acceptable")
        return RecommendationMode.train_as_planned
    if recovery >= RECO_RECOVERY_REDUCE_INTENSITY:
        reason_codes.append("recovery_moderate")
        return RecommendationMode.reduce_intensity
    if recovery >= RECO_RECOVERY_RECOVERY_FOCUSED:
        reason_codes.append("recovery_low")
        return RecommendationMode.recovery_focused
    reason_codes.append("recovery_very_low")
    return RecommendationMode.full_rest


def determine_recommendation(
    recovery_score: float,
    race_readiness_score: float,
    general_health_score: float,
    load_balance_score: float,
    warnings: dict[str, bool],
) -> RecommendationResult:
    """Determine the full recommendation from scores and warnings.

    The algorithm:
    1. Map recovery score to a base mode.
    2. Cap the mode if load-balance or health scores are in caution range.
    3. Apply hard-warning overrides.
    4. Map the final mode to an action, modifiers, and alternative.
    """
    reason_codes: list[str] = []
    risk_flags: list[str] = []

    # Step 1: base mode from recovery
    mode = _recovery_to_base_mode(recovery_score, reason_codes)

    # Step 2: secondary score caps
    if load_balance_score < RECO_LOAD_BALANCE_CAUTION:
        mode = _cap_mode(mode, RecommendationMode.reduce_intensity)
        reason_codes.append("load_balance_poor")

    if general_health_score < RECO_HEALTH_CAUTION:
        mode = _cap_mode(mode, RecommendationMode.reduce_intensity)
        reason_codes.append("health_caution")

    # Step 3: hard-warning overrides
    mode = _apply_warning_overrides(mode, warnings, reason_codes, risk_flags)

    # Step 4: build result
    return RecommendationResult(
        mode=mode,
        recommended_action=_MODE_ACTIONS[mode],
        intensity_modifier=_MODE_INTENSITY[mode],
        duration_modifier=_MODE_DURATION[mode],
        reason_codes=reason_codes,
        next_best_alternative=_MODE_ALTERNATIVES[mode],
        risk_flags=risk_flags,
    )
