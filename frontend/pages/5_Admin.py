import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from api_client import is_authenticated, api_get, api_patch, current_role
from components import render_sidebar
from styles import inject_css

st.set_page_config(page_title="Пользователи — ReVal", page_icon="⚙️", layout="wide")

if not is_authenticated():
    st.switch_page("app.py")

if current_role() != "admin":
    inject_css(authenticated=True)
    render_sidebar()
    st.error("Доступ только для администраторов")
    st.stop()

inject_css(authenticated=True)
render_sidebar()

st.markdown("## ⚙️ Управление пользователями")
st.markdown("<p style='color:#64748b; margin-top:-0.5rem;'>Изменение ролей и статуса пользователей</p>", unsafe_allow_html=True)
st.divider()

r = api_get("/admin/users")
if not r.ok:
    st.error("Не удалось загрузить список пользователей")
    st.stop()

users = r.json()
st.caption(f"Всего пользователей: **{len(users)}**")

df = pd.DataFrame(users).rename(columns={
    "id": "ID", "email": "Email", "role": "Роль", "is_active": "Активен",
})
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.markdown("#### Изменить пользователя")

user_options = {u["email"]: u for u in users}
selected_email = st.selectbox("Выберите пользователя", list(user_options.keys()))
selected = user_options[selected_email]

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    new_role = st.selectbox(
        "Роль",
        ["user", "analyst", "admin"],
        index=["user", "analyst", "admin"].index(selected["role"]),
    )
with col2:
    new_active = st.checkbox("Активен", value=selected["is_active"])
with col3:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if st.button("💾 Сохранить", type="primary"):
        payload = {}
        if new_role != selected["role"]:
            payload["role"] = new_role
        if new_active != selected["is_active"]:
            payload["is_active"] = new_active

        if not payload:
            st.info("Нет изменений")
        else:
            resp = api_patch(f"/admin/users/{selected['id']}", json=payload)
            if resp.ok:
                st.success(f"✅ Пользователь {selected_email} обновлён")
                st.rerun()
            else:
                st.error(resp.json().get("detail", "Ошибка"))
