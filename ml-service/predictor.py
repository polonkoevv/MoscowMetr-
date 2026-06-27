"""
Загрузка модели и инференс.
Переиспользует логику из ml/predict.py, но без зависимости от корневого пакета.
"""

from __future__ import annotations

import json
import os
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from catboost import CatBoostRegressor
from typing import Optional

from schemas import PredictRequest, PredictResponse

# --- Пути: в Docker /app/artifacts/, локально — рядом с файлом ---
_ARTIFACTS = Path(os.getenv("ARTIFACTS_DIR", Path(__file__).parent / "artifacts"))
MODEL_PATH   = _ARTIFACTS / "model.cbm"
METRICS_PATH = _ARTIFACTS / "metrics.json"
OKRUGS_PATH  = _ARTIFACTS / "moscow_okrugs.geojson"

# --- Фичи (должны совпадать с ml/train.py) ---
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


class PricePredictor:
    def __init__(self):
        self.model = CatBoostRegressor()
        self.model.load_model(str(MODEL_PATH))

        self.metrics: dict = {}
        if METRICS_PATH.exists():
            with open(METRICS_PATH) as f:
                self.metrics = json.load(f)

        self._okrugs = _load_okrug_polygons(OKRUGS_PATH)

    @property
    def best_iteration(self) -> Optional[int]:
        return self.metrics.get("best_iteration")

    @property
    def mape(self) -> float:
        return self.metrics.get("model_price", {}).get("mape", 0.0)

    def predict(self, req: PredictRequest) -> PredictResponse:
        raw = req.model_dump()

        # Временные фичи
        now = datetime.now(timezone.utc)
        raw["month"]   = raw["month"]   or now.month
        raw["quarter"] = raw["quarter"] or (now.month - 1) // 3 + 1

        # Округ
        okrug = _get_okrug(raw.get("lat"), raw.get("lon"), self._okrugs)
        raw["okrug"] = okrug

        # Feature engineering
        floor  = raw["floor"]
        floors = raw["floors"]
        raw["floor_ratio"]    = floor / floors if floors else None
        raw["is_first_floor"] = int(floor == 1)
        raw["is_top_floor"]   = int(floor == floors)

        df = pd.DataFrame([raw])

        # NA → пустая строка для категориальных
        for col in CAT_FEATURES + BIN_FEATURES:
            na_mask = df[col].isna()
            df[col] = df[col].astype(str)
            df.loc[na_mask, col] = ""

        df = df[ALL_FEATURES]

        log_pm2  = self.model.predict(df)[0]
        pm2      = float(np.expm1(log_pm2))
        price    = pm2 * req.total_area

        return PredictResponse(
            price        = round(price),
            price_per_m2 = round(pm2),
            mape         = round(self.mape, 2),
            okrug        = okrug,
        )
