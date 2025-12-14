# app/routes/auth.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from .. import models, schemas
from ..dependencies import require_user, CurrentUser
from ..utils.security import hash_password, verify_password, norm_email, norm_login
from ..utils.session_manager import session_manager, SessionUser
from ..utils.cookies import (
    SESSION_COOKIE,
    REMEMBER_COOKIE,
    set_session_cookie,
    clear_session_cookie,
    make_remember_token,
    set_remember_cookie,
    clear_remember_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_session(
    response: Response,
    *,
    kind: str,
    user_id: int,
    remember: bool,
) -> None:
    sid = session_manager.create(SessionUser(kind=kind, user_id=user_id))
    set_session_cookie(response, sid)

    if remember:
        token = make_remember_token({"kind": kind, "user_id": user_id})
        set_remember_cookie(response, token)
    else:
        # если remember выключен — подчистим remember-cookie
        clear_remember_cookie(response)


@router.post("/client/register", response_model=schemas.AuthMeOut)
def client_register(payload: schemas.ClientRegisterIn, response: Response, db: Session = Depends(get_db)):
    email = norm_email(payload.email)
    if not email:
        raise HTTPException(status_code=400, detail="email required")

    try:
        pwd_hash = hash_password(payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    obj = models.Client(
        email=email,
        password_hash=pwd_hash,
        phone=payload.phone,
        first_name=payload.first_name,
        last_name=payload.last_name,
        is_active=True,
    )

    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="email already exists")

    db.refresh(obj)
    _issue_session(response, kind="client", user_id=obj.client_id, remember=payload.remember)

    return schemas.AuthMeOut(
        kind="client",
        id=obj.client_id,
        email=obj.email,
        first_name=obj.first_name,
        last_name=obj.last_name,
    )


@router.post("/client/login", response_model=schemas.AuthMeOut)
def client_login(payload: schemas.ClientLoginIn, response: Response, db: Session = Depends(get_db)):
    email = norm_email(payload.email)
    obj = db.execute(select(models.Client).where(models.Client.email == email)).scalar_one_or_none()
    if not obj or not obj.is_active:
        raise HTTPException(status_code=401, detail="bad credentials")
    if not verify_password(payload.password, obj.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")

    _issue_session(response, kind="client", user_id=obj.client_id, remember=payload.remember)

    return schemas.AuthMeOut(
        kind="client",
        id=obj.client_id,
        email=obj.email,
        first_name=obj.first_name,
        last_name=obj.last_name,
    )


@router.post("/employee/login", response_model=schemas.AuthMeOut)
def employee_login(payload: schemas.EmployeeLoginIn, response: Response, db: Session = Depends(get_db)):
    login = norm_login(payload.login)
    obj = db.execute(select(models.Employee).where(models.Employee.login == login)).scalar_one_or_none()
    if not obj or not obj.is_active:
        raise HTTPException(status_code=401, detail="bad credentials")
    if not verify_password(payload.password, obj.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")

    _issue_session(response, kind="employee", user_id=obj.employee_id, remember=payload.remember)

    return schemas.AuthMeOut(
        kind="employee",
        id=obj.employee_id,
        login=obj.login,
        role=obj.role,
        rental_point_id=obj.rental_point_id,
        first_name=obj.first_name,
        last_name=obj.last_name,
    )


@router.post("/logout")
def logout(request: Request, response: Response):
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        session_manager.delete(sid)

    clear_session_cookie(response)
    clear_remember_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=schemas.AuthMeOut)
def me(user: CurrentUser = Depends(require_user)):
    if user.kind == "client" and user.client:
        c = user.client
        return schemas.AuthMeOut(
            kind="client",
            id=c.client_id,
            email=c.email,
            first_name=c.first_name,
            last_name=c.last_name,
        )
    if user.kind == "employee" and user.employee:
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
    raise HTTPException(status_code=401, detail="not authenticated")


@router.get("/session", response_model=schemas.AuthSessionOut)
def session_status(request: Request):
    # ВАЖНО: этот endpoint НЕ должен продлевать idle-сессию
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return schemas.AuthSessionOut(authenticated=False, remaining_seconds=0)

    left = session_manager.remaining(sid)
    return schemas.AuthSessionOut(authenticated=left > 0, remaining_seconds=left)


@router.post("/ping", response_model=schemas.AuthSessionOut)
def ping(request: Request):
    # ping продлевает idle-сессию
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return schemas.AuthSessionOut(authenticated=False, remaining_seconds=0)

    rec = session_manager.touch(sid)
    if not rec:
        return schemas.AuthSessionOut(authenticated=False, remaining_seconds=0)

    return schemas.AuthSessionOut(authenticated=True, remaining_seconds=rec.remaining_seconds())
