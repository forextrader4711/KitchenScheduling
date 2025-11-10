"""Generate raw SQL statements to seed the development database.

This script mirrors the data produced by ``seed_demo.py`` but writes plain SQL
so we can load it with ``psql`` even when direct Python connections are blocked.

Usage:
    PYTHONPATH=./src python scripts/generate_seed_sql.py [--month YYYY-MM] > seed.sql
    psql postgresql://scheduler:scheduler@localhost:5432/kitchen_scheduler -f seed.sql
"""

from __future__ import annotations

import argparse
import calendar
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from itertools import cycle

from kitchen_scheduler.services.rules import load_default_rules
from kitchen_scheduler.services.scheduler import (
    AbsenceWindow,
    AvailabilityWindow,
    ROLE_ALLOWED_SHIFT_CODES,
    SchedulingContext,
    SchedulingResource,
    SchedulingShift,
    evaluate_rule_violations,
    generate_rule_compliant_schedule,
)
from kitchen_scheduler.schemas.resource import PlanningEntryRead
from kitchen_scheduler.services.holidays import get_vaud_public_holidays


def _validate_month(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError as exc:  # pragma: no cover - defensive
        raise argparse.ArgumentTypeError("Month must be formatted as YYYY-MM") from exc
    return value


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate SQL seed data for the kitchen scheduler demo dataset."
    )
    parser.add_argument(
        "--month",
        type=_validate_month,
        default=date.today().strftime("%Y-%m"),
        help="Target month in YYYY-MM format (defaults to the current month).",
    )
    return parser.parse_args()


def _weekday_template(*, workdays: int, weekend: bool = False) -> list[dict]:
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    weekend_days = ["saturday", "sunday"] if weekend else []
    active_days = list(weekdays[:workdays])
    active_days += weekend_days

    template = []
    for day in weekdays + weekend_days:
        template.append(
            {
                "day": day,
                "is_available": day in active_days,
                "start_time": "07:15" if day in active_days else None,
                "end_time": "19:15" if day in active_days else None,
            }
        )
    return template


def _build_resource_data() -> list[dict]:
    return [
        {
            "name": "Alice Dupont",
            "role": "cook",
            "contract": 160,
            "availability_percent": 100,
            "language": "fr",
            "preferred_shift_codes": [1, 11, 8, 18],
            "undesired_shift_codes": [10, 101],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Bastien Favre",
            "role": "cook",
            "contract": 160,
            "availability_percent": 100,
            "language": "fr",
            "preferred_shift_codes": [1, 11],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Camille Perret",
            "role": "cook",
            "contract": 150,
            "availability_percent": 90,
            "language": "fr",
            "preferred_shift_codes": [11],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=4, weekend=True),
        },
        {
            "name": "David Roux",
            "role": "cook",
            "contract": 160,
            "availability_percent": 100,
            "language": "fr",
            "preferred_shift_codes": [4],
            "undesired_shift_codes": [1],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Estelle Girard",
            "role": "cook",
            "contract": 140,
            "availability_percent": 90,
            "language": "fr",
            "preferred_shift_codes": [1, 11],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=4, weekend=True),
        },
        {
            "name": "Félix Monod",
            "role": "cook",
            "contract": 160,
            "availability_percent": 100,
            "language": "fr",
            "preferred_shift_codes": [1, 11, 4],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Géraldine Weber",
            "role": "cook",
            "contract": 150,
            "availability_percent": 95,
            "language": "fr",
            "preferred_shift_codes": [1, 11],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Hugo Lambert",
            "role": "kitchen_assistant",
            "contract": 128,
            "availability_percent": 80,
            "language": "fr",
            "preferred_shift_codes": [],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Isabelle Morel",
            "role": "kitchen_assistant",
            "contract": 130,
            "availability_percent": 85,
            "language": "fr",
            "preferred_shift_codes": [8, 18, 10, 101],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Julien Mercier",
            "role": "kitchen_assistant",
            "contract": 120,
            "availability_percent": 75,
            "language": "fr",
            "preferred_shift_codes": [8, 18, 10, 101],
            "undesired_shift_codes": [4],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Karim Senn",
            "role": "pot_washer",
            "contract": 120,
            "availability_percent": 100,
            "language": "fr",
            "preferred_shift_codes": [8, 18, 10, 101],
            "undesired_shift_codes": [4],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Louise Hertig",
            "role": "pot_washer",
            "contract": 110,
            "availability_percent": 90,
            "language": "fr",
            "preferred_shift_codes": [8, 18, 10, 101],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5, weekend=True),
        },
        {
            "name": "Maël Schneider",
            "role": "apprentice",
            "contract": 100,
            "availability_percent": 60,
            "language": "fr",
            "preferred_shift_codes": [1],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Nina Clément",
            "role": "apprentice",
            "contract": 110,
            "availability_percent": 70,
            "language": "fr",
            "preferred_shift_codes": [],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Olivier Rey",
            "role": "relief_cook",
            "contract": 80,
            "availability_percent": 50,
            "language": "fr",
            "preferred_shift_codes": [1, 11, 4],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=3, weekend=True),
        },
    ]


