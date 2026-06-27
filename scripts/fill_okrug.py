"""
Скачивает полигоны округов Москвы и заполняет поле okrug
во всех объявлениях датасета по координатам lat/lon.

Запуск из корня проекта:
    python scripts/fill_okrug.py
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape

# ── Пути ─────────────────────────────────────────────────────────────────────
ROOT            = Path(__file__).parent.parent
GEOJSON_PATH    = ROOT / "data" / "moscow_okrugs.geojson"
ML_GEOJSON_PATH = ROOT / "ml-service" / "artifacts" / "moscow_okrugs.geojson"
PARQUET_MAIN    = ROOT / "data" / "listings.parquet"
PARQUET_API     = ROOT / "api-service" / "data" / "listings.parquet"

# ── Overpass: скачать полигоны округов ───────────────────────────────────────
QUERIES = [
    """
[out:json][timeout:60];
area(3602555133)->.moscow;
(
  relation["admin_level"="5"]["boundary"="administrative"](area.moscow);
);
out geom;
""",
    """
[out:json][timeout:60];
(
  relation["admin_level"="5"]["boundary"="administrative"]
          (55.14,36.80,56.02,37.97);
);
out geom;
""",
]

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def fetch_overpass(query: str) -> dict:
    encoded = urllib.parse.urlencode({"data": query}).encode("utf-8")
    for url in ENDPOINTS:
        try:
            req = urllib.request.Request(
                url, data=encoded,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": "MisisProject/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("elements"):
                    print(f"  ✓ {url}")
                    return data
        except Exception as e:
            print(f"  ✗ {url}: {e}")
    return {"elements": []}


def _build_ring(ways: list) -> list:
    segments = [
        [[p["lon"], p["lat"]] for p in w.get("geometry", [])]
        for w in ways if w.get("geometry")
    ]
    if not segments:
        return []
    ring = list(segments[0])
    remaining = segments[1:]
    for _ in range(len(remaining) * 2):
        if not remaining:
            break
        last = ring[-1]
        for i, seg in enumerate(remaining):
            if abs(seg[0][0] - last[0]) < 1e-6 and abs(seg[0][1] - last[1]) < 1e-6:
                ring.extend(seg[1:])
                remaining.pop(i)
                break
            elif abs(seg[-1][0] - last[0]) < 1e-6 and abs(seg[-1][1] - last[1]) < 1e-6:
                ring.extend(reversed(seg[:-1]))
                remaining.pop(i)
                break
    if ring and (ring[0] != ring[-1]):
        ring.append(ring[0])
    return ring


def overpass_to_geojson(data: dict) -> dict:
    features = []
    for el in data.get("elements", []):
        if el.get("type") != "relation":
            continue
        tags  = el.get("tags", {})
        name  = tags.get("name", "Unknown")
        short = tags.get("short_name", name)
        outer = [m for m in el.get("members", []) if m.get("role") == "outer" and m.get("type") == "way"]
        if not outer:
            continue
        coords = _build_ring(outer)
        if not coords or len(coords) < 4:
            continue
        features.append({
            "type": "Feature",
            "properties": {"name": name, "short_name": short},
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        })
    return {"type": "FeatureCollection", "features": features}


def download_geojson() -> dict:
    print("Скачиваю полигоны округов Москвы...")
    for i, query in enumerate(QUERIES, 1):
        print(f"  Запрос {i}/{len(QUERIES)}...")
        data = fetch_overpass(query)
        if data.get("elements"):
            gj = overpass_to_geojson(data)
            if gj["features"]:
                return gj
    return {"type": "FeatureCollection", "features": []}


def load_okrugs(geojson: dict) -> list:
    result = []
    for feat in geojson["features"]:
        try:
            poly  = shape(feat["geometry"])
            name  = feat["properties"].get("short_name") or feat["properties"]["name"]
            result.append({"name": name, "polygon": poly})
        except Exception as e:
            print(f"  Ошибка полигона: {e}")
    return result


def get_okrug(lat: float, lon: float, okrugs: list) -> str:
    pt = Point(float(lon), float(lat))
    for o in okrugs:
        if o["polygon"].contains(pt):
            return o["name"]
    return ""


def fill_okrug(df: pd.DataFrame, okrugs: list) -> pd.DataFrame:
    df = df.copy()
    mask = df["okrug"] == ""
    has_coords = df["lat"].notna() & df["lon"].notna()
    to_fill = mask & has_coords

    print(f"Заполняю okrug для {to_fill.sum():,} объявлений...")
    total = to_fill.sum()
    done  = 0

    for idx in df.index[to_fill]:
        df.at[idx, "okrug"] = get_okrug(df.at[idx, "lat"], df.at[idx, "lon"], okrugs)
        done += 1
        if done % 5000 == 0:
            print(f"  {done:,}/{total:,}...")

    return df


def main():
    # 1. Скачать GeoJSON
    gj = download_geojson()
    n  = len(gj["features"])
    print(f"\nОкругов получено: {n}")
    if n == 0:
        print("ОШИБКА: округа не скачались. Проверь интернет и запусти ещё раз.")
        return

    for f in gj["features"]:
        print(f"  {f['properties']['short_name']}")

    # 2. Сохранить GeoJSON в обе локации
    gj_text = json.dumps(gj, ensure_ascii=False, indent=2)
    GEOJSON_PATH.write_text(gj_text, encoding="utf-8")
    ML_GEOJSON_PATH.write_text(gj_text, encoding="utf-8")
    print(f"\nGeoJSON сохранён: {GEOJSON_PATH}")
    print(f"GeoJSON сохранён: {ML_GEOJSON_PATH}")

    # 3. Загрузить полигоны
    okrugs = load_okrugs(gj)

    # 4. Обогатить датасет
    print(f"\nЧитаю датасет: {PARQUET_MAIN}")
    df = pd.read_parquet(PARQUET_MAIN)

    before = (df["okrug"] != "").sum()
    df = fill_okrug(df, okrugs)
    after  = (df["okrug"] != "").sum()

    print(f"\nРезультат:")
    print(f"  До:    {before:,} объявлений с окр.")
    print(f"  После: {after:,} объявлений с окр. (из {len(df):,})")
    print(f"  Без координат / вне Москвы: {len(df) - after:,}")

    print("\nМедианная цена за м² по округам (после заполнения):")
    print(
        df[df["okrug"] != ""]
        .groupby("okrug")["price_per_m2"]
        .median()
        .sort_values(ascending=False)
        .map(lambda x: f"{x:,.0f} ₽")
    )

    # 5. Сохранить parquet
    df.to_parquet(PARQUET_MAIN, index=False)
    df.to_parquet(PARQUET_API,  index=False)
    print(f"\nДатасет обновлён:")
    print(f"  {PARQUET_MAIN}")
    print(f"  {PARQUET_API}")
    print("\nГотово! Перезапусти api-service, чтобы сбросить кэш Redis.")


if __name__ == "__main__":
    main()
