# app/utils/cookies.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from fastapi import Response, Request
from jose import jwt, JWTError

# Это ожидает app/dependencies.py:
SESSION_COOKIE = "sid"

# "remember me" cookie (на несколько минут, как требует задание)
REMEMBER_COOKIE = "remember"

# Настройки cookie
COOKIE_PATH = "/"
COOKIE_SAMESITE = "lax"
COOKIE_HTTPONLY = True

# В dev обычно http, поэтому secure=False
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"

# По заданию cookie должно жить несколько минут (например 5 минут)
REMEMBER_MAX_AGE_SECONDS = int(os.getenv("REMEMBER_MAX_AGE_SECONDS", "300"))

# Session-cookie можно оставить “дольше”, но реальная жизнь сессии — в session_manager (idle 2 минуты).
SESSION_COOKIE_MAX_AGE_SECONDS = int(os.getenv("SESSION_COOKIE_MAX_AGE_SECONDS", "3600"))

# Секрет для подписи remember-токена
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"


def set_session_cookie(response: Response, sid: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=sid,
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        path=COOKIE_PATH,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path=COOKIE_PATH)


def make_remember_token(payload: Dict[str, Any]) -> str:
    now = int(time.time())
    data = dict(payload)
    data["iat"] = now
    data["exp"] = now + REMEMBER_MAX_AGE_SECONDS
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALG)


def decode_remember_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        return None


def set_remember_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REMEMBER_COOKIE,
        value=token,
        max_age=REMEMBER_MAX_AGE_SECONDS,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        path=COOKIE_PATH,
    )


def clear_remember_cookie(response: Response) -> None:
    response.delete_cookie(key=REMEMBER_COOKIE, path=COOKIE_PATH)


def get_remember_payload(request: Request) -> Optional[Dict[str, Any]]:
    """
    То, чего не хватало: main.py ожидает эту функцию.
    Берём remember-token из cookie и декодируем.
    """
    token = request.cookies.get(REMEMBER_COOKIE)
    if not token:
        return None
    return decode_remember_token(token)
