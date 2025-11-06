from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kitchen_scheduler.db.base import Base

if TYPE_CHECKING:
    from kitchen_scheduler.db.models.planning import PlanningEntry


class ResourceRole(str, Enum):  # type: ignore[call-arg]
    COOK = "cook"
    KITCHEN_ASSISTANT = "kitchen_assistant"
    POT_WASHER = "pot_washer"
    APPRENTICE = "apprentice"
    RELIEF_COOK = "relief_cook"


class Resource(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[ResourceRole] = mapped_column(
        SqlEnum(
            ResourceRole,
            name="resourcerole",
            create_type=False,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    availability_percent: Mapped[int] = mapped_column(Integer, default=100)
    contract_hours_per_month: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    preferred_days_off: Mapped[Optional[str]] = mapped_column(String(120))
    vacation_days: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(5), default="en")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    availability_template: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    preferred_shift_codes: Mapped[Optional[list[int]]] = mapped_column(JSON, default=None)
    undesired_shift_codes: Mapped[Optional[list[int]]] = mapped_column(JSON, default=None)

    planning_entries: Mapped[list["PlanningEntry"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )
    absences: Mapped[list["ResourceAbsence"]] = relationship(
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


class ResourceAbsence(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resource.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    absence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )

    resource: Mapped[Resource] = relationship(back_populates="absences")
