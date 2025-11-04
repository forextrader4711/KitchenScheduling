from datetime import date

from kitchen_scheduler.schemas.planning import PlanScenarioCreate
from kitchen_scheduler.schemas.resource import ResourceCreate, ShiftCreate
from kitchen_scheduler.schemas.system import MonthlyParametersCreate


def build_resource_create(**overrides) -> ResourceCreate:
    data = {
        "name": "Factory Cook",
        "role": "cook",
        "availability_percent": 100,
        "contract_hours_per_month": 160,
        "language": "en",
    }
    data.update(overrides)
    return ResourceCreate(**data)


def build_shift_create(**overrides) -> ShiftCreate:
    data = {
        "code": 99,
        "description": "Factory Shift",
        "start": "08:00",
        "end": "16:00",
        "hours": 8.0,
    }
    data.update(overrides)
    return ShiftCreate(**data)


def build_scenario_create(**overrides) -> PlanScenarioCreate:
    data = {"month": "2024-11", "name": "Factory Scenario", "status": "draft", "entries": []}
    data.update(overrides)
    return PlanScenarioCreate(**data)


def build_monthly_parameters_create(**overrides) -> MonthlyParametersCreate:
    data = {
        "month": "2024-11",
        "contractual_hours": 160.0,
        "max_vacation_overlap": 2,
        "publication_deadline": date(2024, 10, 20),
    }
    data.update(overrides)
    return MonthlyParametersCreate(**data)
