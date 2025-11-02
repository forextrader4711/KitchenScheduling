from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ShiftBase(BaseModel):
    code: int
    description: str
    start: str
    end: str
    hours: float


class ShiftCreate(ShiftBase):
    pass


class ShiftRead(ShiftBase):
    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class PlanningEntryBase(BaseModel):
    resource_id: int
    date: date
    shift_code: int | None = None
    absence_type: str | None = None
    comment: str | None = None


class PlanningEntryRead(PlanningEntryBase):
    id: int

    class Config:
        from_attributes = True
