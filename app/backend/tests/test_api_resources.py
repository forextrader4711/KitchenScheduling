import pytest
from httpx import AsyncClient

from .factories import build_resource_create


@pytest.mark.anyio("asyncio")
async def test_resource_api_crud(api_client: AsyncClient) -> None:
    payload = build_resource_create().model_dump()

    create_response = await api_client.post("/api/resources/", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    resource_id = created["id"]
    assert created["name"] == payload["name"]

    list_response = await api_client.get("/api/resources/")
    assert list_response.status_code == 200
    resources = list_response.json()
    assert len(resources) == 1
    assert resources[0]["id"] == resource_id

    update_response = await api_client.put(
        f"/api/resources/{resource_id}",
        json={"availability_percent": 80, "notes": "updated via api test"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["availability_percent"] == 80
    assert updated["notes"] == "updated via api test"

    delete_response = await api_client.delete(f"/api/resources/{resource_id}")
    assert delete_response.status_code == 204

    list_after_delete = await api_client.get("/api/resources/")
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []
