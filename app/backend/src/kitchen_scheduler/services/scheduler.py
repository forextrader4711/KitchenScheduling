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
    target_hours: float | None = None
    is_relief: bool = False


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
    target_hours: float | None = None
    monthly_hours: float = 0.0
    is_relief: bool = False

ROLE_RULE_KEY_MAP: dict[str, str] = {
    "pot_washer": "pot_washers",
    "kitchen_assistant": "kitchen_assistants",
    "apprentice": "apprentices",
    "cook": "cooks",
    "relief_cook": "cooks",
}


ROLE_ALLOWED_SHIFT_CODES: dict[str, set[int]] = {
    "cook": {1, 4},
    "relief_cook": {1, 4},
    "kitchen_assistant": {1, 8, 10},
    "apprentice": {1},
    "pot_washer": {8, 10},
}

PRIME_SHIFT_BASE: dict[int, int] = {11: 1, 18: 8, 101: 10}
BASE_TO_PRIME_SHIFT: dict[int, int] = {base: prime for prime, base in PRIME_SHIFT_BASE.items()}

ROLE_SELECTION_PRIORITY: dict[str, int] = {
    "cook": 0,
    "relief_cook": 1,
    "kitchen_assistant": 2,
    "apprentice": 3,
    "pot_washer": 4,
}

MONTHLY_OVERRUN_TOLERANCE = 2.0


def _role_rule_key(role: str) -> str:
    return ROLE_RULE_KEY_MAP.get(role, role)


