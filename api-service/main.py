"""
ReVal API Service.
Запуск локально: uvicorn main:app --port 8000 --reload
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import select

from app.auth.passwords import hash_password
from app.config import settings
from app.db.session import AsyncSessionLocal
from app.logger import setup_logging
from app.models.user import Role, User
from app.routers import admin, auth, listings, predict, stats


async def _create_first_admin() -> None:
    """Создаёт первого admin-пользователя если ни одного нет."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.role == Role.admin))
        if result.scalar_one_or_none() is not None:
            return
        admin_user = User(
            email=settings.ADMIN_EMAIL,
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            role=Role.admin,
        )
        db.add(admin_user)
        await db.commit()
        logger.info(f"Создан первый admin: {settings.ADMIN_EMAIL}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("ReVal API Service запускается...")
    await _create_first_admin()
    logger.info("ReVal API Service готов к работе")
    yield
    logger.info("ReVal API Service остановлен")


app = FastAPI(
    title="ReVal API",
    description="Сервис оценки стоимости недвижимости. Авторизация через JWT, ролевая модель: user / analyst / admin.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.1f}ms)"
    )
    return response


app.include_router(auth.router)
app.include_router(predict.router)
app.include_router(listings.router)
app.include_router(stats.router)
app.include_router(admin.router)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok"}
