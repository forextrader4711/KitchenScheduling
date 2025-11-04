import pytest
from httpx import AsyncClient

from .factories import build_shift_create


@pytest.mark.anyio("asyncio")
async def test_shift_api_crud(api_client: AsyncClient) -> None:
    payload = build_shift_create().model_dump()

    create_response = await api_client.post("/api/shifts/", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["code"] == payload["code"]

    list_response = await api_client.get("/api/shifts/")
    assert list_response.status_code == 200
    shifts = list_response.json()
    assert len(shifts) == 1
    assert shifts[0]["code"] == payload["code"]

    update_response = await api_client.put(
        f"/api/shifts/{payload['code']}",
        json={"description": "Updated shift", "hours": 8.5},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["description"] == "Updated shift"
    assert updated["hours"] == 8.5

    delete_response = await api_client.delete(f"/api/shifts/{payload['code']}")
    assert delete_response.status_code == 204

    list_after_delete = await api_client.get("/api/shifts/")
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []
