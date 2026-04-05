"""Seed the local Peakwise database from generated CSV files.

Usage:
    # Generate CSVs and populate the database:
    python -m seeds.seed_db

    # Use existing CSV files:
    python -m seeds.seed_db --data-dir seeds/data --skip-generate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

from peakwise.config import Settings
from peakwise.db import get_engine, get_session_factory
from peakwise.ingestion.pipeline import IngestionManifest, run_ingestion
from peakwise.models import Base
from seeds.generate_seed_data import generate


def seed(data_dir: Path, settings: Settings | None = None) -> None:
    """Run the ingestion pipeline against seed CSV files."""
    if settings is None:
        settings = Settings()

    engine = get_engine(settings)

    # Ensure tables exist
    Base.metadata.create_all(engine)

    session_factory = get_session_factory(settings)

    manifest = IngestionManifest(
        garmin_daily_csv=data_dir / "garmin_daily.csv",
        garmin_activities_csv=data_dir / "garmin_activities.csv",
        apple_health_csv=data_dir / "apple_health_daily.csv",
        strava_csv=data_dir / "strava_activities.csv",
        scale_csv=data_dir / "scale_data.csv",
        manual_input_csv=data_dir / "manual_inputs.csv",
    )

    with session_factory() as session:
        # Clear existing data for a clean seed
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f"DELETE FROM {table.name}"))
        session.flush()

        result = run_ingestion(manifest, session)
        session.commit()

    print("\n=== Seed Results ===")
    print(f"Daily facts:      {result.daily_facts_count}")
    print(f"Workout facts:    {result.workout_facts_count}")
    print(f"Manual inputs:    {result.manual_inputs_count}")
    print(f"Coverage records: {result.coverage_records_count}")
    print(f"Raw events:       {result.raw_events_count}")
    print(f"Duplicates found: {result.duplicates_found}")
    print(f"Total errors:     {result.total_errors}")

    if result.total_errors > 0:
        print("\nErrors:")
        for r in result.results:
            for err in r.errors:
                print(f"  [{err.source}] row {err.row_number}: {err.message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Peakwise database")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).parent / "data",
        help="Directory containing seed CSV files",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Skip CSV generation (use existing files)",
    )
    args = parser.parse_args()

    if not args.skip_generate:
        print("Generating seed data...")
        generate(args.data_dir)
        print()

    # Verify files exist
    expected = [
        "garmin_daily.csv",
        "garmin_activities.csv",
        "apple_health_daily.csv",
        "strava_activities.csv",
        "scale_data.csv",
        "manual_inputs.csv",
    ]
    missing = [f for f in expected if not (args.data_dir / f).exists()]
    if missing:
        print(f"Missing seed files: {missing}", file=sys.stderr)
        sys.exit(1)

    print("Seeding database...")
    seed(args.data_dir)
    print("\nDone.")


if __name__ == "__main__":
    main()
