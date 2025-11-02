from datetime import date

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from kitchen_scheduler.db.base import Base


class MonthlyParameters(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7), unique=True, index=True)  # YYYY-MM
    contractual_hours: Mapped[float] = mapped_column(Numeric(5, 2))
    max_vacation_overlap: Mapped[int] = mapped_column(Integer)
    publication_deadline: Mapped[date] = mapped_column(Date)
