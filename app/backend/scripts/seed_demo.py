"""Seed a handful of baseline records for local development.

Run this after applying Alembic migrations:

    python -m alembic upgrade head
    python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
from datetime import date
from itertools import cycle, islice
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from kitchen_scheduler.core.config import get_settings
from kitchen_scheduler.db.models.planning import PlanScenario
from kitchen_scheduler.db.models.resource import Resource, ResourceAbsence, ResourceRole, Shift, ShiftPrimeRule
from kitchen_scheduler.db.models.system import MonthlyParameters
from kitchen_scheduler.repositories import planning as planning_repo
from kitchen_scheduler.repositories import resource as resource_repo
from kitchen_scheduler.repositories import shift as shift_repo
from kitchen_scheduler.repositories import system as system_repo
from kitchen_scheduler.schemas.planning import PlanGenerationResponse, PlanViolation
from kitchen_scheduler.services.rules import RuleSet, SchedulingRules, load_default_rules
from kitchen_scheduler.services.scheduler import (
    AbsenceWindow,
    AvailabilityWindow,
    SchedulingContext,
    SchedulingResource,
    SchedulingShift,
    generate_stub_schedule,
)


async def seed() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await _ensure_resource_role_enum(session)
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
            resources = _build_resources()
            session.add_all(resources)

            absence_templates = _generate_absence_pairs(date.today().year)
            for resource, (absence_type, start, end) in zip(resources, cycle(absence_templates), strict=False):
                session.add(
                    ResourceAbsence(
                        resource=resource,
                        start_date=start,
                        end_date=end,
                        absence_type=absence_type,
                        comment=f"{absence_type.replace('_', ' ').title()} (demo)",
                    )
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

        await session.flush()
        await _generate_initial_plan(session, current_month)
        await session.commit()

    await engine.dispose()
    print("Seed data inserted (skipped existing rows).")


async def _generate_initial_plan(session, month: str) -> None:
    resources = await resource_repo.list_resources(session)
    shifts = await shift_repo.list_shifts(session)

    if not resources or not shifts:
        return

    config = await system_repo.get_active_rule_config(session)
    if config:
        rule_set = RuleSet(rules=SchedulingRules.model_validate(config.rules))
    else:
        rule_set = load_default_rules()

    scheduling_resources = [
        SchedulingResource(
            id=resource.id,
            role=resource.role.value if hasattr(resource.role, "value") else str(resource.role),
            availability=_map_availability_template(resource.availability_template),
            preferred_shift_codes=list(resource.preferred_shift_codes or []),
            undesired_shift_codes=list(resource.undesired_shift_codes or []),
            absences=[
                AbsenceWindow(
                    start_date=absence.start_date,
                    end_date=absence.end_date,
                    absence_type=absence.absence_type,
                    comment=absence.comment,
                )
                for absence in resource.absences
            ],
        )
        for resource in resources
    ]

    scheduling_shifts = [
        SchedulingShift(
            code=shift.code,
            description=shift.description,
            start=shift.start,
            end=shift.end,
            hours=float(shift.hours),
        )
        for shift in shifts
    ]

    context = SchedulingContext(
        month=month,
        resources=scheduling_resources,
        shifts=scheduling_shifts,
        rules=rule_set,
    )

    result = generate_stub_schedule(context)

    response = PlanGenerationResponse(
        entries=result.entries,
        violations=[
            PlanViolation(
                code=violation.code,
                message=violation.message,
                severity=violation.severity,
                meta=violation.meta,
                scope=violation.scope,
                day=violation.day.isoformat() if isinstance(violation.day, date) else violation.day,
                resource_id=violation.resource_id,
                iso_week=violation.iso_week,
            )
            for violation in result.violations
        ],
    )

    scenario = await planning_repo.ensure_scenario(
        session,
        month=month,
        status="draft",
        name="Draft Scenario",
    )
    scenario.status = "draft"
    await planning_repo.store_plan_generation(session, scenario, response)


async def _ensure_resource_role_enum(session) -> None:
    """Ensure the resourcerole enum stores lowercase values."""

    mappings = [
        ("COOK", "cook"),
        ("KITCHEN_ASSISTANT", "kitchen_assistant"),
        ("POT_WASHER", "pot_washer"),
        ("APPRENTICE", "apprentice"),
        ("RELIEF_COOK", "relief_cook"),
    ]

    for old, new in mappings:
        if old == new:
            continue
        stmt = text(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = 'resourcerole' AND e.enumlabel = :old) THEN "
            f"ALTER TYPE resourcerole RENAME VALUE '{old}' TO '{new}'; "
            "END IF; "
            "END $$;"
        )
        try:
            await session.execute(stmt, {"old": old})
        except Exception:
            # If the value does not exist or the DB doesn't support the operation, skip.
            continue


def _build_resources() -> list[Resource]:
    cooks = [
        Resource(
            name="Alice Dupont",
            role=ResourceRole.COOK,
            contract_hours_per_month=160,
            availability_percent=100,
            language="fr",
            preferred_shift_codes=[1, 8],
            undesired_shift_codes=[10],
            availability_template=_weekday_template(workdays=5),
        ),
        Resource(
            name="Bastien Favre",
            role=ResourceRole.COOK,
            contract_hours_per_month=160,
            availability_percent=100,
            language="fr",
            preferred_shift_codes=[1],
            availability_template=_weekday_template(workdays=5),
        ),
        Resource(
            name="Camille Perret",
            role=ResourceRole.COOK,
            contract_hours_per_month=150,
            availability_percent=90,
            language="fr",
            preferred_shift_codes=[10],
            availability_template=_weekday_template(workdays=4, weekend=True),
        ),
        Resource(
            name="David Roux",
            role=ResourceRole.COOK,
            contract_hours_per_month=160,
            availability_percent=100,
            language="fr",
            preferred_shift_codes=[4],
            undesired_shift_codes=[1],
            availability_template=_weekday_template(workdays=5),
        ),
        Resource(
            name="Estelle Girard",
            role=ResourceRole.COOK,
            contract_hours_per_month=140,
            availability_percent=90,
            language="fr",
            preferred_shift_codes=[8],
            availability_template=_weekday_template(workdays=4),
        ),
        Resource(
            name="Félix Monod",
            role=ResourceRole.COOK,
            contract_hours_per_month=160,
            availability_percent=100,
            language="fr",
            preferred_shift_codes=[1, 4],
            availability_template=_weekday_template(workdays=5),
        ),
        Resource(
            name="Géraldine Weber",
            role=ResourceRole.COOK,
            contract_hours_per_month=150,
            availability_percent=95,
            language="fr",
            preferred_shift_codes=[1, 8],
            availability_template=_weekday_template(workdays=5),
        ),
    ]

    kitchen_assistants = [
        Resource(
            name="Hugo Lambert",
            role=ResourceRole.KITCHEN_ASSISTANT,
            contract_hours_per_month=128,
            availability_percent=80,
            language="fr",
            availability_template=_weekday_template(workdays=4),
        ),
        Resource(
            name="Isabelle Morel",
            role=ResourceRole.KITCHEN_ASSISTANT,
            contract_hours_per_month=130,
            availability_percent=85,
            language="fr",
            preferred_shift_codes=[8, 10],
            availability_template=_weekday_template(workdays=5),
        ),
        Resource(
            name="Julien Mercier",
            role=ResourceRole.KITCHEN_ASSISTANT,
            contract_hours_per_month=120,
            availability_percent=75,
            language="fr",
            undesired_shift_codes=[4],
            availability_template=_weekday_template(workdays=4),
        ),
    ]

    pot_washers = [
        Resource(
            name="Karim Senn",
            role=ResourceRole.POT_WASHER,
            contract_hours_per_month=120,
            availability_percent=100,
            language="fr",
            preferred_shift_codes=[10],
            availability_template=_weekday_template(workdays=5),
        ),
        Resource(
            name="Louise Hertig",
            role=ResourceRole.POT_WASHER,
            contract_hours_per_month=110,
            availability_percent=90,
            language="fr",
            availability_template=_weekday_template(workdays=5, weekend=True),
        ),
    ]

    apprentices = [
        Resource(
            name="Maël Schneider",
            role=ResourceRole.APPRENTICE,
            contract_hours_per_month=100,
            availability_percent=60,
            language="fr",
            preferred_shift_codes=[1],
            availability_template=_weekday_template(workdays=4),
        ),
        Resource(
            name="Nina Clément",
            role=ResourceRole.APPRENTICE,
            contract_hours_per_month=110,
            availability_percent=70,
            language="fr",
            availability_template=_weekday_template(workdays=4),
        ),
    ]

    relief_cooks = [
        Resource(
            name="Olivier Rey",
            role=ResourceRole.RELIEF_COOK,
            contract_hours_per_month=80,
            availability_percent=50,
            language="fr",
            preferred_shift_codes=[4, 10],
            availability_template=_weekday_template(workdays=3, weekend=True),
        )
    ]

    return cooks + kitchen_assistants + pot_washers + apprentices + relief_cooks


def _weekday_template(*, workdays: int, weekend: bool = False) -> list[dict]:
    """Create a simple availability template with optional weekend coverage."""

    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    weekend_days = ["saturday", "sunday"] if weekend else []
    active_days = list(islice(cycle(weekdays), workdays))
    active_days += weekend_days

    template = []
    for day in weekdays + weekend_days:
        template.append(
            {
                "day": day,
                "is_available": day in active_days,
                "start_time": "07:15" if day in active_days else None,
                "end_time": "19:15" if day in active_days else None,
            }
        )
    return template


def _generate_absence_pairs(year: int) -> list[tuple[str, date, date]]:
    """Return a rotating list of absence definitions for the demo dataset."""

    return [
        ("vacation", date(year, 2, 12), date(year, 2, 16)),
        ("vacation", date(year, 4, 8), date(year, 4, 12)),
        ("training", date(year, 5, 20), date(year, 5, 24)),
        ("sick_leave", date(year, 6, 3), date(year, 6, 5)),
        ("vacation", date(year, 7, 15), date(year, 7, 26)),
        ("vacation", date(year, 8, 19), date(year, 8, 23)),
        ("training", date(year, 9, 9), date(year, 9, 13)),
        ("vacation", date(year, 10, 14), date(year, 10, 18)),
        ("sick_leave", date(year, 11, 4), date(year, 11, 8)),
    ]


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
def _map_availability_template(template: Any) -> list[AvailabilityWindow]:
    if not template:
        return []
    windows: list[AvailabilityWindow] = []
    for entry in template:
        if not isinstance(entry, dict):
            continue
        day = entry.get("day")
        if not isinstance(day, str):
            continue
        windows.append(
            AvailabilityWindow(
                day=day,
                is_available=bool(entry.get("is_available", True)),
                start_time=entry.get("start_time"),
                end_time=entry.get("end_time"),
            )
        )
    return windows
