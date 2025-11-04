from kitchen_scheduler.services.rules import load_default_rules


def test_load_default_rules() -> None:
    rule_set = load_default_rules()

    working_time = rule_set.rules.working_time
    assert working_time.max_hours_per_week == 50
    assert "Saturday + Sunday" in working_time.days_off_patterns

    shift_rules = rule_set.rules.shift_rules
    assert shift_rules.minimum_daily_staff == 7
    assert shift_rules.composition["pot_washers"].min == 1

    vacations = rule_set.rules.vacations_and_absences
    assert vacations.max_concurrent_vacations == 4
