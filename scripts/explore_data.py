"""
Разведка данных из БД перед выгрузкой в Parquet.
Запуск: python scripts/explore_data.py
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

# DB_URL = os.getenv(
#     "DATABASE_URL",
#     "postgresql://admin:secret@localhost:5432/du_portal_diploma"
# )

DB_URL = "postgresql://admin:admin@localhost:5432/du_portal_diploma"

engine = create_engine(DB_URL)

# --- 1. Количество строк и заполненность ключевых колонок ---
query_stats = text("""
SELECT
    COUNT(*)                    AS total_rows,
    COUNT(price)                AS has_price,
    COUNT(total_area)           AS has_area,
    COUNT(rooms_code)           AS has_rooms,
    COUNT(floor)                AS has_floor,
    COUNT(floors)               AS has_floors,
    COUNT(distance)             AS has_distance,
    COUNT(region_id)            AS has_region,
    COUNT(new_building)         AS has_new_building,
    COUNT(deal_type_code)       AS has_deal_type,
    COUNT(remont_code)          AS has_remont,
    COUNT(hometype_code)        AS has_hometype,
    COUNT(category)             AS has_category,
    COUNT(property_kind)        AS has_property_kind,
    COUNT(matched_building_id)  AS has_building_id
FROM market_marketlisting
WHERE is_active = true AND price IS NOT NULL;
""")

print("=" * 60)
print("1. СТАТИСТИКА ЗАПОЛНЕННОСТИ (только активные с ценой)")
print("=" * 60)
with engine.connect() as conn:
    df_stats = pd.read_sql(query_stats, conn)
print(df_stats.T.to_string())

# --- 2. Распределение по deal_type_code ---
query_deal = text("""
SELECT deal_type_code, COUNT(*) AS cnt
FROM market_marketlisting
WHERE is_active = true AND price IS NOT NULL
GROUP BY deal_type_code
ORDER BY cnt DESC;
""")

print("\n" + "=" * 60)
print("2. ТИПЫ СДЕЛОК (deal_type_code)")
print("=" * 60)
with engine.connect() as conn:
    df_deal = pd.read_sql(query_deal, conn)
print(df_deal.to_string(index=False))

# --- 3. Распределение цен ---
query_price = text("""
SELECT
    MIN(price)                          AS price_min,
    PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY price) AS price_p5,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY price) AS price_p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY price) AS price_median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY price) AS price_p75,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY price) AS price_p95,
    MAX(price)                          AS price_max,
    AVG(price)                          AS price_mean
FROM market_marketlisting
WHERE is_active = true AND price IS NOT NULL;
""")

print("\n" + "=" * 60)
print("3. РАСПРЕДЕЛЕНИЕ ЦЕН (руб.)")
print("=" * 60)
with engine.connect() as conn:
    df_price = pd.read_sql(query_price, conn)
print(df_price.T.to_string())

# --- 4. Связь с market_marketcomplex ---
query_complex = text("""
SELECT
    COUNT(*) AS total_listings,
    COUNT(ml.matched_building_id) AS linked_to_complex,
    ROUND(COUNT(ml.matched_building_id) * 100.0 / COUNT(*), 1) AS pct_linked
FROM market_marketlisting ml
WHERE ml.is_active = true AND ml.price IS NOT NULL;
""")

print("\n" + "=" * 60)
print("4. СВЯЗЬ С market_marketcomplex")
print("=" * 60)
with engine.connect() as conn:
    df_complex = pd.read_sql(query_complex, conn)
print(df_complex.to_string(index=False))

# --- 5. Пример строк ---
query_sample = text("""
SELECT
    ml.id, ml.price, ml.total_area, ml.rooms_code,
    ml.floor, ml.floors, ml.distance, ml.new_building,
    ml.deal_type_code, ml.remont_code, ml.region_id,
    ml.category, ml.property_kind, ml.bucket,
    mc.building_class, mc.district
FROM market_marketlisting ml
LEFT JOIN market_marketcomplex mc ON ml.matched_building_id = mc.id
WHERE ml.is_active = true AND ml.price IS NOT NULL
LIMIT 5;
""")

print("\n" + "=" * 60)
print("5. ПРИМЕР СТРОК С ДЖОИНОМ market_marketcomplex")
print("=" * 60)
with engine.connect() as conn:
    df_sample = pd.read_sql(query_sample, conn)
print(df_sample.to_string(index=False))

print("\nГотово. Скинь вывод — определим финальный запрос для выгрузки в Parquet.")
