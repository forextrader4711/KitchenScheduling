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


@dataclass
class _ResourceScheduleState:
    resource: SchedulingResource
    rule_role: str
    weekly_days: dict[tuple[int, int], int] = field(default_factory=dict)
    weekly_hours: dict[tuple[int, int], float] = field(default_factory=dict)
    consecutive_days: int = 0
    total_assignments: int = 0
    forced_rest_days: set[date] = field(default_factory=set)

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
    Heuristic planner that prioritises working-time safety constraints and then
    fills daily staffing requirements where possible.
    """
    year, month = map(int, context.month.split("-"))
    month_days = list(_iter_month_days(year, month))
    entries: list[PlanningEntryRead] = []

    if not context.resources or not context.shifts:
        return SchedulingResult(entries=entries, violations=[])

    working_rules = context.rules.rules.working_time
    shift_rules = context.rules.rules.shift_rules

    resource_states: dict[int, _ResourceScheduleState] = {
        resource.id: _ResourceScheduleState(
            resource=resource,
            rule_role=_role_rule_key(resource.role),
        )
        for resource in context.resources
    }

    _apply_mandatory_rest_days(resource_states, month_days, working_rules)

    role_composition = shift_rules.composition
    role_minimums = {role: (data.min or 0) for role, data in role_composition.items()}
    role_maximums = {role: data.max for role, data in role_composition.items()}
    role_order = list(role_composition.keys())

    entry_id = 1

    for current_day in month_days:
        iso_year, iso_week, _ = current_day.isocalendar()
        iso_key = (iso_year, iso_week)

        assigned_today: set[int] = set()
        role_counts: dict[str, int] = defaultdict(int)

        def _eligible_states(target_role: str | None = None) -> list[tuple[_ResourceScheduleState, SchedulingShift]]:
            options: list[tuple[_ResourceScheduleState, SchedulingShift]] = []
            for state in resource_states.values():
                if state.resource.id in assigned_today:
                    continue
                if target_role and state.rule_role != target_role:
                    continue
                if not _resource_available_on_day(state.resource, current_day):
                    continue
                if current_day in state.forced_rest_days:
                    continue
                shift = _select_shift_for_resource(state.resource, context.shifts, state.total_assignments)
                if not shift:
                    continue
                if not _can_assign_with_shift(state, shift, iso_key, working_rules):
                    continue
                options.append((state, shift))
            return options

        def _select_candidate(options: list[tuple[_ResourceScheduleState, SchedulingShift]]) -> tuple[_ResourceScheduleState, SchedulingShift] | None:
            if not options:
                return None

            def _score(item: tuple[_ResourceScheduleState, SchedulingShift]) -> tuple:
                state, shift = item
                weekly_days = state.weekly_days.get(iso_key, 0)
                weekly_hours = state.weekly_hours.get(iso_key, 0.0)
                role_priority = (
                    0 if state.resource.role == "cook" else 1 if state.resource.role == "relief_cook" else 2
                )
                return (
                    weekly_days,
                    weekly_hours,
                    state.consecutive_days,
                    role_priority,
                    state.total_assignments,
                    shift.hours,
                )

            options.sort(key=_score)
            return options[0]

        def _assign(state: _ResourceScheduleState, shift: SchedulingShift) -> None:
            nonlocal entry_id
            entry = PlanningEntryRead(
                id=entry_id,
                resource_id=state.resource.id,
                date=current_day,
                shift_code=shift.code,
                absence_type=None,
                comment="AUTO-STUB",
            )
            entries.append(entry)
            assigned_today.add(state.resource.id)
            role_counts[state.rule_role] += 1

            state.total_assignments += 1
            state.consecutive_days += 1
            state.weekly_days[iso_key] = state.weekly_days.get(iso_key, 0) + 1
            state.weekly_hours[iso_key] = state.weekly_hours.get(iso_key, 0.0) + float(shift.hours)

            entry_id += 1

        # Step 1: satisfy minimums per role.
        for role in role_order:
            required_min = role_minimums.get(role, 0)
            while role_counts[role] < required_min:
                candidate = _select_candidate(_eligible_states(role))
                if not candidate:
                    break
                _assign(*candidate)

        # Step 2: fill remaining slots up to minimum daily staff.
        def _role_can_accept(state: _ResourceScheduleState) -> bool:
            role_key = state.rule_role
            role_max = role_maximums.get(role_key)
            if role_max is not None and role_counts[role_key] >= role_max:
                return False
            return True

        while len(assigned_today) < shift_rules.minimum_daily_staff:
            candidates = [
                option
                for option in _eligible_states()
                if _role_can_accept(option[0])
            ]
            if not candidates:
                break
            candidates.sort(
                key=lambda item: (
                    0 if item[0].resource.role == "cook" else 1 if item[0].resource.role == "relief_cook" else 2,
                    item[0].weekly_days.get(iso_key, 0),
                    item[0].total_assignments,
                )
            )
            _assign(*candidates[0])

        # Step 3: reset consecutive counters for anyone who did not work today.
        for state in resource_states.values():
            if state.resource.id not in assigned_today:
                state.consecutive_days = 0

    violations = evaluate_rule_violations(context, entries)
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


def _iter_month_days(year: int, month: int) -> Iterable[date]:
    current = date(year, month, 1)
    while current.month == month:
        yield current
        current += timedelta(days=1)


def _resource_available_on_day(resource: SchedulingResource, target_day: date) -> bool:
    if _get_absence(resource, target_day):
        return False
    return _is_available(resource, target_day)


def _can_assign_with_shift(
    state: _ResourceScheduleState,
    shift: SchedulingShift,
    iso_key: tuple[int, int],
    working_rules,
) -> bool:
    next_weekly_days = state.weekly_days.get(iso_key, 0) + 1
    next_weekly_hours = state.weekly_hours.get(iso_key, 0.0) + float(shift.hours)

    if working_rules.max_working_days_per_week and next_weekly_days > working_rules.max_working_days_per_week:
        return False
    if working_rules.max_hours_per_week and next_weekly_hours > working_rules.max_hours_per_week:
        return False
    if working_rules.max_consecutive_working_days and state.consecutive_days + 1 > working_rules.max_consecutive_working_days:
        return False
    return True


def _apply_mandatory_rest_days(
    resource_states: dict[int, _ResourceScheduleState],
    month_days: Sequence[date],
    working_rules,
) -> None:
    required_rest = working_rules.required_consecutive_days_off_per_month
    if required_rest <= 1:
        return

    for state in resource_states.values():
        if _existing_rest_block(state.resource, month_days, required_rest):
            continue
        forced_rest = _select_rest_window(state.resource, month_days, required_rest)
        if forced_rest:
            state.forced_rest_days.update(forced_rest)


def _existing_rest_block(resource: SchedulingResource, month_days: Sequence[date], required: int) -> bool:
    streak = 0
    for day in month_days:
        if not _resource_available_on_day(resource, day):
            streak += 1
            if streak >= required:
                return True
        else:
            streak = 0
    return False


def _select_rest_window(resource: SchedulingResource, month_days: Sequence[date], required: int) -> set[date]:
    total_days = len(month_days)
    for idx in range(total_days - required + 1):
        window = month_days[idx : idx + required]
        if all(_resource_available_on_day(resource, day) for day in window):
            return set(window)
    return set()


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

    return generate_stub_schedule(context)
