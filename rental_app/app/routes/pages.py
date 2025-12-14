# app/routes/pages.py
from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..dependencies import get_current_user, CurrentUser
from ..utils.cookies import (
    SESSION_COOKIE,
    clear_session_cookie,
    clear_remember_cookie,
)
from ..utils.session_manager import session_manager

router = APIRouter(include_in_schema=False)

BASE_DIR = Path(__file__).resolve().parents[1]  # .../app
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _render(request: Request, name: str, user: Optional[CurrentUser] = None, **ctx):
    data = {"request": request, "user": user}
    data.update(ctx)
    return templates.TemplateResponse(name, data)


@router.get("/", response_class=HTMLResponse)
def index(request: Request, user: Optional[CurrentUser] = Depends(get_current_user)):
    return _render(request, "index.html", user=user)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: Optional[CurrentUser] = Depends(get_current_user)):
    # можно оставить auth_login.html (у тебя он уже есть и вызывает AuthUI.initLogin())
    return _render(request, "auth_login.html", user=user)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: Optional[CurrentUser] = Depends(get_current_user)):
    return _render(request, "auth_register.html", user=user)


@router.get("/catalog", response_class=HTMLResponse)
def catalog_page(request: Request, user: Optional[CurrentUser] = Depends(get_current_user)):
    return _render(request, "catalog.html", user=user)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: Optional[CurrentUser] = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url=f"/login?next={quote('/dashboard')}", status_code=303)
    return _render(request, "dashboard.html", user=user)


@router.get("/logout")
def logout(request: Request):
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        session_manager.delete(sid)

    resp = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(resp)
    clear_remember_cookie(resp)
    return resp
