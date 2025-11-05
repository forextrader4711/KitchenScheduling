from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Iterable, Sequence, Literal, Optional

from kitchen_scheduler.schemas.resource import PlanningEntryRead
from kitchen_scheduler.services.rules import RuleSet


@dataclass
class AvailabilityWindow:
    day: str
    is_available: bool
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@dataclass
class AbsenceWindow:
    start_date: date
    end_date: date
    absence_type: str
    comment: Optional[str] = None


@dataclass
class SchedulingResource:
    id: int
    role: str
    availability: list[AvailabilityWindow] = field(default_factory=list)
    preferred_shift_codes: list[int] = field(default_factory=list)
    undesired_shift_codes: list[int] = field(default_factory=list)
    absences: list[AbsenceWindow] = field(default_factory=list)


@dataclass
class SchedulingShift:
    code: int
    description: str
    start: str
    end: str
    hours: float


@dataclass
class SchedulingContext:
    month: str
    resources: list[SchedulingResource]
    shifts: list[SchedulingShift]
    rules: RuleSet


@dataclass
class SchedulingViolation:
    code: str
    message: str
    severity: Literal["info", "warning", "critical"] = "warning"
    meta: dict[str, str | int | float] = field(default_factory=dict)
    scope: Literal["schedule", "day", "resource", "week", "month"] = "schedule"
    day: date | None = None
    resource_id: int | None = None
    iso_week: str | None = None


@dataclass
class SchedulingResult:
    entries: list[PlanningEntryRead]
    violations: list[SchedulingViolation] = field(default_factory=list)


def generate_stub_schedule(context: SchedulingContext) -> SchedulingResult:
    """
    Placeholder algorithm that spreads resources across days sequentially.

    This allows the frontend to integrate against a deterministic API while the real
    optimizer is developed (potentially with OR-Tools).
    """
    year, month = map(int, context.month.split("-"))
    day = date(year, month, 1)
    entries: list[PlanningEntryRead] = []
    shift_count = len(context.shifts)
    resource_count = len(context.resources)

    if not resource_count or not shift_count:
        return SchedulingResult(entries=entries, violations=[])

    uncovered_days: list[date] = []

    resource_assignment_counts: dict[int, int] = {resource.id: 0 for resource in context.resources}
    entry_id = 1

    while day.month == month:
        available_resources: list[SchedulingResource] = []
        for resource in context.resources:
            if _get_absence(resource, day):
                continue
            if not _is_available(resource, day):
                continue
            available_resources.append(resource)

        if not available_resources:
            uncovered_days.append(day)
        else:
            for resource in available_resources:
                assignment_idx = resource_assignment_counts.get(resource.id, 0)
                chosen_shift = _select_shift_for_resource(resource, context.shifts, assignment_idx)
                entries.append(
                    PlanningEntryRead(
                        id=entry_id,
                        resource_id=resource.id,
                        date=day,
                        shift_code=chosen_shift.code if chosen_shift else None,
                        absence_type=None,
                        comment="AUTO-STUB",
                    )
                )
                resource_assignment_counts[resource.id] = assignment_idx + 1
                entry_id += 1

        day += timedelta(days=1)
    violations = evaluate_rule_violations(context, entries)

    for missing_day in uncovered_days:
        violations.append(
            SchedulingViolation(
                code="uncovered-day",
                message=f"No available resource for {missing_day.isoformat()}",
                severity="warning",
                meta={"date": missing_day.isoformat()},
                scope="day",
                day=missing_day,
            )
        )

    return SchedulingResult(entries=entries, violations=violations)


def evaluate_rule_violations(
    context: SchedulingContext, entries: list[PlanningEntryRead]
) -> list[SchedulingViolation]:
    """Evaluate key rule families so the frontend can surface violations."""

    violations: list[SchedulingViolation] = []

    if not entries:
        violations.append(
            SchedulingViolation(
                code="empty-schedule",
                message="No planning entries were generated for the requested month.",
                severity="warning",
                scope="schedule",
            )
        )
        return violations

    resource_role_map = {resource.id: resource.role for resource in context.resources}
    shift_hours_map = {shift.code: float(shift.hours) for shift in context.shifts}

    _apply_staffing_rules(context, entries, resource_role_map, violations)
    _apply_working_time_rules(context, entries, shift_hours_map, violations)

    return violations


