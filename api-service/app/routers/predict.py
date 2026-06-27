import hashlib
import json
from datetime import datetime

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.auth.dependencies import get_current_user
from app.config import settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.prediction_log import PredictionLog
from app.models.user import User

router = APIRouter(prefix="/predict", tags=["Prediction"])

# Примерные границы Москвы и ближнего Подмосковья
_LAT_MIN, _LAT_MAX = 55.1, 56.3
_LON_MIN, _LON_MAX = 36.5, 38.5

VALID_PROPERTY_KINDS = {"flat", "room", "house", "cottage", "land", "garage", "commercial"}
VALID_CATEGORIES = {"secondary", "new_building", "commercial", "country"}


class PredictRequest(BaseModel):
    total_area:     float           = Field(..., gt=0, le=10_000, description="Общая площадь, м²")
    floor:          int             = Field(..., ge=1, le=200,    description="Этаж")
    floors:         int             = Field(..., ge=1, le=200,    description="Этажей в доме")
    lat:            Optional[float] = Field(None,                 description="Широта (с карты)")
    lon:            Optional[float] = Field(None,                 description="Долгота (с карты)")
    distance:       Optional[int]   = Field(None, ge=0, le=500_000, description="Расстояние до центра, м")
    rooms_code:     Optional[int]   = Field(None, ge=0, le=20,   description="Код кол-ва комнат")
    remont_code:    Optional[int]   = Field(None, ge=0,          description="Код ремонта")
    hometype_code:  Optional[int]   = Field(None, ge=0,          description="Код типа жилья")
    deal_type_code: Optional[int]   = Field(None, ge=0,          description="Код типа сделки")
    category:       Optional[str]   = Field(None,                 description="Категория объекта")
    property_kind:  Optional[str]   = Field(None,                 description="Вид недвижимости")
    region_id:      Optional[int]   = Field(None,                 description="ID региона")
    bucket:         Optional[str]   = Field(None,                 description="Ценовой сегмент")
    new_building:   Optional[bool]  = Field(None,                 description="Новостройка")

    @model_validator(mode="after")
    def check_floor_le_floors(self) -> "PredictRequest":
        if self.floor > self.floors:
            raise ValueError(f"floor ({self.floor}) не может быть больше floors ({self.floors})")
        return self

    @field_validator("lat")
    @classmethod
    def check_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (_LAT_MIN <= v <= _LAT_MAX):
            raise ValueError(f"lat должна быть в диапазоне [{_LAT_MIN}, {_LAT_MAX}] (Московский регион)")
        return v

    @field_validator("lon")
    @classmethod
    def check_lon(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (_LON_MIN <= v <= _LON_MAX):
            raise ValueError(f"lon должна быть в диапазоне [{_LON_MIN}, {_LON_MAX}] (Московский регион)")
        return v

    @field_validator("property_kind")
    @classmethod
    def check_property_kind(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PROPERTY_KINDS:
            raise ValueError(f"property_kind должен быть одним из: {sorted(VALID_PROPERTY_KINDS)}")
        return v

    @field_validator("category")
    @classmethod
    def check_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CATEGORIES:
            raise ValueError(f"category должна быть одной из: {sorted(VALID_CATEGORIES)}")
        return v

    model_config = {"json_schema_extra": {"example": {
        "total_area": 52,
        "floor": 5,
        "floors": 9,
        "lat": 55.7558,
        "lon": 37.6173,
        "rooms_code": 2,
        "property_kind": "flat",
        "region_id": 47,
        "bucket": "residential",
        "new_building": False,
    }}}


class PredictResponse(BaseModel):
    price:        int
    price_per_m2: int
    mape:         float
    okrug:        str


def _predict_cache_key(body: PredictRequest) -> str:
    """SHA256 от отсортированного JSON входных параметров."""
    payload = json.dumps(body.model_dump(), sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"predict:{digest}"


@router.post("", response_model=PredictResponse)
async def predict(
    body: PredictRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    cache_key = _predict_cache_key(body)

    # Проверяем кэш
    cached = await redis.get(cache_key)
    if cached:
        logger.info(f"Предсказание из кэша для user_id={user.id} | key={cache_key[:16]}…")
        return json.loads(cached.decode())

    logger.debug(f"Запрос предсказания от user_id={user.id}: area={body.total_area}, floor={body.floor}/{body.floors}")

    # Вызов ML Service
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.ML_SERVICE_URL}/predict",
                json=body.model_dump(),
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"ML Service недоступен для user_id={user.id}: {e}")
            raise HTTPException(status_code=502, detail=f"ML Service недоступен: {e}")

    result = resp.json()

    # Кэшируем результат
    await redis.set(cache_key, json.dumps(result).encode(), ex=settings.PREDICT_CACHE_TTL)

    logger.info(
        f"Предсказание для user_id={user.id}: "
        f"price={result.get('price'):,} руб., okrug={result.get('okrug', '—')}"
    )

    # Логируем предсказание в БД
    log = PredictionLog(
        user_id=user.id,
        request_data=body.model_dump(),
        response_data=result,
    )
    db.add(log)
    await db.commit()

    return result


class HistoryItem(BaseModel):
    id:           int
    request_data: dict
    response_data: dict
    created_at:   datetime


class HistoryResponse(BaseModel):
    total: int
    items: list[HistoryItem]


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    limit:  int = Query(20, ge=1, le=100, description="Кол-во записей"),
    offset: int = Query(0,  ge=0,         description="Смещение"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """История предсказаний текущего пользователя, от новых к старым."""
    result = await db.execute(
        select(PredictionLog)
        .where(PredictionLog.user_id == user.id)
        .order_by(desc(PredictionLog.created_at))
        .offset(offset)
        .limit(limit)
    )
    logs = result.scalars().all()

    # Общее кол-во записей пользователя
    count_result = await db.execute(
        select(func.count()).where(PredictionLog.user_id == user.id).select_from(PredictionLog)
    )
    total = count_result.scalar_one()

    return HistoryResponse(
        total=total,
        items=[
            HistoryItem(
                id=log.id,
                request_data=log.request_data,
                response_data=log.response_data,
                created_at=log.created_at,
            )
            for log in logs
        ],
    )
