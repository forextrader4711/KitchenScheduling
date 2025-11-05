from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import resource as resource_repo
from kitchen_scheduler.schemas.resource import (
    ResourceAbsenceCreate,
    ResourceAbsencePatch,
    ResourceAbsenceRead,
    ResourceCreate,
    ResourceRead,
    ResourceUpdate,
)

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
    await session.refresh(resource)
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
    await session.refresh(resource)
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


@router.get("/{resource_id}/absences", response_model=list[ResourceAbsenceRead])
async def list_resource_absences(
    resource_id: int, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> list[ResourceAbsenceRead]:
    resource = await resource_repo.get_resource(session, resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    absences = await resource_repo.list_resource_absences(session, resource_id)
    return [ResourceAbsenceRead.model_validate(item) for item in absences]


@router.post(
    "/{resource_id}/absences",
    response_model=ResourceAbsenceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource_absence(
    resource_id: int,
    payload: ResourceAbsenceCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResourceAbsenceRead:
    resource = await resource_repo.get_resource(session, resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    absence = await resource_repo.create_resource_absence(session, resource_id, payload)
    await session.commit()
    return ResourceAbsenceRead.model_validate(absence)


@router.patch(
    "/{resource_id}/absences/{absence_id}",
    response_model=ResourceAbsenceRead,
)
async def update_resource_absence(
    resource_id: int,
    absence_id: int,
    payload: ResourceAbsencePatch,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResourceAbsenceRead:
    absence = await resource_repo.get_resource_absence(session, resource_id, absence_id)
    if not absence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Absence not found")
    updated = await resource_repo.update_resource_absence(session, absence, payload)
    await session.commit()
    return ResourceAbsenceRead.model_validate(updated)


@router.delete("/{resource_id}/absences/{absence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource_absence(
    resource_id: int,
    absence_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    absence = await resource_repo.get_resource_absence(session, resource_id, absence_id)
    if not absence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Absence not found")
    await resource_repo.delete_resource_absence(session, absence)
    await session.commit()
