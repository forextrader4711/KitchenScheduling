import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.models.resource import Resource
from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import planning as planning_repo
from kitchen_scheduler.repositories import resource as resource_repo
from kitchen_scheduler.repositories import shift as shift_repo
from kitchen_scheduler.repositories import system as system_repo
from kitchen_scheduler.schemas.planning import (
    PlanGenerationRequest,
    PlanGenerationResponse,
    PlanInsightItem,
    PlanInsights,
    PlanOverviewResponse,
    PlanPhaseRead,
    PlanSummaryItem,
    PlanScenarioCreate,
    PlanScenarioRead,
    PlanScenarioSummary,
    PlanScenarioUpdate,
    PlanSuggestedChange,
    PlanSuggestion,
    PlanVersionRead,
    PlanViolation,
    RuleStatus,
)
from kitchen_scheduler.schemas.resource import PlanningEntryRead
from kitchen_scheduler.services.rules import RuleSet, SchedulingRules, load_default_rules
from kitchen_scheduler.services.scheduler import (
    AbsenceWindow,
    AvailabilityWindow,
    SchedulingContext,
    SchedulingResource,
    SchedulingShift,
    SchedulingViolation,
    evaluate_rule_violations,
    generate_rule_compliant_schedule,
)
from kitchen_scheduler.services.scheduler_optimizer import generate_optimised_schedule
from kitchen_scheduler.services.holidays import get_vaud_public_holidays

ROLE_PRIORITY = {
    "cook": 0,
    "relief_cook": 1,
    "kitchen_assistant": 2,
    "pot_washer": 3,
    "apprentice": 4,
}

STANDARD_WORKDAY_HOURS = 8.3
REAL_WORKDAY_HOURS = 8.5

router = APIRouter()

_SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}

_RULE_STATUS_DEFINITIONS = [
    {
        "code": "max-hours-per-week",
        "translation_key": "planning.ruleStatus.maxHoursPerWeek",
        "violation_codes": {"hours-per-week-exceeded"},
    },
    {
        "code": "max-days-per-week",
        "translation_key": "planning.ruleStatus.maxWorkingDaysPerWeek",
        "violation_codes": {"days-per-week-exceeded"},
    },
    {
        "code": "max-consecutive-days",
        "translation_key": "planning.ruleStatus.maxConsecutiveDays",
        "violation_codes": {"consecutive-days-exceeded"},
    },
    {
        "code": "consecutive-rest-days",
        "translation_key": "planning.ruleStatus.consecutiveRestDays",
        "violation_codes": {"insufficient-consecutive-rest"},
    },
    {
        "code": "minimum-daily-staff",
        "translation_key": "planning.ruleStatus.minimumDailyStaff",
        "violation_codes": {"staffing-shortfall"},
    },
    {
        "code": "role-minimums",
        "translation_key": "planning.ruleStatus.roleMinimums",
        "violation_codes": {"role-min-shortfall"},
    },
    {
        "code": "role-maximums",
        "translation_key": "planning.ruleStatus.roleMaximums",
        "violation_codes": {"role-max-exceeded"},
    },
]


def _month_bounds(month: str) -> tuple[date, date]:
    year_str, month_str = month.split("-")
    year = int(year_str)
    month_num = int(month_str)
    start = date(year, month_num, 1)
    last = calendar.monthrange(year, month_num)[1]
    end = date(year, month_num, last)
    return start, end


def _working_day_dates(month: str) -> list[date]:
    start, end = _month_bounds(month)
    holidays = {holiday.date for holiday in get_vaud_public_holidays(start.year) if start <= holiday.date <= end}
    working_days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holidays:
            working_days.append(current)
        current += timedelta(days=1)
    return working_days


def _holiday_dates(month: str) -> list[date]:
    start, end = _month_bounds(month)
    return [
        holiday.date
        for holiday in get_vaud_public_holidays(start.year)
        if start <= holiday.date <= end
    ]


def _vacation_days_for_resource(resource: Resource, working_days: set[date], month: str) -> int:
    start, end = _month_bounds(month)
    count = 0
    for absence in resource.absences or []:
        if absence.absence_type != "vacation":
            continue
        current = max(absence.start_date, start)
        last = min(absence.end_date, end)
        while current <= last:
            if current in working_days:
                count += 1
            current += timedelta(days=1)
    return count


