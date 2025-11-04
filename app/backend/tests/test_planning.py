import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kitchen_scheduler.repositories import planning as planning_repo
from kitchen_scheduler.schemas.planning import PlanScenarioCreate, PlanScenarioUpdate


@pytest.mark.anyio("asyncio")
async def test_plan_scenario_crud(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await _exercise_plan_scenario_crud(session)


async def _exercise_plan_scenario_crud(session: AsyncSession) -> None:
    payload = PlanScenarioCreate(month="2024-11", name="Draft Scenario", status="draft")

    scenario = await planning_repo.create_scenario(session, payload)
    await session.commit()

    assert scenario.id is not None

    scenarios = await planning_repo.list_scenarios(session)
    assert len(scenarios) == 1
    assert scenarios[0].name == "Draft Scenario"

    updated = await planning_repo.update_scenario(
        session,
        scenario,
        PlanScenarioUpdate(name="Published Scenario", status="published"),
    )
    await session.commit()

    assert updated.name == "Published Scenario"
    assert updated.status == "published"

    await planning_repo.delete_scenario(session, updated)
    await session.commit()

    scenarios_after_delete = await planning_repo.list_scenarios(session)
    assert scenarios_after_delete == []
