# Stack Decision

## Backend: Python 3.12 + FastAPI

**Why Python:**
- Natural fit for data processing, rolling averages, baseline computations, and feature engineering
- Strong ecosystem for numerical work (pandas, numpy) needed by the scoring engine
- Best LLM integration libraries (openai, litellm)
- FastAPI provides async, typed endpoints with automatic OpenAPI docs

**Why not Node/TypeScript for backend:**
- The core value is in data transformation and scoring logic, not in request handling
- Python is more ergonomic for the heavy numerical feature engineering this project requires

## Database: PostgreSQL

- Robust support for analytical queries (window functions, CTEs) needed for rolling baselines
- JSON columns for flexible fields (splits, time-in-zones, weather)
- Proven reliability for time-series-like daily data
- Excellent tooling with SQLAlchemy and Alembic for migrations

## ORM and migrations: SQLAlchemy 2.x + Alembic

- SQLAlchemy 2.x with mapped classes for type safety
- Alembic for versioned, reviewable migrations
- Good fit for the multi-layer schema (raw → curated → features)

## Testing: pytest

- Standard Python testing framework
- Good fixture support for database seeding and teardown
- Pairs well with factory patterns for generating test warehouse data

## Linting and formatting: Ruff

- Single tool replaces flake8, isort, black, and many other linters
- Fast, written in Rust
- Configured via `pyproject.toml`, no extra config files

## Frontend: Next.js + TypeScript

- React ecosystem for building the dashboard pages (Today, Running, Health, Strength, Weekly review)
- TypeScript for typed API response handling
- Server components can call the backend directly
- Good charting library support (recharts, nivo) for trend visualizations

## LLM integration: OpenAI-compatible API

- Start with OpenAI API (GPT-4o or similar)
- Use a thin abstraction so the provider can be swapped later
- Structured context in, natural language out — no agent framework needed for V1

## Development environment

- Python 3.12 (available on system)
- Node 22 (available on system)
- PostgreSQL (local via Docker or system install)
- Ruff for linting/formatting
- pytest for testing
- `.env` for secrets and configuration
