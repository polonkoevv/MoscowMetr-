from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import update

from app.models.user import User
from main import app as fastapi_app
from app.db.session import get_db


async def _register(client: AsyncClient, email: str, password: str = "password123"):
    with patch("app.routers.auth.send_verification_email", new_callable=AsyncMock):
        return await client.post("/auth/register", json={"email": email, "password": password})


async def _verify_user(email: str):
    override = fastapi_app.dependency_overrides.get(get_db)
    async for session in override():
        await session.execute(
            update(User).where(User.email == email).values(is_verified=True)
        )
        await session.commit()


async def test_register_success(client: AsyncClient):
    resp = await _register(client, "alice@test.com")
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@test.com"
    assert data["role"] == "user"
    assert data["is_verified"] is False


async def test_register_duplicate_email(client: AsyncClient):
    await _register(client, "bob@test.com")
    resp = await _register(client, "bob@test.com")
    assert resp.status_code == 400
    assert "уже зарегистрирован" in resp.json()["detail"]


async def test_register_short_password(client: AsyncClient):
    resp = await _register(client, "charlie@test.com", password="1234567")
    assert resp.status_code == 422


async def test_register_invalid_email(client: AsyncClient):
    resp = await _register(client, "not-an-email")
    assert resp.status_code == 422


async def test_login_unverified_user(client: AsyncClient):
    await _register(client, "dave@test.com")
    resp = await client.post("/auth/login", json={"email": "dave@test.com", "password": "password123"})
    assert resp.status_code == 403
    assert "не подтверждён" in resp.json()["detail"]


async def test_login_wrong_password(client: AsyncClient):
    await _register(client, "eve@test.com")
    await _verify_user("eve@test.com")
    resp = await client.post("/auth/login", json={"email": "eve@test.com", "password": "wrongpass"})
    assert resp.status_code == 401


async def test_login_success(client: AsyncClient):
    await _register(client, "frank@test.com")
    await _verify_user("frank@test.com")
    resp = await client.post("/auth/login", json={"email": "frank@test.com", "password": "password123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_me_without_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code in (401, 403)  # FastAPI OAuth2 returns 403 when token is missing


async def test_me_with_token(client: AsyncClient):
    await _register(client, "grace@test.com")
    await _verify_user("grace@test.com")
    login = await client.post("/auth/login", json={"email": "grace@test.com", "password": "password123"})
    token = login.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "grace@test.com"
