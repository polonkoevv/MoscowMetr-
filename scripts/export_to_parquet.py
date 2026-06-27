"""
Выгрузка данных из БД в Parquet для обучения модели цен.
Запуск: python scripts/export_to_parquet.py
"""

import json
import os
import pandas as pd
from shapely.geometry import Point, shape
from sqlalchemy import create_engine, text
from pathlib import Path

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:admin@localhost:5432/du_portal_diploma"
)

OUTPUT_PATH = Path("data/listings.parquet")
OKRUGS_PATH = Path("data/moscow_okrugs.geojson")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

QUERY = text("""
SELECT
    ml.id,
    ml.price,
    ml.total_area,
    ml.rooms_code,
    ml.floor,
    ml.floors,
    ml.distance,
    ml.remont_code,
    ml.hometype_code,
    ml.deal_type_code,
    ml.category,
    ml.property_kind,
    ml.region_id,
    ml.bucket,
    ml.new_building,
    ml.lat,
    ml.lon,
    ml.first_seen_at
FROM market_marketlisting ml
WHERE
    ml.is_active = true
    AND ml.price IS NOT NULL
    AND ml.price >= 100000
    AND ml.price <= 500000000
    AND ml.total_area IS NOT NULL
    AND ml.rooms_code IS NOT NULL
    AND ml.total_area > 0
    AND ml.total_area < 10000
    AND ml.rooms_code >= 0
    AND ml.rooms_code <= 20
ORDER BY ml.id;
""")


# ---------------------------------------------------------------------------
# Округа Москвы: point-in-polygon через shapely
# ---------------------------------------------------------------------------

def load_okrug_polygons(path: Path) -> list:
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


def assign_okrug(lat_series: pd.Series, lon_series: pd.Series, okrugs: list) -> pd.Series:
    result = [""] * len(lat_series)
    lats = lat_series.values
    lons = lon_series.values
    for i in range(len(lats)):
        if pd.isna(lats[i]) or pd.isna(lons[i]):
            continue
        pt = Point(float(lons[i]), float(lats[i]))  # shapely: (lon, lat)
        for okrug in okrugs:
            if okrug["polygon"].contains(pt):
                result[i] = okrug["name"]
                break
    return pd.Series(result, index=lat_series.index, dtype="object")


# ---------------------------------------------------------------------------
# Основной скрипт
# ---------------------------------------------------------------------------

print("Подключение к БД...")
engine = create_engine(DB_URL)

print("Выполняем запрос...")
with engine.connect() as conn:
    df = pd.read_sql(QUERY, conn)

print(f"Загружено строк: {len(df):,}")

# --- Типы ---
df["new_building"]   = df["new_building"].astype("boolean")
df["rooms_code"]     = df["rooms_code"].astype("Int16")
df["floor"]          = df["floor"].astype("Int16")
df["floors"]         = df["floors"].astype("Int16")
df["remont_code"]    = df["remont_code"].astype("Int8")
df["hometype_code"]  = df["hometype_code"].astype("Int8")
df["deal_type_code"] = df["deal_type_code"].astype("Int8")
df["region_id"]      = df["region_id"].astype("Int32")
df["price"]          = df["price"].astype("float64")
df["total_area"]     = df["total_area"].astype("float32")
df["distance"]       = df["distance"].astype("Int32")
df["lat"]            = df["lat"].astype("float32")
df["lon"]            = df["lon"].astype("float32")

# --- 1. Цена за м² ---
df["price_per_m2"] = (df["price"] / df["total_area"]).astype("float64")

# --- 2. Временные фичи из first_seen_at ---
df["first_seen_at"] = pd.to_datetime(df["first_seen_at"], utc=True)
df["month"]   = df["first_seen_at"].dt.month.astype("Int8")
df["quarter"] = df["first_seen_at"].dt.quarter.astype("Int8")

# --- 3. Округ через lat/lon ---
print("Определяем округ по координатам...")
okrugs = load_okrug_polygons(OKRUGS_PATH)
print(f"  Загружено округов: {len(okrugs)}")
df["okrug"] = assign_okrug(df["lat"], df["lon"], okrugs)
okrug_fill = (df["okrug"] != "").sum()
print(f"  Определён округ: {okrug_fill:,} из {len(df):,} ({okrug_fill/len(df)*100:.1f}%)")

# --- Статистика ---
print("\n--- Статистика выгрузки ---")
print(f"Строк:    {len(df):,}")
print(f"Колонок:  {len(df.columns)}")

print(f"\nЦена (руб.):")
print(f"  min:    {df['price'].min():>15,.0f}")
print(f"  median: {df['price'].median():>15,.0f}")
print(f"  max:    {df['price'].max():>15,.0f}")

print(f"\nЦена за м² (руб/м²):")
print(f"  min:    {df['price_per_m2'].min():>15,.0f}")
print(f"  median: {df['price_per_m2'].median():>15,.0f}")
print(f"  max:    {df['price_per_m2'].max():>15,.0f}")

print(f"\nОкруга:")
print(df["okrug"].value_counts().to_string())

# --- Сохраняем (без first_seen_at — уже распарсили) ---
df.drop(columns=["first_seen_at"]).to_parquet(
    OUTPUT_PATH, index=False, engine="pyarrow", compression="snappy"
)
print(f"\nСохранено в: {OUTPUT_PATH}")
print(f"Размер файла: {OUTPUT_PATH.stat().st_size / 1024 / 1024:.1f} MB")
