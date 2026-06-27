import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from streamlit_folium import st_folium
import folium
from api_client import is_authenticated, api_post
from components import render_sidebar
from styles import inject_css

st.set_page_config(page_title="Оценить квартиру — ReVal", page_icon="🔮", layout="wide")

if not is_authenticated():
    st.switch_page("app.py")

inject_css(authenticated=True)
render_sidebar()

st.markdown("## 🔮 Оценить квартиру")
st.markdown("<p style='color:#64748b; margin-top:-0.5rem;'>Укажите параметры объекта и выберите местоположение на карте</p>", unsafe_allow_html=True)
st.divider()

col_form, col_map = st.columns([1, 1.2])

with col_form:
    st.markdown("#### Параметры объекта")

    total_area = st.number_input("Общая площадь, м²", min_value=5.0, max_value=1000.0, value=52.0, step=0.5)

    col1, col2 = st.columns(2)
    with col1:
        floor  = st.number_input("Этаж", min_value=1, max_value=100, value=5)
    with col2:
        floors = st.number_input("Этажей в доме", min_value=1, max_value=100, value=9)

    rooms_code = st.selectbox(
        "Количество комнат",
        options=[None, 0, 1, 2, 3, 4, 5],
        format_func=lambda x: "Не указано" if x is None else ("Студия" if x == 0 else f"{x}-комнатная"),
    )

    property_kind = st.selectbox(
        "Тип объекта",
        options=[None, "flat", "room", "house", "cottage", "commercial"],
        format_func=lambda x: "Не указано" if x is None else {
            "flat": "Квартира", "room": "Комната", "house": "Дом",
            "cottage": "Коттедж", "commercial": "Коммерческая"
        }.get(x, x),
    )

    new_building = st.checkbox("Новостройка")

with col_map:
    st.markdown("#### Местоположение")
    st.caption("Нажмите на карту, чтобы указать координаты объекта")

    m = folium.Map(location=[55.7558, 37.6173], zoom_start=10, tiles="CartoDB positron")

    if "lat" in st.session_state and "lon" in st.session_state:
        folium.Marker(
            [st.session_state.lat, st.session_state.lon],
            tooltip="Выбранный объект",
            icon=folium.Icon(color="blue", icon="home", prefix="fa"),
        ).add_to(m)

    map_data = st_folium(m, height=360, width="100%", key="predict_map")

    if map_data and map_data.get("last_clicked"):
        st.session_state.lat = map_data["last_clicked"]["lat"]
        st.session_state.lon = map_data["last_clicked"]["lng"]

    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    if lat and lon:
        st.success(f"📍 Координаты: {lat:.5f}, {lon:.5f}")
    else:
        st.info("Координаты не выбраны")

st.divider()

if st.button("🔮 Оценить стоимость", type="primary"):
    if floor > floors:
        st.error(f"Этаж ({floor}) не может быть больше этажности дома ({floors})")
    else:
        payload = {
            "total_area":    total_area,
            "floor":         floor,
            "floors":        floors,
            "rooms_code":    rooms_code,
            "property_kind": property_kind,
            "new_building":  new_building,
            "lat":           st.session_state.get("lat"),
            "lon":           st.session_state.get("lon"),
        }

        with st.spinner("Рассчитываю стоимость..."):
            r = api_post("/predict", json=payload)

        if r.ok:
            result = r.json()
            st.markdown("#### Результат оценки")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 Стоимость",         f"{result['price']:,} ₽".replace(",", " "))
            c2.metric("📐 Цена за м²",         f"{result['price_per_m2']:,} ₽".replace(",", " "))
            c3.metric("📍 Округ",              result["okrug"] or "Не определён")
            c4.metric("📊 Погрешность модели", f"{result['mape']:.1f}%")
        else:
            st.error(f"Ошибка: {r.json().get('detail', 'Неизвестная ошибка')}")
