from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kitchen_scheduler.db.base import Base


class ResourceRole(str, Enum):  # type: ignore[call-arg]
    COOK = "cook"
    KITCHEN_ASSISTANT = "kitchen_assistant"
    POT_WASHER = "pot_washer"
    APPRENTICE = "apprentice"
    RELIEF_COOK = "relief_cook"


class Resource(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[ResourceRole] = mapped_column(SqlEnum(ResourceRole), nullable=False)
    availability_percent: Mapped[int] = mapped_column(Integer, default=100)
    contract_hours_per_month: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    preferred_days_off: Mapped[Optional[str]] = mapped_column(String(120))
    vacation_days: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(5), default="en")
    notes: Mapped[Optional[str]] = mapped_column(Text)

    planning_entries: Mapped[list["PlanningEntry"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )


class Shift(Base):
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(120), nullable=False)
    start: Mapped[str] = mapped_column(String(5), nullable=False)
    end: Mapped[str] = mapped_column(String(5), nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)

    prime_rule: Mapped[Optional["ShiftPrimeRule"]] = relationship(
        back_populates="shift", uselist=False, cascade="all, delete-orphan"
    )


class ShiftPrimeRule(Base):
    shift_code: Mapped[int] = mapped_column(
        Integer, ForeignKey("shift.code", ondelete="CASCADE"), primary_key=True
    )
    allowed: Mapped[bool] = mapped_column(default=True)

    shift: Mapped[Shift] = relationship(back_populates="prime_rule")
