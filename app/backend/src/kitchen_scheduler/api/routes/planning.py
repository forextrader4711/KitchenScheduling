from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import planning as planning_repo
from kitchen_scheduler.repositories import resource as resource_repo
from kitchen_scheduler.repositories import shift as shift_repo
from kitchen_scheduler.repositories import system as system_repo
from kitchen_scheduler.schemas.planning import (
    PlanGenerationRequest,
    PlanGenerationResponse,
    PlanScenarioCreate,
    PlanScenarioRead,
    PlanScenarioUpdate,
    PlanVersionRead,
    PlanViolation,
    PlanOverviewResponse,
    PlanPhaseRead,
    PlanScenarioSummary,
    PlanInsights,
    PlanInsightItem,
)
from kitchen_scheduler.services.rules import RuleSet, SchedulingRules, load_default_rules
from kitchen_scheduler.services.scheduler import (
    AbsenceWindow,
    AvailabilityWindow,
    SchedulingContext,
    SchedulingResource,
    SchedulingShift,
    generate_stub_schedule,
)
from kitchen_scheduler.schemas.resource import PlanningEntryRead

router = APIRouter()


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


async def _run_generation(
    session: AsyncSession,
    month: str,
) -> PlanGenerationResponse:
    resources = await resource_repo.list_resources(session)
    shifts = await shift_repo.list_shifts(session)

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
    result = generate_stub_schedule(context)
    violations = [_map_violation(v) for v in result.violations]
    response = PlanGenerationResponse(entries=result.entries, violations=violations)

    scenario = await planning_repo.ensure_scenario(
        session,
        month=month,
        status="draft",
        name="Draft Scenario",
    )
    scenario.status = "draft"
    await planning_repo.store_plan_generation(session, scenario, response)
    await session.commit()

    return response


@router.post("/generate", response_model=PlanGenerationResponse)
async def generate_plan(
    payload: PlanGenerationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlanGenerationResponse:
    return await _run_generation(session, payload.month)


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
        severity_rank = {"info": 0, "warning": 1, "critical": 2}
        daily: dict[str, PlanInsightItem] = {}
        resource: dict[int, PlanInsightItem] = {}
        weekly: dict[str, PlanInsightItem] = {}

        for violation in violations:
            if violation.day:
                _merge_item(daily, violation.day, violation, severity_rank)
            if violation.resource_id is not None:
                _merge_item(resource, violation.resource_id, violation, severity_rank)
            if violation.iso_week:
                _merge_item(weekly, violation.iso_week, violation, severity_rank)

        if violations:
            severity = max(violations, key=lambda v: severity_rank[v.severity]).severity
            monthly = {"month": PlanInsightItem(severity=severity, violations=list(violations))}
        else:
            monthly = {}

        return PlanInsights(daily=daily, resource=resource, weekly=weekly, monthly=monthly)

    def _to_phase(scenario) -> PlanPhaseRead:
        summary = PlanScenarioSummary.model_validate(scenario)
        ordered_entries = sorted(scenario.entries, key=lambda entry: (entry.date, entry.resource_id))
        entries = [PlanningEntryRead.model_validate(entry) for entry in ordered_entries]
        violations = [
            PlanViolation.model_validate(violation) if not isinstance(violation, PlanViolation) else violation
            for violation in scenario.violations or []
        ]
        insights = _aggregate_insights(violations)
        return PlanPhaseRead(scenario=summary, entries=entries, violations=violations, insights=insights)

    preparation = None
    approved = None
    for scenario in scenarios:
        if scenario.status == "approved":
            approved = _to_phase(scenario)
        else:
            # Treat everything else as preparation phase for now (draft, ready, etc.)
            if preparation is None:
                preparation = _to_phase(scenario)

    return PlanOverviewResponse(month=month, preparation=preparation, approved=approved)


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
