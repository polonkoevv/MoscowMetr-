"""
Скачивает полигоны административных округов Москвы из OpenStreetMap (Overpass API).
Сохраняет в data/moscow_okrugs.geojson.

Запуск: python scripts/download_okrugs.py
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

OUTPUT_PATH = Path("data/moscow_okrugs.geojson")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Москва в OSM: relation/2555133 → area ID = 3602555133
QUERIES = [
    # Вариант 1: через area ID Москвы
    """
[out:json][timeout:60];
area(3602555133)->.moscow;
(
  relation["admin_level"="5"]["boundary"="administrative"](area.moscow);
);
out geom;
""",
    # Вариант 2: по bbox Москвы
    """
[out:json][timeout:60];
(
  relation["admin_level"="5"]["boundary"="administrative"]
          (55.14,36.80,56.02,37.97);
);
out geom;
""",
    # Вариант 3: по имени с regexp
    """
[out:json][timeout:60];
(
  relation["admin_level"="5"]["boundary"="administrative"]
          ["name"~"округ"](55.14,36.80,56.02,37.97);
);
out geom;
""",
]

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def fetch(query: str) -> dict:
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
                    print(f"  OK: {url}")
                    return data
        except Exception as e:
            print(f"  Ошибка {url}: {e}")
    return {"elements": []}


def overpass_to_geojson(data: dict) -> dict:
    features = []
    for element in data.get("elements", []):
        if element.get("type") != "relation":
            continue
        tags  = element.get("tags", {})
        name  = tags.get("name", "Unknown")
        short = tags.get("short_name", name)

        outer_ways = [
            m for m in element.get("members", [])
            if m.get("role") == "outer" and m.get("type") == "way"
        ]
        if not outer_ways:
            continue

        coords = _build_ring(outer_ways)
        if not coords or len(coords) < 4:
            continue

        features.append({
            "type": "Feature",
            "properties": {"name": name, "short_name": short},
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        })
    return {"type": "FeatureCollection", "features": features}


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
            if _close(seg[0], last):
                ring.extend(seg[1:])
                remaining.pop(i)
                break
            elif _close(seg[-1], last):
                ring.extend(reversed(seg[:-1]))
                remaining.pop(i)
                break
    if ring and not _close(ring[0], ring[-1]):
        ring.append(ring[0])
    return ring


def _close(a, b, tol=1e-6):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def main():
    geojson = {"type": "FeatureCollection", "features": []}

    for i, query in enumerate(QUERIES, 1):
        print(f"\nЗапрос {i}/{len(QUERIES)}...")
        data = fetch(query)
        n = len(data.get("elements", []))
        print(f"  Элементов: {n}")
        if n > 0:
            geojson = overpass_to_geojson(data)
            if geojson["features"]:
                break

    n_feat = len(geojson["features"])
    print(f"\nОкругов в GeoJSON: {n_feat}")
    for f in geojson["features"]:
        print(f"  {f['properties']['name']}")

    OUTPUT_PATH.write_text(json.dumps(geojson, ensure_ascii=False, indent=2))
    print(f"\nСохранено: {OUTPUT_PATH}")

    if n_feat == 0:
        print("\nВНИМАНИЕ: округа не скачались. Запусти скрипт позже или проверь интернет.")


if __name__ == "__main__":
    main()
