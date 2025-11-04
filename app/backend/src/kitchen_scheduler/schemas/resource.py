from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShiftBase(BaseModel):
    code: int
    description: str
    start: str
    end: str
    hours: float


class ShiftCreate(ShiftBase):
    pass


class ShiftRead(ShiftBase):
    model_config = ConfigDict(from_attributes=True)


class ShiftUpdate(BaseModel):
    description: str | None = None
    start: str | None = None
    end: str | None = None
    hours: float | None = None


class ResourceBase(BaseModel):
    name: str
    role: Literal["cook", "kitchen_assistant", "pot_washer", "apprentice", "relief_cook"]
    availability_percent: int = 100
    contract_hours_per_month: float = Field(gt=0)
    preferred_days_off: str | None = None
    vacation_days: str | None = None
    language: str = "en"
    notes: str | None = None


class ResourceCreate(ResourceBase):
    pass


class ResourceRead(ResourceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ResourceUpdate(BaseModel):
    name: str | None = None
    role: Literal["cook", "kitchen_assistant", "pot_washer", "apprentice", "relief_cook"] | None = None
    availability_percent: int | None = None
    contract_hours_per_month: float | None = Field(default=None, gt=0)
    preferred_days_off: str | None = None
    vacation_days: str | None = None
    language: str | None = None
    notes: str | None = None


class PlanningEntryBase(BaseModel):
    resource_id: int
    date: date
    shift_code: int | None = None
    absence_type: str | None = None
    comment: str | None = None


class PlanningEntryRead(PlanningEntryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
