from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
import pandas as pd

from app.auth.dependencies import role_required
from app.config import settings
from app.models.user import Role, User

router = APIRouter(prefix="/listings", tags=["Listings"])

# Parquet читается один раз при первом обращении
_df: pd.DataFrame | None = None


def get_df() -> pd.DataFrame:
    global _df
    if _df is None:
        _df = pd.read_parquet(settings.LISTINGS_PATH)
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
):
    df = get_df().copy()

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
