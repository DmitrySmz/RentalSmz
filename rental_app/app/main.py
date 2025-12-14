from __future__ import annotations

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from .routes import equipment
from .routes import auth as auth_routes
from .dependencies import require_user
from .database import SessionLocal
from . import models, schemas
from .utils.cookies import (
    get_remember_payload,
    set_session_cookie,
    clear_remember_cookie,
)
from .utils.session_manager import session_manager, SessionUser

app = FastAPI(title="Rental App")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

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

    # проверяем в БД, что пользователь ещё активен
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


# Каталог и доступность
app.include_router(equipment.router)

# Auth API
app.include_router(auth_routes.router)


# Нормальная ручка /auth/me (без костылей)
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
