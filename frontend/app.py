import streamlit as st
from api_client import is_authenticated, login, register, current_user, current_role
from components import render_sidebar
from styles import inject_css

st.set_page_config(
    page_title="ReVal — Оценка недвижимости",
    page_icon="🏠",
    layout="wide",
)


def render_auth() -> None:
    inject_css(authenticated=False)

    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        st.markdown("""
        <div class="login-card">
            <div class="login-logo">🏠</div>
            <p class="login-title">ReVal</p>
            <p class="login-subtitle">Интеллектуальная оценка стоимости недвижимости</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["Войти", "Регистрация"])

        with tab_login:
            email    = st.text_input("📧 Email", placeholder="you@example.com", key="login_email")
            password = st.text_input("🔑 Пароль", type="password", placeholder="••••••••", key="login_password")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.button("Войти", type="primary", use_container_width=True, key="btn_login"):
                if not email or not password:
                    st.error("Введите email и пароль")
                else:
                    with st.spinner("Вхожу..."):
                        error = login(email, password)
                    if error:
                        st.error(error)
                    else:
                        st.rerun()

        with tab_register:
            reg_email    = st.text_input("📧 Email", placeholder="you@example.com", key="reg_email")
            reg_password = st.text_input("🔑 Пароль", type="password", placeholder="Минимум 8 символов", key="reg_password")
            reg_password2 = st.text_input("🔑 Повторите пароль", type="password", placeholder="••••••••", key="reg_password2")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.button("Зарегистрироваться", type="primary", use_container_width=True, key="btn_register"):
                if not reg_email or not reg_password or not reg_password2:
                    st.error("Заполните все поля")
                elif reg_password != reg_password2:
                    st.error("Пароли не совпадают")
                elif len(reg_password) < 8:
                    st.error("Пароль должен быть не менее 8 символов")
                else:
                    with st.spinner("Регистрирую..."):
                        error = register(reg_email, reg_password)
                    if error:
                        st.error(error)
                    else:
                        st.success("Аккаунт создан! Войдите на вкладке «Войти»")


def render_home() -> None:
    inject_css(authenticated=True)
    render_sidebar()

    st.markdown("## Добро пожаловать в ReVal 🏠")
    st.markdown("Выберите раздел в боковой панели слева.")

    user = current_user()
    role = current_role()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"👤 **{user.get('email', '')}**\n\nРоль: `{role}`")
    with col2:
        st.info("🔮 **Оценка квартиры**\n\nВыберите параметры и получите прогноз цены")
    with col3:
        if role in ("analyst", "admin"):
            st.info("📊 **Статистика и аналитика**\n\nРаспределение цен по округам Москвы")
        else:
            st.info("📋 **История оценок**\n\nВсе ваши прошлые запросы в одном месте")


if not is_authenticated():
    render_auth()
else:
    render_home()
