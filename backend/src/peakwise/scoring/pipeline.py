"""Scoring pipeline.

Orchestrates the computation of all four scores plus warnings from the
feature layer and curated warehouse, then persists results to the
score_snapshot table.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from peakwise.config import SCORE_ENGINE_VERSION
from peakwise.models import DailyFact, DailyFeatures, RecommendationSnapshot, ScoreSnapshot
from peakwise.scoring.breakdowns import persist_score_breakdown
from peakwise.scoring.health import compute_general_health_score
from peakwise.scoring.load_balance import compute_load_balance_score
from peakwise.scoring.race_readiness import compute_race_readiness_score
from peakwise.scoring.recovery import compute_recovery_score
from peakwise.scoring.warnings import compute_all_warnings
from peakwise.trust import compute_decision_confidence

logger = logging.getLogger("peakwise.scoring")


@dataclass
class ScoringPipelineResult:
    dates_scored: int = 0
    dates_skipped: int = 0
    errors: list[str] = field(default_factory=list)


def compute_scores_for_date(
    target_date: date,
    daily_facts: dict[date, DailyFact],
    features: dict[date, DailyFeatures],
) -> ScoreSnapshot | None:
    """Compute all scores for a single date and return a ScoreSnapshot.

    Returns ``None`` if the required data is missing for the target date.
    """
    feat = features.get(target_date)
    fact = daily_facts.get(target_date)
    if feat is None or fact is None:
        return None

    recovery, recovery_subs = compute_recovery_score(feat, fact)
    race_readiness, race_subs = compute_race_readiness_score(feat)
    health, health_subs = compute_general_health_score(feat)
    load_balance, load_subs = compute_load_balance_score(feat)
    warnings = compute_all_warnings(feat, fact)

    subcomponents: dict[str, dict[str, float | None] | dict[str, bool]] = {
        "recovery": recovery_subs,
        "race_readiness": race_subs,
        "general_health": health_subs,
        "load_balance": load_subs,
    }

    return ScoreSnapshot(
        date=target_date,
        score_engine_version=SCORE_ENGINE_VERSION,
        recovery_score=recovery,
        race_readiness_score=race_readiness,
        general_health_score=health,
        load_balance_score=load_balance,
        subcomponents_json=subcomponents,
        warnings_json=warnings,
    )


def run_scoring_pipeline(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ScoringPipelineResult:
    """Compute and persist scores for a date range.

    Requires the feature layer (daily_features) to already be populated.
    """
    result = ScoringPipelineResult()

    # Determine date range from daily_features
    all_feature_dates: list[date] = [
        row[0]
        for row in session.execute(
            select(DailyFeatures.date).order_by(DailyFeatures.date)
        ).all()
    ]
    if not all_feature_dates:
        return result

    effective_start = start_date or all_feature_dates[0]
    effective_end = end_date or all_feature_dates[-1]

    # Load data
    daily_rows: list[DailyFact] = list(
        session.scalars(
            select(DailyFact).where(
                DailyFact.date >= effective_start,
                DailyFact.date <= effective_end,
            )
        ).all()
    )
    daily_facts: dict[date, DailyFact] = {f.date: f for f in daily_rows}

    feature_rows: list[DailyFeatures] = list(
        session.scalars(
            select(DailyFeatures).where(
                DailyFeatures.date >= effective_start,
                DailyFeatures.date <= effective_end,
            )
        ).all()
    )
    features: dict[date, DailyFeatures] = {f.date: f for f in feature_rows}

    # Score each date
    current = effective_start
    while current <= effective_end:
        if current not in features or current not in daily_facts:
            result.dates_skipped += 1
            current += timedelta(days=1)
            continue
        try:
            snapshot = compute_scores_for_date(current, daily_facts, features)
            if snapshot is None:
                result.dates_skipped += 1
            else:
                session.merge(snapshot)

                # Persist score breakdown (best-effort)
                try:
                    fact = daily_facts.get(current)
                    conf_score, conf_level = compute_decision_confidence(fact, current, session)
                    rec: RecommendationSnapshot | None = session.get(RecommendationSnapshot, current)
                    persist_score_breakdown(
                        target_date=current,
                        score_snapshot=snapshot,
                        rec_snapshot=rec,
                        confidence_score=conf_score,
                        confidence_level=conf_level,
                        session=session,
                    )
                except Exception as exc:
                    logger.warning("Failed to persist breakdown for %s: %s", current, exc)

                result.dates_scored += 1
        except Exception as exc:
            msg = f"Error scoring {current}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
        current += timedelta(days=1)

    session.flush()
    logger.info(
        "Scoring pipeline complete: %d scored, %d skipped, %d errors",
        result.dates_scored,
        result.dates_skipped,
        len(result.errors),
    )
    return result
