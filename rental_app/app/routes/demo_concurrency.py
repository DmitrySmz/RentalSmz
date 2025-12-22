# app/routes/demo_concurrency.py
from __future__ import annotations

import time
from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from .. import models, schemas
from ..dependencies import CurrentUser, require_user

# Берём хелперы из основного флоу, но сам основной флоу НЕ МЕНЯЕМ.
from .rentals import _as_contract_out, _check_overlap, _d, _lock_items, _pick_employee_for_point, _calc_totals  # noqa


router = APIRouter(prefix="/demo/concurrency", tags=["demo-concurrency"])
templates = Jinja2Templates(directory="app/templates")


def _sleep_ms(ms: int) -> None:
    if ms and ms > 0:
        time.sleep(ms / 1000.0)


def _load_items_no_lock(db: Session, item_ids: List[int]) -> List[models.Item]:
    if not item_ids:
        return []
    q = (
        select(models.Item)
        .where(models.Item.item_id.in_(item_ids))
        .options(selectinload(models.Item.product))
    )
    items = db.execute(q).scalars().all()
    if len(items) != len(set(item_ids)):
        raise HTTPException(status_code=400, detail="some item_id not found")
    return items


def _create_contract_impl(
    *,
    payload: schemas.ContractCreate,
    db: Session,
    client_id: int,
    employee_id: int,
    lock_items: bool,
    delay_ms: int,
    delay_stage: str,
) -> schemas.ContractOut:
    """
    delay_stage:
      - "after_overlap" (сломанный сценарий: расширяем окно гонки)
      - "after_lock"    (правильный сценарий: держим блокировку)
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="items cannot be empty")
    if payload.planned_end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="planned_end_date < start_date")

    item_ids = [int(x.item_id) for x in payload.items]

    # 1) Получаем предметы (с блокировкой или без)
    if lock_items:
        items = _lock_items(db, item_ids)  # SELECT ... FOR UPDATE
    else:
        items = _load_items_no_lock(db, item_ids)

    # 2) Валидация: все предметы из одного пункта и пригодны к аренде
    for it in items:
        if int(it.rental_point_id) != int(payload.rental_point_id):
            raise HTTPException(status_code=400, detail="item belongs to another rental point")
        if it.condition_status in ("broken", "lost"):
            raise HTTPException(status_code=409, detail="item not rentable (broken/lost)")
        if not bool(it.is_available):
            # is_available отражает active/overdue, но как защита — проверяем
            raise HTTPException(status_code=409, detail="item is not available")

    # 3) Правильный сценарий: задержка после захвата блокировки (держим FOR UPDATE)
    if lock_items and delay_stage == "after_lock":
        _sleep_ms(delay_ms)

    # 4) Проверка пересечений (ВАЖНО: в сломанном сценарии НЕ перепроверяем после sleep)
    conflicts = _check_overlap(
        db,
        item_ids=item_ids,
        start=payload.start_date,
        end=payload.planned_end_date,
        statuses=("draft", "active", "overdue"),
    )
    if conflicts:
        raise HTTPException(status_code=409, detail=f"overlap conflicts: {conflicts[:5]}")

    # 5) Сломанный сценарий: окно гонки между overlap-check и INSERT
    if (not lock_items) and delay_stage == "after_overlap":
        _sleep_ms(delay_ms)

    # 6) Создаём договор (как в обычном API, но отдельно)
    c = models.RentalContract(
        client_id=client_id,
        employee_id=employee_id,
        rental_point_id=payload.rental_point_id,
        start_date=payload.start_date,
        planned_end_date=payload.planned_end_date,
        status="draft",
        total_rent_amount=_d(0),
        total_deposit_amount=_d(0),
    )
    db.add(c)
    db.flush()  # получаем contract_id

    # 7) Подтягиваем продукты, чтобы взять дефолтные цены/залог
    prod_ids = list({int(it.product_id) for it in items})
    prod_q = select(models.Product).where(models.Product.product_id.in_(prod_ids))
    products = {int(p.product_id): p for p in db.execute(prod_q).scalars().all()}

    by_item = {int(it.item_id): it for it in items}

    for req in payload.items:
        it = by_item[int(req.item_id)]
        prod = products[int(it.product_id)]
        daily_price = _d(req.daily_price) if req.daily_price is not None else _d(prod.default_daily_price)
        deposit_amount = _d(req.deposit_amount) if req.deposit_amount is not None else _d(prod.default_deposit)
        db.add(
            models.ContractItem(
                contract_id=int(c.contract_id),
                item_id=int(it.item_id),
                daily_price=daily_price,
                deposit_amount=deposit_amount,
            )
        )

    db.flush()

    # 8) Итоги
    c = db.execute(
        select(models.RentalContract)
        .where(models.RentalContract.contract_id == c.contract_id)
        .options(selectinload(models.RentalContract.items))
    ).scalar_one()
    total_rent, total_deposit = _calc_totals(c)
    c.total_rent_amount = total_rent
    c.total_deposit_amount = total_deposit

    db.commit()

    # 9) Возвращаем как в обычном API
    c = db.execute(
        select(models.RentalContract)
        .where(models.RentalContract.contract_id == c.contract_id)
        .options(
            selectinload(models.RentalContract.items)
            .selectinload(models.ContractItem.item)
            .selectinload(models.Item.product),
            selectinload(models.RentalContract.payments),
        )
    ).scalar_one()

    return _as_contract_out(c)


@router.get("", response_class=HTMLResponse)
def demo_concurrency_page(
    request: Request,
    user: CurrentUser = Depends(require_user),
):
    # Страница доступна всем залогиненным, но сценарий рассчитан на клиентов
    return templates.TemplateResponse("demo_concurrency.html", {"request": request, "user": user})


@router.post("/contracts/no-lock", response_model=schemas.ContractOut)
def demo_create_contract_no_lock(
    payload: schemas.ContractCreate,
    delay_ms: int = Query(0, ge=0, le=60000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    """
    СЛОМАННЫЙ сценарий:
    - НЕ ставим SELECT ... FOR UPDATE на items
    - делаем задержку ПОСЛЕ overlap-check и ДО INSERT (окно гонки)
    """
    if user.kind != "client" or not user.client:
        raise HTTPException(status_code=403, detail="demo is for clients")

    client_id = int(user.client.client_id)
    employee_id = _pick_employee_for_point(db, payload.rental_point_id)

    return _create_contract_impl(
        payload=payload,
        db=db,
        client_id=client_id,
        employee_id=employee_id,
        lock_items=False,
        delay_ms=delay_ms,
        delay_stage="after_overlap",
    )


@router.post("/contracts/with-lock", response_model=schemas.ContractOut)
def demo_create_contract_with_lock(
    payload: schemas.ContractCreate,
    delay_ms: int = Query(0, ge=0, le=60000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    """
    ПРАВИЛЬНЫЙ сценарий:
    - ставим SELECT ... FOR UPDATE на items
    - задержка ПОСЛЕ захвата блокировки (второй запрос упрётся в ожидание)
    """
    if user.kind != "client" or not user.client:
        raise HTTPException(status_code=403, detail="demo is for clients")

    client_id = int(user.client.client_id)
    employee_id = _pick_employee_for_point(db, payload.rental_point_id)

    return _create_contract_impl(
        payload=payload,
        db=db,
        client_id=client_id,
        employee_id=employee_id,
        lock_items=True,
        delay_ms=delay_ms,
        delay_stage="after_lock",
    )


@router.get("/item-balance")
def demo_item_balance(
    item_id: int = Query(..., ge=1),
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
) -> Dict[str, Any]:
    """
    "Баланс" по одному item_id:
      total_units = 1
      reserved_units = сколько строк contract_items (draft/active/overdue) пересекаются по датам
      balance_units = 1 - reserved_units
    Если без блокировок удалось создать 2 договора на один предмет → balance_units станет отрицательным.
    """
    if end < start:
        raise HTTPException(status_code=400, detail="end < start")

    it = db.execute(
        select(models.Item)
        .where(models.Item.item_id == item_id)
        .options(selectinload(models.Item.product))
    ).scalar_one_or_none()
    if not it:
        raise HTTPException(status_code=404, detail="item not found")

    q_cnt = (
        select(func.count())
        .select_from(models.ContractItem)
        .join(models.RentalContract, models.RentalContract.contract_id == models.ContractItem.contract_id)
        .where(models.ContractItem.item_id == item_id)
        .where(models.RentalContract.status.in_(("draft", "active", "overdue")))
        .where(models.RentalContract.planned_end_date >= start)
        .where(models.RentalContract.start_date <= end)
    )
    reserved = int(db.execute(q_cnt).scalar_one())

    q_contracts = (
        select(
            models.RentalContract.contract_id,
            models.RentalContract.client_id,
            models.RentalContract.status,
            models.RentalContract.start_date,
            models.RentalContract.planned_end_date,
        )
        .select_from(models.ContractItem)
        .join(models.RentalContract, models.RentalContract.contract_id == models.ContractItem.contract_id)
        .where(models.ContractItem.item_id == item_id)
        .where(models.RentalContract.status.in_(("draft", "active", "overdue")))
        .where(models.RentalContract.planned_end_date >= start)
        .where(models.RentalContract.start_date <= end)
        .order_by(models.RentalContract.contract_id.asc())
    )
    contracts = [
        dict(
            contract_id=int(r.contract_id),
            client_id=int(r.client_id),
            status=str(r.status),
            start_date=str(r.start_date),
            planned_end_date=str(r.planned_end_date),
        )
        for r in db.execute(q_contracts).all()
    ]

    total_units = 1
    balance = total_units - reserved

    return {
        "item_id": int(it.item_id),
        "product_id": int(it.product_id),
        "product_name": it.product.name if it.product else None,
        "rental_point_id": int(it.rental_point_id),
        "period": {"start": str(start), "end": str(end)},
        "total_units": total_units,
        "reserved_units": reserved,
        "balance_units": balance,
        "contracts": contracts,
    }


@router.post("/reset-my-drafts")
def demo_reset_my_drafts(
    item_id: int = Query(..., ge=1),
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
) -> Dict[str, Any]:
    """
    Удобство для демонстрации: отменяем (status=canceled) ВСЕ draft-договоры
    текущего клиента, которые включают item_id и пересекаются с периодом.
    """
    if user.kind != "client" or not user.client:
        raise HTTPException(status_code=403, detail="demo is for clients")
    if end < start:
        raise HTTPException(status_code=400, detail="end < start")

    client_id = int(user.client.client_id)

    q_ids = (
        select(models.RentalContract.contract_id)
        .select_from(models.ContractItem)
        .join(models.RentalContract, models.RentalContract.contract_id == models.ContractItem.contract_id)
        .where(models.ContractItem.item_id == item_id)
        .where(models.RentalContract.client_id == client_id)
        .where(models.RentalContract.status == "draft")
        .where(models.RentalContract.planned_end_date >= start)
        .where(models.RentalContract.start_date <= end)
    )
    ids = [int(x) for x in db.execute(q_ids).scalars().all()]
    if not ids:
        return {"ok": True, "canceled_contract_ids": []}

    db.execute(
        update(models.RentalContract)
        .where(models.RentalContract.contract_id.in_(ids))
        .values(status="canceled")
    )
    db.commit()
    return {"ok": True, "canceled_contract_ids": ids}
# app/routes/demo_concurrency.py

import time
from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from .. import models, schemas
from ..dependencies import CurrentUser, require_user

# Берём хелперы из основного флоу, но сам основной флоу НЕ МЕНЯЕМ.
from .rentals import _as_contract_out, _check_overlap, _d, _lock_items, _pick_employee_for_point, _calc_totals  # noqa


router = APIRouter(prefix="/demo/concurrency", tags=["demo-concurrency"])
templates = Jinja2Templates(directory="app/templates")


def _sleep_ms(ms: int) -> None:
    if ms and ms > 0:
        time.sleep(ms / 1000.0)


def _load_items_no_lock(db: Session, item_ids: List[int]) -> List[models.Item]:
    if not item_ids:
        return []
    q = (
        select(models.Item)
        .where(models.Item.item_id.in_(item_ids))
        .options(selectinload(models.Item.product))
    )
    items = db.execute(q).scalars().all()
    if len(items) != len(set(item_ids)):
        raise HTTPException(status_code=400, detail="some item_id not found")
    return items


def _create_contract_impl(
    *,
    payload: schemas.ContractCreate,
    db: Session,
    client_id: int,
    employee_id: int,
    lock_items: bool,
    delay_ms: int,
    delay_stage: str,
) -> schemas.ContractOut:
    """
    delay_stage:
      - "after_overlap" (сломанный сценарий: расширяем окно гонки)
      - "after_lock"    (правильный сценарий: держим блокировку)
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="items cannot be empty")
    if payload.planned_end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="planned_end_date < start_date")

    item_ids = [int(x.item_id) for x in payload.items]

    # 1) Получаем предметы (с блокировкой или без)
    if lock_items:
        items = _lock_items(db, item_ids)  # SELECT ... FOR UPDATE
    else:
        items = _load_items_no_lock(db, item_ids)

    # 2) Валидация: все предметы из одного пункта и пригодны к аренде
    for it in items:
        if int(it.rental_point_id) != int(payload.rental_point_id):
            raise HTTPException(status_code=400, detail="item belongs to another rental point")
        if it.condition_status in ("broken", "lost"):
            raise HTTPException(status_code=409, detail="item not rentable (broken/lost)")
        if not bool(it.is_available):
            # is_available отражает active/overdue, но как защита — проверяем
            raise HTTPException(status_code=409, detail="item is not available")

    # 3) Правильный сценарий: задержка после захвата блокировки (держим FOR UPDATE)
    if lock_items and delay_stage == "after_lock":
        _sleep_ms(delay_ms)

    # 4) Проверка пересечений (ВАЖНО: в сломанном сценарии НЕ перепроверяем после sleep)
    conflicts = _check_overlap(
        db,
        item_ids=item_ids,
        start=payload.start_date,
        end=payload.planned_end_date,
        statuses=("draft", "active", "overdue"),
    )
    if conflicts:
        raise HTTPException(status_code=409, detail=f"overlap conflicts: {conflicts[:5]}")

    # 5) Сломанный сценарий: окно гонки между overlap-check и INSERT
    if (not lock_items) and delay_stage == "after_overlap":
        _sleep_ms(delay_ms)

    # 6) Создаём договор (как в обычном API, но отдельно)
    c = models.RentalContract(
        client_id=client_id,
        employee_id=employee_id,
        rental_point_id=payload.rental_point_id,
        start_date=payload.start_date,
        planned_end_date=payload.planned_end_date,
        status="draft",
        total_rent_amount=_d(0),
        total_deposit_amount=_d(0),
    )
    db.add(c)
    db.flush()  # получаем contract_id

    # 7) Подтягиваем продукты, чтобы взять дефолтные цены/залог
    prod_ids = list({int(it.product_id) for it in items})
    prod_q = select(models.Product).where(models.Product.product_id.in_(prod_ids))
    products = {int(p.product_id): p for p in db.execute(prod_q).scalars().all()}

    by_item = {int(it.item_id): it for it in items}

    for req in payload.items:
        it = by_item[int(req.item_id)]
        prod = products[int(it.product_id)]
        daily_price = _d(req.daily_price) if req.daily_price is not None else _d(prod.default_daily_price)
        deposit_amount = _d(req.deposit_amount) if req.deposit_amount is not None else _d(prod.default_deposit)
        db.add(
            models.ContractItem(
                contract_id=int(c.contract_id),
                item_id=int(it.item_id),
                daily_price=daily_price,
                deposit_amount=deposit_amount,
            )
        )

    db.flush()

    # 8) Итоги
    c = db.execute(
        select(models.RentalContract)
        .where(models.RentalContract.contract_id == c.contract_id)
        .options(selectinload(models.RentalContract.items))
    ).scalar_one()
    total_rent, total_deposit = _calc_totals(c)
    c.total_rent_amount = total_rent
    c.total_deposit_amount = total_deposit

    db.commit()

    # 9) Возвращаем как в обычном API
    c = db.execute(
        select(models.RentalContract)
        .where(models.RentalContract.contract_id == c.contract_id)
        .options(
            selectinload(models.RentalContract.items)
            .selectinload(models.ContractItem.item)
            .selectinload(models.Item.product),
            selectinload(models.RentalContract.payments),
        )
    ).scalar_one()

    return _as_contract_out(c)


