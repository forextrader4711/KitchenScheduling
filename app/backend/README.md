# Kitchen Scheduling Backend

FastAPI service that exposes scheduling, resource, and configuration APIs for the professional kitchen planning system.

## Quickstart

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
uvicorn kitchen_scheduler.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. Interactive documentation: `http://127.0.0.1:8000/docs`.

Copy `.env.example` to `.env` (or export the variables another way) before starting the server so the configuration points to the right database.

## Structure

- `src/kitchen_scheduler/core` – runtime configuration and security utilities.
- `src/kitchen_scheduler/db` – SQLAlchemy models and session management.
- `src/kitchen_scheduler/api/routes` – REST endpoints for auth, resources, shifts, and planning.
- `src/kitchen_scheduler/services` – scheduling and validation domain services.
- `src/kitchen_scheduler/schemas` – Pydantic request/response models.

## Database Migrations

### Start a local PostgreSQL instance

If you don't already have PostgreSQL running, a Docker Compose file (`docker-compose.yml`) is provided. From `app/backend`:

```bash
docker compose up -d db
```

The container exposes port `5432` with default credentials (`scheduler` / `scheduler`) and database `kitchen_scheduler`. Update `.env` if you change these defaults.

### Apply and manage migrations

Alembic is configured for the async SQLAlchemy stack. Typical workflow:

```bash
# ensure environment variables (e.g., KITCHEN_DATABASE_URL) are set
alembic -c alembic.ini upgrade head        # apply migrations
alembic -c alembic.ini revision --autogenerate -m "your change"  # create new migration
alembic -c alembic.ini downgrade -1        # rollback last migration
```

Run migrations before starting the API locally or in CI.

### Seed Demo Data

A lightweight async seed script is available to populate shifts, resources, and monthly parameters for local development:

```bash
python scripts/seed_demo.py
```

The script is idempotent; rerunning it skips rows that already exist.

## Next Steps

- Implement real user persistence and role-based authorization.
- Add integration tests that cover repositories and API routes against a transient PostgreSQL instance.
- Replace the stub scheduling algorithm with rule-aware optimization.
- Extend validation endpoints to surface constraint violations to the frontend.

## Tests

```bash
# Quick checks (SQLite)
scripts/lint.sh
scripts/run_tests.sh

# Default (SQLite in-memory)
python -m pytest

# Postgres-backed integration
docker compose -f tests/docker-compose.yml up -d db
export TEST_DATABASE_URL="postgresql+asyncpg://scheduler:scheduler@localhost:5433/kitchen_scheduler_test"
python -m pytest
docker compose -f tests/docker-compose.yml down
```
