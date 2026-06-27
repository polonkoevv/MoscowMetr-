import io
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from loguru import logger
from pydantic import BaseModel
import pandas as pd

from app.auth.dependencies import role_required
from app.config import settings
from app.db.redis import get_redis
from app.models.user import Role, User

router = APIRouter(prefix="/listings", tags=["Listings"])

_PARQUET_KEY = "listings:parquet"

# L1 — in-process кэш (быстрее Redis при повторных запросах в том же процессе)
_df: pd.DataFrame | None = None


async def _load_df(redis: aioredis.Redis) -> pd.DataFrame:
    """L1 → L2 (Redis) → диск."""
    global _df
    if _df is not None:
        return _df

    cached_bytes = await redis.get(_PARQUET_KEY)
    if cached_bytes:
        logger.debug("Listings DataFrame загружен из Redis")
        _df = pd.read_parquet(io.BytesIO(cached_bytes))
        return _df

    logger.debug("Listings DataFrame загружен с диска, кэшируется в Redis")
    _df = pd.read_parquet(settings.LISTINGS_PATH)

    buf = io.BytesIO()
    _df.to_parquet(buf)
    await redis.set(_PARQUET_KEY, buf.getvalue(), ex=settings.STATS_CACHE_TTL)

    return _df


class ListingItem(BaseModel):
    id:            int
    price:         float
    price_per_m2:  float
    total_area:    float
    rooms_code:    Optional[int]
    floor:         Optional[int]
    floors:        Optional[int]
    property_kind: Optional[str]
    region_id:     Optional[int]
    okrug:         Optional[str]
    lat:           Optional[float]
    lon:           Optional[float]


class ListingsResponse(BaseModel):
    total: int
    items: list[ListingItem]


@router.get("", response_model=ListingsResponse)
async def get_listings(
    okrug:         Optional[str]   = Query(None, description="Фильтр по округу (ЦАО, САО, ...)"),
    property_kind: Optional[str]   = Query(None, description="Фильтр по типу объекта"),
    min_price:     Optional[float] = Query(None, description="Минимальная цена, руб."),
    max_price:     Optional[float] = Query(None, description="Максимальная цена, руб."),
    min_area:      Optional[float] = Query(None, description="Минимальная площадь, м²"),
    max_area:      Optional[float] = Query(None, description="Максимальная площадь, м²"),
    limit:         int             = Query(50, ge=1, le=500, description="Кол-во записей"),
    offset:        int             = Query(0, ge=0, description="Смещение"),
    _: User = Depends(role_required(Role.analyst, Role.admin)),
    redis: aioredis.Redis = Depends(get_redis),
):
    df = (await _load_df(redis)).copy()

    if okrug:
        df = df[df["okrug"] == okrug]
    if property_kind:
        df = df[df["property_kind"] == property_kind]
    if min_price is not None:
        df = df[df["price"] >= min_price]
    if max_price is not None:
        df = df[df["price"] <= max_price]
    if min_area is not None:
        df = df[df["total_area"] >= min_area]
    if max_area is not None:
        df = df[df["total_area"] <= max_area]

    total = len(df)
    page  = df.iloc[offset: offset + limit]

    items = []
    for row in page.itertuples():
        items.append(ListingItem(
            id            = int(row.id),
            price         = float(row.price),
            price_per_m2  = float(row.price_per_m2),
            total_area    = float(row.total_area),
            rooms_code    = int(row.rooms_code)    if pd.notna(row.rooms_code)    else None,
            floor         = int(row.floor)         if pd.notna(row.floor)         else None,
            floors        = int(row.floors)        if pd.notna(row.floors)        else None,
            property_kind = str(row.property_kind) if pd.notna(row.property_kind) else None,
            region_id     = int(row.region_id)     if pd.notna(row.region_id)     else None,
            okrug         = str(row.okrug)         if pd.notna(row.okrug) and row.okrug != "" else None,
            lat           = float(row.lat)         if pd.notna(row.lat)           else None,
            lon           = float(row.lon)         if pd.notna(row.lon)           else None,
        ))

    return ListingsResponse(total=total, items=items)
