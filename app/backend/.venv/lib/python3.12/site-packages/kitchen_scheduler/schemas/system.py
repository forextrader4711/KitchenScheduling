from datetime import date

from pydantic import BaseModel


class MonthlyParametersBase(BaseModel):
    month: str
    contractual_hours: float
    max_vacation_overlap: int
    publication_deadline: date


class MonthlyParametersCreate(MonthlyParametersBase):
    pass


class MonthlyParametersRead(MonthlyParametersBase):
    id: int

    class Config:
        from_attributes = True
