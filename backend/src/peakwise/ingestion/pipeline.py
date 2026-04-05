from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from peakwise.ingestion.apple_health import parse_apple_health_csv
from peakwise.ingestion.base import (
    IngestionResult,
    ParsedDailyRecord,
    ParsedManualInput,
    ParsedWorkoutRecord,
)
from peakwise.ingestion.dedup import deduplicate_workouts
from peakwise.ingestion.garmin import parse_garmin_activities_csv, parse_garmin_daily_csv
from peakwise.ingestion.manual import parse_manual_input_csv
from peakwise.ingestion.normalize import (
    apply_manual_inputs,
    build_raw_events,
    build_source_coverage,
    build_workout_facts,
    mark_missing_days,
    merge_daily_records,
)
from peakwise.ingestion.scale import parse_scale_csv
from peakwise.ingestion.strava import parse_strava_csv

logger = logging.getLogger("peakwise.ingestion")


@dataclass
class IngestionManifest:
    """Paths to source CSV files for ingestion."""

    garmin_daily_csv: Path | None = None
    garmin_activities_csv: Path | None = None
    apple_health_csv: Path | None = None
    strava_csv: Path | None = None
    scale_csv: Path | None = None
    manual_input_csv: Path | None = None


@dataclass
class PipelineResult:
    daily_facts_count: int = 0
    workout_facts_count: int = 0
    manual_inputs_count: int = 0
    coverage_records_count: int = 0
    raw_events_count: int = 0
    duplicates_found: int = 0
    results: list[IngestionResult] = field(default_factory=list)

    @property
    def total_errors(self) -> int:
        return sum(len(r.errors) for r in self.results)


def run_ingestion(
    manifest: IngestionManifest,
    session: Session,
) -> PipelineResult:
    """Run the full ingestion pipeline: parse → normalize → deduplicate → persist.

    This is the main entry point for rebuilding the warehouse from exported
    data files.  Each run is idempotent — existing rows for the same dates
    are replaced (merge-upsert strategy).
    """
    pipeline = PipelineResult()
    all_daily: list[ParsedDailyRecord] = []
    all_workouts: list[ParsedWorkoutRecord] = []
    all_manual: list[ParsedManualInput] = []

    # ---- Parse each source ----

    if manifest.garmin_daily_csv and manifest.garmin_daily_csv.exists():
        records, result = parse_garmin_daily_csv(manifest.garmin_daily_csv)
        all_daily.extend(records)
        pipeline.results.append(result)
        logger.info("Garmin daily: %d rows imported", result.rows_imported)

    if manifest.garmin_activities_csv and manifest.garmin_activities_csv.exists():
        records, result = parse_garmin_activities_csv(manifest.garmin_activities_csv)
        all_workouts.extend(records)
        pipeline.results.append(result)
        logger.info("Garmin activities: %d rows imported", result.rows_imported)

    if manifest.apple_health_csv and manifest.apple_health_csv.exists():
        records, result = parse_apple_health_csv(manifest.apple_health_csv)
        all_daily.extend(records)
        pipeline.results.append(result)
        logger.info("Apple Health: %d rows imported", result.rows_imported)

    if manifest.strava_csv and manifest.strava_csv.exists():
        records, result = parse_strava_csv(manifest.strava_csv)
        all_workouts.extend(records)
        pipeline.results.append(result)
        logger.info("Strava: %d rows imported", result.rows_imported)

    if manifest.scale_csv and manifest.scale_csv.exists():
        records, result = parse_scale_csv(manifest.scale_csv)
        all_daily.extend(records)
        pipeline.results.append(result)
        logger.info("Scale: %d rows imported", result.rows_imported)

    if manifest.manual_input_csv and manifest.manual_input_csv.exists():
        records, result = parse_manual_input_csv(manifest.manual_input_csv)
        all_manual.extend(records)
        pipeline.results.append(result)
        logger.info("Manual input: %d rows imported", result.rows_imported)

    # ---- Normalize ----

    daily_facts = merge_daily_records(all_daily)
    manual_input_models = apply_manual_inputs(daily_facts, all_manual)
    workout_facts = build_workout_facts(all_workouts)

    # ---- Deduplicate workouts ----

    deduplicate_workouts(workout_facts)
    pipeline.duplicates_found = sum(1 for w in workout_facts if w.is_duplicate)

    # ---- Build coverage & mark missing days ----

    coverage = build_source_coverage(daily_facts, workout_facts, manual_input_models)
    coverage = mark_missing_days(daily_facts, coverage)

    # ---- Build raw events for lineage ----

    raw_events = build_raw_events(all_daily, all_workouts, all_manual)

    # ---- Persist ----

    _persist(session, daily_facts, workout_facts, manual_input_models, coverage, raw_events)

    pipeline.daily_facts_count = len(daily_facts)
    pipeline.workout_facts_count = len(workout_facts)
    pipeline.manual_inputs_count = len(manual_input_models)
    pipeline.coverage_records_count = len(coverage)
    pipeline.raw_events_count = len(raw_events)

    logger.info(
        "Ingestion complete: %d daily, %d workouts (%d duplicates), "
        "%d manual, %d coverage, %d raw events, %d errors",
        pipeline.daily_facts_count,
        pipeline.workout_facts_count,
        pipeline.duplicates_found,
        pipeline.manual_inputs_count,
        pipeline.coverage_records_count,
        pipeline.raw_events_count,
        pipeline.total_errors,
    )

    return pipeline


def _persist(session, daily_facts, workout_facts, manual_inputs, coverage, raw_events):
    """Write all records to the database using merge (upsert) semantics."""
    for fact in daily_facts:
        session.merge(fact)

    for wf in workout_facts:
        session.merge(wf)

    for mi in manual_inputs:
        session.add(mi)

    for cov in coverage:
        session.merge(cov)

    for evt in raw_events:
        session.add(evt)

    session.flush()
