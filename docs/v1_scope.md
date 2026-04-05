# V1 Scope

## Purpose
Version 1 is the minimum product that can answer one core daily question reliably:

**What should I do today, and why?**

V1 should produce a grounded daily recommendation based on normalized training and health data, deterministic scores, and a short LLM explanation layer.

This scope is derived from the bedrock specification and intentionally prioritizes decision support over breadth.

---

## Product goal for V1
Build a usable MVP that:
- ingests historical and current health/training data into a common warehouse
- computes deterministic daily scores
- outputs one daily action recommendation
- explains that recommendation in plain language
- lets the user inspect the main drivers behind the recommendation

The MVP should be good enough to act as a daily operating system for hybrid training and general health.

---

## Core V1 user story
Each morning, the user opens the app and can understand within 30 seconds:
- current recovery status
- whether half-marathon progress is on track
- whether general health is stable or drifting
- whether CrossFit and running are balanced coherently
- what to do today
- why that is the right choice

---

## In scope for V1

### 1. Data ingestion and normalization
V1 must support importing and normalizing the following data sources into a common warehouse:
- Garmin data
- Apple Health data
- Strava data
- connected scale data or exported weight history
- manual inputs such as pain, soreness, mood, illness, motivation
- at least one year of historical archive if available

Initial ingestion can be file-based or export-based rather than real-time sync.

### 2. Warehouse foundation
V1 must implement:
- daily fact table
- workout fact table
- baseline tables for rolling history and historical comparison
- source lineage and coverage flags
- curated and raw layers where possible

### 3. Deterministic feature layer
V1 must compute:
- 7-day rolling averages
- 28-day baseline deviations
- 90-day health baselines where relevant
- recent load summaries
- sleep debt
- body-weight slope
- recovery trend
- simple training balance features
- CrossFit lower-body and intensity tags where available

### 4. Deterministic scoring engine
V1 must compute these four headline scores daily:
- Recovery score
- Race-readiness score
- General-health score
- Load-balance score

All scores must be:
- deterministic
- interpretable
- decomposable into subcomponents
- testable

### 5. Recommendation engine
V1 must convert scores and context into one recommendation mode:
- full go
- train as planned
- train but reduce intensity
- recovery-focused
- full rest
- injury-watch

And one recommended action such as:
- easy run
- quality run only
- long run
- CrossFit only
- CrossFit plus easy run
- mobility walk
- full rest

Recommendation output must include reason codes.

### 6. User interface surfaces
V1 must include these product surfaces:
- Today page
- Running page
- Health page
- Strength / CrossFit page
- Weekly review page

The Today page is the primary surface and the most important one for launch.

### 7. LLM explanation layer
The LLM layer in V1 must:
- receive structured context only
- explain the recommendation and current status
- produce a short daily briefing
- produce a weekly review summary
- answer basic grounded questions using the computed metrics and rule outputs

The LLM must not invent scores or unsupported causal claims.

### 8. Feedback loop
V1 should support basic user feedback on recommendation quality, such as:
- good recommendation
- too hard
- too easy
- ignored
- pain increased
- felt accurate

This can be stored for later tuning rather than immediately adapting the plan.

---

## Explicitly out of scope for V1
These items are intentionally deferred:
- automatic adaptive training-plan rewriting
- fully automated live sync for every source from day one
- advanced anomaly narratives beyond basic flags
- sophisticated injury-risk modeling
- travel mode, illness mode, and calendar-aware scheduling
- calorie-deficit modeling and advanced nutrition logic
- push notifications
- mobile-native app packaging
- App Store launch work
- multi-user support
- social features
- coaching marketplace features

---

## Product principles for V1
- Decision-first, not dashboard-first
- Personal baselines over generic norms
- Explainability over black-box scoring
- Health guardrails over single-goal obsession
- CrossFit and running modeled as one system
- Trend interpretation over point estimates

---

## Acceptance criteria for V1
V1 is considered successful if:
- one-click daily briefing exists and is understandable
- the user can see a recommendation and the reasons behind it
- historical baselines are visible and used in scoring
- at least one year of prior data can be ingested and queried
- weekly review can summarize what improved, what worsened, and what to change next week
- the recommendation engine is inspectable and deterministic
- the LLM explanation is grounded in structured context

---

## Suggested implementation order
1. Warehouse foundation
2. Feature layer
3. Score engine
4. Recommendation engine
5. Today page
6. Trend pages
7. Weekly review
8. LLM explanation layer
9. Data-source refinement and tuning

---

## First milestone
The first real milestone is:

**Given seeded historical data, the app computes scores, produces a daily recommendation, and renders a Today screen with a grounded explanation on localhost.**
