import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kitchen_scheduler.db import session as db_session
from kitchen_scheduler.db.base import Base
from kitchen_scheduler.main import create_application


@pytest.fixture()
def database_url() -> str:
    return os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest_asyncio.fixture()
async def async_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    """Provide a per-test async engine, resetting schema before each run."""
    engine = create_async_engine(database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture()
def session_factory(async_engine: AsyncEngine) -> Iterator[async_sessionmaker[AsyncSession]]:
    factory = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    yield factory


@pytest.fixture(autouse=True)
def _swap_db_engine(async_engine: AsyncEngine) -> Iterator[None]:
    original_engine = db_session.engine
    original_factory = db_session.async_session_factory
    test_factory = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    try:
        db_session.engine = async_engine
        db_session.async_session_factory = test_factory
        yield
    finally:
        db_session.engine = original_engine
        db_session.async_session_factory = original_factory


@pytest.fixture()
async def api_client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    app = create_application()
    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[db_session.get_db_session] = _get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"
