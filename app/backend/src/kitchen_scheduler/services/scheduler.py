from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Iterable, Literal, Optional, Sequence

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

ROLE_RULE_KEY_MAP: dict[str, str] = {
    "pot_washer": "pot_washers",
    "kitchen_assistant": "kitchen_assistants",
    "apprentice": "apprentices",
    "cook": "cooks",
    "relief_cook": "cooks",
}


def _role_rule_key(role: str) -> str:
    return ROLE_RULE_KEY_MAP.get(role, role)


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

    resource_role_map = {resource.id: _role_rule_key(resource.role) for resource in context.resources}
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
        if entry.absence_type:
            continue
        day_totals[entry.date] = day_totals.get(entry.date, 0) + 1
        role = resource_role_map.get(entry.resource_id)
        if role is None:
            continue
        rule_key = _role_rule_key(role)
        role_totals.setdefault(entry.date, {})
        role_totals[entry.date][rule_key] = role_totals[entry.date].get(rule_key, 0) + 1

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


def generate_rule_compliant_schedule(context: SchedulingContext) -> SchedulingResult:
    """Produce a deterministic schedule that respects core working-time rules."""

    role_shift_map = {
        "pot_washer": 10,
        "kitchen_assistant": 8,
        "apprentice": 1,
        "cook": 1,
        "relief_cook": 1,
    }
    role_requirements = [
        ("pot_washers", 1, 2),
        ("kitchen_assistants", 2, 2),
        ("apprentices", 1, 2),
    ]
    daily_target = max(context.rules.rules.shift_rules.minimum_daily_staff, 9)

    year, month = map(int, context.month.split("-"))
    current_day = date(year, month, 1)
    month_days: list[date] = []
    while current_day.month == month:
        month_days.append(current_day)
        current_day += timedelta(days=1)

    role_to_resources: dict[str, list[SchedulingResource]] = defaultdict(list)
    for resource in context.resources:
        role_key = _role_rule_key(resource.role)
        role_to_resources[role_key].append(resource)

    consecutive_pairs = [
        (month_days[index], month_days[index + 1])
        for index in range(len(month_days) - 1)
        if month_days[index + 1].month == month
    ]

    rest_map: dict[int, set[date]] = defaultdict(set)
    if consecutive_pairs:
        available_indices = list(range(len(consecutive_pairs)))

        def assign_pair(resource_id: int, index_value: int) -> None:
            pair = consecutive_pairs[index_value]
            rest_map[resource_id].update(pair)
            if index_value in available_indices:
                available_indices.remove(index_value)

        preferred_indices = {
            "pot_washers": [0, 14],
            "kitchen_assistants": [4, 10, 16],
            "apprentices": [6, 22],
        }

        for role_key, indices in preferred_indices.items():
            resources_for_role = role_to_resources.get(role_key, [])
            for resource, index_value in zip(resources_for_role, indices, strict=False):
                idx = index_value % len(consecutive_pairs)
                assign_pair(resource.id, idx)

        idx_iter = iter(available_indices)
        for resources_for_role in role_to_resources.values():
            for resource in resources_for_role:
                if resource.id in rest_map:
                    continue
                try:
                    idx = next(idx_iter)
                except StopIteration:
                    idx = available_indices[-1] if available_indices else 0
                assign_pair(resource.id, idx)

    shift_lookup = {shift.code: shift for shift in context.shifts}

    stats = {
        resource.id: {
            "assignments": 0,
            "weekly_hours": defaultdict(float),
            "weekly_days": defaultdict(int),
            "last_day": None,
            "consecutive": 0,
        }
        for resource in context.resources
    }

    def choose_shift(resource: SchedulingResource) -> SchedulingShift | None:
        code = role_shift_map.get(resource.role, 1)
        return shift_lookup.get(code) or (context.shifts[0] if context.shifts else None)

    def can_assign(resource: SchedulingResource, day_obj: date, shift: SchedulingShift | None) -> bool:
        if shift is None:
            return False
        if day_obj in rest_map.get(resource.id, set()):
            return False
        if _get_absence(resource, day_obj):
            return False
        if not _is_available(resource, day_obj):
            return False

        iso_year, iso_week, _ = day_obj.isocalendar()
        week_key = (iso_year, iso_week)
        stat = stats[resource.id]

        if (
            stat["weekly_hours"][week_key] + float(shift.hours)
            > context.rules.rules.working_time.max_hours_per_week
        ):
            return False
        max_days_allowed = max(1, context.rules.rules.working_time.max_working_days_per_week - 1)
        if stat["weekly_days"][week_key] >= max_days_allowed:
            return False
        last_day: date | None = stat["last_day"]
        if last_day is not None and (day_obj - last_day).days == 1:
            if stat["consecutive"] >= context.rules.rules.working_time.max_consecutive_working_days:
                return False
        return True

    def register_assignment(resource: SchedulingResource, day_obj: date, shift: SchedulingShift) -> None:
        iso_year, iso_week, _ = day_obj.isocalendar()
        week_key = (iso_year, iso_week)
        stat = stats[resource.id]
        stat["assignments"] += 1
        stat["weekly_hours"][week_key] += float(shift.hours)
        stat["weekly_days"][week_key] += 1
        last_day: date | None = stat["last_day"]
        if last_day is not None and (day_obj - last_day).days == 1:
            stat["consecutive"] += 1
        else:
            stat["consecutive"] = 1
        stat["last_day"] = day_obj

    def sorted_candidates(resources_list: list[SchedulingResource], iso_key: tuple[int, int]) -> list[SchedulingResource]:
        return sorted(
            resources_list,
            key=lambda res: (
                stats[res.id]["weekly_days"][iso_key],
                stats[res.id]["assignments"],
                res.id,
            ),
        )

    entries: list[PlanningEntryRead] = []

    for day_obj in month_days:
        iso_year, iso_week, _ = day_obj.isocalendar()
        iso_key = (iso_year, iso_week)
        assigned_ids: set[int] = set()
        role_counts: dict[str, int] = defaultdict(int)
        resting_resources = {
            resource.id
            for resource in context.resources
            if day_obj in rest_map.get(resource.id, set())
        }

        def assign_for_role(
            role_key: str,
            allow_extra: bool = False,
            *,
            week_key=iso_key,
            assigned=assigned_ids,
            rest=resting_resources,
            target_day=day_obj,
            counts=role_counts,
        ) -> bool:
            candidates = sorted_candidates(role_to_resources.get(role_key, []), week_key)
            composition = context.rules.rules.shift_rules.composition.get(role_key)
            for resource in candidates:
                if resource.id in assigned:
                    continue
                if resource.id in rest:
                    continue
                shift = choose_shift(resource)
                if not can_assign(resource, target_day, shift):
                    continue
                current = counts[role_key]
                if composition and composition.max is not None and current >= composition.max:
                    if not allow_extra:
                        return False
                    continue
                assigned.add(resource.id)
                register_assignment(resource, target_day, shift)
                counts[role_key] += 1
                entries.append(
                    PlanningEntryRead(
                        id=len(entries) + 1,
                        resource_id=resource.id,
                        date=target_day,
                        shift_code=shift.code,
                        absence_type=None,
                        comment="AUTO-COMPLIANT",
                    )
                )
                return True
            return False

        for role_key, minimum, _maximum in role_requirements:
            for _ in range(minimum):
                assign_for_role(role_key)

        priority_roles = ["cooks", "kitchen_assistants", "apprentices", "pot_washers"]
        while len(assigned_ids) < daily_target:
            filled = False
            for role_key in priority_roles:
                composition = context.rules.rules.shift_rules.composition.get(role_key)
                if composition and composition.max is not None and role_counts[role_key] >= composition.max:
                    continue
                if assign_for_role(role_key, allow_extra=True):
                    filled = True
                    break
            if not filled:
                break

        for resource_id in resting_resources:
            if resource_id in assigned_ids:
                continue
            entries.append(
                PlanningEntryRead(
                    id=len(entries) + 1,
                    resource_id=resource_id,
                    date=day_obj,
                    shift_code=None,
                    absence_type="rest_day",
                    comment="AUTO-COMPLIANT",
                )
            )

    violations = evaluate_rule_violations(context, entries)
    return SchedulingResult(entries=entries, violations=violations)