def _generate_absence_pairs(year: int) -> list[tuple[str, date, date]]:
    return [
        ("vacation", date(year, 2, 12), date(year, 2, 16)),
        ("vacation", date(year, 4, 8), date(year, 4, 12)),
        ("training", date(year, 5, 20), date(year, 5, 24)),
        ("sick_leave", date(year, 6, 3), date(year, 6, 5)),
        ("vacation", date(year, 7, 15), date(year, 7, 26)),
        ("vacation", date(year, 8, 19), date(year, 8, 23)),
        ("training", date(year, 9, 9), date(year, 9, 13)),
        ("vacation", date(year, 10, 14), date(year, 10, 18)),
        ("sick_leave", date(year, 11, 4), date(year, 11, 8)),
    ]


def _escape(value: str) -> str:
    return value.replace("'", "''")


def _ensure_pot_washer_pairs(
    entries: list[PlanningEntryRead],
    resources: list[SchedulingResource],
    month: str,
    max_pair_days: int = 6,
) -> list[PlanningEntryRead]:
    pot_resources = [resource for resource in resources if resource.role == "pot_washer"]
    if len(pot_resources) < 2:
        return entries

    pot_ids = [resource.id for resource in pot_resources]
    entries_by_day: dict[date, list[PlanningEntryRead]] = defaultdict(list)
    for entry in entries:
        entries_by_day[entry.date].append(entry)

    assignment_cycle = cycle(
        [
            ((pot_ids[0], 8), (pot_ids[1], 10)),
            ((pot_ids[0], 10), (pot_ids[1], 8)),
        ]
    )

    enforced_days = 0
    updated_entries: list[PlanningEntryRead] = []

    for day in sorted(entries_by_day.keys()):
        assignments = entries_by_day[day]
        if day.weekday() >= 5:
            updated_entries.extend(assignments)
            continue

        pot_entries = [
            entry
            for entry in assignments
            if entry.resource_id in pot_ids and entry.shift_code is not None
        ]

        desired_pair = next(assignment_cycle)

        if len(pot_entries) >= 2:
            existing_map = {entry.resource_id: entry for entry in pot_entries}
            retained = [entry for entry in assignments if entry.resource_id not in pot_ids]
            for resource_id, shift_code in desired_pair:
                existing = existing_map.get(resource_id)
                if existing:
                    retained.append(
                        PlanningEntryRead(
                            id=existing.id,
                            resource_id=existing.resource_id,
                            date=existing.date,
                            shift_code=shift_code,
                            absence_type=existing.absence_type,
                            comment=existing.comment or "AUTO-SEED",
                        )
                    )
            for entry in pot_entries:
                if entry.resource_id not in {resource_id for resource_id, _ in desired_pair}:
                    retained.append(entry)
            updated_entries.extend(retained)
            continue

        if len(pot_entries) == 1 and enforced_days < max_pair_days:
            existing = pot_entries[0]
            other_pot = next(resource for resource in pot_resources if resource.id != existing.resource_id)
            if _is_resource_available(other_pot, day):
                retained = [entry for entry in assignments if entry != existing]
                retained.append(
                    PlanningEntryRead(
                        id=existing.id,
                        resource_id=existing.resource_id,
                        date=existing.date,
                        shift_code=desired_pair[0][1] if desired_pair[0][0] == existing.resource_id else desired_pair[1][1],
                        absence_type=existing.absence_type,
                        comment=existing.comment or "AUTO-SEED",
                    )
                )
                retained.append(
                    PlanningEntryRead(
                        id=0,
                        resource_id=other_pot.id,
                        date=day,
                        shift_code=desired_pair[0][1] if desired_pair[0][0] == other_pot.id else desired_pair[1][1],
                        absence_type=None,
                        comment="AUTO-SEED",
                    )
                )
                updated_entries.extend(retained)
                enforced_days += 1
                continue

        updated_entries.extend(assignments)

    updated_entries.sort(key=lambda entry: (entry.date, entry.resource_id))
    return updated_entries


