from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import resource as resource_repo
from kitchen_scheduler.schemas.resource import ResourceCreate, ResourceRead

router = APIRouter()


@router.get("/", response_model=list[ResourceRead])
async def list_resources(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> list[ResourceRead]:
    resources = await resource_repo.list_resources(session)
    return [ResourceRead.model_validate(resource) for resource in resources]


@router.post("/", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
async def create_resource(
    payload: ResourceCreate, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> ResourceRead:
    resource = await resource_repo.create_resource(session, payload)
    await session.commit()
    return ResourceRead.model_validate(resource)
