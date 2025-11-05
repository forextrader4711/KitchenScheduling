from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from kitchen_scheduler.db.models.resource import Resource, ResourceAbsence
from kitchen_scheduler.schemas.resource import (
    ResourceAbsenceCreate,
    ResourceAbsencePatch,
    ResourceCreate,
    ResourceUpdate,
)


async def list_resources(session: AsyncSession) -> list[Resource]:
    result = await session.execute(select(Resource).options(selectinload(Resource.absences)))
    return list(result.scalars().all())


async def create_resource(session: AsyncSession, payload: ResourceCreate) -> Resource:
    resource = Resource(**payload.model_dump())
    session.add(resource)
    await session.flush()
    await session.refresh(resource)
    return resource


async def get_resource(session: AsyncSession, resource_id: int) -> Resource | None:
    return await session.get(Resource, resource_id, options=[selectinload(Resource.absences)])


async def update_resource(
    session: AsyncSession, resource: Resource, payload: ResourceUpdate
) -> Resource:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(resource, field, value)
    await session.flush()
    await session.refresh(resource)
    return resource


async def delete_resource(session: AsyncSession, resource: Resource) -> None:
    await session.delete(resource)


async def list_resource_absences(session: AsyncSession, resource_id: int) -> list[ResourceAbsence]:
    result = await session.execute(
        select(ResourceAbsence).where(ResourceAbsence.resource_id == resource_id)
    )
    return list(result.scalars().all())


async def get_resource_absence(
    session: AsyncSession, resource_id: int, absence_id: int
) -> ResourceAbsence | None:
    result = await session.execute(
        select(ResourceAbsence)
        .where(ResourceAbsence.resource_id == resource_id)
        .where(ResourceAbsence.id == absence_id)
    )
    return result.scalars().first()


async def create_resource_absence(
    session: AsyncSession, resource_id: int, payload: ResourceAbsenceCreate
) -> ResourceAbsence:
    absence = ResourceAbsence(resource_id=resource_id, **payload.model_dump())
    session.add(absence)
    await session.flush()
    await session.refresh(absence)
    return absence


async def update_resource_absence(
    session: AsyncSession, absence: ResourceAbsence, payload: ResourceAbsencePatch
) -> ResourceAbsence:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(absence, field, value)
    await session.flush()
    await session.refresh(absence)
    return absence


async def delete_resource_absence(session: AsyncSession, absence: ResourceAbsence) -> None:
    await session.delete(absence)
