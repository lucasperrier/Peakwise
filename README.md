# Peakwise

A personal daily decision system for hybrid athletes. It answers one question each morning:

**What should I do today, and why?**

Peakwise ingests data from Garmin, Apple Health, Strava, a connected scale, and manual inputs, normalizes it into a common warehouse, computes deterministic scores, and produces a grounded daily recommendation with an LLM explanation layer.

## Core scores

| Score | Purpose |
|---|---|
| Recovery | Readiness to absorb training today |
| Race-readiness | Progression toward the half-marathon target |
| General health | Long-term wellbeing beyond performance |
| Load balance | CrossFit and running coherence |

## Design principles

- Decision-first, not dashboard-first
- Personal baselines over generic norms
- Explainability over black-box scoring
- Health guardrails over single-goal obsession
- CrossFit and running modeled as one system

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Alembic
- **Database**: PostgreSQL
- **Testing**: pytest
- **Linting**: Ruff
- **Frontend**: Next.js with TypeScript
- **LLM**: OpenAI-compatible API

See [docs/stack_decision.md](docs/stack_decision.md) for rationale.

## Project structure

```
backend/           Python backend (FastAPI + scoring engine)
  src/peakwise/    Application source
  tests/           Test suite
frontend/          Next.js frontend
docs/              Design documents and specifications
```

## Getting started

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
pytest

# Frontend
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env` and fill in the required values before running.

## Documentation

- [Bedrock specification](docs/bedrock_spec.md)
- [V1 scope](docs/v1_scope.md)
- [Data model](docs/data_model.md)
- [Scoring](docs/scoring.md)
- [Stack decision](docs/stack_decision.md)
- [Conventions](docs/conventions.md)
- [Task list](TASKS.md)
