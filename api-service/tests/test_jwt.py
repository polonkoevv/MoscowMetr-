"""Unit-тесты JWT-токенов."""

from app.auth.jwt import create_access_token, decode_token


def test_create_and_decode_token():
    token = create_access_token(subject=42, role="user")
    payload = decode_token(token)

    assert payload["sub"] == "42"
    assert payload["role"] == "user"


def test_decode_invalid_token():
    payload = decode_token("this.is.not.a.valid.token")
    assert payload == {}


def test_decode_tampered_token():
    token = create_access_token(subject=1, role="admin")
    tampered = token[:-5] + "XXXXX"
    assert decode_token(tampered) == {}
