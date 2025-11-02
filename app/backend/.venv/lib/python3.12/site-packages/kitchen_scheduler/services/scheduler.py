from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from kitchen_scheduler.schemas.resource import PlanningEntryRead


@dataclass
class SchedulingContext:
    month: str
    resources: list[dict]
    shifts: list[dict]
    rules: dict


def generate_stub_schedule(context: SchedulingContext) -> Iterable[PlanningEntryRead]:
    """
    Placeholder algorithm that spreads resources across days sequentially.

    This allows the frontend to integrate against a deterministic API while the real
    optimizer is developed (potentially with OR-Tools).
    """
    year, month = map(int, context.month.split("-"))
    day = date(year, month, 1)
    entries: list[PlanningEntryRead] = []
    shift_codes = [shift["code"] for shift in context.shifts]
    shift_count = len(shift_codes)

    resource_count = len(context.resources)
    if not resource_count or not shift_count:
        return entries

    idx = 0
    while day.month == month:
        resource = context.resources[idx % resource_count]
        shift_code = shift_codes[idx % shift_count]
        entries.append(
            PlanningEntryRead(
                id=idx + 1,
                resource_id=resource["id"],
                date=day,
                shift_code=shift_code,
                absence_type=None,
                comment="AUTO-STUB",
            )
        )
        day += timedelta(days=1)
        idx += 1
    return entries