def daily_staff_target(context: SchedulingContext) -> int:
    shift_rules = context.rules.rules.shift_rules
    min_staff = shift_rules.minimum_daily_staff
    available = max(len(context.resources), min_staff)
    if available <= min_staff:
        return min_staff
    return min_staff + 1 if available > min_staff else min_staff


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
            target_hours=resource.target_hours,
            is_relief=resource.is_relief,
        )
        for resource in context.resources
    }

    _apply_mandatory_rest_days(resource_states, month_days, working_rules)

    role_composition = shift_rules.composition
    role_minimums = {role: (data.min or 0) for role, data in role_composition.items()}
    role_maximums = {role: data.max for role, data in role_composition.items()}
    role_order = list(role_composition.keys())
    shift_lookup = {shift.code: shift for shift in context.shifts}
    daily_target = daily_staff_target(context)

    entry_id = 1

    for day_index, current_day in enumerate(month_days):
        iso_year, iso_week, _ = current_day.isocalendar()
        iso_key = (iso_year, iso_week)

        assigned_today: set[int] = set()
        role_counts: dict[str, int] = defaultdict(int)
        role_shift_assignments: dict[str, list[int]] = defaultdict(list)

        def _eligible_states(
            target_role: str | None = None,
            *,
            allow_extra_pot_washers: bool = True,
            allow_over_target: bool = False,
        ) -> list[tuple[_ResourceScheduleState, SchedulingShift]]:
            options: list[tuple[_ResourceScheduleState, SchedulingShift]] = []
            for state in resource_states.values():
                if state.resource.id in assigned_today:
                    continue
                if target_role and state.rule_role != target_role:
                    continue
                if (
                    target_role is None
                    and not allow_extra_pot_washers
                    and state.rule_role == "pot_washers"
                    and role_counts[state.rule_role] >= 1
                ):
                    continue
                if not _resource_available_on_day(state.resource, current_day):
                    continue
                if current_day in state.forced_rest_days:
                    continue
                allowed_codes = ROLE_ALLOWED_SHIFT_CODES.get(state.resource.role)
                preferred_sequence: list[int] | None = None
                if state.rule_role == "pot_washers":
                    assigned_codes = role_shift_assignments[state.rule_role]
                    early_count = sum(code == 8 for code in assigned_codes)
                    late_count = sum(code == 10 for code in assigned_codes)
                    if early_count <= late_count:
                        preferred_sequence = [8, 10]
                    else:
                        preferred_sequence = [10, 8]
                shift = _select_shift_for_resource(
                    state.resource,
                    context.shifts,
                    state.total_assignments,
                    allowed_codes=allowed_codes,
                    preferred_sequence=preferred_sequence,
                )
                if not shift:
                    continue
                if (
                    not allow_over_target
                    and state.target_hours is not None
                    and state.monthly_hours + float(shift.hours)
                    > state.target_hours + MONTHLY_OVERRUN_TOLERANCE
                ):
                    continue
                if not _can_assign_with_shift(state, shift, iso_key, working_rules):
                    continue
                options.append((state, shift))
            return options

        def _select_candidate(options: list[tuple[_ResourceScheduleState, SchedulingShift]]) -> tuple[_ResourceScheduleState, SchedulingShift] | None:
            if not options:
                return None

            best_option: tuple[_ResourceScheduleState, SchedulingShift] | None = None
            best_score = float("inf")

            for state, shift in options:
                score = _assignment_cost(
                    state=state,
                    shift=shift,
                    iso_key=iso_key,
                    working_rules=working_rules,
                    role_counts=role_counts,
                    role_minimums=role_minimums,
                    role_maximums=role_maximums,
                    shift_lookup=shift_lookup,
                    current_assignments=len(assigned_today),
                    daily_target=daily_target,
                )
                if score < best_score:
                    best_score = score
                    best_option = (state, shift)

            return best_option

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
            role_shift_assignments[state.rule_role].append(shift.code)

            state.total_assignments += 1
            state.consecutive_days += 1
            state.weekly_days[iso_key] = state.weekly_days.get(iso_key, 0) + 1
            state.weekly_hours[iso_key] = state.weekly_hours.get(iso_key, 0.0) + float(shift.hours)
            state.monthly_hours += float(shift.hours)

            entry_id += 1

        # Step 1: satisfy minimums per role.
        for role in role_order:
            required_min = role_minimums.get(role, 0)
            while role_counts[role] < required_min:
                candidate = _select_candidate(_eligible_states(role, allow_over_target=True))
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

        def _has_deficit(state: _ResourceScheduleState) -> bool:
            if state.target_hours is None:
                return False
            return state.target_hours - state.monthly_hours > 4.0

        def _fill_day(target: int) -> None:
            while len(assigned_today) < target:
                candidates = [
                    option
                    for option in _eligible_states(allow_extra_pot_washers=False)
                    if _role_can_accept(option[0])
                ]
                if not candidates:
                    candidates = [
                        option
                        for option in _eligible_states(allow_extra_pot_washers=True)
                        if _role_can_accept(option[0])
                    ]
                if not candidates:
                    candidates = [
                        option
                        for option in _eligible_states(allow_extra_pot_washers=True)
                    ]
                if not candidates:
                    candidates = [
                        option
                        for option in _eligible_states(
                            allow_extra_pot_washers=True, allow_over_target=True
                        )
                    ]
                if not candidates:
                    break
                best = _select_candidate(candidates)
                if not best:
                    break
                _assign(*best)

        _fill_day(shift_rules.minimum_daily_staff)

        linear_target = max(shift_rules.minimum_daily_staff, daily_target)
        if len(assigned_today) < linear_target:
            _fill_day(linear_target)

        max_daily_staff = min(len(resource_states), linear_target + 1)
        while len(assigned_today) < max_daily_staff:
            candidates = [
                option
                for option in _eligible_states(allow_extra_pot_washers=True)
                if _has_deficit(option[0]) and _role_can_accept(option[0])
            ]
            if not candidates:
                break
            best = _select_candidate(candidates)
            if not best:
                break
            _assign(*best)

        # Step 3: reset consecutive counters for anyone who did not work today.
        for state in resource_states.values():
            if state.resource.id not in assigned_today:
                state.consecutive_days = 0

    apply_prime_shift_relaxation(context, entries)
    violations = evaluate_rule_violations(context, entries)
    return SchedulingResult(entries=entries, violations=violations)


