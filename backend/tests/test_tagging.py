"""Tests for the CrossFit workout tagging module."""

from __future__ import annotations

import pytest

from peakwise.tagging import parse_crossfit_notes


class TestParseCrossfitNotes:
    def test_squat_detection(self):
        result = parse_crossfit_notes("5x5 back squat, then AMRAP")
        assert "squat" in result.tags

    def test_hinge_detection(self):
        result = parse_crossfit_notes("Deadlift 3x3 then RDLs")
        assert "hinge" in result.tags

    def test_olympic_lift_detection(self):
        result = parse_crossfit_notes("Clean and jerk complex, 5 sets")
        assert "olympic_lift" in result.tags
        assert "hinge" in result.tags

    def test_upper_push_detection(self):
        result = parse_crossfit_notes("Bench press 5x5, then push-ups")
        assert "upper_push" in result.tags

    def test_upper_pull_detection(self):
        result = parse_crossfit_notes("Pull-ups 3 sets to failure")
        assert "upper_pull" in result.tags

    def test_metcon_detection(self):
        result = parse_crossfit_notes("WOD: Fran 21-15-9 thrusters")
        assert "metcon" in result.tags
        assert "squat" in result.tags

    def test_engine_detection(self):
        result = parse_crossfit_notes("20min EMOM: row 500m / bike 1min")
        assert "engine" in result.tags

    def test_lunge_detection(self):
        result = parse_crossfit_notes("Walking lunges with KB, then box jumps")
        assert "lunge" in result.tags
        assert "jump" in result.tags

    def test_jump_detection(self):
        result = parse_crossfit_notes("Box jump overs, then burpees")
        assert "jump" in result.tags

    def test_lower_body_dominant(self):
        """Heavy squat + lunge → lower body dominant."""
        result = parse_crossfit_notes("Back squat 5x5, then walking lunges, then box jumps")
        assert result.is_lower_body_dominant is True

    def test_upper_body_session(self):
        """Pull-ups + bench → not lower body dominant."""
        result = parse_crossfit_notes("Pull-ups and bench press")
        assert result.is_lower_body_dominant is False

    def test_empty_text(self):
        result = parse_crossfit_notes("")
        assert result.tags == []
        assert result.lower_body_stress_score == 0.0
        assert result.interference_risk_24h == 0.0
        assert result.is_lower_body_dominant is False

    def test_none_text(self):
        result = parse_crossfit_notes(None)
        assert result.tags == []

    def test_interference_risk_high_lower_body(self):
        """Heavy lower body session → high interference risk."""
        result = parse_crossfit_notes("Back squat 5x5, deadlifts, box jumps, lunges")
        assert result.interference_risk_24h > 0.5

    def test_case_insensitive(self):
        result = parse_crossfit_notes("BACK SQUAT 5x5")
        assert "squat" in result.tags

    def test_multiple_tags(self):
        result = parse_crossfit_notes("Clean and jerk, then burpee box jumps, pull-ups")
        assert len(result.tags) >= 3
