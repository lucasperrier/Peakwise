"""CrossFit workout text parser.

Parses Strava notes / manual logs to extract movement tags, infer
lower-body stress, and compute interference risk for subsequent sessions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from peakwise.config import CROSSFIT_KEYWORDS, LOWER_BODY_TAGS


@dataclass
class ParsedWorkoutTags:
    """Result of parsing a CrossFit workout description."""

    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    lower_body_stress_score: float = 0.0
    interference_risk_24h: float = 0.0
    is_lower_body_dominant: bool = False


def parse_crossfit_notes(text: str | None) -> ParsedWorkoutTags:
    """Parse workout notes/description to extract movement tags.

    Returns a ParsedWorkoutTags with detected tags and derived scores.
    """
    if not text or not text.strip():
        return ParsedWorkoutTags(confidence=0.0)

    lowered = text.lower()
    found_tags: set[str] = set()

    for tag, keywords in CROSSFIT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lowered:
                found_tags.add(tag)
                break

    if not found_tags:
        return ParsedWorkoutTags(confidence=0.3)

    tags = sorted(found_tags)

    # Compute lower-body stress
    lower_body_count = sum(1 for t in tags if t in LOWER_BODY_TAGS)
    total_count = len(tags)
    lower_body_fraction = lower_body_count / total_count if total_count > 0 else 0.0

    # Lower-body stress 0-100
    lower_body_stress = min(100.0, lower_body_count * 25.0)

    # Is lower-body dominant?
    is_lower_body_dominant = lower_body_fraction >= 0.5

    # Interference risk for next 24-48h (0-100)
    # Higher if more lower-body, metcon, jumps
    interference = lower_body_stress * 0.6
    if "jump" in found_tags:
        interference += 15.0
    if "metcon" in found_tags:
        interference += 10.0
    if "engine" in found_tags:
        interference += 5.0
    interference = min(100.0, interference)

    # Confidence: higher if more tags matched
    confidence = min(1.0, 0.5 + total_count * 0.1)

    return ParsedWorkoutTags(
        tags=tags,
        confidence=confidence,
        lower_body_stress_score=round(lower_body_stress, 1),
        interference_risk_24h=round(interference, 1),
        is_lower_body_dominant=is_lower_body_dominant,
    )


def parse_and_tag_workout(
    raw_notes: str | None,
    session_type: str,
    existing_tags: dict[str, bool | None] | None = None,
) -> ParsedWorkoutTags:
    """Parse and tag a workout, combining existing tags with parsed results.

    If the workout already has manual tags (from WorkoutFact), those are
    used as ground truth with high confidence, and the parser fills gaps.
    """
    # If not a CrossFit/strength workout, skip parsing
    if session_type not in ("crossfit", "strength"):
        return ParsedWorkoutTags(confidence=0.0)

    parsed = parse_crossfit_notes(raw_notes)

    # Merge with existing boolean tags from WorkoutFact
    if existing_tags:
        tag_map = {
            "has_squats": "squat",
            "has_hinges": "hinge",
            "has_jumps": "jump",
            "has_oly_lifts": "olympic_lift",
            "is_strength": "squat",  # approximate
            "is_engine": "engine",
            "is_metcon": "metcon",
        }
        for field_name, tag in tag_map.items():
            if existing_tags.get(field_name) is True and tag not in parsed.tags:
                parsed.tags.append(tag)

        parsed.tags = sorted(set(parsed.tags))

        # Recompute derived scores with merged tags
        lower_body_count = sum(1 for t in parsed.tags if t in LOWER_BODY_TAGS)
        total_count = len(parsed.tags)

        parsed.lower_body_stress_score = min(100.0, lower_body_count * 25.0)
        parsed.is_lower_body_dominant = (lower_body_count / total_count >= 0.5) if total_count > 0 else False
        parsed.confidence = min(1.0, max(parsed.confidence, 0.8))

    return parsed
