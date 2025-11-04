from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kitchen_scheduler.repositories import system as system_repo
from kitchen_scheduler.schemas.system import (
    MonthlyParametersCreate,
    MonthlyParametersUpdate,
)


@pytest.mark.anyio("asyncio")
async def test_monthly_parameters_crud(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await _exercise_monthly_parameters_crud(session)


async def _exercise_monthly_parameters_crud(session: AsyncSession) -> None:
    payload = MonthlyParametersCreate(
        month="2024-11",
        contractual_hours=160.0,
        max_vacation_overlap=2,
        publication_deadline=date(2024, 10, 20),
    )

    parameters = await system_repo.create_monthly_parameters(session, payload)
    await session.commit()

    assert parameters.id is not None

    records = await system_repo.list_monthly_parameters(session)
    assert len(records) == 1
    assert records[0].contractual_hours == payload.contractual_hours

    updated = await system_repo.update_monthly_parameters(
        session,
        parameters,
        MonthlyParametersUpdate(max_vacation_overlap=3),
    )
    await session.commit()

    assert updated.max_vacation_overlap == 3

    await system_repo.delete_monthly_parameters(session, updated)
    await session.commit()

    records_after_delete = await system_repo.list_monthly_parameters(session)
    assert records_after_delete == []
