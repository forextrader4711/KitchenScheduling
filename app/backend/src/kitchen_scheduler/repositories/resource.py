from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.models.resource import Resource
from kitchen_scheduler.schemas.resource import ResourceCreate, ResourceUpdate


async def list_resources(session: AsyncSession) -> list[Resource]:
    result = await session.execute(select(Resource))
    return list(result.scalars().all())


async def create_resource(session: AsyncSession, payload: ResourceCreate) -> Resource:
    resource = Resource(**payload.model_dump())
    session.add(resource)
    await session.flush()
    await session.refresh(resource)
    return resource


async def get_resource(session: AsyncSession, resource_id: int) -> Resource | None:
    return await session.get(Resource, resource_id)


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
