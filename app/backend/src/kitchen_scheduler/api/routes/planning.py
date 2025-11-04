from typing import Annotated

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
)
from kitchen_scheduler.services.rules import RuleSet, SchedulingRules, load_default_rules
from kitchen_scheduler.services.scheduler import SchedulingContext, generate_stub_schedule

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
    return PlanViolation(code=v.code, message=v.message, severity=v.severity, meta=v.meta)


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

    context = SchedulingContext(
        month=month,
        resources=[{"id": resource.id, "role": resource.role} for resource in resources],
        shifts=[{"code": shift.code, "hours": float(shift.hours)} for shift in shifts],
        rules=rule_set,
    )
    result = generate_stub_schedule(context)
    violations = [_map_violation(v) for v in result.violations]
    response = PlanGenerationResponse(entries=result.entries, violations=violations)

    scenario = await planning_repo.get_scenario_by_month(session, month)
    if scenario:
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
