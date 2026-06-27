import streamlit as st
from api_client import current_user, current_role, logout


def render_sidebar() -> None:
    with st.sidebar:
        # Лого
        st.markdown("""
        <div style="padding: 1.2rem 0.5rem 0.5rem; text-align:center;">
            <span style="font-size:2rem;">🏠</span>
            <p style="margin:0; font-size:1.4rem; font-weight:700; color:#1e293b; letter-spacing:-0.5px;">ReVal</p>
            <p style="margin:0; font-size:0.75rem; color:#94a3b8;">Оценка недвижимости</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Информация о пользователе
        user = current_user()
        role = current_role()
        role_badge = {"admin": "🔴 Администратор", "analyst": "🟡 Аналитик", "user": "🟢 Пользователь"}.get(role, role)

        st.markdown(f"""
        <div style="background:#f1f5f9; border-radius:10px; padding:0.75rem 1rem; margin-bottom:0.5rem;">
            <p style="margin:0; font-size:0.8rem; color:#64748b;">Вы вошли как</p>
            <p style="margin:0; font-weight:600; color:#1e293b; font-size:0.9rem; word-break:break-all;">{user.get('email', '')}</p>
            <p style="margin:0.25rem 0 0; font-size:0.8rem; color:#475569;">{role_badge}</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Навигация
        st.markdown("<p style='font-size:0.7rem; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:0.1em; margin:0 0 0.5rem;'>Навигация</p>", unsafe_allow_html=True)

        st.page_link("app.py",             label="🏠  Главная")
        st.page_link("pages/1_Predict.py", label="🔮  Оценить квартиру")
        st.page_link("pages/2_History.py", label="📋  История оценок")

        if role in ("analyst", "admin"):
            st.markdown("<p style='font-size:0.7rem; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:0.1em; margin:0.75rem 0 0.5rem;'>Аналитика</p>", unsafe_allow_html=True)
            st.page_link("pages/3_Listings.py", label="🗂  Объявления")
            st.page_link("pages/4_Stats.py",    label="📊  Статистика")

        if role == "admin":
            st.markdown("<p style='font-size:0.7rem; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:0.1em; margin:0.75rem 0 0.5rem;'>Управление</p>", unsafe_allow_html=True)
            st.page_link("pages/5_Admin.py", label="⚙️  Пользователи")

        # Кнопка выхода внизу
        st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)
        st.divider()
        if st.button("🚪  Выйти", use_container_width=True):
            logout()
            st.rerun()