def _apply_staffing_rules(
    context: SchedulingContext,
    entries: list[PlanningEntryRead],
    resource_role_map: dict[int, str],
    violations: list[SchedulingViolation],
) -> None:
    rules = context.rules.rules.shift_rules
    min_daily_staff = rules.minimum_daily_staff

    day_totals: dict[date, int] = {}
    role_totals: dict[date, dict[str, int]] = {}

    for entry in entries:
        day_totals[entry.date] = day_totals.get(entry.date, 0) + 1
        role_totals.setdefault(entry.date, {})
        role = resource_role_map.get(entry.resource_id)
        if role is None:
            continue
        role_totals[entry.date][role] = role_totals[entry.date].get(role, 0) + 1

    for day, count in day_totals.items():
        if count < min_daily_staff:
            violations.append(
                SchedulingViolation(
                    code="staffing-shortfall",
                    message=f"Only {count} resources assigned on {day}; minimum is {min_daily_staff}.",
                    severity="warning",
                    scope="day",
                    day=day,
                    meta={"date": day.isoformat(), "assigned": count, "required": min_daily_staff},
                )
            )

        for role, composition in rules.composition.items():
            assigned = role_totals.get(day, {}).get(role, 0)
            if composition.min is not None and assigned < composition.min:
                violations.append(
                    SchedulingViolation(
                        code="role-min-shortfall",
                        message=f"{role} minimum not met on {day}: assigned {assigned}, required {composition.min}.",
                        severity="critical",
                        scope="day",
                        day=day,
                        meta={"date": day.isoformat(), "role": role, "assigned": assigned, "min": composition.min},
                    )
                )
            if composition.max is not None and assigned > composition.max:
                violations.append(
                    SchedulingViolation(
                        code="role-max-exceeded",
                        message=f"{role} maximum exceeded on {day}: assigned {assigned}, cap {composition.max}.",
                        severity="warning",
                        scope="day",
                        day=day,
                        meta={"date": day.isoformat(), "role": role, "assigned": assigned, "max": composition.max},
                    )
                )


