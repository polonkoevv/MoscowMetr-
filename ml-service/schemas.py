"""Pydantic-схемы для ML Service."""

from pydantic import BaseModel, Field
from typing import Optional


class PredictRequest(BaseModel):
    """Входные данные для предсказания цены."""

    total_area:     float        = Field(..., gt=0,   description="Общая площадь, м²")
    floor:          int          = Field(..., ge=1,   description="Этаж")
    floors:         int          = Field(..., ge=1,   description="Этажей в доме")
    distance:       Optional[int]   = Field(None, ge=0, description="Расстояние до центра, м")
    lat:            Optional[float] = Field(None,       description="Широта")
    lon:            Optional[float] = Field(None,       description="Долгота")

    rooms_code:     Optional[int]   = Field(None, description="Код кол-ва комнат")
    remont_code:    Optional[int]   = Field(None, description="Код ремонта")
    hometype_code:  Optional[int]   = Field(None, description="Код типа жилья")
    deal_type_code: Optional[int]   = Field(None, description="Код типа сделки")
    category:       Optional[str]   = Field(None, description="Категория объекта")
    property_kind:  Optional[str]   = Field(None, description="Вид недвижимости")
    region_id:      Optional[int]   = Field(None, description="ID региона")
    bucket:         Optional[str]   = Field(None, description="Ценовой сегмент")
    new_building:   Optional[bool]  = Field(None, description="Новостройка")

    month:          Optional[int]   = Field(None, ge=1, le=12, description="Месяц (1-12)")
    quarter:        Optional[int]   = Field(None, ge=1, le=4,  description="Квартал (1-4)")

    model_config = {"json_schema_extra": {
        "example": {
            "total_area": 52.0,
            "floor": 5,
            "floors": 9,
            "distance": 3000,
            "lat": 55.75,
            "lon": 37.62,
            "rooms_code": 2,
            "remont_code": 1,
            "hometype_code": 1,
            "property_kind": "flat",
            "region_id": 47,
            "bucket": "residential",
            "new_building": False,
        }
    }}


class PredictResponse(BaseModel):
    """Результат предсказания."""

    price:        int   = Field(..., description="Предсказанная цена, руб.")
    price_per_m2: int   = Field(..., description="Цена за м², руб/м²")
    mape:         float = Field(..., description="Ожидаемая погрешность модели, %")
    okrug:        str   = Field("",  description="Определённый округ Москвы")


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    best_iteration: Optional[int] = None
