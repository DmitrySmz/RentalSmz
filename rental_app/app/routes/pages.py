# app/routes/pages.py
from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..dependencies import get_current_user, require_user, CurrentUser

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["pages"])


def render(request: Request, name: str, **ctx):
    # единый способ пробрасывать user во все шаблоны
    return templates.TemplateResponse(name, {"request": request, **ctx})


@router.get("/", response_class=HTMLResponse)
def index(request: Request, user=Depends(get_current_user)):
    return render(request, "index.html", user=user)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return render(request, "login.html", user=user)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return render(request, "register.html", user=user)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: CurrentUser = Depends(require_user)):
    # пока реализуем клиентский кабинет (сотрудников сделаем потом)
    return render(request, "dashboard.html", user=user)


@router.get("/catalog", response_class=HTMLResponse)
def catalog_page(request: Request, user=Depends(get_current_user)):
    return render(request, "catalog.html", user=user)


@router.get("/my/contracts", response_class=HTMLResponse)
def my_contracts_page(request: Request, user: CurrentUser = Depends(require_user)):
    return render(request, "contracts.html", user=user)


@router.get("/contracts/{contract_id}/view", response_class=HTMLResponse)
def contract_view_page(contract_id: int, request: Request, user: CurrentUser = Depends(require_user)):
    return render(request, "contract_view.html", user=user, contract_id=contract_id)
