# Kitchen Scheduling Project Roadmap & Test Guide

This roadmap breaks the stakeholder requirements into executable milestones and outlines how to verify each increment. Work through the milestones in order; every milestone should finish in a working, demoable state before moving on.

## Milestone 0 – Developer Environment & CI
- Install Python 3.11+, Node 18+, and Docker (for DB and integration tests).
- Create virtualenv inside `app/backend`, install dependencies via `pip install -e .[dev]`.
- Install frontend packages in `app/frontend` with `npm install`.
- Add pre-commit hooks or `ruff`/`black`/`mypy` scripts; configure CI (GitHub Actions) to run lint + tests + type checks on every push.

## Milestone 1 – Persistence Foundation
- Introduce Alembic migrations to create tables for resources, shifts, planning entries, monthly parameters, and scenarios.
- Seed baseline master data (default shifts, roles, demo users) via migrations or fixtures.
- Flesh out repository methods (`list/create/update/delete`) for resources, shifts, scenarios; ensure all endpoints return Pydantic models.
- Add async integration tests that spin up a transient Postgres (Docker) and exercise the repositories + API routes.

## Milestone 2 – Rule-Aware Scheduling Engine
- Translate rule JSON into structured models/services (work-time limits, composition requirements, vacation caps).
- Replace the stub `generate_stub_schedule` with an algorithm that enforces hard constraints and reports soft violations.
- Expose planning endpoints to trigger schedule generation, return violation reports, and version schedules.
- Cover the scheduling logic with unit tests (rule satisfaction, violation reporting) plus end-to-end API tests on representative datasets.

## Milestone 3 – Planner UI Enhancements
- Implement authentication guard (JWT storage, role-based routing) and secure API requests.
- Expand the monthly grid for interactive editing (drag/drop, context menu, shift palette) using state from `scheduleStore`.
- Surface scenario comparison, summary calculations, and violation panels based on backend responses.
- Localize all new UI strings in `src/locales/en.json` and `fr.json`; add UI tests (React Testing Library) for critical components.

## Milestone 4 – Releases & Operations
- Add export endpoints (PDF/Excel) and link them to the UI.
- Implement publication workflow (deadline enforcement, version tracking, audit metadata).
- Wire observability (structured logging, fastapi health endpoints, uptime alerts).
- Finalize deployment manifests for Fly.io (Dockerfile, fly.toml, secrets) and document operational runbooks.

---

## Testing Playbook

### Backend
- `pytest`: run unit/integration suites; configure `pytest-asyncio` for async tests.
- `ruff check` / `mypy`: maintain code quality and typing guarantees.
- Integration tests: use `docker compose -f app/backend/tests/docker-compose.yml up -d` (to be added) to start Postgres, then run API tests against the real database.

### Frontend
- `npm run lint` (ESLint) and `npm run typecheck` (TypeScript) for static analysis.
- `npm run test` with Vitest + React Testing Library for component logic.
- End-to-end: adopt Playwright or Cypress to script planner flows (login → load schedule → adjust shift → save).

### Full-Stack & Manual Verification
- Start backend (`uvicorn kitchen_scheduler.main:app --reload`) and frontend (`npm run dev`).
- Use seeded credentials (`planner / planner` until real users exist) to walk through core scenarios:
  1. Create resources/shifts via API or UI.
  2. Generate a schedule for a sample month.
  3. Inspect violation reports and summaries.
  4. Publish a plan and verify version history.
- Capture findings in QA checklists so regressions surface early.

Keep this document up to date as milestones evolve; link tasks to tracker tickets for visibility.
