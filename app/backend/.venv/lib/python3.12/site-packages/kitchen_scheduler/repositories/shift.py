from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.models.resource import Shift
from kitchen_scheduler.schemas.resource import ShiftCreate


async def list_shifts(session: AsyncSession) -> list[Shift]:
    result = await session.execute(select(Shift))
    return list(result.scalars().all())


async def create_shift(session: AsyncSession, payload: ShiftCreate) -> Shift:
    shift = Shift(**payload.dict())
    session.add(shift)
    await session.flush()
    await session.refresh(shift)
    return shift
