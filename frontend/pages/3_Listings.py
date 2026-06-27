import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
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

st.caption(f"Найдено: **{total}** объявлений")

if not items:
    st.info("Ничего не найдено с выбранными фильтрами")
    st.stop()

df = pd.DataFrame(items).rename(columns={
    "id": "ID", "price": "Цена, ₽", "price_per_m2": "₽/м²",
    "total_area": "Площадь", "rooms_code": "Комнат", "floor": "Этаж",
    "floors": "Этажей", "property_kind": "Тип", "region_id": "Регион",
    "okrug": "Округ", "lat": "Широта", "lon": "Долгота",
})

st.dataframe(df, use_container_width=True, hide_index=True)
