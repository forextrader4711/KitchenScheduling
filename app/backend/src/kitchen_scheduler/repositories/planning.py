import json

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.models.planning import PlanningEntry, PlanScenario, PlanVersion
from kitchen_scheduler.schemas.planning import (
    PlanGenerationResponse,
    PlanScenarioCreate,
    PlanScenarioUpdate,
)


async def list_scenarios(session: AsyncSession) -> list[PlanScenario]:
    result = await session.execute(select(PlanScenario))
    return list(result.scalars().all())


async def get_scenario_by_month(session: AsyncSession, month: str) -> PlanScenario | None:
    result = await session.execute(select(PlanScenario).where(PlanScenario.month == month))
    return result.scalars().first()


async def store_plan_generation(
    session: AsyncSession,
    scenario: PlanScenario,
    payload: PlanGenerationResponse,
) -> PlanScenario:
    await session.execute(delete(PlanningEntry).where(PlanningEntry.scenario_id == scenario.id))

    entries = []
    for item in payload.entries:
        entry = PlanningEntry(
            resource_id=item.resource_id,
            shift_code=item.shift_code,
            date=item.date,
            absence_type=item.absence_type,
            comment=item.comment,
            scenario_id=scenario.id,
        )
        session.add(entry)
        entries.append(entry)

    scenario.violations = [violation.model_dump() for violation in payload.violations]
    scenario.updated_at = func.now()
    await session.flush()
    await session.refresh(scenario)

    count_result = await session.execute(
        select(func.count(PlanVersion.id)).where(PlanVersion.scenario_id == scenario.id)
    )
    existing_count = count_result.scalar_one()
    next_label = f"v{existing_count + 1}"

    summary = {
        "entries": len(payload.entries),
        "violations": len(payload.violations),
        "critical_violations": len([v for v in payload.violations if v.severity == "critical"]),
    }

    version = PlanVersion(
        scenario_id=scenario.id,
        version_label=next_label,
        summary_hours=json.dumps(summary),
    )
    session.add(version)

    return scenario


async def list_versions(session: AsyncSession, scenario_id: int) -> list[PlanVersion]:
    result = await session.execute(
        select(PlanVersion)
        .where(PlanVersion.scenario_id == scenario_id)
        .order_by(PlanVersion.created_at.desc())
    )
    return list(result.scalars().all())


async def create_scenario(session: AsyncSession, payload: PlanScenarioCreate) -> PlanScenario:
    scenario = PlanScenario(month=payload.month, name=payload.name, status=payload.status)
    session.add(scenario)
    await session.flush()
    await session.refresh(scenario)
    return scenario


async def get_scenario(session: AsyncSession, scenario_id: int) -> PlanScenario | None:
    return await session.get(PlanScenario, scenario_id)


async def update_scenario(
    session: AsyncSession, scenario: PlanScenario, payload: PlanScenarioUpdate
) -> PlanScenario:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(scenario, field, value)
    await session.flush()
    await session.refresh(scenario)
    return scenario


async def delete_scenario(session: AsyncSession, scenario: PlanScenario) -> None:
    await session.delete(scenario)
