from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.models.resource import Resource
from kitchen_scheduler.schemas.resource import ResourceCreate


async def list_resources(session: AsyncSession) -> list[Resource]:
    result = await session.execute(select(Resource))
    return list(result.scalars().all())


async def create_resource(session: AsyncSession, payload: ResourceCreate) -> Resource:
    resource = Resource(**payload.dict())
    session.add(resource)
    await session.flush()
    await session.refresh(resource)
    return resource
