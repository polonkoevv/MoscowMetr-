import secrets
from datetime import timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
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
from app.services.email import send_verification_email

router = APIRouter(prefix="/auth", tags=["Auth"])

_REFRESH_PREFIX = "refresh:"
_VERIFY_PREFIX  = "verify:"
_REFRESH_TTL    = int(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
_VERIFY_TTL     = int(timedelta(hours=24).total_seconds())


# ── Схемы ──────────────────────────────────────────────────────

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
    id:          int
    email:       str
    role:        Role
    is_active:   bool
    is_verified: bool

    model_config = {"from_attributes": True}


# ── HTML-ответы верификации ────────────────────────────────────

def _html_page(title: str, message: str, success: bool = True) -> HTMLResponse:
    color  = "#2563EB" if success else "#dc2626"
    icon   = "✅" if success else "❌"
    action = '<p><a href="http://localhost:8501" style="color:#2563EB;">Перейти в приложение →</a></p>' if success else ""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title} — ReVal</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #f1f5f9;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; margin:0; }}
  .card {{ background:#fff; border-radius:16px; padding:2.5rem 3rem; text-align:center;
           box-shadow:0 8px 32px rgba(0,0,0,0.1); max-width:420px; }}
  h1 {{ color:{color}; font-size:1.5rem; margin:0.5rem 0; }}
  p  {{ color:#475569; line-height:1.6; }}
  .icon {{ font-size:3rem; }}
</style></head>
<body><div class="card">
  <div class="icon">{icon}</div>
  <h1>{title}</h1>
  <p>{message}</p>
  {action}
</div></body></html>"""
    return HTMLResponse(content=html)


# ── Эндпоинты ─────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        logger.warning(f"Попытка регистрации с уже существующим email: {body.email} | IP: {request.client.host}")
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Токен верификации в Redis
    verify_token = secrets.token_urlsafe(32)
    await redis.set(f"{_VERIFY_PREFIX}{verify_token}", str(user.id).encode(), ex=_VERIFY_TTL)

    # Письмо отправляется в фоне — ответ не ждёт завершения
    background_tasks.add_task(send_verification_email, user.email, verify_token)

    logger.info(f"Зарегистрирован новый пользователь: {user.email} (id={user.id}) | IP: {request.client.host}")
    return user


@router.get("/verify", response_class=HTMLResponse)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    raw = await redis.get(f"{_VERIFY_PREFIX}{token}")
    if raw is None:
        return _html_page(
            "Ссылка недействительна",
            "Токен верификации не найден или истёк. Зарегистрируйтесь заново.",
            success=False,
        )

    user_id = int(raw.decode())
    result  = await db.execute(select(User).where(User.id == user_id))
    user    = result.scalar_one_or_none()

    if not user:
        return _html_page("Пользователь не найден", "Аккаунт был удалён.", success=False)

    if user.is_verified:
        return _html_page("Email уже подтверждён", "Вы можете войти в систему.")

    user.is_verified = True
    user.is_active   = True
    await db.commit()
    await redis.delete(f"{_VERIFY_PREFIX}{token}")

    logger.info(f"Email подтверждён: {user.email} (id={user.id})")
    return _html_page(
        "Email подтверждён!",
        f"Адрес <strong>{user.email}</strong> успешно подтверждён. Теперь вы можете войти в систему."
    )


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
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email не подтверждён. Проверьте почту.")
    if not user.is_active:
        logger.warning(f"Вход заблокированного аккаунта: {body.email} | IP: {request.client.host}")
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")

    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token_value, _ = create_refresh_token()

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
    result  = await db.execute(select(User).where(User.id == user_id))
    user    = result.scalar_one_or_none()

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