def _working_day_dates(month: str) -> list[date]:
    year_str, month_str = month.split("-")
    year = int(year_str)
    month_num = int(month_str)
    start = date(year, month_num, 1)
    last_day = calendar.monthrange(year, month_num)[1]
    end = date(year, month_num, last_day)

    holidays = {
        holiday.date
        for holiday in get_vaud_public_holidays(year)
        if start <= holiday.date <= end
    }

    working_days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holidays:
            working_days.append(current)
        current += timedelta(days=1)
    return working_days


def _all_month_days(month: str) -> list[date]:
    year_str, month_str = month.split("-")
    year = int(year_str)
    month_num = int(month_str)
    last_day = calendar.monthrange(year, month_num)[1]
    start = date(year, month_num, 1)
    return [start + timedelta(days=offset) for offset in range(last_day)]


def _is_resource_available(resource: SchedulingResource, target_day: date) -> bool:
    for absence in resource.absences:
        if absence.start_date <= target_day <= absence.end_date:
            return False

    weekday_name = target_day.strftime("%A").lower()
    for window in resource.availability:
        if window.day == weekday_name:
            return window.is_available
    return False


def _select_shift_code(
    resource: SchedulingResource,
    shift_lookup: dict[int, SchedulingShift],
) -> int | None:
    allowed = ROLE_ALLOWED_SHIFT_CODES.get(resource.role, set(shift_lookup.keys()))
    allowed_codes = [code for code in allowed if code in shift_lookup]
    if not allowed_codes:
        allowed_codes = list(shift_lookup.keys())

    undesired = set(resource.undesired_shift_codes or [])
    preferred = [
        code
        for code in (resource.preferred_shift_codes or [])
        if code in allowed_codes and code not in undesired
    ]

    candidates = preferred or [code for code in allowed_codes if code not in undesired] or allowed_codes
    if not candidates:
        return None

    candidates.sort(key=lambda code: shift_lookup[code].hours, reverse=True)
    return candidates[0]


