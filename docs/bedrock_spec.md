# Hybrid Training Intelligence Dashboard - Bedrock Specification

Foundation document for a daily decision system combining Garmin, Apple Health, Strava, scale data, historical baselines, and an LLM explanation layer.

## Purpose
Define the product, metrics engine, data model, user experience, recommendation logic, and implementation roadmap for a personal dashboard that acts as a daily operating system for hybrid training and general health.

## North-star product statement
A personal decision system that tells the user what to do today, why that choice is appropriate, whether progress toward the half marathon target is on track, and whether long-term health is improving or drifting.

## Design principles
- Decision-first, not dashboard-first: every screen must reduce uncertainty and end with an action recommendation.
- Personal baselines over generic norms: the system should compare the user primarily against their own 7-day, 28-day, 90-day, and seasonal history.
- Explainability over black-box scoring: deterministic metrics compute the core scores; the LLM interprets and explains them.
- Health guardrails over single-goal obsession: race preparation cannot silently degrade recovery, body composition, mood, pain, or sleep.
- Hybrid-athlete logic: CrossFit and running must be modeled together, including interference risk and local lower-body fatigue.
- Trend interpretation over point estimates: daily values matter less than direction, stability, and anomalies.

## User goals and operating context

| Goal layer | Examples for this project |
|---|---|
| Outcome goals | Run a strong half marathon, target sub-1h50, keep CrossFit 4x/week, reduce injury risk, improve body composition. |
| Capacity goals | Improve aerobic base, raise tolerance to long runs, maintain strength, reduce fatigue volatility, improve recovery consistency. |
| Health guardrails | Avoid persistent sleep debt, sustained HRV suppression, recurring outer-knee pain, aggressive weight loss, or chronic overload. |

## Primary product surfaces
- Today: Daily briefing with recommendation, recovery status, load balance, race-readiness, health state, and a short LLM explanation.
- Running: Half-marathon readiness, weekly distance, long-run progression, easy-run efficiency at fixed heart rate, projected race time, and plan adherence.
- Strength / CrossFit: Session content, lower-body load density, interference with key runs, and weekly structure quality.
- General health: Weight trend, sleep trend, resting heart rate, HRV, steps, pain, mood, stress, and recovery consistency.
- Coach / Reviews: Weekly summaries, anomaly detection, historical comparisons, and suggested plan adjustments.

## Data sources and ingestion scope

| Source | Data expected | Role in system |
|---|---|---|
| Garmin | Training readiness, HRV, resting HR, sleep, runs, load, stress, body battery if available. | Primary recovery and endurance source. |
| Apple Health | Steps, workouts, weight if synced, sleep, heart metrics, health-history consistency. | Secondary aggregator and health continuity layer. |
| Strava | Run metadata, titles, notes, CrossFit logs, training descriptions. | Workout archive and content parsing source. |
| Connected scale | Body weight, body fat estimate, trend consistency. | Body composition trend and weight-performance relationship. |
| Manual inputs | Knee pain, soreness, stress, mood, motivation, illness, subjective energy. | Context missing from wearable data. |
| Historical archive | At least one year of prior trends and event history. | Personal baselines, seasonality, anomaly context, progression analysis. |

### Key modeling choice
Normalize all incoming data into a common warehouse with two core grains: daily records and workout-session records. This avoids fragmented logic across source-specific schemas.

## Core warehouse schema

### 1. Daily fact table
- `date`, source coverage flags, body weight, body fat estimate, resting heart rate, HRV, sleep duration, sleep score, steps, active energy, training readiness, stress, body battery if present
- subjective fields: soreness, left-knee pain score, motivation, mood, illness, perceived fatigue
- derived fields: 7-day rolling averages, deviations from 28-day baseline, sleep debt, recovery trend, body-weight slope, health score components

### 2. Workout fact table
- `workout_id`, start/end time, source, session type, duration, average and max HR, TRIMP or equivalent load, distance, pace, elevation, calories if available
- run-specific fields: route type, cadence if available, splits, time in zones, weather if later added
- CrossFit-specific fields from notes: strength, squats, hinges, jumps, oly lifts, engine, metcon, upper-body dominant, lower-body dominant, RPE, local muscular stress tags
- post-processing fields: interference score contribution, next-day soreness linkage, training phase label

