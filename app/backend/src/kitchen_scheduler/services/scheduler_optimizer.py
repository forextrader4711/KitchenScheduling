from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Tuple

from ortools.sat.python import cp_model

from kitchen_scheduler.services.scheduler import (
    ROLE_ALLOWED_SHIFT_CODES,
    SchedulingContext,
    SchedulingResult,
    SchedulingShift,
    SchedulingViolation,
    AbsenceWindow,
    SchedulingResource,
    PlanningEntryRead,
    _iter_month_days,
    _resource_available_on_day,
    _get_absence,
    _role_rule_key,
    evaluate_rule_violations,
    PRIME_SHIFT_BASE,
)

HOURS_SCALE = 4  # quarter-hour precision


@dataclass
class OptimizerConfig:
    overtime_penalty: int = 15
    undertime_penalty: int = 20
    undesired_shift_penalty: int = 30
    relief_shift_penalty: int = 50
    late_hours_threshold: int = 46  # hours per ISO week before penalties
    late_hours_penalty: int = 10
    prime_optional_penalty: int = 20


def _scaled(hours: float) -> int:
    return int(round(hours * HOURS_SCALE))


def generate_optimised_schedule(context: SchedulingContext, config: OptimizerConfig | None = None) -> SchedulingResult:
    if config is None:
        config = OptimizerConfig()

    year, month_number = map(int, context.month.split("-"))
    month_days = list(_iter_month_days(year, month_number))
    if not month_days:
        return SchedulingResult(entries=[], violations=[])

    shift_map: Dict[int, SchedulingShift] = {shift.code: shift for shift in context.shifts}
    max_daily_units = max((_scaled(shift.hours) for shift in context.shifts), default=_scaled(12.0))
    max_month_units = len(month_days) * max_daily_units if max_daily_units else 0

    model = cp_model.CpModel()

    # Variable containers
    shift_vars: Dict[Tuple[int, int, int], cp_model.IntVar] = {}
    available_codes: Dict[Tuple[int, int], List[int]] = {}
    off_vars: Dict[Tuple[int, int], cp_model.IntVar] = {}
    work_vars: Dict[Tuple[int, int], cp_model.IntVar] = {}
    hour_vars: Dict[Tuple[int, int], cp_model.IntVar] = {}
    objective_terms: List[cp_model.LinearExpr] = []

    # Helper caches
    absence_cache: Dict[Tuple[int, date], AbsenceWindow | None] = {}
    availability_cache: Dict[Tuple[int, date], bool] = {}

    def is_available(resource: SchedulingResource, target_day: date) -> bool:
        cache_key = (resource.id, target_day)
        if cache_key not in availability_cache:
            availability_cache[cache_key] = _resource_available_on_day(resource, target_day)
        return availability_cache[cache_key]

    def get_absence(resource: SchedulingResource, target_day: date) -> AbsenceWindow | None:
        cache_key = (resource.id, target_day)
        if cache_key not in absence_cache:
            absence_cache[cache_key] = _get_absence(resource, target_day)
        return absence_cache[cache_key]

    # Build decision variables
    for resource in context.resources:
        allowed_codes = set(ROLE_ALLOWED_SHIFT_CODES.get(resource.role, shift_map.keys()))
        available_shift_codes = sorted(code for code in allowed_codes if code in shift_map)
        for day_index, day in enumerate(month_days):
            key = (resource.id, day_index)
            absence = get_absence(resource, day)
            available = is_available(resource, day) and absence is None

            off_var = model.NewBoolVar(f"off_r{resource.id}_d{day_index}")
            work_var = model.NewBoolVar(f"work_r{resource.id}_d{day_index}")
            hour_var = model.NewIntVar(0, max_daily_units, f"hours_r{resource.id}_d{day_index}")

            off_vars[key] = off_var
            work_vars[key] = work_var
            hour_vars[key] = hour_var

            if not available:
                # Forced off day (either absence or not available)
                model.Add(off_var == 1)
                model.Add(work_var == 0)
                model.Add(hour_var == 0)
                continue

            # Build shift decision vars
            vars_for_day: List[cp_model.IntVar] = []
            expression_terms: List[Tuple[int, cp_model.IntVar]] = []
            available_codes[key] = available_shift_codes.copy()

            for shift_code in available_shift_codes:
                shift_var = model.NewBoolVar(f"x_r{resource.id}_d{day_index}_s{shift_code}")
                shift_vars[(resource.id, day_index, shift_code)] = shift_var
                vars_for_day.append(shift_var)
                expression_terms.append((_scaled(shift_map[shift_code].hours), shift_var))

            # Exactly one status: working on a shift or off
            model.Add(sum(vars_for_day) + off_var == 1)
            model.Add(work_var == sum(vars_for_day))

            if expression_terms:
                model.Add(hour_var == sum(coeff * var for coeff, var in expression_terms))
            else:
                model.Add(hour_var == 0)
                model.Add(off_var == 1)
                model.Add(work_var == 0)

    # Coverage constraints
    shift_rules = context.rules.rules.shift_rules
    working_rules = context.rules.rules.working_time

    for day_index, _day in enumerate(month_days):
        day_work_vars: List[cp_model.IntVar] = []
        role_work_vars: Dict[str, List[cp_model.IntVar]] = defaultdict(list)
        pot_washer_shift_early: List[cp_model.IntVar] = []
        pot_washer_shift_late: List[cp_model.IntVar] = []

        for resource in context.resources:
            key = (resource.id, day_index)
            work_var = work_vars[key]
            day_work_vars.append(work_var)

            role_key = _role_rule_key(resource.role)
            role_work_vars[role_key].append(work_var)

            if role_key == "pot_washers":
                early_shifts = [shift_vars.get((resource.id, day_index, code)) for code in (8, 18)]
                late_shifts = [shift_vars.get((resource.id, day_index, code)) for code in (10, 101)]
                pot_washer_shift_early.extend([var for var in early_shifts if var is not None])
                pot_washer_shift_late.extend([var for var in late_shifts if var is not None])

        total_staff = model.NewIntVar(0, len(context.resources), f"total_day_{day_index}")
        model.Add(total_staff == sum(day_work_vars))
        model.Add(total_staff >= shift_rules.minimum_daily_staff)

        for role_key, variables in role_work_vars.items():
            total_role = model.NewIntVar(0, len(variables), f"role_{role_key}_day_{day_index}")
            model.Add(total_role == sum(variables))

            role_composition = shift_rules.composition.get(role_key)
            if role_composition:
                if role_composition.min is not None and role_composition.min > 0:
                    model.Add(total_role >= role_composition.min)
                if role_composition.max is not None:
                    model.Add(total_role <= role_composition.max)

        # Pot washer pairing rule
        if pot_washer_shift_early and pot_washer_shift_late:
            total_pot_washers = model.NewIntVar(0, len(pot_washer_shift_early) + len(pot_washer_shift_late), f"pot_total_{day_index}")
            model.Add(total_pot_washers == sum(pot_washer_shift_early + pot_washer_shift_late))
            has_two = model.NewBoolVar(f"pot_two_{day_index}")
            model.Add(total_pot_washers >= 2).OnlyEnforceIf(has_two)
            model.Add(total_pot_washers <= 1).OnlyEnforceIf(has_two.Not())
            model.Add(sum(pot_washer_shift_early) >= 1).OnlyEnforceIf(has_two)
            model.Add(sum(pot_washer_shift_late) >= 1).OnlyEnforceIf(has_two)

    # Working-time constraints per resource
    iso_week_to_days: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    day_to_iso: Dict[int, Tuple[int, int]] = {}
    for index, day in enumerate(month_days):
        iso_year, iso_week, _ = day.isocalendar()
        iso_key = (iso_year, iso_week)
        iso_week_to_days[iso_key].append(index)
        day_to_iso[index] = iso_key

    for resource in context.resources:
        total_hours = model.NewIntVar(0, max_month_units, f"total_hours_{resource.id}")
        model.Add(total_hours == sum(hour_vars[(resource.id, day_index)] for day_index in range(len(month_days))))

        # Weekly hour and day caps
        for iso_key, days in iso_week_to_days.items():
            week_hours = model.NewIntVar(0, len(days) * max_daily_units, f"week_hours_r{resource.id}_{iso_key[0]}_{iso_key[1]}")
            model.Add(week_hours == sum(hour_vars[(resource.id, day_index)] for day_index in days))
            model.Add(week_hours <= _scaled(working_rules.max_hours_per_week))

            week_days = model.NewIntVar(0, len(days), f"week_days_r{resource.id}_{iso_key[0]}_{iso_key[1]}")
            model.Add(week_days == sum(work_vars[(resource.id, day_index)] for day_index in days))
            model.Add(week_days <= working_rules.max_working_days_per_week)

            overtime_threshold = _scaled(config.late_hours_threshold)
            if overtime_threshold > 0:
                overtime_var = model.NewIntVar(0, len(days) * max_daily_units, f"week_over_{resource.id}_{iso_key[0]}_{iso_key[1]}")
                model.Add(overtime_var >= week_hours - overtime_threshold)
                model.Add(overtime_var >= 0)
                objective_terms.append(overtime_var * config.late_hours_penalty)

        # Consecutive day limit
        limit = working_rules.max_consecutive_working_days
        if limit > 0:
            for start in range(len(month_days) - limit):
                window = [work_vars[(resource.id, idx)] for idx in range(start, start + limit + 1)]
                model.Add(sum(window) <= limit)

        # Required rest block
        required_rest = working_rules.required_consecutive_days_off_per_month
        if required_rest > 1 and required_rest <= len(month_days):
            rest_block_vars = []
            for start in range(len(month_days) - required_rest + 1):
                rest_block = model.NewBoolVar(f"rest_r{resource.id}_{start}")
                for offset in range(required_rest):
                    work_var = work_vars[(resource.id, start + offset)]
                    model.Add(work_var == 0).OnlyEnforceIf(rest_block)
                rest_block_vars.append(rest_block)
            if rest_block_vars:
                model.Add(sum(rest_block_vars) >= 1)

        # Monthly hour deviation (soft objective)
        if resource.target_hours is not None:
            target_units = _scaled(resource.target_hours)
            tolerance_units = _scaled(12.0)
            lower_bound = target_units - tolerance_units if target_units > tolerance_units else 0
            model.Add(total_hours <= target_units + tolerance_units)
            model.Add(total_hours >= lower_bound)
            deviation_pos = model.NewIntVar(0, max_month_units, f"dev_pos_{resource.id}")
            deviation_neg = model.NewIntVar(0, max_month_units, f"dev_neg_{resource.id}")
            model.Add(total_hours - target_units == deviation_pos - deviation_neg)
            objective_terms.append(deviation_pos * config.overtime_penalty)
            objective_terms.append(deviation_neg * config.undertime_penalty)
        else:
            # Relief cooks: small penalty on hours to discourage use
            objective_terms.append(total_hours * config.relief_shift_penalty)

        # Shift preference penalties
        undesired = set(resource.undesired_shift_codes or [])
        for day_index in range(len(month_days)):
            for shift_code in undesired:
                var = shift_vars.get((resource.id, day_index, shift_code))
                if var is not None:
                    objective_terms.append(var * config.undesired_shift_penalty)
            for prime_code, base_code in PRIME_SHIFT_BASE.items():
                var_prime = shift_vars.get((resource.id, day_index, prime_code))
                if var_prime is not None:
                    objective_terms.append(var_prime * config.prime_optional_penalty)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_search_workers = 8
    if objective_terms:
        model.Minimize(cp_model.LinearExpr.Sum(objective_terms))
    else:
        model.Minimize(0)

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Fallback to heuristic if optimizer cannot find a solution
        return SchedulingResult(entries=[], violations=[SchedulingViolation(
            code="optimizer-failed",
            message="Optimizer could not find a feasible schedule.",
            severity="critical",
        )])

    entries: List[PlanningEntryRead] = []
    entry_id = 1

    for resource in context.resources:
        for day_index, day in enumerate(month_days):
            absence = get_absence(resource, day)
            key = (resource.id, day_index)
            work_var = work_vars[key]
            if solver.Value(work_var) <= 0:
                if absence:
                    entries.append(
                        PlanningEntryRead(
                            id=entry_id,
                            resource_id=resource.id,
                            date=day,
                            shift_code=None,
                            absence_type=absence.absence_type,
                            comment=absence.comment or "OPT-ABSENCE",
                        )
                    )
                    entry_id += 1
                continue

            assigned_shift = None
            for shift_code in available_codes.get((resource.id, day_index), []):
                var = shift_vars.get((resource.id, day_index, shift_code))
                if var is not None and solver.Value(var) > 0:
                    assigned_shift = shift_code
                    break

            if assigned_shift is None:
                continue

            entries.append(
                PlanningEntryRead(
                    id=entry_id,
                    resource_id=resource.id,
                    date=day,
                    shift_code=assigned_shift,
                    absence_type=None,
                    comment="OPT-ASSIGN",
                )
            )
            entry_id += 1

    violations = evaluate_rule_violations(context, entries)
    return SchedulingResult(entries=entries, violations=violations)
