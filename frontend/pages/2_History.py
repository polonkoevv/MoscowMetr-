import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from api_client import is_authenticated, api_get
from components import render_sidebar
from styles import inject_css

st.set_page_config(page_title="История оценок — ReVal", page_icon="📋", layout="wide")

if not is_authenticated():
    st.switch_page("app.py")

inject_css(authenticated=True)
render_sidebar()

st.markdown("## 📋 История оценок")
st.markdown("<p style='color:#64748b; margin-top:-0.5rem;'>Все ваши прошлые запросы, от новых к старым</p>", unsafe_allow_html=True)
st.divider()

col1, col2 = st.columns([1, 4])
with col1:
    limit = st.selectbox("Записей на странице", [10, 20, 50], index=1)
with col2:
    page = st.number_input("Страница", min_value=1, value=1, step=1)

offset = (page - 1) * limit

with st.spinner("Загружаю историю..."):
    r = api_get("/predict/history", params={"limit": limit, "offset": offset})

if not r.ok:
    st.error("Не удалось загрузить историю")
    st.stop()

data  = r.json()
total = data["total"]
items = data["items"]

total_pages = max(1, -(-total // limit))
st.caption(f"Всего оценок: **{total}** · Страница {page} из {total_pages}")

if not items:
    st.info("История пуста — сделайте первую оценку на странице «Оценить квартиру»")
    st.stop()

rows = []
for item in items:
    req  = item["request_data"]
    resp = item["response_data"]
    rows.append({
        "Дата":        pd.to_datetime(item["created_at"]).strftime("%d.%m.%Y %H:%M"),
        "Площадь, м²": req.get("total_area"),
        "Этаж":        f"{req.get('floor')}/{req.get('floors')}",
        "Тип":         req.get("property_kind") or "—",
        "Округ":       resp.get("okrug") or "—",
        "Цена, ₽":     f"{resp.get('price', 0):,}".replace(",", " "),
        "₽/м²":        f"{resp.get('price_per_m2', 0):,}".replace(",", " "),
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
