import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kitchen_scheduler.repositories import shift as shift_repo
from kitchen_scheduler.schemas.resource import ShiftCreate, ShiftUpdate


@pytest.mark.anyio("asyncio")
async def test_shift_crud(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await _exercise_shift_crud(session)


async def _exercise_shift_crud(session: AsyncSession) -> None:
    payload = ShiftCreate(
        code=1,
        description="Morning",
        start="07:00",
        end="15:00",
        hours=8.0,
    )

    created = await shift_repo.create_shift(session, payload)
    await session.commit()

    assert created.code == 1
    shifts = await shift_repo.list_shifts(session)
    assert len(shifts) == 1
    assert shifts[0].description == "Morning"

    updated = await shift_repo.update_shift(
        session,
        created,
        ShiftUpdate(description="Updated Morning", hours=8.5),
    )
    await session.commit()

    assert updated.description == "Updated Morning"
    assert float(updated.hours) == 8.5

    await shift_repo.delete_shift(session, updated)
    await session.commit()

    shifts_after_delete = await shift_repo.list_shifts(session)
    assert shifts_after_delete == []