def _assignment_cost(
    *,
    state: _ResourceScheduleState,
    shift: SchedulingShift,
    iso_key: tuple[int, int],
    working_rules,
    role_counts: dict[str, int],
    role_minimums: dict[str, int],
    role_maximums: dict[str, int | None],
    shift_lookup: dict[int, SchedulingShift],
    current_assignments: int,
    daily_target: int,
) -> float:
    """
    Compute a weighted score representing how undesirable it is to assign `state`
    to `shift` on the current day. Lower scores are preferred.
    """

    score = 0.0
    hours = float(shift.hours)
    projected_hours = state.monthly_hours + hours
    target_hours = state.target_hours

    # Encourage filling role shortfalls and penalise oversupply.
    current_role_total = role_counts.get(state.rule_role, 0)
    role_min = role_minimums.get(state.rule_role, 0)
    role_max = role_maximums.get(state.rule_role)
    if current_role_total < role_min:
        score -= 40.0 * (role_min - current_role_total)
    elif role_max is not None and current_role_total >= role_max:
        score += 80.0 * (current_role_total - role_max + 1)

    # Fairness and workload balancing.
    if target_hours is not None:
        deficit = max(0.0, target_hours - projected_hours)
        overage = max(0.0, projected_hours - target_hours)
        if deficit > 0:
            score -= min(deficit, hours) * 45.0
        if overage > 0:
            score += overage * 25.0

    # Weekly hours safeguard (approach the 50h hard limit cautiously).
    next_weekly_hours = state.weekly_hours.get(iso_key, 0.0) + hours
    weekly_buffer = max(0.0, next_weekly_hours - 46.0)
    score += weekly_buffer * 20.0

    # Consecutive day fatigue – push back before the hard limit triggers.
    next_consecutive = state.consecutive_days + 1
    fatigue_threshold = max(0, working_rules.max_consecutive_working_days - 1)
    if next_consecutive > fatigue_threshold:
        score += (next_consecutive - fatigue_threshold) * 65.0

    # Weekly days count – avoid hitting the 6-day cap too early.
    next_weekly_days = state.weekly_days.get(iso_key, 0) + 1
    if next_weekly_days >= working_rules.max_working_days_per_week:
        score += 140.0

    # Shift preferences.
    if shift.code in (state.resource.undesired_shift_codes or []):
        score += 60.0
    if shift.code in (state.resource.preferred_shift_codes or []):
        score -= 30.0

    # Pot washer rotation: gently discourage assigning a second pot washer unless needed.
    if state.rule_role == "pot_washers" and role_counts.get(state.rule_role, 0) >= 1:
        score += 40.0
    prime_base = PRIME_SHIFT_BASE.get(shift.code)
    if prime_base is not None:
        base_shift = shift_lookup.get(prime_base)
        if base_shift:
            base_hours = float(base_shift.hours)
            projected_week_with_base = state.weekly_hours.get(iso_key, 0.0) + base_hours
            projected_month_with_base = state.monthly_hours + base_hours
            exceeds_week = projected_week_with_base > working_rules.max_hours_per_week
            exceeds_target = (
                state.target_hours is not None
                and projected_month_with_base > (state.target_hours + 2)
            )
            if not exceeds_week and not exceeds_target:
                score += 30.0
    if state.target_hours is not None and projected_hours > state.target_hours + MONTHLY_OVERRUN_TOLERANCE:
        score += (projected_hours - state.target_hours) * 120.0
    if state.is_relief:
        score += 120.0

    # Small tie-breaker on total assignments to spread workload.
    score += state.total_assignments * 2.0
    score += ROLE_SELECTION_PRIORITY.get(state.resource.role, 99)

    projected_day_total = current_assignments + 1
    if projected_day_total > max(daily_target, 0):
        score += (projected_day_total - daily_target) * 75.0

    return score