def _apply_working_time_rules(
    context: SchedulingContext,
    entries: list[PlanningEntryRead],
    shift_hours_map: dict[int, float],
    violations: list[SchedulingViolation],
) -> None:
    working_rules = context.rules.rules.working_time

    per_week_hours: dict[int, dict[tuple[int, int], float]] = {}
    per_week_days: dict[int, dict[tuple[int, int], set[date]]] = {}
    resource_dates: dict[int, set[date]] = {}

    for entry in entries:
        resource_id = entry.resource_id
        hours = shift_hours_map.get(entry.shift_code or 0, 0.0)
        iso_year, iso_week, _ = entry.date.isocalendar()
        key = (iso_year, iso_week)

        per_week_hours.setdefault(resource_id, {}).setdefault(key, 0.0)
        per_week_hours[resource_id][key] += hours

        per_week_days.setdefault(resource_id, {}).setdefault(key, set())
        per_week_days[resource_id][key].add(entry.date)

        resource_dates.setdefault(resource_id, set()).add(entry.date)

    for resource_id, weekly_hours in per_week_hours.items():
        for (iso_year, iso_week), hours in weekly_hours.items():
            if hours > working_rules.max_hours_per_week:
                violations.append(
                    SchedulingViolation(
                        code="hours-per-week-exceeded",
                        message=(
                            f"Resource {resource_id} scheduled {hours:.1f}h "
                            f"in ISO week {iso_week}/{iso_year}, exceeding "
                            f"{working_rules.max_hours_per_week}h."
                        ),
                        severity="critical",
                        scope="week",
                        resource_id=resource_id,
                        iso_week=f"{iso_year}-W{iso_week:02d}",
                        meta={
                            "resource_id": resource_id,
                            "week": f"{iso_year}-W{iso_week}",
                            "hours": round(hours, 2),
                            "limit": working_rules.max_hours_per_week,
                        },
                    )
                )

    for resource_id, weekly_days in per_week_days.items():
        for (iso_year, iso_week), days in weekly_days.items():
            count = len(days)
            if count > working_rules.max_working_days_per_week:
                violations.append(
                    SchedulingViolation(
                        code="days-per-week-exceeded",
                        message=(
                            f"Resource {resource_id} works {count} days in ISO week {iso_week}/{iso_year}, "
                            f"limit is {working_rules.max_working_days_per_week}."
                        ),
                        severity="critical",
                        scope="week",
                        resource_id=resource_id,
                        iso_week=f"{iso_year}-W{iso_week:02d}",
                        meta={
                            "resource_id": resource_id,
                            "week": f"{iso_year}-W{iso_week}",
                            "days": count,
                            "limit": working_rules.max_working_days_per_week,
                        },
                    )
                )

    for resource_id, dates in resource_dates.items():
        max_streak = _longest_consecutive_stretch(sorted(dates))
        if max_streak > working_rules.max_consecutive_working_days:
            violations.append(
                SchedulingViolation(
                    code="consecutive-days-exceeded",
                    message=f"Resource {resource_id} works {max_streak} consecutive days; "
                    f"limit is {working_rules.max_consecutive_working_days}.",
                    severity="critical",
                    scope="resource",
                    resource_id=resource_id,
                    meta={"resource_id": resource_id, "streak": max_streak},
                )
            )

        required_off = working_rules.required_consecutive_days_off_per_month
        if not _has_consecutive_days_off(context.month, sorted(dates), required_off):
            violations.append(
                SchedulingViolation(
                    code="insufficient-consecutive-rest",
                    message=f"Resource {resource_id} does not have {required_off} consecutive days off in {context.month}.",
                    severity="warning",
                    scope="resource",
                    resource_id=resource_id,
                    meta={"resource_id": resource_id, "required_off": required_off},
                )
            )


def _longest_consecutive_stretch(sorted_dates: Iterable[date]) -> int:
    longest = 0
    current = 0
    previous: date | None = None

    for day in sorted_dates:
        if previous is not None and (day - previous).days == 1:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        previous = day
    return longest


def _has_consecutive_days_off(month: str, sorted_dates: Iterable[date], required_off: int) -> bool:
    if required_off <= 0:
        return True

    year, month_value = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, month_value)[1]
    working_days = set(sorted_dates)

    streak = 0
    for day in range(1, days_in_month + 1):
        current_day = date(year, month_value, day)
        if current_day not in working_days:
            streak += 1
            if streak >= required_off:
                return True
        else:
            streak = 0
    return False
def _select_shift_for_resource(
    resource: SchedulingResource, shifts: Sequence[SchedulingShift], assignment_index: int
) -> SchedulingShift | None:
    if not shifts:
        return None

    filtered_shifts = [shift for shift in shifts if shift.code not in set(resource.undesired_shift_codes)]
    preferred_shifts = [
        shift for shift in filtered_shifts if shift.code in set(resource.preferred_shift_codes)
    ]

    candidate_pool = preferred_shifts or filtered_shifts or list(shifts)
    return candidate_pool[assignment_index % len(candidate_pool)]


def _get_absence(resource: SchedulingResource, day: date) -> AbsenceWindow | None:
    for absence in resource.absences:
        if absence.start_date <= day <= absence.end_date:
            return absence
    return None


@lru_cache(maxsize=16)
def _weekday_cache() -> tuple[str, ...]:
    return ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _is_available(resource: SchedulingResource, day: date) -> bool:
    weekday = _weekday_cache()[day.weekday()]
    for window in resource.availability:
        if window.day == weekday:
            return window.is_available
    # Default to available if no template defined
    return True
