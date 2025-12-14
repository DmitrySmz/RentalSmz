from __future__ import annotations

from typing import Optional, Iterable, Set

from fastapi import Depends, HTTPException, Cookie, Request
from sqlalchemy.orm import Session
from sqlalchemy import select

from .database import get_db
from . import models
from .utils.session_manager import session_manager, SessionUser
from .utils.cookies import SESSION_COOKIE


class CurrentUser:
    def __init__(self, kind: str, client: Optional[models.Client] = None, employee: Optional[models.Employee] = None):
        self.kind = kind
        self.client = client
        self.employee = employee

    @property
    def id(self) -> int:
        if self.kind == "client" and self.client:
            return self.client.client_id
        if self.kind == "employee" and self.employee:
            return self.employee.employee_id
        raise RuntimeError("user not loaded")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> Optional[CurrentUser]:
    """Return user or None (guest).

    We refresh session on normal requests, but NOT on `/auth/session`
    so that the idle-timer demo can work (polling won't prolong the session).
    """
    # middleware может положить sid сюда
    sid = sid or getattr(request.state, "sid", None)
    if not sid:
        return None

    if request.url.path == "/auth/session":
        rec = session_manager.get(sid)
    else:
        rec = session_manager.touch(sid)

    if not rec:
        return None

    u: SessionUser = rec.user
    if u.kind == "client":
        obj = db.execute(select(models.Client).where(models.Client.client_id == u.user_id)).scalar_one_or_none()
        if not obj or not obj.is_active:
            return None
        return CurrentUser(kind="client", client=obj)

    obj = db.execute(select(models.Employee).where(models.Employee.employee_id == u.user_id)).scalar_one_or_none()
    if not obj or not obj.is_active:
        return None
    return CurrentUser(kind="employee", employee=obj)


def require_user(user: Optional[CurrentUser] = Depends(get_current_user)) -> CurrentUser:
    if not user:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


def require_employee(allowed_roles: Optional[Iterable[str]] = None):
    allowed: Optional[Set[str]] = set(allowed_roles) if allowed_roles else None

    def _dep(user: CurrentUser = Depends(require_user)) -> CurrentUser:
        if user.kind != "employee" or not user.employee:
            raise HTTPException(status_code=403, detail="employee access required")
        if allowed and user.employee.role not in allowed:
            raise HTTPException(status_code=403, detail="insufficient role")
        return user

    return _dep
