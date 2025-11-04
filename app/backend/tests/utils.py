from collections.abc import Callable

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def create_async_client(app: FastAPI) -> Callable[[], AsyncClient]:
    async def _client() -> AsyncClient:
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://testserver")

    return _client
