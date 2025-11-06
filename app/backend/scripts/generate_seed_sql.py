"""Generate raw SQL statements to seed the development database.

This script mirrors the data produced by ``seed_demo.py`` but writes plain SQL
so we can load it with ``psql`` even when direct Python connections are blocked.

Usage:
    PYTHONPATH=./src python scripts/generate_seed_sql.py > seed.sql
    psql postgresql://scheduler:scheduler@localhost:5432/kitchen_scheduler -f seed.sql
"""

from __future__ import annotations

import json
from datetime import date

from kitchen_scheduler.services.rules import load_default_rules
from kitchen_scheduler.services.scheduler import (
    AbsenceWindow,
    AvailabilityWindow,
    SchedulingContext,
    SchedulingResource,
    SchedulingShift,
    generate_rule_compliant_schedule,
)


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
            "preferred_shift_codes": [1, 8],
            "undesired_shift_codes": [10],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Bastien Favre",
            "role": "cook",
            "contract": 160,
            "availability_percent": 100,
            "language": "fr",
            "preferred_shift_codes": [1],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Camille Perret",
            "role": "cook",
            "contract": 150,
            "availability_percent": 90,
            "language": "fr",
            "preferred_shift_codes": [10],
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
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Estelle Girard",
            "role": "cook",
            "contract": 140,
            "availability_percent": 90,
            "language": "fr",
            "preferred_shift_codes": [8],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=4),
        },
        {
            "name": "Félix Monod",
            "role": "cook",
            "contract": 160,
            "availability_percent": 100,
            "language": "fr",
            "preferred_shift_codes": [1, 4],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Géraldine Weber",
            "role": "cook",
            "contract": 150,
            "availability_percent": 95,
            "language": "fr",
            "preferred_shift_codes": [1, 8],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Hugo Lambert",
            "role": "kitchen_assistant",
            "contract": 128,
            "availability_percent": 80,
            "language": "fr",
            "preferred_shift_codes": [],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Isabelle Morel",
            "role": "kitchen_assistant",
            "contract": 130,
            "availability_percent": 85,
            "language": "fr",
            "preferred_shift_codes": [8, 10],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Julien Mercier",
            "role": "kitchen_assistant",
            "contract": 120,
            "availability_percent": 75,
            "language": "fr",
            "preferred_shift_codes": [],
            "undesired_shift_codes": [4],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Karim Senn",
            "role": "pot_washer",
            "contract": 120,
            "availability_percent": 100,
            "language": "fr",
            "preferred_shift_codes": [10],
            "undesired_shift_codes": [],
            "availability_template": _weekday_template(workdays=5),
        },
        {
            "name": "Louise Hertig",
            "role": "pot_washer",
            "contract": 110,
            "availability_percent": 90,
            "language": "fr",
            "preferred_shift_codes": [],
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
            "preferred_shift_codes": [4, 10],
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


def main() -> None:
    current_month = date.today().strftime("%Y-%m")

    shifts = [
        {"code": 1, "description": "Standard morning shift", "start": "07:00", "end": "16:15", "hours": 9.25},
        {"code": 4, "description": "Long shift", "start": "07:15", "end": "19:15", "hours": 12.0},
        {"code": 8, "description": "Medium shift", "start": "08:00", "end": "17:15", "hours": 9.25},
        {"code": 10, "description": "Late shift", "start": "10:15", "end": "19:30", "hours": 9.25},
    ]

    shift_prime_rules = [
        (1, True),
        (4, False),
        (8, True),
        (10, True),
    ]

    resources = _build_resource_data()
    absences = _generate_absence_pairs(date.today().year)

    print("BEGIN;")
    print(
        "TRUNCATE TABLE "
        "planningentry, "
        "planversion, "
        "planscenario, "
        "monthlyparameters, "
        "resourceabsence, "
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
            )
        )

    for stmt in resource_absence_statements:
        print(stmt)

    print(
        "INSERT INTO monthlyparameters (month, contractual_hours, max_vacation_overlap, publication_deadline) "
        f"VALUES ('{current_month}', 160, 4, '{date.today().replace(day=15).isoformat()}');"
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
        "INSERT INTO planversion (id, scenario_id, version_label, published_at, published_by, summary_hours) "
        f"VALUES (1, 1, 'v1', NULL, NULL, '{_escape(summary_json)}');"
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
