# app/utils/security.py
from __future__ import annotations

from passlib.context import CryptContext
from typing import Optional


# ВАЖНО:
# - pbkdf2_sha256: без лимита 72 bytes
# - bcrypt оставляем вторым, чтобы уметь проверять старые хэши (если они были)
_pwd = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],
    deprecated="auto",
)


def norm_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    return v or None


def norm_login(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip()
    return v or None


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("password required")

    # Защита от DoS/мусора (на всякий): но твой пароль 'hram123' точно проходит
    if len(password.encode("utf-8")) > 1024:
        raise ValueError("password too long")

    # Хэшируем pbkdf2_sha256 (первый в списке schemes)
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return _pwd.verify(password, password_hash)
    except Exception:
        return False
