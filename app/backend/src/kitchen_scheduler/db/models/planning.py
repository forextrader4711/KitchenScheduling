from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kitchen_scheduler.db.base import Base

if TYPE_CHECKING:
    from kitchen_scheduler.db.models.resource import Resource, Shift


class PlanningEntry(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resource.id", ondelete="CASCADE"), index=True)
    shift_code: Mapped[int | None] = mapped_column(ForeignKey("shift.code"), nullable=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    absence_type: Mapped[str | None] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text)

    scenario_id: Mapped[int | None] = mapped_column(ForeignKey("planscenario.id", ondelete="CASCADE"))
    resource: Mapped["Resource"] = relationship(back_populates="planning_entries")
    shift: Mapped["Shift"] = relationship()
    scenario: Mapped["PlanScenario"] = relationship(back_populates="entries")


class PlanScenario(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[str] = mapped_column(String(7), index=True)  # Format YYYY-MM
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Draft")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    entries: Mapped[list["PlanningEntry"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    versions: Mapped[list["PlanVersion"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )


class PlanVersion(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("planscenario.id", ondelete="CASCADE"))
    version_label: Mapped[str] = mapped_column(String(32), default="v1")
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_by: Mapped[str | None] = mapped_column(String(120))
    summary_hours: Mapped[str | None] = mapped_column(Text)

    scenario: Mapped["PlanScenario"] = relationship(back_populates="versions")
