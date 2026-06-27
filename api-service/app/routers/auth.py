from datetime import timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.passwords import hash_password, verify_password
from app.config import settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import Role, User

router = APIRouter(prefix="/auth", tags=["Auth"])

_REFRESH_PREFIX = "refresh:"
_REFRESH_TTL = int(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Пароль должен содержать не менее 8 символов")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"


class UserResponse(BaseModel):
    id:        int
    email:     str
    role:      Role
    is_active: bool

    model_config = {"from_attributes": True}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        logger.warning(f"Попытка регистрации с уже существующим email: {body.email} | IP: {request.client.host}")
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"Зарегистрирован новый пользователь: {user.email} (id={user.id}) | IP: {request.client.host}")
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        logger.warning(f"Неудачная попытка входа: {body.email} | IP: {request.client.host}")
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_active:
        logger.warning(f"Вход заблокированного аккаунта: {body.email} | IP: {request.client.host}")
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")

    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token_value, _ = create_refresh_token()

    # Сохраняем в Redis: ключ = "refresh:{token}", значение = user_id, TTL = 30 дней
    await redis.set(f"{_REFRESH_PREFIX}{refresh_token_value}", str(user.id).encode(), ex=_REFRESH_TTL)

    logger.info(f"Успешный вход: {user.email} (id={user.id}, role={user.role.value}) | IP: {request.client.host}")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token_value)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    raw = await redis.get(f"{_REFRESH_PREFIX}{body.refresh_token}")
    if raw is None:
        raise HTTPException(status_code=401, detail="Refresh токен не найден или истёк")

    user_id = int(raw.decode())
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        await redis.delete(f"{_REFRESH_PREFIX}{body.refresh_token}")
        raise HTTPException(status_code=401, detail="Пользователь не найден или заблокирован")

    access_token = create_access_token(subject=user.id, role=user.role.value)
    logger.info(f"Выдан новый access token для user_id={user.id}")
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    redis: aioredis.Redis = Depends(get_redis),
):
    deleted = await redis.delete(f"{_REFRESH_PREFIX}{body.refresh_token}")
    if deleted:
        logger.info("Logout: refresh токен отозван")


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