def _role_key(resource: Resource) -> str:
    role = resource.role
    if hasattr(role, "value"):
        return str(role.value)
    return str(role)


def _calculate_plan_summaries(
    month: str,
    entries: list[PlanningEntryRead],
    resources: dict[int, Resource],
    shift_hours: dict[int, float],
    opening_balances: dict[int, float],
) -> tuple[list[PlanSummaryItem], dict[int, tuple[float, float]]]:
    working_day_list = _working_day_dates(month)
    working_day_set = set(working_day_list)
    working_day_count = len(working_day_list)
    actual_hours_map: dict[int, float] = defaultdict(float)
    for entry in entries:
        if entry.shift_code is not None:
            actual_hours_map[entry.resource_id] += float(shift_hours.get(entry.shift_code, 0.0))
        elif entry.absence_type == "sick_leave":
            actual_hours_map[entry.resource_id] += STANDARD_WORKDAY_HOURS

    vacation_days_map: dict[int, int] = {}
    for resource_id, resource in resources.items():
        vacation_days = _vacation_days_for_resource(resource, working_day_set, month)
        vacation_days_map[resource_id] = vacation_days
        if vacation_days:
            actual_hours_map[resource_id] -= vacation_days * STANDARD_WORKDAY_HOURS

    closing_updates: dict[int, tuple[float, float]] = {}
    summaries: list[PlanSummaryItem] = []
    for resource_id, resource in resources.items():
        actual_hours = round(actual_hours_map.get(resource_id, 0.0), 2)
        opening_hours = round(opening_balances.get(resource_id, 0.0), 2)
        availability_percent = getattr(resource, "availability_percent", 100) or 100
        availability_factor = max(availability_percent, 0) / 100.0
        due_hours = round(working_day_count * STANDARD_WORKDAY_HOURS * availability_factor, 2)
        due_real_hours = round(working_day_count * REAL_WORKDAY_HOURS * availability_factor, 2)
        closing_hours = round(opening_hours + actual_hours - due_hours, 2)
        summaries.append(
            PlanSummaryItem(
                resource_id=resource_id,
                resource_name=resource.name,
                actual_hours=actual_hours,
                due_hours=due_hours,
                due_real_hours=due_real_hours,
                opening_balance_hours=opening_hours,
                closing_balance_hours=closing_hours,
                working_days=working_day_count,
                vacation_days=vacation_days_map.get(resource_id, 0),
            )
        )
        closing_updates[resource_id] = (opening_hours, closing_hours)

    summaries.sort(
        key=lambda item: (
            ROLE_PRIORITY.get(_role_key(resources[item.resource_id]), 99),
            resources[item.resource_id].name,
        )
    )
    return summaries, closing_updates