@router.get("", response_class=HTMLResponse)
def demo_concurrency_page(
    request: Request,
    user: CurrentUser = Depends(require_user),
):
    # Страница доступна всем залогиненным, но сценарий рассчитан на клиентов
    return templates.TemplateResponse("demo_concurrency.html", {"request": request, "user": user})


@router.post("/contracts/no-lock", response_model=schemas.ContractOut)
def demo_create_contract_no_lock(
    payload: schemas.ContractCreate,
    delay_ms: int = Query(0, ge=0, le=60000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    """
    СЛОМАННЫЙ сценарий:
    - НЕ ставим SELECT ... FOR UPDATE на items
    - делаем задержку ПОСЛЕ overlap-check и ДО INSERT (окно гонки)
    """
    if user.kind != "client" or not user.client:
        raise HTTPException(status_code=403, detail="demo is for clients")

    client_id = int(user.client.client_id)
    employee_id = _pick_employee_for_point(db, payload.rental_point_id)

    return _create_contract_impl(
        payload=payload,
        db=db,
        client_id=client_id,
        employee_id=employee_id,
        lock_items=False,
        delay_ms=delay_ms,
        delay_stage="after_overlap",
    )


@router.post("/contracts/with-lock", response_model=schemas.ContractOut)
def demo_create_contract_with_lock(
    payload: schemas.ContractCreate,
    delay_ms: int = Query(0, ge=0, le=60000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    """
    ПРАВИЛЬНЫЙ сценарий:
    - ставим SELECT ... FOR UPDATE на items
    - задержка ПОСЛЕ захвата блокировки (второй запрос упрётся в ожидание)
    """
    if user.kind != "client" or not user.client:
        raise HTTPException(status_code=403, detail="demo is for clients")

    client_id = int(user.client.client_id)
    employee_id = _pick_employee_for_point(db, payload.rental_point_id)

    return _create_contract_impl(
        payload=payload,
        db=db,
        client_id=client_id,
        employee_id=employee_id,
        lock_items=True,
        delay_ms=delay_ms,
        delay_stage="after_lock",
    )


@router.get("/item-balance")
def demo_item_balance(
    item_id: int = Query(..., ge=1),
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
) -> Dict[str, Any]:
    """
    "Баланс" по одному item_id:
      total_units = 1
      reserved_units = сколько строк contract_items (draft/active/overdue) пересекаются по датам
      balance_units = 1 - reserved_units
    Если без блокировок удалось создать 2 договора на один предмет → balance_units станет отрицательным.
    """
    if end < start:
        raise HTTPException(status_code=400, detail="end < start")

    it = db.execute(
        select(models.Item)
        .where(models.Item.item_id == item_id)
        .options(selectinload(models.Item.product))
    ).scalar_one_or_none()
    if not it:
        raise HTTPException(status_code=404, detail="item not found")

    q_cnt = (
        select(func.count())
        .select_from(models.ContractItem)
        .join(models.RentalContract, models.RentalContract.contract_id == models.ContractItem.contract_id)
        .where(models.ContractItem.item_id == item_id)
        .where(models.RentalContract.status.in_(("draft", "active", "overdue")))
        .where(models.RentalContract.planned_end_date >= start)
        .where(models.RentalContract.start_date <= end)
    )
    reserved = int(db.execute(q_cnt).scalar_one())

    q_contracts = (
        select(
            models.RentalContract.contract_id,
            models.RentalContract.client_id,
            models.RentalContract.status,
            models.RentalContract.start_date,
            models.RentalContract.planned_end_date,
        )
        .select_from(models.ContractItem)
        .join(models.RentalContract, models.RentalContract.contract_id == models.ContractItem.contract_id)
        .where(models.ContractItem.item_id == item_id)
        .where(models.RentalContract.status.in_(("draft", "active", "overdue")))
        .where(models.RentalContract.planned_end_date >= start)
        .where(models.RentalContract.start_date <= end)
        .order_by(models.RentalContract.contract_id.asc())
    )
    contracts = [
        dict(
            contract_id=int(r.contract_id),
            client_id=int(r.client_id),
            status=str(r.status),
            start_date=str(r.start_date),
            planned_end_date=str(r.planned_end_date),
        )
        for r in db.execute(q_contracts).all()
    ]

    total_units = 1
    balance = total_units - reserved

    return {
        "item_id": int(it.item_id),
        "product_id": int(it.product_id),
        "product_name": it.product.name if it.product else None,
        "rental_point_id": int(it.rental_point_id),
        "period": {"start": str(start), "end": str(end)},
        "total_units": total_units,
        "reserved_units": reserved,
        "balance_units": balance,
        "contracts": contracts,
    }


@router.post("/reset-my-drafts")
def demo_reset_my_drafts(
    item_id: int = Query(..., ge=1),
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
) -> Dict[str, Any]:
    """
    Удобство для демонстрации: отменяем (status=canceled) ВСЕ draft-договоры
    текущего клиента, которые включают item_id и пересекаются с периодом.
    """
    if user.kind != "client" or not user.client:
        raise HTTPException(status_code=403, detail="demo is for clients")
    if end < start:
        raise HTTPException(status_code=400, detail="end < start")

    client_id = int(user.client.client_id)

    q_ids = (
        select(models.RentalContract.contract_id)
        .select_from(models.ContractItem)
        .join(models.RentalContract, models.RentalContract.contract_id == models.ContractItem.contract_id)
        .where(models.ContractItem.item_id == item_id)
        .where(models.RentalContract.client_id == client_id)
        .where(models.RentalContract.status == "draft")
        .where(models.RentalContract.planned_end_date >= start)
        .where(models.RentalContract.start_date <= end)
    )
    ids = [int(x) for x in db.execute(q_ids).scalars().all()]
    if not ids:
        return {"ok": True, "canceled_contract_ids": []}

    db.execute(
        update(models.RentalContract)
        .where(models.RentalContract.contract_id.in_(ids))
        .values(status="canceled")
    )
    db.commit()
    return {"ok": True, "canceled_contract_ids": ids}
