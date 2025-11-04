from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from kitchen_scheduler.db.base import Base


class MonthlyParameters(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7), unique=True, index=True)  # YYYY-MM
    contractual_hours: Mapped[float] = mapped_column(Numeric(5, 2))
    max_vacation_overlap: Mapped[int] = mapped_column(Integer)
    publication_deadline: Mapped[date] = mapped_column(Date)


class SchedulingRuleConfig(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Default Rule Set", nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    rules: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