@router.get("/scenarios", response_model=list[PlanScenarioRead])
async def list_scenarios(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> list[PlanScenarioRead]:
    scenarios = await planning_repo.list_scenarios(session)
    return [PlanScenarioRead.model_validate(scenario) for scenario in scenarios]


@router.post("/scenarios", response_model=PlanScenarioRead, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    payload: PlanScenarioCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlanScenarioRead:
    scenario = await planning_repo.create_scenario(session, payload)
    await session.commit()
    return PlanScenarioRead.model_validate(scenario)


@router.put("/scenarios/{scenario_id}", response_model=PlanScenarioRead)
async def update_scenario(
    scenario_id: int,
    payload: PlanScenarioUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlanScenarioRead:
    scenario = await planning_repo.get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    scenario = await planning_repo.update_scenario(session, scenario, payload)
    await session.commit()
    return PlanScenarioRead.model_validate(scenario)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    scenario = await planning_repo.get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    await planning_repo.delete_scenario(session, scenario)
    await session.commit()


@router.get("/scenarios/{scenario_id}/versions", response_model=list[PlanVersionRead])
async def list_versions(
    scenario_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PlanVersionRead]:
    scenario = await planning_repo.get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    versions = await planning_repo.list_versions(session, scenario_id)
    return [PlanVersionRead.model_validate(version) for version in versions]


def _map_violation(v):
    day_value = v.day.isoformat() if isinstance(v.day, date) else v.day
    return PlanViolation(
        code=v.code,
        message=v.message,
        severity=v.severity,
        meta=v.meta,
        scope=v.scope,
        day=day_value,
        resource_id=v.resource_id,
        iso_week=v.iso_week,
    )


def _summarize_optimizer_shortfalls(violations: list[SchedulingViolation]) -> tuple[str | None, dict[str, list[str]]]:
    shortfalls: dict[str, set[str]] = {}
    for violation in violations:
        if violation.code not in {"role-min-shortfall", "staffing-shortfall"}:
            continue
        if violation.day is None:
            continue
        day_key = violation.day.isoformat() if isinstance(violation.day, date) else str(violation.day)
        role_label = (
            str(violation.meta.get("role") or violation.meta.get("rule") or "staffing")
            if violation.code == "role-min-shortfall"
            else "staffing"
        )
        shortfalls.setdefault(day_key, set()).add(role_label)
    if not shortfalls:
        return None, {}
    segments = [f"{day}: {', '.join(sorted(roles))}" for day, roles in sorted(shortfalls.items())]
    message = "Optimizer fallback: insufficient coverage for " + "; ".join(segments)
    return message, {day: sorted(roles) for day, roles in shortfalls.items()}


async def _run_generation(
    session: AsyncSession,
    month: str,
    *,
    label: str | None = None,
    strategy: Literal["heuristic", "optimized"] = "heuristic",
) -> PlanGenerationResponse:
    resources = await resource_repo.list_resources(session)
    shifts = await shift_repo.list_shifts(session)
    working_day_count = len(_working_day_dates(month))
    due_hours = working_day_count * STANDARD_WORKDAY_HOURS

    config = await system_repo.get_active_rule_config(session)
    if config:
        rule_set = RuleSet(rules=SchedulingRules.model_validate(config.rules))
    else:
        rule_set = load_default_rules()

    scheduling_resources = [
        SchedulingResource(
            id=resource.id,
            role=resource.role.value if hasattr(resource.role, "value") else str(resource.role),
            availability=_map_availability_template(resource.availability_template),
            preferred_shift_codes=list(resource.preferred_shift_codes or []),
            undesired_shift_codes=list(resource.undesired_shift_codes or []),
            absences=[
                AbsenceWindow(
                    start_date=absence.start_date,
                    end_date=absence.end_date,
                    absence_type=absence.absence_type,
                    comment=absence.comment,
                )
                for absence in resource.absences
            ],
            target_hours=due_hours if _role_key(resource) != "relief_cook" else None,
            is_relief=_role_key(resource) == "relief_cook",
        )
        for resource in resources
    ]

    scheduling_shifts = [
        SchedulingShift(
            code=shift.code,
            description=shift.description,
            start=shift.start,
            end=shift.end,
            hours=float(shift.hours),
        )
        for shift in shifts
    ]

    context = SchedulingContext(
        month=month,
        resources=scheduling_resources,
        shifts=scheduling_shifts,
        rules=rule_set,
    )
    if strategy == "optimized":
        optimized_result = generate_optimised_schedule(context)
        optimizer_violation = any(violation.code == "optimizer-failed" for violation in optimized_result.violations)
        if optimizer_violation or not optimized_result.entries:
            result = generate_rule_compliant_schedule(context)
            summary, meta = _summarize_optimizer_shortfalls(result.violations)
            if summary:
                result.violations.append(
                    SchedulingViolation(
                        code="optimizer-infeasible",
                        message=summary,
                        severity="warning",
                        scope="schedule",
                        meta={"shortfalls": meta},
                    )
                )
        else:
            result = optimized_result
    else:
        result = generate_rule_compliant_schedule(context)
    violations = [_map_violation(v) for v in result.violations]
    response = PlanGenerationResponse(entries=result.entries, violations=violations)

    scenario = await planning_repo.ensure_scenario(
        session,
        month=month,
        status="draft",
        name="Draft Scenario",
    )
    scenario.status = "draft"
    await planning_repo.store_plan_generation(
        session,
        scenario,
        response,
        version_label=label or ("Optimized" if strategy == "optimized" else None),
    )

    resource_map = {resource.id: resource for resource in resources}
    shift_hours_map = {shift.code: float(shift.hours) for shift in scheduling_shifts}
    opening_balances = await planning_repo.get_opening_balances(session, month)
    _, closing_updates = _calculate_plan_summaries(
        month,
        response.entries,
        resource_map,
        shift_hours_map,
        opening_balances,
    )
    await planning_repo.upsert_monthly_balances(session, month, closing_updates)
    await session.commit()

    return response


@router.post("/generate", response_model=PlanGenerationResponse)
async def generate_plan(
    payload: PlanGenerationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlanGenerationResponse:
    return await _run_generation(session, payload.month, label=payload.label, strategy="heuristic")


@router.post("/generate/optimized", response_model=PlanGenerationResponse)
async def generate_optimized_plan(
    payload: PlanGenerationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlanGenerationResponse:
    return await _run_generation(session, payload.month, label=payload.label, strategy="optimized")


@router.post("/scenarios/{scenario_id}/generate", response_model=PlanGenerationResponse)
async def generate_plan_for_scenario(
    scenario_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlanGenerationResponse:
    scenario = await planning_repo.get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return await _run_generation(session, scenario.month)


@router.get("/overview", response_model=PlanOverviewResponse)
async def get_plan_overview(
    month: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlanOverviewResponse:
    await planning_repo.ensure_scenario(session, month=month, status="draft", name="Draft Scenario")
    await session.commit()

    resources = await resource_repo.list_resources(session)
    resource_lookup = {resource.id: resource for resource in resources}
    shifts = await shift_repo.list_shifts(session)
    shift_hours_map = {shift.code: float(shift.hours) for shift in shifts}
    opening_balances = await planning_repo.get_opening_balances(session, month)
    holiday_dates = [holiday.isoformat() for holiday in _holiday_dates(month)]

    scenarios = await planning_repo.preload_scenarios_for_month(session, month)

    def _merge_item(
        bucket: dict,
        key,
        violation: PlanViolation,
        severity_rank: dict[str, int],
    ) -> None:
        if key is None:
            return
        existing = bucket.get(key)
        if existing:
            if severity_rank[violation.severity] > severity_rank[existing.severity]:
                existing.severity = violation.severity
            existing.violations.append(violation)
        else:
            bucket[key] = PlanInsightItem(severity=violation.severity, violations=[violation])

    def _aggregate_insights(violations: list[PlanViolation]) -> PlanInsights:
        daily: dict[str, PlanInsightItem] = {}
        resource: dict[int, PlanInsightItem] = {}
        weekly: dict[str, PlanInsightItem] = {}

        for violation in violations:
            if violation.day:
                _merge_item(daily, violation.day, violation, _SEVERITY_RANK)
            if violation.resource_id is not None:
                _merge_item(resource, violation.resource_id, violation, _SEVERITY_RANK)
            if violation.iso_week:
                _merge_item(weekly, violation.iso_week, violation, _SEVERITY_RANK)

        if violations:
            severity = max(violations, key=lambda v: _SEVERITY_RANK[v.severity]).severity
            monthly = {"month": PlanInsightItem(severity=severity, violations=list(violations))}
        else:
            monthly = {}

        return PlanInsights(daily=daily, resource=resource, weekly=weekly, monthly=monthly)

    def _build_rule_statuses(violations: list[PlanViolation]) -> list[RuleStatus]:
        statuses: list[RuleStatus] = []
        for config in _RULE_STATUS_DEFINITIONS:
            matched = [violation for violation in violations if violation.code in config["violation_codes"]]
            if matched:
                highest = max(matched, key=lambda v: _SEVERITY_RANK[v.severity]).severity
                status_value = "critical" if highest == "critical" else "warning"
            else:
                status_value = "ok"
            statuses.append(
                RuleStatus(
                    code=config["code"],
                    translation_key=config["translation_key"],
                    status=status_value,
                    violations=matched,
                )
            )
        return statuses

    def _to_phase(
        scenario,
        resource_map: dict[int, Resource],
    ) -> PlanPhaseRead:
        summary = PlanScenarioSummary.model_validate(scenario)
        ordered_entries = sorted(scenario.entries, key=lambda entry: (entry.date, entry.resource_id))
        entries = [PlanningEntryRead.model_validate(entry) for entry in ordered_entries]
        violations = [
            PlanViolation.model_validate(violation) if not isinstance(violation, PlanViolation) else violation
            for violation in scenario.violations or []
        ]
        insights = _aggregate_insights(violations)
        rule_statuses = _build_rule_statuses(violations)
        suggestions = _build_suggestions(violations, entries, resource_map)
        summaries, _ = _calculate_plan_summaries(
            scenario.month,
            entries,
            resource_map,
            shift_hours_map,
            opening_balances,
        )
        return PlanPhaseRead(
            scenario=summary,
            entries=entries,
            violations=violations,
            insights=insights,
            rule_statuses=rule_statuses,
            suggestions=suggestions,
            summaries=summaries,
        )

    preparation = None
    approved = None
    for scenario in scenarios:
        if scenario.status == "approved":
            approved = _to_phase(scenario, resource_lookup)
        else:
            # Treat everything else as preparation phase for now (draft, ready, etc.)
            if preparation is None:
                preparation = _to_phase(scenario, resource_lookup)

    return PlanOverviewResponse(month=month, preparation=preparation, approved=approved, holidays=holiday_dates)


def _build_suggestions(
    violations: list[PlanViolation],
    entries: list[PlanningEntryRead],
    resources: dict[int, Resource],
) -> list[PlanSuggestion]:
    if not violations:
        return []

    assignments_by_day: dict[str, set[int]] = defaultdict(set)
    absence_entries: set[tuple[str, int]] = set()

    for entry in entries:
        entry_date = entry.date.isoformat() if isinstance(entry.date, date) else str(entry.date)
        if entry.shift_code is not None:
            assignments_by_day[entry_date].add(entry.resource_id)
        if entry.absence_type:
            absence_entries.add((entry_date, entry.resource_id))

    resources_by_role: dict[str, list[Resource]] = defaultdict(list)
    for resource in resources.values():
        role_value = resource.role.value if hasattr(resource.role, "value") else str(resource.role)
        resources_by_role[role_value].append(resource)

    suggestions: list[PlanSuggestion] = []

    def _entries_for_resource(resource_id: int) -> list[PlanningEntryRead]:
        return sorted(
            [
                entry
                for entry in entries
                if entry.resource_id == resource_id and entry.shift_code is not None
            ],
            key=lambda record: record.date,
        )

    def _parse_week(week_value: str | None) -> tuple[int, int] | None:
        if not week_value:
            return None
        try:
            year_str, week_str = week_value.split("-W")
            return int(year_str), int(week_str)
        except ValueError:
            return None

    def _candidate_for_role(role_key: str, iso_date: str) -> Resource | None:
        target_role = _resolve_role(role_key)
        candidate_pool = resources_by_role.get(target_role, [])
        if not candidate_pool:
            return None
        target_day = date.fromisoformat(iso_date)
        for resource in sorted(candidate_pool, key=lambda r: r.id):
            if resource.id in assignments_by_day.get(iso_date, set()):
                continue
            if (iso_date, resource.id) in absence_entries:
                continue
            if _resource_has_absence(resource, target_day):
                continue
            if not _resource_is_available(resource, target_day):
                continue
            return resource
        return None

    for index, violation in enumerate(violations):
        meta = violation.meta or {}
        suggestion_id = f"{violation.code}-{index}"

        if violation.code == "role-min-shortfall":
            iso_date = meta.get("date")
            if not iso_date:
                continue
            role_key = meta.get("role")
            if not role_key:
                continue
            candidate = _candidate_for_role(role_key, iso_date)
            if candidate:
                preferred_shift = (candidate.preferred_shift_codes or [None])[0]
                shift_code = preferred_shift if preferred_shift is not None else 1
                role_value = candidate.role.value if hasattr(candidate.role, "value") else str(candidate.role)
                suggestions.append(
                    PlanSuggestion(
                        id=suggestion_id,
                        type="assign-role-shortfall",
                        title=f"Assign {candidate.name}",
                        description=(
                            f"Assign {candidate.name} ({role_value}) to cover the {role_key} shortfall on {iso_date}."
                        ),
                        severity=violation.severity,
                        related_violation=violation.code,
                        change=PlanSuggestedChange(
                            action="assign_shift",
                            resource_id=candidate.id,
                            date=iso_date,
                            shift_code=shift_code,
                        ),
                        metadata={
                            "role": role_key,
                            "date": iso_date,
                            "resource_name": candidate.name,
                            "suggested_shift": shift_code,
                        },
                    )
                )
            else:
                suggestions.append(
                    PlanSuggestion(
                        id=suggestion_id,
                        type="role-min-shortfall",
                        title=f"Resolve {role_key} shortfall",
                        description=(
                            f"No available {role_key} found for {iso_date}. Adjust other assignments or review availability."
                        ),
                        severity=violation.severity,
                        related_violation=violation.code,
                        metadata={"role": role_key, "date": iso_date},
                    )
                )
        elif violation.code == "staffing-shortfall":
            iso_date = meta.get("date")
            if not iso_date:
                continue
            candidate = None
            target_day = date.fromisoformat(iso_date)
            for resource in sorted(resources.values(), key=lambda r: r.id):
                role_value = resource.role.value if hasattr(resource.role, "value") else str(resource.role)
                if role_value == "apprentice":
                    continue
                if resource.id in assignments_by_day.get(iso_date, set()):
                    continue
                if (iso_date, resource.id) in absence_entries:
                    continue
                if _resource_has_absence(resource, target_day):
                    continue
                if not _resource_is_available(resource, target_day):
                    continue
                candidate = resource
                break
            if candidate:
                preferred_shift = (candidate.preferred_shift_codes or [None])[0]
                shift_code = preferred_shift if preferred_shift is not None else 1
                suggestions.append(
                    PlanSuggestion(
                        id=suggestion_id,
                        type="assign-staffing-shortfall",
                        title=f"Add {candidate.name}",
                        description=f"Assign {candidate.name} to cover the staffing shortfall on {iso_date}.",
                        severity=violation.severity,
                        related_violation=violation.code,
                        change=PlanSuggestedChange(
                            action="assign_shift",
                            resource_id=candidate.id,
                            date=iso_date,
                            shift_code=shift_code,
                        ),
                        metadata={
                            "date": iso_date,
                            "resource_name": candidate.name,
                            "suggested_shift": shift_code,
                        },
                    )
                )
            else:
                suggestions.append(
                    PlanSuggestion(
                        id=suggestion_id,
                        type="staffing-shortfall",
                        title="Review staffing gap",
                        description=(
                            f"No available resource found to cover staffing shortfall on {iso_date}. "
                            "Consider adjusting assignments or availability."
                        ),
                        severity=violation.severity,
                        related_violation=violation.code,
                        metadata={"date": iso_date},
                    )
                )
        elif violation.code in {"hours-per-week-exceeded", "days-per-week-exceeded"}:
            resource_id = meta.get("resource_id") or violation.resource_id
            week_key = meta.get("week") or violation.iso_week
            week_parsed = _parse_week(week_key)
            if not resource_id or not week_parsed:
                continue
            year, week_number = week_parsed
            affected_entries = [
                entry
                for entry in entries
                if entry.resource_id == resource_id
                and entry.shift_code is not None
                and entry.date.isocalendar()[:2] == (year, week_number)
            ]
            if not affected_entries:
                continue
            entry_to_adjust = max(affected_entries, key=lambda record: record.date)
            resource_obj = resources.get(resource_id)
            if not resource_obj:
                continue
            suggestions.append(
                PlanSuggestion(
                    id=suggestion_id,
                    type=violation.code,
                    title=f"Reduce load for {resource_obj.name}",
                    description=(
                        f"Remove the assignment on {entry_to_adjust.date.isoformat()} to help {resource_obj.name}"
                        f" meet weekly limits."
                    ),
                    severity=violation.severity,
                    related_violation=violation.code,
                    change=PlanSuggestedChange(
                        action="remove_assignment",
                        resource_id=resource_obj.id,
                        date=entry_to_adjust.date.isoformat(),
                    ),
                    metadata={
                        "date": entry_to_adjust.date.isoformat(),
                        "resource_name": resource_obj.name,
                        "week": week_key,
                    },
                )
            )
        elif violation.code == "consecutive-days-exceeded":
            resource_id = meta.get("resource_id") or violation.resource_id
            if not resource_id:
                continue
            resource_entries = _entries_for_resource(resource_id)
            if not resource_entries:
                continue
            entry_to_adjust = resource_entries[-1]
            resource_obj = resources.get(resource_id)
            if not resource_obj:
                continue
            suggestions.append(
                PlanSuggestion(
                    id=suggestion_id,
                    type="consecutive-days-exceeded",
                    title=f"Insert rest day for {resource_obj.name}",
                    description=(
                        f"Add a rest day on {entry_to_adjust.date.isoformat()} to break the consecutive streak."
                    ),
                    severity=violation.severity,
                    related_violation=violation.code,
                    change=PlanSuggestedChange(
                        action="set_rest_day",
                        resource_id=resource_obj.id,
                        date=entry_to_adjust.date.isoformat(),
                        absence_type="rest_day",
                    ),
                    metadata={
                        "date": entry_to_adjust.date.isoformat(),
                        "resource_name": resource_obj.name,
                    },
                )
            )
        elif violation.code == "insufficient-consecutive-rest":
            resource_id = meta.get("resource_id") or violation.resource_id
            if not resource_id:
                continue
            resource_entries = _entries_for_resource(resource_id)
            if not resource_entries:
                continue
            entry_to_adjust = resource_entries[-1]
            resource_obj = resources.get(resource_id)
            if not resource_obj:
                continue
            suggestions.append(
                PlanSuggestion(
                    id=suggestion_id,
                    type="insufficient-consecutive-rest",
                    title=f"Give {resource_obj.name} additional rest",
                    description=(
                        f"Schedule {resource_obj.name} off on {entry_to_adjust.date.isoformat()} to add a rest pair."
                    ),
                    severity=violation.severity,
                    related_violation=violation.code,
                    change=PlanSuggestedChange(
                        action="set_rest_day",
                        resource_id=resource_obj.id,
                        date=entry_to_adjust.date.isoformat(),
                        absence_type="rest_day",
                    ),
                    metadata={
                        "date": entry_to_adjust.date.isoformat(),
                        "resource_name": resource_obj.name,
                    },
                )
            )

    return suggestions


_ROLE_RESOLVE_MAP = {
    "pot_washers": "pot_washer",
    "kitchen_assistants": "kitchen_assistant",
    "apprentices": "apprentice",
    "cooks": "cook",
    "relief_cooks": "relief_cook",
}


def _resolve_role(role_key: str) -> str:
    return _ROLE_RESOLVE_MAP.get(role_key, role_key.rstrip("s"))


def _resource_is_available(resource: Resource, target_date: date) -> bool:
    template = resource.availability_template or []
    weekday = target_date.strftime("%A").lower()
    for window in template:
        if window.get("day") == weekday:
            return bool(window.get("is_available", True))
    return True


def _resource_has_absence(resource: Resource, target_date: date) -> str | None:
    for absence in resource.absences or []:
        if absence.start_date <= target_date <= absence.end_date:
            return absence.absence_type
    return None


class ApplySuggestionPayload(BaseModel):
    change: PlanSuggestedChange
    label: str | None = None


@router.post("/scenarios/{scenario_id}/apply-suggestion", response_model=PlanGenerationResponse)
async def apply_suggestion_to_scenario(
    scenario_id: int,
    payload: ApplySuggestionPayload,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlanGenerationResponse:
    scenario = await planning_repo.get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    await session.refresh(scenario, attribute_names=["entries"])

    change = payload.change
    try:
        target_date = date.fromisoformat(change.date)
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format") from exc

    resources = await resource_repo.list_resources(session)
    resource_lookup = {resource.id: resource for resource in resources}
    if change.resource_id not in resource_lookup:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown resource")

    entries_data: list[dict[str, Any]] = []
    for entry in scenario.entries:
        entries_data.append(
            {
                "resource_id": entry.resource_id,
                "date": entry.date if isinstance(entry.date, date) else date.fromisoformat(str(entry.date)),
                "shift_code": entry.shift_code,
                "absence_type": entry.absence_type,
                "comment": entry.comment,
            }
        )

    existing_index = next(
        (idx for idx, item in enumerate(entries_data) if item["resource_id"] == change.resource_id and item["date"] == target_date),
        None,
    )

    if change.action == "assign_shift":
        if change.shift_code is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="shift_code is required for assign_shift")
        entry_payload = {
            "resource_id": change.resource_id,
            "date": target_date,
            "shift_code": change.shift_code,
            "absence_type": None,
            "comment": "APPLIED-SUGGESTION",
        }
        if existing_index is not None:
            entries_data[existing_index] = entry_payload
        else:
            entries_data.append(entry_payload)
    elif change.action == "set_rest_day":
        entry_payload = {
            "resource_id": change.resource_id,
            "date": target_date,
            "shift_code": None,
            "absence_type": change.absence_type or "rest_day",
            "comment": "APPLIED-SUGGESTION",
        }
        if existing_index is not None:
            entries_data[existing_index] = entry_payload
        else:
            entries_data.append(entry_payload)
    elif change.action == "remove_assignment":
        if existing_index is not None:
            entries_data.pop(existing_index)
    else:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported action")

    sorted_entries = sorted(entries_data, key=lambda item: (item["date"], item["resource_id"]))
    planning_entries: list[PlanningEntryRead] = []
    for idx, item in enumerate(sorted_entries, start=1):
        planning_entries.append(
            PlanningEntryRead(
                id=idx,
                resource_id=item["resource_id"],
                date=item["date"],
                shift_code=item["shift_code"],
                absence_type=item["absence_type"],
                comment=item["comment"],
            )
        )

    shifts = await shift_repo.list_shifts(session)
    rule_config = await system_repo.get_active_rule_config(session)
    if rule_config:
        rule_set = RuleSet(rules=SchedulingRules.model_validate(rule_config.rules))
    else:
        rule_set = load_default_rules()

    working_day_count = len(_working_day_dates(scenario.month))
    due_hours = working_day_count * STANDARD_WORKDAY_HOURS

    scheduling_resources = [
        SchedulingResource(
            id=res.id,
            role=res.role.value if hasattr(res.role, "value") else str(res.role),
            availability=_map_availability_template(res.availability_template),
            preferred_shift_codes=list(res.preferred_shift_codes or []),
            undesired_shift_codes=list(res.undesired_shift_codes or []),
            absences=[
                AbsenceWindow(
                    start_date=absence.start_date,
                    end_date=absence.end_date,
                    absence_type=absence.absence_type,
                    comment=absence.comment,
                )
                for absence in res.absences or []
            ],
            target_hours=due_hours if _role_key(res) != "relief_cook" else None,
            is_relief=_role_key(res) == "relief_cook",
        )
        for res in resources
    ]

    scheduling_shifts = [
        SchedulingShift(
            code=shift.code,
            description=shift.description,
            start=shift.start,
            end=shift.end,
            hours=float(shift.hours),
        )
        for shift in shifts
    ]

    context = SchedulingContext(
        month=scenario.month,
        resources=scheduling_resources,
        shifts=scheduling_shifts,
        rules=rule_set,
    )
    violations_raw = evaluate_rule_violations(context, planning_entries)
    violations = [_map_violation(v) for v in violations_raw]

    response = PlanGenerationResponse(entries=planning_entries, violations=violations)
    await planning_repo.store_plan_generation(session, scenario, response, version_label=payload.label)
    await session.commit()
    return response


def _map_availability_template(template: Any) -> list[AvailabilityWindow]:
    if not template:
        return []
    windows: list[AvailabilityWindow] = []
    for entry in template:
        if not isinstance(entry, dict):
            continue
        day = entry.get("day")
        if not isinstance(day, str):
            continue
        windows.append(
            AvailabilityWindow(
                day=day,
                is_available=bool(entry.get("is_available", True)),
                start_time=entry.get("start_time"),
                end_time=entry.get("end_time"),
            )
        )
    return windows
