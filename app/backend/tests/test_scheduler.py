from kitchen_scheduler.schemas.resource import PlanningEntryRead
from kitchen_scheduler.services.rules import load_default_rules
from kitchen_scheduler.services.scheduler import SchedulingContext, generate_stub_schedule


def test_generate_stub_schedule_creates_entries_and_violations() -> None:
    rule_set = load_default_rules()
    context = SchedulingContext(
        month="2024-11",
        resources=[{"id": 1, "role": "cook"}],
        shifts=[{"code": 1}],
        rules=rule_set,
    )

    result = generate_stub_schedule(context)

    assert result.entries, "stub scheduler should create entries"
    assert all(isinstance(entry, PlanningEntryRead) for entry in result.entries)

    # With only one resource per day, minimum staffing rule should trigger.
    assert any(violation.code == "staffing-shortfall" for violation in result.violations)
