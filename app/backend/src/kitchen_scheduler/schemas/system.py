from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from kitchen_scheduler.services.rules import SchedulingRules


class MonthlyParametersBase(BaseModel):
    month: str
    contractual_hours: float
    max_vacation_overlap: int
    publication_deadline: date


class MonthlyParametersCreate(MonthlyParametersBase):
    pass


class MonthlyParametersRead(MonthlyParametersBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class MonthlyParametersUpdate(BaseModel):
    contractual_hours: float | None = None
    max_vacation_overlap: int | None = None
    publication_deadline: date | None = None


class SchedulingRuleConfigBase(BaseModel):
    name: str = "Default Rule Set"
    version: str = "v1"
    rules: SchedulingRules
    is_active: bool = True


class SchedulingRuleConfigCreate(SchedulingRuleConfigBase):
    pass


class SchedulingRuleConfigRead(SchedulingRuleConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SchedulingRuleConfigUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    rules: SchedulingRules | None = None
    is_active: bool | None = None


class HolidayRead(BaseModel):
    code: str
    date: date
    name: str
    localized_name: str
