import json
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.models.planning import PlanScenario, PlanVersion


async def create_plan_version(
    session: AsyncSession,
    scenario: PlanScenario,
    *,
    label: Optional[str] = None,
    summary: Optional[dict] = None,
) -> PlanVersion:
    if label:
        version_label = label
    else:
        count_result = await session.execute(
            select(func.count(PlanVersion.id)).where(PlanVersion.scenario_id == scenario.id)
        )
        existing_count = count_result.scalar_one()
        version_label = f"v{existing_count + 1}"

    plan_version = PlanVersion(
        scenario_id=scenario.id,
        version_label=version_label,
        summary_hours=json.dumps(summary) if summary else None,
    )
    session.add(plan_version)
    await session.flush()
    await session.refresh(plan_version)
    return plan_version
