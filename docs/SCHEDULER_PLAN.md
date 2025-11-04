# Scheduler Implementation Plan

This document captures how the rule-aware planner will evolve from the current
stub into a production-ready service.

## Rule Modelling

- Represent rules with typed models (`SchedulingRules`, `WorkingTimeRules`,
  `ShiftRules`, `VacationRules`). The default JSON in
  `kitchen_scheduler/services/data/default_rules.json` seeds the structure.
- Persist rule versions in the database later so planners can adjust
  constraints per month while keeping historical context.
- Provide an admin API to read/update rules; until then `load_default_rules()`
  serves as the source of truth.

## Algorithm Roadmap

1. **Preprocessing**
   - Expand monthly calendar days, annotate public holidays and weekends.
   - Fetch resource availability (vacations, requested rest days, percent of
     contract hours).
   - Generate feasible shift options per role (respecting prime shift
     eligibility).

2. **Core Optimisation Loop**
   - Formulate a constraint model (initially MILP with OR-Tools or PuLP).
   - Hard constraints: staffing composition, max hours, consecutive day limits,
     max concurrent vacations.
   - Soft constraints (e.g., desired rest days) expressed as penalty weights.
   - Objective function favours balanced workloads and minimal violations.

3. **Post-processing**
   - Compute per-resource summaries (worked hours vs contract).
   - Detect violations that remain (carry as structured messages for the UI).
   - Generate scenario metadata (status, version bump, audit trail).

## Integration Steps

- Replace `generate_stub_schedule()` with orchestrator that loads rules,
  executes optimisation, and returns both plan entries and violation messages.
- Extend API to return `violations` and `summary` payloads; update frontend
  store/components to display them.
- Add scenario persistence so generated plans are stored and can be published or
  iterated.
- Introduce regression tests covering representative rule sets and edge cases
  (e.g., insufficient staff available, conflicting rules).

## Tooling & Observability

- Keep solver execution behind a service boundary that records run metadata
  (input snapshot, runtime, violations, solver status).
- Log solver diagnostics and expose via `/api/system` endpoints for support.
- Consider feature flags or configuration toggles to fall back to the stub
  algorithm if the optimiser fails.
