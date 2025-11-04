from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import resource as resource_repo
from kitchen_scheduler.schemas.resource import ResourceCreate, ResourceRead, ResourceUpdate

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


@router.put("/{resource_id}", response_model=ResourceRead)
async def update_resource(
    resource_id: int,
    payload: ResourceUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResourceRead:
    resource = await resource_repo.get_resource(session, resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    resource = await resource_repo.update_resource(session, resource, payload)
    await session.commit()
    return ResourceRead.model_validate(resource)


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: int, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> None:
    resource = await resource_repo.get_resource(session, resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    await resource_repo.delete_resource(session, resource)
    await session.commit()