def apply_prime_shift_relaxation(context: SchedulingContext, entries: list[PlanningEntryRead]) -> None:
    weekly_limit = context.rules.rules.working_time.max_hours_per_week
    if weekly_limit <= 0 or not entries:
        return
    shift_hours = {shift.code: float(shift.hours) for shift in context.shifts}
    if not shift_hours:
        return
    base_to_prime = {
        base: prime for base, prime in BASE_TO_PRIME_SHIFT.items() if base in shift_hours and prime in shift_hours
    }
    if not base_to_prime:
        return

    resource_lookup = {resource.id: resource for resource in context.resources}
    weekly_totals: dict[tuple[int, int, int], float] = defaultdict(float)
    weekly_candidates: dict[tuple[int, int, int], list[tuple[float, int, int]]] = defaultdict(list)
    monthly_totals: dict[int, float] = defaultdict(float)
    monthly_candidates: dict[int, list[tuple[float, int, int]]] = defaultdict(list)

    for index, entry in enumerate(entries):
        if entry.shift_code is None:
            continue
        hours = shift_hours.get(entry.shift_code, 0.0)
        iso_year, iso_week, _ = entry.date.isocalendar()
        week_key = (entry.resource_id, iso_year, iso_week)
        weekly_totals[week_key] += hours
        monthly_totals[entry.resource_id] += hours
        prime_code = base_to_prime.get(entry.shift_code)
        if prime_code is None:
            continue
        delta = hours - shift_hours.get(prime_code, hours)
        if delta <= 0:
            continue
        weekly_candidates[week_key].append((delta, index, prime_code))
        monthly_candidates[entry.resource_id].append((delta, index, prime_code))

    def _mark_conversion(idx: int, prime_code: int) -> float:
        entry = entries[idx]
        if entry.shift_code == prime_code:
            return 0.0
        base_code = entry.shift_code
        base_hours = shift_hours.get(base_code, 0.0)
        prime_hours = shift_hours.get(prime_code, base_hours)
        if base_hours <= prime_hours:
            return 0.0
        entry.shift_code = prime_code
        base_comment = entry.comment or "AUTO-STUB"
        lower_comment = base_comment.lower()
        if "prime adjustment" not in lower_comment:
            entry.comment = f"{base_comment} (prime adjustment)"
        return base_hours - prime_hours

    for key, options in weekly_candidates.items():
        total = weekly_totals.get(key, 0.0)
        if total <= weekly_limit:
            continue
        options.sort(key=lambda item: item[0], reverse=True)
        for _delta, idx, prime_code in options:
            if total <= weekly_limit:
                break
            delta = _mark_conversion(idx, prime_code)
            if delta <= 0:
                continue
            total -= delta
            weekly_totals[key] = total
            resource_id = entries[idx].resource_id
            monthly_totals[resource_id] -= delta

    for resource_id, options in monthly_candidates.items():
        resource = resource_lookup.get(resource_id)
        target = getattr(resource, "target_hours", None)
        if target is None:
            continue
        target_limit = target + MONTHLY_OVERRUN_TOLERANCE
        total = monthly_totals.get(resource_id, 0.0)
        if total <= target_limit:
            continue
        options.sort(key=lambda item: item[0], reverse=True)
        for _delta, idx, prime_code in options:
            if total <= target_limit:
                break
            delta = _mark_conversion(idx, prime_code)
            if delta <= 0:
                continue
            total -= delta
            monthly_totals[resource_id] = total
            iso_year, iso_week, _ = entries[idx].date.isocalendar()
            week_key = (resource_id, iso_year, iso_week)
            weekly_totals[week_key] = max(weekly_totals.get(week_key, 0.0) - delta, 0.0)


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
    if total_days < required:
        return set()

    midpoint = total_days / 2
    candidate_windows: list[tuple[float, int, list[date]]] = []

    for idx in range(total_days - required + 1):
        window = month_days[idx : idx + required]
        if not all(_resource_available_on_day(resource, day) for day in window):
            continue
        center = idx + required / 2
        edge_penalty = 2 if idx == 0 or idx + required == total_days else 0
        score = abs(center - midpoint) + edge_penalty
        candidate_windows.append((score, idx, list(window)))

    if not candidate_windows:
        return set()

    candidate_windows.sort(key=lambda item: (item[0], item[1]))
    selection_index = resource.id % len(candidate_windows)
    selected = candidate_windows[selection_index][2]
    return set(selected)


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
    resource: SchedulingResource,
    shifts: Sequence[SchedulingShift],
    assignment_index: int,
    *,
    allowed_codes: set[int] | None = None,
    preferred_sequence: list[int] | None = None,
) -> SchedulingShift | None:
    if not shifts:
        return None

    allowed_set = allowed_codes if allowed_codes else None
    undesired_codes = set(resource.undesired_shift_codes or [])
    preferred_codes = set(resource.preferred_shift_codes or [])

    def within_allowed(shift: SchedulingShift) -> bool:
        return allowed_set is None or shift.code in allowed_set

    candidates = [shift for shift in shifts if within_allowed(shift)]
    if not candidates:
        candidates = list(shifts)

    filtered_candidates = [shift for shift in candidates if shift.code not in undesired_codes]
    preferred_candidates = [shift for shift in filtered_candidates if shift.code in preferred_codes]

    def sequence_key(shift: SchedulingShift, fallback: int) -> tuple[int, int]:
        if preferred_sequence and shift.code in preferred_sequence:
            return (preferred_sequence.index(shift.code), shift.code)
        return (fallback, shift.code)

    if preferred_sequence:
        preferred_candidates.sort(key=lambda shift: sequence_key(shift, len(preferred_sequence)))
        filtered_candidates.sort(key=lambda shift: sequence_key(shift, len(preferred_sequence)))
        candidates.sort(key=lambda shift: sequence_key(shift, len(preferred_sequence) + 1))

    pool = preferred_candidates or filtered_candidates or candidates
    if not pool:
        return None

    return pool[assignment_index % len(pool)]


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
