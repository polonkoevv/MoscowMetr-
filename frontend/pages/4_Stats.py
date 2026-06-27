import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.express as px
import pandas as pd
from api_client import is_authenticated, api_get, current_role
from components import render_sidebar
from styles import inject_css

st.set_page_config(page_title="Статистика — ReVal", page_icon="📊", layout="wide")

if not is_authenticated():
    st.switch_page("app.py")

if current_role() not in ("analyst", "admin"):
    inject_css(authenticated=True)
    render_sidebar()
    st.error("Доступ только для аналитиков и администраторов")
    st.stop()

inject_css(authenticated=True)
render_sidebar()

st.markdown("## 📊 Статистика")
st.markdown("<p style='color:#64748b; margin-top:-0.5rem;'>Сводные данные по базе объявлений и метрики модели</p>", unsafe_allow_html=True)
st.divider()

with st.spinner("Загружаю данные..."):
    r = api_get("/stats")

if not r.ok:
    st.error("Не удалось загрузить статистику")
    st.stop()

data = r.json()

# ── Метрики ────────────────────────────────────────────────────
st.markdown("#### Показатели модели CatBoost")
m = data.get("model_metrics", {})
c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Объявлений в базе", f"{data['total_listings']:,}".replace(",", " "))
c2.metric("MAPE",  f"{m['mape']:.1f}%"   if m.get("mape")  else "—")
c3.metric("MAE",   f"{m['mae']:,.0f} ₽".replace(",", " ")  if m.get("mae")  else "—")
c4.metric("RMSE",  f"{m['rmse']:,.0f} ₽".replace(",", " ") if m.get("rmse") else "—")

st.divider()

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### Медианная цена за м² по округам")
    okrug_data = data.get("price_by_okrug", [])
    if okrug_data:
        df_okrug = pd.DataFrame(okrug_data).sort_values("median_pm2", ascending=True)
        fig = px.bar(
            df_okrug, x="median_pm2", y="okrug", orientation="h",
            labels={"median_pm2": "₽/м²", "okrug": ""},
            color="median_pm2",
            color_continuous_scale=["#bfdbfe", "#2563EB"],
            text="median_pm2",
        )
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig.update_layout(
            coloraxis_showscale=False,
            margin=dict(l=0, r=60, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown("#### Распределение по типам объектов")
    kind_data = data.get("property_kind_dist", {})
    if kind_data:
        labels_ru = {
            "flat": "Квартира", "room": "Комната", "house": "Дом",
            "cottage": "Коттедж", "commercial": "Коммерческая", "land": "Участок",
        }
        df_kind = pd.DataFrame([
            {"Тип": labels_ru.get(k, k), "Кол-во": v} for k, v in kind_data.items()
        ])
        fig2 = px.pie(
            df_kind, names="Тип", values="Кол-во",
            color_discrete_sequence=["#2563EB", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe", "#dbeafe"],
            hole=0.4,
        )
        fig2.update_traces(textposition="inside", textinfo="percent+label")
        fig2.update_layout(
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)

# ── Таблица ────────────────────────────────────────────────────
if okrug_data:
    st.markdown("#### Детализация по округам")
    df_table = pd.DataFrame(okrug_data).rename(columns={
        "okrug": "Округ", "median_pm2": "Медиана ₽/м²", "count": "Объявлений",
    }).sort_values("Медиана ₽/м²", ascending=False)
    st.dataframe(df_table, use_container_width=True, hide_index=True)