def _ensure_minimum_hours(
    entries: list[PlanningEntryRead],
    resources: list[SchedulingResource],
    shifts: list[SchedulingShift],
    month: str,
    contract_hours: dict[int, float],
) -> list[PlanningEntryRead]:
    shift_lookup = {shift.code: shift for shift in shifts}
    working_days = _working_day_dates(month)
    monthly_due_hours = len(working_days) * 8.3

    hours_per_resource: dict[int, float] = defaultdict(float)
    day_assignments: dict[date, dict[int, PlanningEntryRead]] = defaultdict(dict)

    for entry in entries:
        day_assignments[entry.date][entry.resource_id] = entry
        if entry.shift_code is not None and entry.shift_code in shift_lookup:
            hours_per_resource[entry.resource_id] += float(shift_lookup[entry.shift_code].hours)

    additions: list[PlanningEntryRead] = []

    for resource in resources:
        contract_target = contract_hours.get(resource.id, 0.0)
        target_hours = max(contract_target, monthly_due_hours)
        if target_hours <= 0:
            continue

        current_hours = hours_per_resource.get(resource.id, 0.0)
        if current_hours >= target_hours:
            continue

        available_days = [
            day
            for day in working_days
            if resource.id not in day_assignments.get(day, {})
            and _is_resource_available(resource, day)
        ]

        for day in available_days:
            if current_hours >= target_hours:
                break

            shift_code = _select_shift_code(resource, shift_lookup)
            if shift_code is None:
                break

            shift = shift_lookup[shift_code]
            entry = PlanningEntryRead(
                id=0,
                resource_id=resource.id,
                date=day,
                shift_code=shift_code,
                absence_type=None,
                comment="AUTO-CONTRACT",
            )

            additions.append(entry)
            day_assignments.setdefault(day, {})[resource.id] = entry
            current_hours += float(shift.hours)

        hours_per_resource[resource.id] = current_hours

    combined = entries + additions
    combined.sort(key=lambda entry: (entry.date, entry.resource_id))
    return combined


def _ensure_daily_staffing(
    entries: list[PlanningEntryRead],
    resources: list[SchedulingResource],
    shifts: list[SchedulingShift],
    month: str,
    minimum_daily_staff: int,
) -> list[PlanningEntryRead]:
    if minimum_daily_staff <= 0:
        return entries

    shift_lookup = {shift.code: shift for shift in shifts}
    days = _all_month_days(month)
    entries_by_day: dict[date, list[PlanningEntryRead]] = defaultdict(list)
    hours_per_resource: dict[int, float] = defaultdict(float)
    role_priority = {
        "cook": 0,
        "relief_cook": 1,
        "kitchen_assistant": 2,
        "apprentice": 3,
        "pot_washer": 4,
    }

    for entry in entries:
        entries_by_day[entry.date].append(entry)
        if entry.shift_code is not None and entry.shift_code in shift_lookup:
            hours_per_resource[entry.resource_id] += float(shift_lookup[entry.shift_code].hours)

    updated_entries = list(entries)

    for day in days:
        assigned_entries = entries_by_day.get(day, [])
        assigned_ids = {
            entry.resource_id
            for entry in assigned_entries
            if entry.shift_code is not None
        }

        if len(assigned_ids) >= minimum_daily_staff:
            continue

        candidates = [
            resource
            for resource in resources
            if resource.id not in assigned_ids and _is_resource_available(resource, day)
        ]

        candidates.sort(
            key=lambda res: (
                hours_per_resource.get(res.id, 0.0),
                role_priority.get(res.role, 5),
                res.id,
            )
        )

        for resource in candidates:
            if len(assigned_ids) >= minimum_daily_staff:
                break

            shift_code = _select_shift_code(resource, shift_lookup)
            if shift_code is None:
                continue

            entry = PlanningEntryRead(
                id=0,
                resource_id=resource.id,
                date=day,
                shift_code=shift_code,
                absence_type=None,
                comment="AUTO-DAILY",
            )

            updated_entries.append(entry)
            entries_by_day.setdefault(day, []).append(entry)
            assigned_ids.add(resource.id)
            hours_per_resource[resource.id] += float(shift_lookup[shift_code].hours)

    updated_entries.sort(key=lambda entry: (entry.date, entry.resource_id))
    return updated_entries


