from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import planning as planning_repo
from kitchen_scheduler.repositories import resource as resource_repo
from kitchen_scheduler.repositories import shift as shift_repo
from kitchen_scheduler.schemas.planning import PlanGenerationRequest, PlanScenarioRead
from kitchen_scheduler.schemas.resource import PlanningEntryRead
from kitchen_scheduler.services.scheduler import SchedulingContext, generate_stub_schedule

router = APIRouter()


@router.get("/scenarios", response_model=list[PlanScenarioRead])
async def list_scenarios(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> list[PlanScenarioRead]:
    scenarios = await planning_repo.list_scenarios(session)
    return [PlanScenarioRead.model_validate(scenario) for scenario in scenarios]


@router.post("/generate", response_model=list[PlanningEntryRead])
async def generate_plan(
    payload: PlanGenerationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PlanningEntryRead]:
    resources = await resource_repo.list_resources(session)
    shifts = await shift_repo.list_shifts(session)

    context = SchedulingContext(
        month=payload.month,
        resources=[{"id": resource.id, "role": resource.role} for resource in resources],
        shifts=[{"code": shift.code} for shift in shifts],
        rules={},
    )
    entries = list(generate_stub_schedule(context))
    return entries
