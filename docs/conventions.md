# Coding Conventions

## Python

### Style
- Format and lint with Ruff (configured in `pyproject.toml`)
- Target Python 3.12+
- Use type hints on all function signatures
- Prefer `from __future__ import annotations` for forward references

### Structure
- Application code lives in `backend/src/peakwise/`
- Tests live in `backend/tests/`, mirroring the source structure
- One module per responsibility: `api/`, `ingestion/`, `features/`, `scoring/`, `recommendations/`, `llm/`

### Naming
- snake_case for modules, functions, variables
- PascalCase for classes and SQLAlchemy models
- Constants in UPPER_SNAKE_CASE
- Prefix private helpers with underscore

### Database
- All schema changes go through Alembic migrations — no manual DDL
- Models use SQLAlchemy 2.x mapped-column style
- Table names are snake_case, singular (e.g., `daily_fact`, `workout_fact`)

### Testing
- Every scoring formula and recommendation rule must have tests
- Use pytest fixtures for database sessions and seed data
- Test files named `test_<module>.py`
- Aim for deterministic tests — no reliance on external services

### Configuration
- All thresholds and weights live in config, not scattered in code
- Use Pydantic Settings for environment-based config
- Secrets go in `.env`, never committed

## TypeScript / Frontend

### Style
- ESLint + Prettier (configured in `frontend/`)
- Strict TypeScript — no `any` unless truly unavoidable
- Functional React components with hooks

### Structure
- Pages in `app/` (Next.js app router)
- Shared components in `components/`
- API client types generated from or aligned with backend response schemas

## Agent guardrails

These rules apply to any AI coding agent working on this project:

1. Never invent score formulas outside the documented rules in `docs/scoring.md`
2. Never bypass typed contracts — API responses must match defined schemas
3. Keep business logic out of UI components — components render, services compute
4. All score outputs must expose subcomponents for explainability
5. Preserve source lineage in ingestion — never discard source metadata
6. Keep thresholds in config, not hard-coded in multiple places
7. Add tests for every scoring and recommendation module
8. LLM outputs must be based on structured context only — no raw data hallucination
9. Do not add features, refactor code, or make changes beyond what is asked
10. Do not silently impute missing data — mark gaps explicitly
