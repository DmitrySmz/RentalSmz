from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..dependencies import get_current_user, require_user
from ..utils.cookies import clear_session_cookie, clear_remember_cookie, SESSION_COOKIE
from ..utils.session_manager import session_manager

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["pages"])

@router.get("/")
def home(request: Request, user=Depends(get_current_user)):
    # Просто отдаём каталог (шаблон у тебя уже есть)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@router.get("/login")
def login_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "user": user})

@router.get("/register")
def register_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request, "user": user})

@router.get("/dashboard")
def dashboard(request: Request, user=Depends(require_user)):
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@router.get("/logout")
def logout_page(request: Request):
    # Сделаем logout как обычный GET для UI (удобно),
    # но чистим sid и remember + удаляем запись из session_manager.
    resp = RedirectResponse("/login", status_code=303)

    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        session_manager.delete(sid)

    clear_session_cookie(resp)
    clear_remember_cookie(resp)
    return resp
