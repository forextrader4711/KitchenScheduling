"""Seed a handful of baseline records for local development.

Run this after applying Alembic migrations:

    python -m alembic upgrade head
    python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from kitchen_scheduler.core.config import get_settings
from kitchen_scheduler.db.models.planning import PlanScenario
from kitchen_scheduler.db.models.resource import Resource, ResourceRole, Shift, ShiftPrimeRule
from kitchen_scheduler.db.models.system import MonthlyParameters


async def seed() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Seed shifts
        existing_shifts = await session.scalar(select(func.count(Shift.code)))
        if not existing_shifts:
            session.add_all(
                [
                    Shift(code=1, description="Standard morning shift", start="07:00", end="16:15", hours=9.25),
                    Shift(code=4, description="Long shift", start="07:15", end="19:15", hours=12.0),
                    Shift(code=8, description="Medium shift", start="08:00", end="17:15", hours=9.25),
                    Shift(code=10, description="Late shift", start="10:15", end="19:30", hours=9.25),
                ]
            )
            session.add_all(
                [
                    ShiftPrimeRule(shift_code=1, allowed=True),
                    ShiftPrimeRule(shift_code=4, allowed=False),
                    ShiftPrimeRule(shift_code=8, allowed=True),
                    ShiftPrimeRule(shift_code=10, allowed=True),
                ]
            )

        # Seed resources
        existing_resources = await session.scalar(select(func.count(Resource.id)))
        if not existing_resources:
            session.add_all(
                [
                    Resource(
                        name="Alice Dupont",
                        role=ResourceRole.COOK,
                        contract_hours_per_month=160,
                        availability_percent=100,
                        language="fr",
                    ),
                    Resource(
                        name="Marc Leroy",
                        role=ResourceRole.KITCHEN_ASSISTANT,
                        contract_hours_per_month=128,
                        availability_percent=80,
                        language="fr",
                    ),
                    Resource(
                        name="Léa Martin",
                        role=ResourceRole.POT_WASHER,
                        contract_hours_per_month=120,
                        availability_percent=100,
                        language="fr",
                    ),
                ]
            )

        # Seed monthly parameters
        current_month = date.today().strftime("%Y-%m")
        parameters_exists = await session.scalar(
            select(func.count(MonthlyParameters.id)).where(MonthlyParameters.month == current_month)
        )
        if not parameters_exists:
            session.add(
                MonthlyParameters(
                    month=current_month,
                    contractual_hours=160,
                    max_vacation_overlap=4,
                    publication_deadline=date.today().replace(day=15),
                )
            )

        # Seed a default scenario shell
        scenario_exists = await session.scalar(select(func.count(PlanScenario.id)))
        if not scenario_exists:
            session.add(
                PlanScenario(
                    month=current_month,
                    name="Draft Scenario",
                    status="draft",
                )
            )

        await session.commit()

    await engine.dispose()
    print("Seed data inserted (skipped existing rows).")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
