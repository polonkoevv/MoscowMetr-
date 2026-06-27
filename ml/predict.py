"""
Инференс модели предсказания цены недвижимости.

Использование:
    from ml.predict import PricePredictor
    predictor = PricePredictor()
    result = predictor.predict(features)
"""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from catboost import CatBoostRegressor
from pydantic import BaseModel, Field
from typing import Optional

# --- Пути ---
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
MODEL_PATH    = ARTIFACTS_DIR / "model.cbm"
METRICS_PATH  = ARTIFACTS_DIR / "metrics.json"
OKRUGS_PATH   = Path(__file__).parent.parent / "data" / "moscow_okrugs.geojson"

# --- Фичи (должны совпадать с train.py) ---
NUM_FEATURES = [
    "total_area", "floor", "floors", "distance",
    "lat", "lon", "floor_ratio",
    "month", "quarter",
]
CAT_FEATURES = [
    "rooms_code", "remont_code", "hometype_code", "deal_type_code",
    "category", "property_kind", "region_id", "bucket", "okrug",
]
BIN_FEATURES = [
    "new_building", "is_first_floor", "is_top_floor",
]
ALL_FEATURES = NUM_FEATURES + CAT_FEATURES + BIN_FEATURES


# ---------------------------------------------------------------------------
# Pydantic-схема входных данных
# ---------------------------------------------------------------------------

class ListingFeatures(BaseModel):
    total_area:     float           = Field(..., gt=0,  description="Общая площадь, м²")
    floor:          int             = Field(..., ge=1,  description="Этаж")
    floors:         int             = Field(..., ge=1,  description="Этажей в доме")
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

    # Временные фичи — если не переданы, берём текущую дату
    month:          Optional[int]   = Field(None, ge=1, le=12, description="Месяц (1-12)")
    quarter:        Optional[int]   = Field(None, ge=1, le=4,  description="Квартал (1-4)")


# ---------------------------------------------------------------------------
# Определение округа через shapely
# ---------------------------------------------------------------------------

def _load_okrug_polygons(path: Path) -> list:
    if not path.exists():
        return []
    from shapely.geometry import shape
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    result = []
    for feat in gj["features"]:
        try:
            poly = shape(feat["geometry"])
            name = feat["properties"].get("short_name") or feat["properties"]["name"]
            result.append({"name": name, "polygon": poly})
        except Exception:
            pass
    return result


def _get_okrug(lat: Optional[float], lon: Optional[float], okrugs: list) -> str:
    if lat is None or lon is None or not okrugs:
        return ""
    from shapely.geometry import Point
    pt = Point(float(lon), float(lat))
    for okrug in okrugs:
        if okrug["polygon"].contains(pt):
            return okrug["name"]
    return ""


# ---------------------------------------------------------------------------
# Предиктор
# ---------------------------------------------------------------------------

class PricePredictor:
    def __init__(self, model_path: Path = MODEL_PATH):
        self.model = CatBoostRegressor()
        self.model.load_model(str(model_path))

        self.metrics = {}
        if METRICS_PATH.exists():
            with open(METRICS_PATH) as f:
                self.metrics = json.load(f)

        self._okrugs = _load_okrug_polygons(OKRUGS_PATH)
        self._cat_idx = [ALL_FEATURES.index(c) for c in CAT_FEATURES + BIN_FEATURES]

    def _to_dataframe(self, features: ListingFeatures) -> pd.DataFrame:
        raw = features.model_dump()

        # Временные фичи
        now = datetime.now(timezone.utc)
        raw["month"]   = raw["month"]   or now.month
        raw["quarter"] = raw["quarter"] or (now.month - 1) // 3 + 1

        # Округ через lat/lon
        raw["okrug"] = _get_okrug(raw.get("lat"), raw.get("lon"), self._okrugs)

        # Feature engineering
        floor  = raw["floor"]
        floors = raw["floors"]
        raw["floor_ratio"]    = floor / floors if floors else None
        raw["is_first_floor"] = int(floor == 1)
        raw["is_top_floor"]   = int(floor == floors)

        df = pd.DataFrame([raw])

        # Категориальные → строка, NA → пустая строка
        for col in CAT_FEATURES + BIN_FEATURES:
            na_mask = df[col].isna()
            df[col] = df[col].astype(str)
            df.loc[na_mask, col] = ""

        return df[ALL_FEATURES]

    def predict(self, features: ListingFeatures) -> dict:
        """
        Возвращает:
            price_per_m2 — предсказанная цена за м², руб/м²
            price        — итоговая цена (price_per_m2 × total_area), руб.
            mape         — ожидаемая погрешность модели, %
            okrug        — определённый округ (если lat/lon переданы)
        """
        df = self._to_dataframe(features)

        log_pm2  = self.model.predict(df)[0]
        pm2      = float(np.expm1(log_pm2))
        price    = pm2 * features.total_area
        okrug    = df["okrug"].iloc[0]

        return {
            "price_per_m2": round(pm2),
            "price":        round(price),
            "mape":         self.metrics.get("model_price", {}).get("mape"),
            "okrug":        okrug,
        }


# ---------------------------------------------------------------------------
# Быстрая проверка при прямом запуске
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    predictor = PricePredictor()

    test_listing = ListingFeatures(
        total_area=52.0,
        floor=5,
        floors=9,
        distance=3000,
        lat=55.75,
        lon=37.62,
        rooms_code=2,
        remont_code=1,
        hometype_code=1,
        deal_type_code=None,
        category=None,
        property_kind="flat",
        region_id=47,
        bucket="residential",
        new_building=False,
    )

    result = predictor.predict(test_listing)
    print(f"Округ:               {result['okrug'] or '—'}")
    print(f"Цена за м²:         {result['price_per_m2']:>12,.0f} руб/м²")
    print(f"Предсказанная цена: {result['price']:>12,.0f} руб.")
    print(f"Ожидаемая погрешность: ~{result['mape']:.1f}%")
