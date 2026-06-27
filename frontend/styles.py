import streamlit as st


def inject_css(authenticated: bool = True) -> None:
    """
    Инжектирует глобальный CSS.
    authenticated=False — скрывает сайдбар и применяет стиль логин-страницы.
    """

    sidebar_css = """
        [data-testid="stSidebar"],
        [data-testid="collapsedControl"],
        [data-testid="stSidebarNav"] { display: none !important; }
    """ if not authenticated else ""

    login_bg_css = """
        .stApp {
            background: linear-gradient(135deg, #0f2044 0%, #1a3a6b 50%, #2563EB 100%) !important;
            min-height: 100vh;
        }
    """ if not authenticated else ""

    st.markdown(f"""
    <style>

    /* ── Типографика и базовые стили ────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}

    /* ── Скрыть стандартный header Streamlit ────────────────── */
    #MainMenu, footer, header {{ visibility: hidden; }}

    /* ── Sidebar ─────────────────────────────────────────────── */
    {sidebar_css}

    [data-testid="stSidebar"] {{
        background: #ffffff !important;
        border-right: 1px solid #e2e8f0;
        padding-top: 0 !important;
    }}

    [data-testid="stSidebarNav"] {{ display: none !important; }}

    /* ── Кнопки ──────────────────────────────────────────────── */
    .stButton > button {{
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 0.5rem 1.25rem !important;
        transition: all 0.2s ease !important;
        border: none !important;
    }}

    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, #2563EB, #1d4ed8) !important;
        color: white !important;
        box-shadow: 0 4px 14px rgba(37,99,235,0.35) !important;
    }}

    .stButton > button[kind="primary"]:hover {{
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(37,99,235,0.45) !important;
    }}

    .stButton > button[kind="secondary"] {{
        background: #f1f5f9 !important;
        color: #475569 !important;
    }}

    /* ── Inputs ──────────────────────────────────────────────── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {{
        border-radius: 8px !important;
        border: 2px solid #e2e8f0 !important;
        padding: 0.6rem 0.9rem !important;
        font-size: 0.95rem !important;
        transition: border-color 0.2s !important;
        background: #f8fafc !important;
    }}

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {{
        border-color: #2563EB !important;
        background: #fff !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
    }}

    /* ── Selectbox ───────────────────────────────────────────── */
    [data-testid="stSelectbox"] > div > div {{
        border-radius: 8px !important;
        border: 2px solid #e2e8f0 !important;
        background: #f8fafc !important;
    }}

    /* ── Метрики ─────────────────────────────────────────────── */
    [data-testid="stMetric"] {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.2rem 1.5rem !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }}

    [data-testid="stMetricLabel"] {{
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b !important;
    }}

    [data-testid="stMetricValue"] {{
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: #1e293b !important;
    }}

    /* ── Dataframe ───────────────────────────────────────────── */
    [data-testid="stDataFrame"] {{
        border-radius: 12px !important;
        overflow: hidden;
        border: 1px solid #e2e8f0 !important;
    }}

    /* ── Алерты/инфо ─────────────────────────────────────────── */
    [data-testid="stAlert"] {{
        border-radius: 10px !important;
    }}

    /* ── Divider ─────────────────────────────────────────────── */
    hr {{ border-color: #e2e8f0 !important; }}

    /* ── Логин-фон ───────────────────────────────────────────── */
    {login_bg_css}

    /* ── Login card ──────────────────────────────────────────── */
    .login-card {{
        background: white;
        border-radius: 20px;
        padding: 2.5rem 2.5rem 2rem;
        box-shadow: 0 25px 60px rgba(0,0,0,0.35);
        max-width: 420px;
        margin: 0 auto;
    }}

    .login-logo {{
        text-align: center;
        font-size: 3rem;
        margin-bottom: 0.25rem;
    }}

    .login-title {{
        text-align: center;
        font-size: 1.75rem;
        font-weight: 700;
        color: #1e293b;
        margin: 0;
    }}

    .login-subtitle {{
        text-align: center;
        color: #64748b;
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }}

    </style>
    """, unsafe_allow_html=True)
