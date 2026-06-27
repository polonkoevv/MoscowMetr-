import json
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel
from typing import Optional
import pandas as pd

from app.auth.dependencies import role_required
from app.config import settings
from app.db.redis import get_redis
from app.models.user import Role, User

router = APIRouter(prefix="/stats", tags=["Stats"])

METRICS_PATH = Path("/app/data/metrics.json")
_STATS_KEY = "stats:main"


class ModelMetrics(BaseModel):
    mae:  Optional[float]
    rmse: Optional[float]
    mape: Optional[float]


class PriceByOkrug(BaseModel):
    okrug:      str
    median_pm2: float
    count:      int


class StatsResponse(BaseModel):
    total_listings:     int
    model_metrics:      ModelMetrics
    price_by_okrug:     list[PriceByOkrug]
    property_kind_dist: dict[str, int]

    model_config = {"protected_namespaces": ()}


@router.get("", response_model=StatsResponse)
async def get_stats(
    _: User = Depends(role_required(Role.analyst, Role.admin)),
    redis: aioredis.Redis = Depends(get_redis),
):
    # Проверяем кэш
    cached = await redis.get(_STATS_KEY)
    if cached:
        logger.debug("Stats из кэша")
        return StatsResponse.model_validate_json(cached.decode())

    df = pd.read_parquet(settings.LISTINGS_PATH)

    # Метрики модели
    metrics: dict = {}
    if METRICS_PATH.exists():
        with open(METRICS_PATH) as f:
            metrics = json.load(f)
    model_m = metrics.get("model_price", {})

    # Медианная цена за м² по округам
    okrug_df = df[df["okrug"] != ""].groupby("okrug").agg(
        median_pm2=("price_per_m2", "median"),
        count=("id", "count"),
    ).reset_index()

    price_by_okrug = [
        PriceByOkrug(okrug=row.okrug, median_pm2=round(row.median_pm2), count=int(row.count))
        for row in okrug_df.itertuples()
    ]

    kind_dist = df["property_kind"].value_counts().to_dict()
    kind_dist = {k: int(v) for k, v in kind_dist.items() if pd.notna(k)}

    result = StatsResponse(
        total_listings=len(df),
        model_metrics=ModelMetrics(
            mae=model_m.get("mae"),
            rmse=model_m.get("rmse"),
            mape=model_m.get("mape"),
        ),
        price_by_okrug=price_by_okrug,
        property_kind_dist=kind_dist,
    )

    await redis.set(_STATS_KEY, result.model_dump_json().encode(), ex=settings.STATS_CACHE_TTL)
    logger.debug("Stats вычислены и закэшированы")
    return result
