import os
from unittest.mock import AsyncMock, patch

os.environ.update({
    "SECRET_KEY":     "a" * 32,
    "DATABASE_URL":   "sqlite+aiosqlite:///:memory:",
    "REDIS_URL":      "redis://localhost:6379/0",
    "ML_SERVICE_URL": "http://localhost:8001",
    "ADMIN_EMAIL":    "admin@test.com",
    "ADMIN_PASSWORD": "testadmin123",
    "SMTP_HOST":      "smtp.test.com",
    "SMTP_USER":      "test@test.com",
    "SMTP_PASSWORD":  "testpass",
    "FRONTEND_URL":   "http://localhost:8501",
    "CORS_ORIGINS":   "http://localhost:8501",
})

import pytest_asyncio
import fakeredis.aioredis

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.session import Base, get_db
from app.db.redis import get_redis
import app.models  # noqa: F401

# Import FastAPI instance last, after app package is imported
from main import app as fastapi_app

_TEST_ENGINE = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_TestSession = async_sessionmaker(_TEST_ENGINE, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    async with _TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await _TEST_ENGINE.dispose()


@pytest_asyncio.fixture
async def fake_redis():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.flushall()
    await r.aclose()


@pytest_asyncio.fixture
async def client(fake_redis):
    async def _override_db():
        async with _TestSession() as session:
            yield session

    async def _override_redis():
        return fake_redis

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[get_redis] = _override_redis

    with patch("main.init_redis", new_callable=AsyncMock):
        with patch("main.close_redis", new_callable=AsyncMock):
            with patch("main._create_first_admin", new_callable=AsyncMock):
                async with AsyncClient(
                    transport=ASGITransport(app=fastapi_app),
                    base_url="http://test",
                ) as c:
                    yield c

    fastapi_app.dependency_overrides.clear()
