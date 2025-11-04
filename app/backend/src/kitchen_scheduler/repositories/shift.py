from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.models.resource import Shift
from kitchen_scheduler.schemas.resource import ShiftCreate, ShiftUpdate


async def list_shifts(session: AsyncSession) -> list[Shift]:
    result = await session.execute(select(Shift))
    return list(result.scalars().all())


async def create_shift(session: AsyncSession, payload: ShiftCreate) -> Shift:
    shift = Shift(**payload.model_dump())
    session.add(shift)
    await session.flush()
    await session.refresh(shift)
    return shift


async def get_shift(session: AsyncSession, shift_code: int) -> Shift | None:
    return await session.get(Shift, shift_code)


async def update_shift(session: AsyncSession, shift: Shift, payload: ShiftUpdate) -> Shift:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(shift, field, value)
    await session.flush()
    await session.refresh(shift)
    return shift


async def delete_shift(session: AsyncSession, shift: Shift) -> None:
    await session.delete(shift)
