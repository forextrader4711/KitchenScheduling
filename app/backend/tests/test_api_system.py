import pytest
from httpx import AsyncClient

from kitchen_scheduler.services.rules import load_default_rules

from .factories import build_monthly_parameters_create


@pytest.mark.anyio("asyncio")
async def test_monthly_parameters_api_crud(api_client: AsyncClient) -> None:
    payload = build_monthly_parameters_create().model_dump(mode="json")

    create_response = await api_client.post("/api/system/monthly-parameters", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    parameters_id = created["id"]
    assert created["month"] == payload["month"]

    list_response = await api_client.get("/api/system/monthly-parameters")
    assert list_response.status_code == 200
    records = list_response.json()
    assert len(records) == 1
    assert records[0]["id"] == parameters_id

    update_response = await api_client.put(
        f"/api/system/monthly-parameters/{parameters_id}",
        json={"max_vacation_overlap": 4},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["max_vacation_overlap"] == 4

    delete_response = await api_client.delete(f"/api/system/monthly-parameters/{parameters_id}")
    assert delete_response.status_code == 204

    list_after_delete = await api_client.get("/api/system/monthly-parameters")
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []


@pytest.mark.anyio("asyncio")
async def test_rule_config_api(api_client: AsyncClient) -> None:
    # active endpoint should bootstrap default rules
    active_response = await api_client.get("/api/system/rules/active")
    assert active_response.status_code == 200
    active_data = active_response.json()
    assert active_data["rules"]["working_time"]["max_hours_per_week"] == 50

    base_rules = load_default_rules().rules.model_copy(deep=True)
    base_rules.working_time.max_hours_per_week = 45
    payload = {
        "name": "Adjusted November Rules",
        "version": "v2",
        "rules": base_rules.model_dump(),
        "is_active": True,
    }

    create_response = await api_client.post("/api/system/rules", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["version"] == "v2"
    assert created["rules"]["working_time"]["max_hours_per_week"] == 45

    update_response = await api_client.put(
        f"/api/system/rules/{created['id']}",
        json={"version": "v2.1", "is_active": True},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["version"] == "v2.1"

    # requesting active rules again should reflect latest version
    final_active = await api_client.get("/api/system/rules/active")
    assert final_active.status_code == 200
    assert final_active.json()["version"] == "v2.1"
