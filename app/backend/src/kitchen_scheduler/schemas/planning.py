from datetime import datetime
from typing import List

from pydantic import BaseModel

from kitchen_scheduler.schemas.resource import PlanningEntryRead


class PlanScenarioBase(BaseModel):
    month: str  # YYYY-MM
    name: str = "Draft"
    status: str = "draft"


class PlanScenarioCreate(PlanScenarioBase):
    entries: List[PlanningEntryRead] = []


class PlanScenarioRead(PlanScenarioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlanGenerationRequest(BaseModel):
    month: str
