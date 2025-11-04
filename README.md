# Kitchen Scheduling System

Web-based platform that generates, manages, and visualizes monthly work schedules for a professional kitchen brigade. The solution is split into a FastAPI backend and a React/Vite frontend designed from the provided functional, data, and rules specifications.

## Structure

- `app/backend` – FastAPI service with SQLAlchemy models, REST endpoints, and scheduling service stubs.
- `app/frontend` – React (Vite + TypeScript) single-page application with Material UI and i18n support.
- `Scheduling Requirements` – Original JSON requirement files supplied by the stakeholder (kept for reference).

## Development Environment

### Backend

```bash
cd app/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
alembic -c alembic.ini upgrade head
uvicorn kitchen_scheduler.main:app --reload
```

Run tests with `python -m pytest`. To exercise the API against Postgres locally, bring up the container at `app/backend/tests/docker-compose.yml` and set `TEST_DATABASE_URL` before running the suite.

### Frontend

```bash
cd app/frontend
npm install
npm run dev
```

Visit `http://localhost:5173` for the UI (proxied to backend at `http://127.0.0.1:8000`).

## Current Capabilities

- CRUD-ready REST scaffolding for resources, shifts, and planning endpoints.
- Configurable application settings via environment variables (`app/backend/.env.example`).
- Stub scheduling service that returns deterministic plans for integration testing.
- Basic frontend layout with monthly grid visualization, hours summary, and violation placeholder.
- English/French localization dictionaries with runtime toggle.

## Planned Enhancements

1. Harden persistence with repository integration tests and data validation layers.
2. Replace the stub scheduler with rule-aware optimization (e.g., OR-Tools) and constraint reporting.
3. Implement authentication with JWT tokens and role-based route guarding.
4. Expand frontend interactions (manual adjustments, scenario comparisons, exports).
5. Add automated tests (backend unit/integration, frontend component tests) and CI workflows.

Refer to the README files inside `app/backend` and `app/frontend` for deeper details and next steps within each subsystem.
