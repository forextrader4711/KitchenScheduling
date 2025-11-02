from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.models.planning import PlanScenario


async def list_scenarios(session: AsyncSession) -> list[PlanScenario]:
    result = await session.execute(select(PlanScenario))
    return list(result.scalars().all())