### 3. Baseline tables
- 7-day and 28-day rolling baselines for readiness variables
- 90-day baselines for health variables such as body weight, resting HR, and sleep consistency
- historical best blocks: best 4-week run consistency, best recovery block, best weight-to-performance window
- seasonality windows if enough history exists, such as comparing current half-marathon build with prior spring blocks

## Scoring engine

| Score | Purpose | Main inputs |
|---|---|---|
| Recovery score | Estimate ability to absorb training today. | HRV vs baseline, resting HR deviation, sleep, recent load, soreness, illness, readiness. |
| Race-readiness score | Estimate progression toward half-marathon target. | Weekly km, long-run completion, easy-run efficiency, workout adherence, threshold trend, projected time. |
| General-health score | Track long-term health rather than only performance. | Sleep consistency, weight trend, resting HR trend, HRV stability, steps, pain, mood, stress. |
| Load-balance score | Measure whether running and CrossFit are coherently balanced. | Hard-day density, lower-body CrossFit load, session spacing, long-run protection, intensity distribution. |

### Implementation rule
Each score should be deterministic, interpretable, and decomposable. The LLM explains the score; it does not invent the score.

## Recommendation engine
- Input layer: the four headline scores, recent anomalies, today’s planned session, current phase of the 12-week half-marathon plan, and user-imposed constraints.
- Decision modes: full go, train as planned, train but reduce intensity, recovery-focused, full rest, or injury-watch.
- Output layer: a recommended action such as CrossFit + easy run, quality run only, long run, CrossFit only, mobility walk, or full rest.
- Supporting rationale: which variables drove the recommendation, which tradeoffs are being made, and what the next-best alternative would be.

## LLM layer
- Receives only structured context: computed scores, recent changes, anomalies, training plan, baselines, and open warnings.
- Produces natural-language explanations, weekly reviews, answerable queries, and coaching-style summaries.
- Must not directly infer hidden raw-data relationships without support from the metrics engine; every claim should be anchored to observable features or explicit heuristics.
- Should support question answering such as: Why is today a yellow day? Is sub-1h50 still realistic? Is weight loss helping or hurting recovery? What pattern do you see around knee pain?

## Daily dashboard blueprint

| Panel | What it shows | Decision value |
|---|---|---|
| Today’s recommendation | The action for today, intensity, duration, and constraints. | Removes ambiguity immediately. |
| Recovery card | Readiness, HRV delta, resting HR delta, sleep, soreness. | Shows whether intensity is appropriate. |
| Half-marathon card | Weekly km, long-run status, easy-run efficiency, projected race readiness. | Shows whether the race plan is on track. |
| Health card | Weight trend, sleep consistency, pain, stress, steps. | Prevents narrow performance obsession. |
| Training-balance card | 7-day load, hard-day density, lower-body CrossFit interference. | Protects from overload and schedule mistakes. |
| LLM explanation | One short paragraph explaining status and today’s choice. | Makes the dashboard understandable and actionable. |

## Core visualizations
- Easy-run pace at fixed heart-rate band across time.
- Weekly running distance with plan overlay and compliance markers.
- Longest run per week and upcoming long-run target.
- Body weight 7-day average with annotation for race-readiness and recovery events.
- HRV and resting-heart-rate deviation from baseline, shown together.
- Load balance strip showing runs, CrossFit sessions, hard days, and recovery days in one weekly timeline.

## Primary KPIs

| Category | Primary KPIs |
|---|---|
| Performance | Weekly km, longest run, easy pace at fixed HR, quality-session completion, projected HM time. |
| Recovery | HRV vs baseline, resting HR vs baseline, sleep duration and debt, soreness, readiness trend. |
| Health | 7-day body-weight average, sleep consistency, pain-free training days, mood/stress trend, steps consistency. |
| Hybrid balance | Run intensity distribution, hard-day count, lower-body CrossFit density, interference score. |

## Definition of success
- The user can open the app in under 30 seconds each morning and understand what to do today.
- The system can explain whether progress toward sub-1h50 is improving, stagnating, or regressing.
- General health can improve at the same time as race readiness; the product makes tradeoffs visible rather than implicit.
- CrossFit and running are modeled as one system, not two unrelated activity streams.
- The user can ask follow-up questions in natural language and receive grounded explanations.

