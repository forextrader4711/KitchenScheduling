import pytest
from httpx import AsyncClient

from .factories import build_scenario_create


@pytest.mark.anyio("asyncio")
async def test_plan_scenario_api_crud(api_client: AsyncClient) -> None:
    payload = build_scenario_create().model_dump()

    create_response = await api_client.post("/api/planning/scenarios", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    scenario_id = created["id"]
    assert created["month"] == payload["month"]

    list_response = await api_client.get("/api/planning/scenarios")
    assert list_response.status_code == 200
    scenarios = list_response.json()
    assert len(scenarios) == 1
    assert scenarios[0]["id"] == scenario_id

    update_response = await api_client.put(
        f"/api/planning/scenarios/{scenario_id}",
        json={"name": "Updated Scenario", "status": "published"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Updated Scenario"
    assert updated["status"] == "published"

    delete_response = await api_client.delete(f"/api/planning/scenarios/{scenario_id}")
    assert delete_response.status_code == 204

    list_after_delete = await api_client.get("/api/planning/scenarios")
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []


@pytest.mark.anyio("asyncio")
async def test_plan_generation_response(api_client: AsyncClient) -> None:
    await api_client.post(
        "/api/planning/scenarios",
        json={"month": "2024-11", "name": "Auto", "status": "draft", "entries": []},
    )

    response = await api_client.post("/api/planning/generate", json={"month": "2024-11"})
    assert response.status_code == 200
    payload = response.json()

    assert "entries" in payload and isinstance(payload["entries"], list)
    assert "violations" in payload and isinstance(payload["violations"], list)
    if payload["entries"]:
        first_entry = payload["entries"][0]
        assert {"id", "resource_id", "date"}.issubset(first_entry.keys())

    scenarios_response = await api_client.get("/api/planning/scenarios")
    assert scenarios_response.status_code == 200
    scenarios = scenarios_response.json()
    assert scenarios
    first_scenario = scenarios[0]
    if first_scenario["month"] == "2024-11":
        assert first_scenario.get("violations") is not None
        versions_response = await api_client.get(f"/api/planning/scenarios/{first_scenario['id']}/versions")
        assert versions_response.status_code == 200
        versions = versions_response.json()
        assert versions


@pytest.mark.anyio("asyncio")
async def test_generate_for_specific_scenario(api_client: AsyncClient) -> None:
    create_response = await api_client.post(
        "/api/planning/scenarios",
        json={"month": "2024-12", "name": "December draft", "status": "draft", "entries": []},
    )
    assert create_response.status_code == 201
    scenario_id = create_response.json()["id"]

    response = await api_client.post(f"/api/planning/scenarios/{scenario_id}/generate")
    assert response.status_code == 200
    payload = response.json()
    assert "entries" in payload

    scenario_response = await api_client.get("/api/planning/scenarios")
    data = scenario_response.json()
    target = [item for item in data if item["id"] == scenario_id][0]
    assert target.get("violations") is not None
    versions_response = await api_client.get(f"/api/planning/scenarios/{scenario_id}/versions")
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert versions and versions[0]["version_label"].startswith("v")
