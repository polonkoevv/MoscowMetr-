"""
Обёртка над requests для работы с ReVal API.
Хранит токены в st.session_state, автоматически обновляет access token при 401.
"""

import os
import streamlit as st
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")


# ── Вспомогательные функции ────────────────────────────────────

def _headers() -> dict:
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _try_refresh() -> bool:
    """Обновляет access token через refresh token. Возвращает True при успехе."""
    refresh_token = st.session_state.get("refresh_token")
    if not refresh_token:
        return False
    r = requests.post(f"{API_URL}/auth/refresh", json={"refresh_token": refresh_token}, timeout=10)
    if r.ok:
        st.session_state.access_token = r.json()["access_token"]
        return True
    # Refresh токен тоже истёк — выходим
    logout()
    return False


def _request(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{API_URL}{path}"
    r = getattr(requests, method)(url, headers=_headers(), timeout=15, **kwargs)
    if r.status_code == 401 and _try_refresh():
        r = getattr(requests, method)(url, headers=_headers(), timeout=15, **kwargs)
    return r


def api_get(path: str, **kwargs) -> requests.Response:
    return _request("get", path, **kwargs)


def api_post(path: str, **kwargs) -> requests.Response:
    return _request("post", path, **kwargs)


def api_patch(path: str, **kwargs) -> requests.Response:
    return _request("patch", path, **kwargs)


# ── Auth ───────────────────────────────────────────────────────

def register(email: str, password: str) -> str | None:
    """
    Регистрирует нового пользователя.
    Возвращает сообщение об ошибке или None при успехе.
    """
    r = requests.post(f"{API_URL}/auth/register", json={"email": email, "password": password}, timeout=10)
    if not r.ok:
        return r.json().get("detail", "Ошибка регистрации")
    return None


def login(email: str, password: str) -> str | None:
    """
    Авторизует пользователя.
    Сохраняет токены и данные пользователя в session_state.
    Возвращает сообщение об ошибке или None при успехе.
    """
    r = requests.post(f"{API_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
    if not r.ok:
        return r.json().get("detail", "Ошибка входа")

    data = r.json()
    st.session_state.access_token  = data["access_token"]
    st.session_state.refresh_token = data["refresh_token"]

    # Загружаем данные пользователя
    me = api_get("/auth/me")
    if me.ok:
        st.session_state.user = me.json()

    return None


def logout() -> None:
    refresh_token = st.session_state.get("refresh_token")
    if refresh_token:
        try:
            requests.post(f"{API_URL}/auth/logout", json={"refresh_token": refresh_token}, timeout=5)
        except Exception:
            pass
    for key in ("access_token", "refresh_token", "user"):
        st.session_state.pop(key, None)


def is_authenticated() -> bool:
    return bool(st.session_state.get("access_token"))


def current_user() -> dict:
    return st.session_state.get("user", {})


def current_role() -> str:
    return current_user().get("role", "")
