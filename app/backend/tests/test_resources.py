import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kitchen_scheduler.repositories import resource as resource_repo
from kitchen_scheduler.schemas.resource import ResourceCreate, ResourceUpdate


@pytest.mark.anyio("asyncio")
async def test_resource_crud(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await _exercise_resource_crud(session)


async def _exercise_resource_crud(session: AsyncSession) -> None:
    payload = ResourceCreate(
        name="Test Cook",
        role="cook",
        availability_percent=100,
        contract_hours_per_month=160,
        language="en",
    )

    created = await resource_repo.create_resource(session, payload)
    await session.commit()

    assert created.id is not None
    resources = await resource_repo.list_resources(session)
    assert len(resources) == 1
    assert resources[0].name == "Test Cook"

    updated = await resource_repo.update_resource(
        session,
        created,
        ResourceUpdate(availability_percent=80, notes="Updated via test"),
    )
    await session.commit()

    assert updated.availability_percent == 80
    assert updated.notes == "Updated via test"

    await resource_repo.delete_resource(session, updated)
    await session.commit()

    resources_after_delete = await resource_repo.list_resources(session)
    assert resources_after_delete == []