## Functional requirements for version 1
- Import and normalize Garmin, Apple Health, Strava, manual notes, and scale data.
- Compute the four headline scores daily.
- Generate one daily recommendation with reason codes and LLM explanation.
- Display the Today page, Running page, Health page, Strength/CrossFit page, and weekly review.
- Support historical trend analysis and baseline comparison using at least one year of data.
- Allow user feedback on recommendation quality so the logic can be refined.

## Version 2 expansion areas
- Adaptive training-plan updates based on compliance and fatigue response.
- Anomaly detection and “what changed?” narratives.
- Body-weight-to-performance modeling and calorie-deficit warnings.
- Travel, illness, and schedule-disruption modes.
- Calendar integration and proactive session scheduling.
- More advanced injury-risk heuristics and context-aware prompts.

## System architecture
1. Connectors ingest source data through APIs, exports, or sync jobs.
2. A normalization layer maps all records into warehouse tables with source lineage and coverage flags.
3. A feature layer computes rolling baselines, deltas, trend slopes, training-load features, and CrossFit content tags.
4. A deterministic scoring engine computes the four headline scores and recommendation mode.
5. An LLM orchestration layer receives structured context and generates explanations, reviews, and conversational answers.
6. A front-end dashboard renders the Today screen, trends, and review surfaces.

## Suggested technical decomposition

| Layer | Recommended responsibility |
|---|---|
| Data ingestion | Source connectors, exports, schedule jobs, validation, retries, source coverage monitoring. |
| Storage | Event store plus analytics-friendly warehouse, ideally with both raw and curated tables. |
| Feature engineering | Baselines, trend slopes, zone summaries, session classification, note parsing, quality flags. |
| Decision engine | Recovery, race-readiness, health, load-balance scoring and recommendation rules. |
| LLM orchestration | Prompt assembly, explanation generation, Q&A, audit logging, hallucination constraints. |
| Front-end | Daily briefing, trend views, plan tracking, reviews, and coach interactions. |

## Security, privacy, and trust constraints
- Health and training data are sensitive. Data minimization, explicit source permissions, and clear retention rules are required.
- The user must be able to inspect why a recommendation was made. Explanations should cite score components and trend deltas, not vague claims.
- Raw source values and source availability should be preserved so data-quality gaps are visible instead of silently imputed.
- LLM outputs should be logged with the structured context used to produce them for debugging and trust.

## Practical roadmap

| Phase | Outcome |
|---|---|
| Phase 1: warehouse foundation | Import historical data, build daily/session schema, and create baseline features. |
| Phase 2: scoring engine | Implement deterministic scores and the recommendation mode classifier. |
| Phase 3: dashboard MVP | Ship Today, Running, Health, and Strength screens with the main KPIs. |
| Phase 4: LLM coach | Add explanation layer, daily briefing text, and weekly reviews. |
| Phase 5: refinement | Tune thresholds with lived data, add feedback loops, and improve anomaly handling. |

## Open implementation decisions to settle early
- Which sync path is most robust for Garmin and Apple Health in the chosen deployment environment?
- How much manual tagging of CrossFit logs is acceptable before building note-parsing heuristics?
- Should version 1 support direct plan adaptation or remain recommendation-only?
- What exact weight trend range is considered healthy and sustainable for the user?
- What threshold should trigger a knee-risk warning, and how much should pain suppress intensity recommendations?

## Recommended interpretation of health
For this product, health should be defined as sustained physical capacity, stable recovery, acceptable body composition trends, low recurring pain, adequate sleep, and the ability to train consistently without hidden deterioration.

## Minimal acceptance checklist
- One-click daily briefing exists and is understandable.
- Historical baselines are visible and used in scoring.
- At least one year of prior data can be ingested and queried.
- Weekly review can summarize what improved, what worsened, and what to change next week.
- The recommendation engine is inspectable and not LLM-only.
- The system can answer “what should I do today and why?” reliably.

## No further questions required for the foundation document
This specification is sufficient to act as the bedrock for product scoping and the first implementation pass.

The next step is not more ideation but converting this document into a technical product spec with database schema, score formulas, API contracts, and screen-level UI wireframes.
