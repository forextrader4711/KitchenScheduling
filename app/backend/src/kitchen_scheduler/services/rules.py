"""Domain representations for scheduling rules and loaders."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class WorkingTimeRules(BaseModel):
    max_hours_per_week: int
    max_working_days_per_week: int
    max_consecutive_working_days: int
    required_consecutive_days_off_per_month: int
    days_off_patterns: list[str] = Field(default_factory=list)


class RoleComposition(BaseModel):
    min: int | None = None
    max: int | None = None
    remaining_positions: bool = False

    @model_validator(mode="after")
    def validate_bounds(self) -> "RoleComposition":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min cannot exceed max in role composition")
        return self


class PrimeShiftRules(BaseModel):
    allowed_for: list[int] = Field(default_factory=list)
    excluded_for: list[int] = Field(default_factory=list)


class ShiftRules(BaseModel):
    minimum_daily_staff: int
    composition: dict[str, RoleComposition]
    specific_allocations: list[str] = Field(default_factory=list)
    prime_shifts: PrimeShiftRules


class DesiredRestDaysRules(BaseModel):
    max_per_month_per_resource: int
    priority: Literal["soft", "hard"] = "soft"


class VacationRules(BaseModel):
    max_concurrent_vacations: int
    desired_rest_days: DesiredRestDaysRules


class SchedulingRules(BaseModel):
    working_time: WorkingTimeRules
    shift_rules: ShiftRules
    vacations_and_absences: VacationRules


@dataclass(frozen=True)
class RuleSet:
    """Wrapper used by the scheduler to access typed rules."""

    rules: SchedulingRules


def _load_rules_from_json() -> SchedulingRules:
    with resources.files("kitchen_scheduler.services.data").joinpath("default_rules.json").open(
        "r", encoding="utf-8"
    ) as handle:
        payload = json.load(handle)
    return SchedulingRules.model_validate(payload["rules"])


@lru_cache(maxsize=1)
def load_default_rules() -> RuleSet:
    """Return the default rule set bundled with the application."""

    return RuleSet(rules=_load_rules_from_json())
