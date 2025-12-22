# app/main.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from .database import SessionLocal
from . import models, schemas
from .dependencies import require_user
from .routes import pages, equipment, rentals
from .routes import auth as auth_routes
from .routes import admin as admin_routes
from .routes import demo_concurrency as demo_concurrency_routes

from .utils.session_manager import session_manager, SessionUser
from .utils.cookies import (
    get_remember_payload,
    clear_remember_cookie,
    set_session_cookie,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(title="Rental App")

# статика и шаблоны
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# HTML страницы
app.include_router(pages.router)

# API
app.include_router(equipment.router)
app.include_router(rentals.router)
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(demo_concurrency_routes.router)


# -------- Remember-cookie auto-login middleware --------
@app.middleware("http")
async def remember_login_mw(request: Request, call_next):
    sid = request.cookies.get("sid")
    if sid:
        return await call_next(request)

    payload = get_remember_payload(request)
    if not payload:
        return await call_next(request)

    kind = payload.get("kind")
    user_id = payload.get("user_id")

    if kind not in ("client", "employee") or not isinstance(user_id, int):
        response = await call_next(request)
        clear_remember_cookie(response)
        return response

    db = SessionLocal()
    try:
        if kind == "client":
            obj = db.execute(select(models.Client).where(models.Client.client_id == user_id)).scalar_one_or_none()
            ok = bool(obj and obj.is_active)
        else:
            obj = db.execute(select(models.Employee).where(models.Employee.employee_id == user_id)).scalar_one_or_none()
            ok = bool(obj and obj.is_active)
    finally:
        db.close()

    if not ok:
        response = await call_next(request)
        clear_remember_cookie(response)
        return response

    new_sid = session_manager.create(SessionUser(kind=kind, user_id=user_id))
    request.state.sid = new_sid

    response = await call_next(request)
    set_session_cookie(response, new_sid)
    return response


# /auth/me (нормальный)
@app.get("/auth/me", response_model=schemas.AuthMeOut, tags=["auth"])
def auth_me(user=Depends(require_user)):
    if user.kind == "client" and user.client:
        c = user.client
        return schemas.AuthMeOut(
            kind="client",
            id=c.client_id,
            email=c.email,
            first_name=c.first_name,
            last_name=c.last_name,
        )
    e = user.employee
    return schemas.AuthMeOut(
        kind="employee",
        id=e.employee_id,
        login=e.login,
        role=e.role,
        rental_point_id=e.rental_point_id,
        first_name=e.first_name,
        last_name=e.last_name,
    )
