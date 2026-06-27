import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from api_client import is_authenticated, api_get, current_role
from components import render_sidebar
from styles import inject_css

st.set_page_config(page_title="Объявления — ReVal", page_icon="🗂", layout="wide")

if not is_authenticated():
    st.switch_page("app.py")

if current_role() not in ("analyst", "admin"):
    inject_css(authenticated=True)
    render_sidebar()
    st.error("Доступ только для аналитиков и администраторов")
    st.stop()

inject_css(authenticated=True)
render_sidebar()

st.markdown("## 🗂 Объявления")
st.markdown("<p style='color:#64748b; margin-top:-0.5rem;'>База объявлений с фильтрацией</p>", unsafe_allow_html=True)
st.divider()

with st.sidebar:
    st.markdown("---")
    st.markdown("<p style='font-size:0.7rem; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:0.1em;'>Фильтры</p>", unsafe_allow_html=True)

    okrug = st.selectbox("Округ",
        [None, "ЦАО", "САО", "СВАО", "ВАО", "ЮВАО", "ЮАО", "ЮЗАО", "ЗАО", "СЗАО"],
        format_func=lambda x: "Все округа" if x is None else x,
    )

    property_kind = st.selectbox("Тип объекта",
        [None, "flat", "room", "house", "cottage", "commercial"],
        format_func=lambda x: "Все типы" if x is None else {
            "flat": "Квартира", "room": "Комната", "house": "Дом",
            "cottage": "Коттедж", "commercial": "Коммерческая"
        }.get(x, x),
    )

    st.caption("Цена, ₽")
    min_price = st.number_input("от", min_value=0, value=0, step=500_000, key="min_p")
    max_price = st.number_input("до", min_value=0, value=0, step=500_000, key="max_p")

    st.caption("Площадь, м²")
    min_area = st.number_input("от", min_value=0.0, value=0.0, step=5.0, key="min_a")
    max_area = st.number_input("до", min_value=0.0, value=0.0, step=5.0, key="max_a")

    limit = st.select_slider("Записей", options=[50, 100, 200, 500], value=100)

params = {
    "limit": limit, "offset": 0,
    **({"okrug":         okrug}         if okrug         else {}),
    **({"property_kind": property_kind} if property_kind else {}),
    **({"min_price":     min_price}     if min_price > 0 else {}),
    **({"max_price":     max_price}     if max_price > 0 else {}),
    **({"min_area":      min_area}      if min_area  > 0 else {}),
    **({"max_area":      max_area}      if max_area  > 0 else {}),
}

with st.spinner("Загружаю объявления..."):
    r = api_get("/listings", params=params)

if not r.ok:
    st.error("Не удалось загрузить объявления")
    st.stop()

data  = r.json()
total = data["total"]
items = data["items"]

st.caption(f"Найдено: **{total}** объявлений (показано: {len(items)})")

if not items:
    st.info("Ничего не найдено с выбранными фильтрами")
    st.stop()

df = pd.DataFrame(items)

# ── Таблица ───────────────────────────────────────────────────────────────────
st.dataframe(
    df.rename(columns={
        "id": "ID", "price": "Цена, ₽", "price_per_m2": "₽/м²",
        "total_area": "Площадь", "rooms_code": "Комнат", "floor": "Этаж",
        "floors": "Этажей", "property_kind": "Тип", "region_id": "Регион",
        "okrug": "Округ", "lat": "Широта", "lon": "Долгота",
    }),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── Карта ─────────────────────────────────────────────────────────────────────
df_map = df[df["lat"].notna() & df["lon"].notna()].copy()

st.markdown(f"#### 🗺 Карта объявлений")
st.caption(f"Объявлений с координатами: {len(df_map)} из {len(df)}")

if df_map.empty:
    st.info("У выбранных объявлений нет координат для отображения на карте")
else:
    def _int(val) -> str:
        """Конвертирует значение в строку, возвращает '—' для None/NaN."""
        try:
            return str(int(val)) if val is not None and val == val else "—"
        except (TypeError, ValueError):
            return "—"

    PROPERTY_KIND_RU = {
        "flat": "Квартира", "room": "Комната", "house": "Дом",
        "cottage": "Коттедж", "commercial": "Коммерческая",
        "land": "Участок", "garage": "Гараж",
    }

    center_lat = df_map["lat"].median()
    center_lon = df_map["lon"].median()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles="CartoDB positron",
    )

    cluster = MarkerCluster(
        options={"maxClusterRadius": 40, "disableClusteringAtZoom": 14}
    ).add_to(m)

    for row in df_map.itertuples():
        kind_ru    = PROPERTY_KIND_RU.get(row.property_kind or "", row.property_kind or "—")
        price_fmt  = f"{int(row.price):,}".replace(",", " ")
        pm2_fmt    = f"{int(row.price_per_m2):,}".replace(",", " ")
        rooms      = _int(row.rooms_code)
        okrug_str  = row.okrug or "—"

        popup_html = f"""
        <div style="font-family:Arial,sans-serif; font-size:13px; min-width:180px;">
            <b style="font-size:14px;">💰 {price_fmt} ₽</b><br>
            <span style="color:#64748b;">{pm2_fmt} ₽/м²</span>
            <hr style="margin:6px 0; border-color:#e2e8f0;">
            <b>Тип:</b> {kind_ru}<br>
            <b>Площадь:</b> {row.total_area} м²<br>
            <b>Комнат:</b> {rooms}<br>
            <b>Этаж:</b> {_int(row.floor)} / {_int(row.floors)}<br>
            <b>Округ:</b> {okrug_str}
        </div>
        """

        folium.CircleMarker(
            location=[row.lat, row.lon],
            radius=6,
            color="#2563EB",
            fill=True,
            fill_color="#2563EB",
            fill_opacity=0.7,
            weight=1,
            popup=folium.Popup(popup_html, max_width=220),
            tooltip=f"{price_fmt} ₽ · {row.total_area} м²",
        ).add_to(cluster)

    st_folium(m, height=500, use_container_width=True, returned_objects=[])
