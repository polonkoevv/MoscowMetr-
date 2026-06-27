"""Unit-тесты хэширования паролей."""

from app.auth.passwords import hash_password, verify_password


def test_hash_is_not_plain():
    assert hash_password("secret123") != "secret123"


def test_verify_correct_password():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_two_hashes_differ():
    """bcrypt использует случайную соль — два хэша одного пароля не равны."""
    h1 = hash_password("samepassword")
    h2 = hash_password("samepassword")
    assert h1 != h2
    assert verify_password("samepassword", h1)
    assert verify_password("samepassword", h2)
