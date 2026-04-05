"""Generate realistic seed CSV files for the Peakwise warehouse.

Produces ~365 days of synthetic data for a hybrid athlete doing CrossFit 4x/week
and running 3x/week, targeting a half marathon sub-1h50.

Usage:
    python -m seeds.generate_seed_data [--output-dir seeds/data]
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

START_DATE = date(2025, 4, 1)
END_DATE = date(2026, 4, 5)
SEED = 42

# Baseline ranges for the athlete
BODY_WEIGHT_BASE = 77.0
BODY_FAT_BASE = 15.5
RESTING_HR_BASE = 52
HRV_BASE = 48.0
SLEEP_BASE_MIN = 420  # 7 hours
STEPS_BASE = 8500
ACTIVE_ENERGY_BASE = 600

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RNG = random.Random(SEED)


def _jitter(base: float, pct: float = 0.05) -> float:
    return base * (1 + RNG.uniform(-pct, pct))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _round2(value: float) -> float:
    return round(value, 2)


# ---------------------------------------------------------------------------
# Daily metrics generation
# ---------------------------------------------------------------------------


def _generate_daily_metrics() -> list[dict]:
    """Generate Garmin-style daily metric rows."""
    rows: list[dict] = []
    current = START_DATE
    day_num = 0
    weight = BODY_WEIGHT_BASE

    while current <= END_DATE:
        day_num += 1

        # Gradual weight trend: slight cut then maintenance
        week = day_num // 7
        if week < 20:
            weight_trend = -0.03  # slow cut
        elif week < 40:
            weight_trend = -0.01
        else:
            weight_trend = 0.005  # slight regain / maintenance
        weight += weight_trend + RNG.gauss(0, 0.15)
        weight = _clamp(weight, 70.0, 85.0)

        body_fat = BODY_FAT_BASE + (weight - BODY_WEIGHT_BASE) * 0.3 + RNG.gauss(0, 0.3)
        body_fat = _clamp(body_fat, 10.0, 22.0)

        # Seasonal HRV variation: better in warmer months
        month_factor = 1.0 + 0.05 * math.sin(2 * math.pi * (current.month - 4) / 12)
        hrv = HRV_BASE * month_factor + RNG.gauss(0, 5)
        hrv = _clamp(hrv, 20, 90)

        resting_hr = RESTING_HR_BASE + RNG.gauss(0, 2)
        # Fatigue spikes resting HR
        if day_num % 7 in (5, 6):  # late-week fatigue
            resting_hr += RNG.uniform(1, 3)
        resting_hr = _clamp(resting_hr, 42, 70)

        sleep_min = SLEEP_BASE_MIN + RNG.gauss(0, 30)
        # Weekend tendency for more sleep
        if current.weekday() in (5, 6):
            sleep_min += RNG.uniform(10, 40)
        sleep_min = _clamp(sleep_min, 300, 540)

        sleep_score = 50 + (sleep_min - 360) / 3.6 + RNG.gauss(0, 5)
        sleep_score = _clamp(sleep_score, 30, 100)

        steps = int(STEPS_BASE + RNG.gauss(0, 2000))
        # Rest days have fewer steps
        if current.weekday() == 0:  # Monday rest
            steps = int(steps * 0.7)
        steps = max(2000, steps)

        active_energy = ACTIVE_ENERGY_BASE + RNG.gauss(0, 100)
        active_energy = _clamp(active_energy, 200, 1200)

        training_readiness = 50 + (hrv - HRV_BASE) * 0.5 + (420 - abs(sleep_min - 420)) * 0.05
        training_readiness += RNG.gauss(0, 5)
        training_readiness = _clamp(training_readiness, 20, 100)

        stress_score = 40 + RNG.gauss(0, 10)
        stress_score = _clamp(stress_score, 10, 90)

        body_battery = 60 + (sleep_score - 70) * 0.3 + RNG.gauss(0, 8)
        body_battery = _clamp(body_battery, 15, 100)

        # Occasional missing data (skip ~3% of days for Garmin)
        if RNG.random() < 0.03:
            current += timedelta(days=1)
            continue

        rows.append({
            "date": current.isoformat(),
            "body_weight_kg": _round2(weight),
            "body_fat_pct": _round2(body_fat),
            "resting_hr_bpm": int(round(resting_hr)),
            "hrv_ms": _round2(hrv),
            "sleep_duration_min": _round2(sleep_min),
            "sleep_score": _round2(sleep_score),
            "steps": steps,
            "active_energy_kcal": _round2(active_energy),
            "training_readiness": _round2(training_readiness),
            "stress_score": _round2(stress_score),
            "body_battery": _round2(body_battery),
        })

        current += timedelta(days=1)

    return rows


def _generate_apple_health_daily() -> list[dict]:
    """Generate Apple Health daily rows (subset of fields, some overlap with Garmin)."""
    rows: list[dict] = []
    current = START_DATE
    day_num = 0

    while current <= END_DATE:
        day_num += 1

        # Apple Health provides slightly different readings
        resting_hr = RESTING_HR_BASE + 1 + RNG.gauss(0, 2)
        resting_hr = _clamp(resting_hr, 42, 70)

        hrv = HRV_BASE - 2 + RNG.gauss(0, 5)
        hrv = _clamp(hrv, 20, 90)

        sleep_min = SLEEP_BASE_MIN - 5 + RNG.gauss(0, 25)
        if current.weekday() in (5, 6):
            sleep_min += RNG.uniform(10, 40)
        sleep_min = _clamp(sleep_min, 300, 540)

        steps = int(STEPS_BASE + 200 + RNG.gauss(0, 1800))
        steps = max(2000, steps)

        active_energy = ACTIVE_ENERGY_BASE + 20 + RNG.gauss(0, 90)
        active_energy = _clamp(active_energy, 200, 1200)

        # Skip ~5% of days
        if RNG.random() < 0.05:
            current += timedelta(days=1)
            continue

        rows.append({
            "date": current.isoformat(),
            "resting_hr_bpm": int(round(resting_hr)),
            "hrv_ms": _round2(hrv),
            "sleep_duration_min": _round2(sleep_min),
            "steps": steps,
            "active_energy_kcal": _round2(active_energy),
        })

        current += timedelta(days=1)

    return rows


def _generate_scale_data() -> list[dict]:
    """Generate scale readings (not every day — ~5 per week)."""
    rows: list[dict] = []
    current = START_DATE
    weight = BODY_WEIGHT_BASE

    while current <= END_DATE:
        week = (current - START_DATE).days // 7
        if week < 20:
            weight += -0.03 + RNG.gauss(0, 0.12)
        elif week < 40:
            weight += -0.01 + RNG.gauss(0, 0.10)
        else:
            weight += 0.005 + RNG.gauss(0, 0.10)
        weight = _clamp(weight, 70.0, 85.0)

        body_fat = BODY_FAT_BASE + (weight - BODY_WEIGHT_BASE) * 0.3 + RNG.gauss(0, 0.4)
        body_fat = _clamp(body_fat, 10.0, 22.0)

        # Weigh ~5 out of 7 days
        if RNG.random() < 5 / 7:
            rows.append({
                "date": current.isoformat(),
                "body_weight_kg": _round2(weight),
                "body_fat_pct": _round2(body_fat),
            })

        current += timedelta(days=1)

    return rows


# ---------------------------------------------------------------------------
# Workout generation
# ---------------------------------------------------------------------------

# Weekly template: Mon=rest, Tue=CF, Wed=run_easy, Thu=CF, Fri=run_quality,
# Sat=CF+run_easy, Sun=run_long (periodised)
_WEEKLY_TEMPLATE = {
    0: [],  # Monday rest
    1: ["crossfit"],
    2: ["run_easy"],
    3: ["crossfit"],
    4: ["run_quality"],
    5: ["crossfit", "run_easy"],  # double day
    6: ["run_long"],
}


def _generate_garmin_workouts() -> list[dict]:
    """Generate Garmin activity rows."""
    rows: list[dict] = []
    current = START_DATE
    workout_id = 1000
    week_num = 0

    while current <= END_DATE:
        dow = current.weekday()
        week_num = (current - START_DATE).days // 7

        # Progressive overload for running: weekly km increases over blocks
        if week_num < 12:
            km_factor = 0.8 + week_num * 0.03  # build up
        elif week_num < 24:
            km_factor = 1.1 + (week_num - 12) * 0.02
        elif week_num < 36:
            km_factor = 1.3  # maintenance
        else:
            km_factor = 1.2  # taper-ish

        sessions = _WEEKLY_TEMPLATE.get(dow, [])

        # Occasional missed sessions (~8%)
        sessions = [s for s in sessions if RNG.random() > 0.08]

        for session_type in sessions:
            workout_id += 1
            hour = 6 if "run" in session_type else 17
            start_dt = datetime(current.year, current.month, current.day, hour, 0)

            if session_type == "run_easy":
                distance = _round2(_jitter(8.0 * km_factor, 0.10))
                duration = _round2(distance * (5.5 + RNG.uniform(-0.3, 0.3)))
                avg_hr = int(_clamp(140 + RNG.gauss(0, 5), 125, 160))
                max_hr = avg_hr + int(RNG.uniform(10, 20))
                pace = _round2(duration * 60 / distance) if distance > 0 else None
                load = _round2(duration * avg_hr * 0.01)
                notes = ""
                route_type = RNG.choice(["road", "trail", "road"])

            elif session_type == "run_quality":
                distance = _round2(_jitter(10.0 * km_factor, 0.12))
                duration = _round2(distance * (4.8 + RNG.uniform(-0.3, 0.3)))
                avg_hr = int(_clamp(155 + RNG.gauss(0, 5), 140, 175))
                max_hr = avg_hr + int(RNG.uniform(10, 25))
                pace = _round2(duration * 60 / distance) if distance > 0 else None
                load = _round2(duration * avg_hr * 0.012)
                notes = RNG.choice([
                    "Tempo 4x2km",
                    "Intervals 6x1km",
                    "Threshold 20min",
                    "Fartlek",
                    "Hill repeats 8x400m",
                ])
                route_type = "road"

            elif session_type == "run_long":
                base_dist = 14.0 + min(week_num, 30) * 0.15
                distance = _round2(_jitter(base_dist * km_factor, 0.08))
                distance = _clamp(distance, 12.0, 24.0)
                duration = _round2(distance * (5.8 + RNG.uniform(-0.2, 0.4)))
                avg_hr = int(_clamp(138 + RNG.gauss(0, 4), 125, 155))
                max_hr = avg_hr + int(RNG.uniform(8, 18))
                pace = _round2(duration * 60 / distance) if distance > 0 else None
                load = _round2(duration * avg_hr * 0.011)
                notes = RNG.choice(["Long run", "Long steady", "Sunday long", ""])
                route_type = RNG.choice(["road", "trail"])

            elif session_type == "crossfit":
                distance = None
                duration = _round2(55 + RNG.uniform(-5, 10))
                avg_hr = int(_clamp(148 + RNG.gauss(0, 8), 125, 175))
                max_hr = avg_hr + int(RNG.uniform(15, 30))
                pace = None
                load = _round2(duration * avg_hr * 0.011)
                cf_notes = RNG.choice([
                    "Back squats 5x5, then AMRAP 12min: wall balls, box jumps, pull-ups",
                    "Clean and jerk complex, then 21-15-9 thrusters and burpees",
                    "Deadlifts 5x3, then 4 rounds: 400m run, 15 KB swings, 12 T2B",
                    "Strict press 5x5, then Cindy variant with push-ups and ring rows",
                    "Front squats 4x6, then EMOM 16min: cal row, DB snatch, box step-overs",
                    "Power cleans, then chipper: wall balls, DU, HSPU, lunges",
                    "Snatch practice, then 3 rounds: 500m row, 15 OH squats, 10 MU",
                    "Bench press 5x5, then 5 rounds: 10 DB thrusters, 15 cal bike, 20 sit-ups",
                ])
                notes = cf_notes
                route_type = ""
            else:
                continue

            end_dt = start_dt + timedelta(minutes=float(duration))

            rows.append({
                "source_workout_id": f"g{workout_id}",
                "session_date": current.isoformat(),
                "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "session_type": session_type if session_type != "crossfit" else "CrossFit",
                "duration_min": duration,
                "avg_hr_bpm": avg_hr,
                "max_hr_bpm": max_hr,
                "distance_km": distance or "",
                "avg_pace_sec_per_km": pace or "",
                "elevation_gain_m": int(RNG.uniform(20, 200)) if distance else "",
                "calories_kcal": int(load * 5 + RNG.uniform(50, 150)) if load else "",
                "training_load": load or "",
                "route_type": route_type,
                "cadence_spm": int(RNG.uniform(165, 180)) if distance else "",
                "notes": notes,
            })

        current += timedelta(days=1)

    return rows


def _generate_strava_workouts(garmin_rows: list[dict]) -> list[dict]:
    """Generate Strava rows for running workouts (overlap with Garmin for dedup testing)."""
    rows: list[dict] = []
    strava_id = 50000

    for g in garmin_rows:
        session_type = g["session_type"]
        # Only running workouts appear on Strava, and ~85% of them
        if session_type.startswith("run_") and RNG.random() < 0.85:
            strava_id += 1
            # Slightly different readings from Strava
            rows.append({
                "source_workout_id": f"s{strava_id}",
                "session_date": g["session_date"],
                "start_time": g["start_time"],
                "session_type": "Running",
                "duration_min": g["duration_min"],
                "distance_km": g["distance_km"],
                "avg_hr_bpm": g["avg_hr_bpm"],
                "max_hr_bpm": g["max_hr_bpm"],
                "avg_pace_sec_per_km": g["avg_pace_sec_per_km"],
                "elevation_gain_m": g["elevation_gain_m"],
                "calories_kcal": g["calories_kcal"],
                "notes": g["notes"],
            })

    return rows


# ---------------------------------------------------------------------------
# Manual input generation
# ---------------------------------------------------------------------------


def _generate_manual_inputs() -> list[dict]:
    """Generate sporadic manual input entries (~3 per week)."""
    rows: list[dict] = []
    current = START_DATE

    while current <= END_DATE:
        # ~3 entries per week
        if RNG.random() < 3 / 7:
            knee_pain = 0.0
            # Occasional knee flare-ups in blocks
            week = (current - START_DATE).days // 7
            if 8 <= week <= 10 or 28 <= week <= 30:
                knee_pain = _round2(RNG.uniform(2, 5))
            elif RNG.random() < 0.1:
                knee_pain = _round2(RNG.uniform(1, 3))

            global_pain = _round2(RNG.uniform(0, 3))
            soreness = _round2(RNG.uniform(1, 6))

            # Soreness higher after heavy days
            if current.weekday() in (2, 4, 6):  # day after CF or quality
                soreness = _round2(soreness + RNG.uniform(0, 2))
            soreness = _clamp(soreness, 0, 10)

            mood = _round2(_clamp(RNG.gauss(7, 1.5), 1, 10))
            motivation = _round2(_clamp(RNG.gauss(7.5, 1.2), 1, 10))
            stress = _round2(_clamp(RNG.gauss(4, 1.5), 1, 10))

            illness = "false"
            note = ""
            # Rare illness blocks
            if 18 <= week <= 19 and RNG.random() < 0.5:
                illness = "true"
                note = RNG.choice(["Cold symptoms", "Sore throat", "Feeling under the weather"])
                mood = _round2(_clamp(mood - 2, 1, 10))
                motivation = _round2(_clamp(motivation - 3, 1, 10))

            if knee_pain >= 3:
                note = RNG.choice([
                    "Knee stiff after long run",
                    "Outer knee aching",
                    "IT band area tender",
                    "Knee pain during squats",
                ])

            rows.append({
                "date": current.isoformat(),
                "left_knee_pain_score": knee_pain,
                "global_pain_score": global_pain,
                "soreness_score": _round2(soreness),
                "mood_score": mood,
                "motivation_score": motivation,
                "stress_score": stress,
                "illness_flag": illness,
                "note": note,
            })

        current += timedelta(days=1)

    return rows


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def _write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def generate(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating Garmin daily metrics...")
    garmin_daily = _generate_daily_metrics()
    _write_csv(garmin_daily, output_dir / "garmin_daily.csv")
    print(f"  → {len(garmin_daily)} rows")

    print("Generating Apple Health daily metrics...")
    apple_health = _generate_apple_health_daily()
    _write_csv(apple_health, output_dir / "apple_health_daily.csv")
    print(f"  → {len(apple_health)} rows")

    print("Generating scale data...")
    scale = _generate_scale_data()
    _write_csv(scale, output_dir / "scale_data.csv")
    print(f"  → {len(scale)} rows")

    print("Generating Garmin workouts...")
    garmin_workouts = _generate_garmin_workouts()
    _write_csv(garmin_workouts, output_dir / "garmin_activities.csv")
    print(f"  → {len(garmin_workouts)} rows")

    print("Generating Strava workouts...")
    strava_workouts = _generate_strava_workouts(garmin_workouts)
    _write_csv(strava_workouts, output_dir / "strava_activities.csv")
    print(f"  → {len(strava_workouts)} rows")

    print("Generating manual inputs...")
    manual = _generate_manual_inputs()
    _write_csv(manual, output_dir / "manual_inputs.csv")
    print(f"  → {len(manual)} rows")

    print(f"\nSeed data written to {output_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Peakwise seed data")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "data",
        help="Output directory for CSV files",
    )
    args = parser.parse_args()
    generate(args.output_dir)