def main() -> None:
    args = _parse_args()
    current_month = args.month
    month_anchor = datetime.strptime(f"{current_month}-01", "%Y-%m-%d").date()
    working_day_list = _working_day_dates(current_month)
    due_hours = len(working_day_list) * 8.3

    shifts = [
        {"code": 1, "description": "Standard morning shift", "start": "07:00", "end": "16:15", "hours": 9.25},
        {"code": 4, "description": "Long shift", "start": "07:15", "end": "19:15", "hours": 12.0},
        {"code": 8, "description": "Medium shift", "start": "08:00", "end": "17:15", "hours": 9.25},
        {"code": 10, "description": "Late shift", "start": "10:15", "end": "19:30", "hours": 9.25},
        {"code": 11, "description": "Standard morning shift (prime)", "start": "08:00", "end": "16:15", "hours": 8.25},
        {
            "code": 18,
            "description": "Medium shift (prime)",
            "start": "09:00",
            "end": "17:15",
            "hours": 8.25,
        },
        {
            "code": 101,
            "description": "Late shift (prime)",
            "start": "11:15",
            "end": "19:30",
            "hours": 8.25,
        },
    ]

    shift_prime_rules = [
        (1, True),
        (4, False),
        (8, True),
        (10, True),
        (11, True),
        (18, True),
        (101, True),
    ]

    resources = _build_resource_data()
    absences = _generate_absence_pairs(month_anchor.year)

    print("BEGIN;")
    print(
        "TRUNCATE TABLE "
        "planningentry, "
        "planversion, "
        "planscenario, "
        "monthlyparameters, "
        "resourceabsence, "
        "resource_monthly_balance, "
        "\"resource\", "
        "shiftprimerule, "
        "shift "
        "RESTART IDENTITY CASCADE;"
    )

    for shift in shifts:
        print(
            f"INSERT INTO shift (code, description, start, \"end\", hours) "
            f"VALUES ({shift['code']}, '{_escape(shift['description'])}', '{shift['start']}', "
            f"'{shift['end']}', {shift['hours']});"
        )

    for code, allowed in shift_prime_rules:
        allowed_text = "true" if allowed else "false"
        print(
            "INSERT INTO shiftprimerule (shift_code, allowed) "
            f"VALUES ({code}, {allowed_text});"
        )

    resource_absence_statements: list[str] = []
    scheduling_resources: list[SchedulingResource] = []
    contract_hours: dict[int, float] = {}

    for idx, resource in enumerate(resources, start=1):
        availability_json = json.dumps(resource["availability_template"])
        preferred_json = json.dumps(resource["preferred_shift_codes"])
        undesired_json = json.dumps(resource["undesired_shift_codes"])

        print(
            "INSERT INTO resource "
            "(id, name, role, availability_percent, contract_hours_per_month, "
            "preferred_days_off, vacation_days, language, notes, availability_template, "
            "preferred_shift_codes, undesired_shift_codes) VALUES "
            f"({idx}, '{_escape(resource['name'])}', '{resource['role']}', "
            f"{resource['availability_percent']}, {resource['contract']}, "
            "NULL, NULL, "
            f"'{resource['language']}', NULL, "
            f"'{availability_json}'::jsonb, '{preferred_json}'::jsonb, '{undesired_json}'::jsonb);"
        )

        absence_type, start_date, end_date = absences[(idx - 1) % len(absences)]
        resource_absence_statements.append(
            "INSERT INTO resourceabsence (resource_id, start_date, end_date, absence_type, comment) "
            f"VALUES ({idx}, '{start_date.isoformat()}', '{end_date.isoformat()}', "
            f"'{absence_type}', '{absence_type.replace('_', ' ').title()} (demo)');"
        )

        scheduling_resources.append(
            SchedulingResource(
                id=idx,
                role=resource["role"],
                availability=[
                    AvailabilityWindow(
                        day=window["day"],
                        is_available=window["is_available"],
                        start_time=window["start_time"],
                        end_time=window["end_time"],
                    )
                    for window in resource["availability_template"]
                ],
                preferred_shift_codes=list(resource["preferred_shift_codes"]),
                undesired_shift_codes=list(resource["undesired_shift_codes"]),
                absences=[
                    AbsenceWindow(
                        start_date=start_date,
                        end_date=end_date,
                        absence_type=absence_type,
                        comment=f"{absence_type.replace('_', ' ').title()} (demo)",
                    )
                ],
                target_hours=due_hours if resource["role"] != "relief_cook" else None,
                is_relief=resource["role"] == "relief_cook",
            )
        )
        contract_hours[idx] = float(resource["contract"])

    for stmt in resource_absence_statements:
        print(stmt)

    print(
        "INSERT INTO monthlyparameters (month, contractual_hours, max_vacation_overlap, publication_deadline) "
        f"VALUES ('{current_month}', 160, 4, '{month_anchor.replace(day=15).isoformat()}');"
    )

    rule_set = load_default_rules()
    scheduling_shifts = [
        SchedulingShift(
            code=shift["code"],
            description=shift["description"],
            start=shift["start"],
            end=shift["end"],
            hours=shift["hours"],
        )
        for shift in shifts
    ]

    context = SchedulingContext(
        month=current_month,
        resources=scheduling_resources,
        shifts=scheduling_shifts,
        rules=rule_set,
    )

    result = generate_rule_compliant_schedule(context)
    result.entries = _ensure_minimum_hours(
        result.entries,
        scheduling_resources,
        scheduling_shifts,
        current_month,
        contract_hours,
    )
    minimum_daily_staff = rule_set.rules.shift_rules.minimum_daily_staff or 0
    result.entries = _ensure_daily_staffing(
        result.entries,
        scheduling_resources,
        scheduling_shifts,
        current_month,
        minimum_daily_staff,
    )
    result.entries = _ensure_pot_washer_pairs(
        result.entries,
        scheduling_resources,
        current_month,
    )
    result.violations = evaluate_rule_violations(context, result.entries)

    print(
        "INSERT INTO planscenario (id, month, name, status, created_at, updated_at, violations) "
        f"VALUES (1, '{current_month}', 'Draft Scenario', 'draft', CURRENT_TIMESTAMP, "
        "CURRENT_TIMESTAMP, '%s'::jsonb);"
        % _escape(
            json.dumps(
                [
                    {
                        "code": violation.code,
                        "message": violation.message,
                        "severity": violation.severity,
                        "meta": violation.meta,
                        "scope": violation.scope,
                        "day": violation.day.isoformat() if violation.day else None,
                        "resource_id": violation.resource_id,
                        "iso_week": violation.iso_week,
                    }
                    for violation in result.violations
                ]
            )
        )
    )

    total_entries = len(result.entries)
    total_violations = len(result.violations)
    critical_violations = len([v for v in result.violations if v.severity == "critical"])
    summary_json = json.dumps(
        {
            "entries": total_entries,
            "violations": total_violations,
            "critical_violations": critical_violations,
        }
    )

    print(
        "INSERT INTO planversion (scenario_id, version_label, published_at, published_by, summary_hours) "
        f"VALUES (1, 'v1', NULL, NULL, '{_escape(summary_json)}');"
    )

    for idx, entry in enumerate(result.entries, start=1):
        shift_code = entry.shift_code if entry.shift_code is not None else "NULL"
        absence_value = (
            f"'{entry.absence_type}'" if entry.absence_type is not None else "NULL"
        )
        comment = entry.comment if entry.comment else ""
        print(
            "INSERT INTO planningentry (id, resource_id, shift_code, date, absence_type, comment, scenario_id) "
            f"VALUES ({idx}, {entry.resource_id}, {shift_code}, "
            f"'{entry.date.isoformat()}', {absence_value}, '{_escape(comment)}', 1);"
        )

    print("COMMIT;")


if __name__ == "__main__":
    main()
