from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import planning as planning_repo
from kitchen_scheduler.schemas.planning import PlanVersionRead

router = APIRouter(prefix="/versions", tags=["plan_versions"])


@router.get("/{scenario_id}", response_model=list[PlanVersionRead])
async def get_versions_for_scenario(
    scenario_id: int, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> list[PlanVersionRead]:
    scenario = await planning_repo.get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    versions = await planning_repo.list_versions(session, scenario_id)
    return [PlanVersionRead.model_validate(version) for version in versions]

