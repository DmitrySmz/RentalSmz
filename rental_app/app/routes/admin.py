# app/routes/admin.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from .. import models, schemas
from ..dependencies import require_employee, CurrentUser

router = APIRouter(prefix="/admin", tags=["admin"])


def _d(x) -> Decimal:
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


# -------------------------
# Categories
# -------------------------

@router.get("/categories", response_model=List[schemas.CategoryOut])
def admin_list_categories(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    q = select(models.Category).order_by(models.Category.name.asc())
    return db.execute(q).scalars().all()


@router.post("/categories", response_model=schemas.CategoryOut)
def admin_create_category(
    payload: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    obj = models.Category(name=payload.name, description=payload.description)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="category name already exists")
    db.refresh(obj)
    return obj


@router.put("/categories/{category_id}", response_model=schemas.CategoryOut)
def admin_update_category(
    category_id: int,
    payload: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    obj = db.execute(select(models.Category).where(models.Category.category_id == category_id)).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="category not found")

    obj.name = payload.name
    obj.description = payload.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="category name already exists")
    db.refresh(obj)
    return obj


@router.delete("/categories/{category_id}", response_model=schemas.OkOut)
def admin_delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    obj = db.execute(select(models.Category).where(models.Category.category_id == category_id)).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="category not found")
    db.delete(obj)
    db.commit()
    return schemas.OkOut(ok=True)


# -------------------------
# Products
# -------------------------

@router.get("/products", response_model=List[schemas.ProductOut])
def admin_list_products(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
    category_id: Optional[int] = Query(None),
):
    q = select(models.Product).order_by(models.Product.product_id.desc())
    if category_id:
        q = q.where(models.Product.category_id == category_id)
    return db.execute(q).scalars().all()


@router.post("/products", response_model=schemas.ProductOut)
def admin_create_product(
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    # verify category exists
    cat = db.execute(select(models.Category.category_id).where(models.Category.category_id == payload.category_id)).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=400, detail="category_id not found")

    obj = models.Product(
        category_id=payload.category_id,
        name=payload.name,
        brand=payload.brand,
        description=payload.description,
        volume_liters=payload.volume_liters,
        people_count=payload.people_count,
        temperature_min=payload.temperature_min,
        default_daily_price=_d(payload.default_daily_price),
        default_deposit=_d(payload.default_deposit),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/products/{product_id}", response_model=schemas.ProductOut)
def admin_update_product(
    product_id: int,
    payload: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    obj = db.execute(select(models.Product).where(models.Product.product_id == product_id)).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="product not found")

    # verify category exists
    cat = db.execute(select(models.Category.category_id).where(models.Category.category_id == payload.category_id)).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=400, detail="category_id not found")

    obj.category_id = payload.category_id
    obj.name = payload.name
    obj.brand = payload.brand
    obj.description = payload.description
    obj.volume_liters = payload.volume_liters
    obj.people_count = payload.people_count
    obj.temperature_min = payload.temperature_min
    obj.default_daily_price = _d(payload.default_daily_price)
    obj.default_deposit = _d(payload.default_deposit)

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/products/{product_id}", response_model=schemas.OkOut)
def admin_delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    obj = db.execute(select(models.Product).where(models.Product.product_id == product_id)).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="product not found")
    db.delete(obj)
    db.commit()
    return schemas.OkOut(ok=True)


# -------------------------
# Items (inventory)
# -------------------------

@router.get("/items", response_model=List[schemas.ItemOut])
def admin_list_items(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
    point_id: Optional[int] = Query(None),
    product_id: Optional[int] = Query(None),
):
    q = select(models.Item).options(selectinload(models.Item.product)).order_by(models.Item.item_id.desc())
    if point_id:
        q = q.where(models.Item.rental_point_id == point_id)
    if product_id:
        q = q.where(models.Item.product_id == product_id)
    items = db.execute(q).scalars().all()
    return [
        schemas.ItemOut(
            item_id=i.item_id,
            product_id=i.product_id,
            product_name=i.product.name if i.product else None,
            rental_point_id=i.rental_point_id,
            inventory_number=i.inventory_number,
            color=i.color,
            size=i.size,
            condition_status=i.condition_status,
            is_available=bool(i.is_available),
        )
        for i in items
    ]


@router.post("/items", response_model=schemas.ItemOut)
def admin_create_item(
    payload: schemas.ItemCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    # verify point/product exist
    p = db.execute(select(models.Product).where(models.Product.product_id == payload.product_id)).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=400, detail="product_id not found")
    rp = db.execute(select(models.RentalPoint).where(models.RentalPoint.rental_point_id == payload.rental_point_id)).scalar_one_or_none()
    if not rp:
        raise HTTPException(status_code=400, detail="rental_point_id not found")

    obj = models.Item(
        product_id=payload.product_id,
        rental_point_id=payload.rental_point_id,
        inventory_number=payload.inventory_number,
        color=payload.color,
        size=payload.size,
        condition_status=payload.condition_status,
        is_available=payload.is_available if payload.is_available is not None else True,
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="inventory_number must be unique")
    db.refresh(obj)

    return schemas.ItemOut(
        item_id=obj.item_id,
        product_id=obj.product_id,
        product_name=p.name,
        rental_point_id=obj.rental_point_id,
        inventory_number=obj.inventory_number,
        color=obj.color,
        size=obj.size,
        condition_status=obj.condition_status,
        is_available=bool(obj.is_available),
    )


@router.put("/items/{item_id}", response_model=schemas.ItemOut)
def admin_update_item(
    item_id: int,
    payload: schemas.ItemUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    obj = db.execute(select(models.Item).where(models.Item.item_id == item_id).options(selectinload(models.Item.product))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="item not found")

    if payload.color is not None:
        obj.color = payload.color
    if payload.size is not None:
        obj.size = payload.size
    if payload.condition_status is not None:
        obj.condition_status = payload.condition_status
        if payload.condition_status in ("broken", "lost"):
            obj.is_available = False
    if payload.is_available is not None:
        obj.is_available = payload.is_available

    db.commit()
    db.refresh(obj)
    return schemas.ItemOut(
        item_id=obj.item_id,
        product_id=obj.product_id,
        product_name=obj.product.name if obj.product else None,
        rental_point_id=obj.rental_point_id,
        inventory_number=obj.inventory_number,
        color=obj.color,
        size=obj.size,
        condition_status=obj.condition_status,
        is_available=bool(obj.is_available),
    )


@router.post("/items/{item_id}/move", response_model=schemas.ItemOut)
def admin_move_item(
    item_id: int,
    payload: schemas.ItemMove,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    obj = db.execute(select(models.Item).where(models.Item.item_id == item_id).options(selectinload(models.Item.product))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="item not found")

    # cannot move if item is currently in active/overdue contract
    busy = db.execute(
        select(func.count())
        .select_from(models.ContractItem)
        .join(models.RentalContract, models.RentalContract.contract_id == models.ContractItem.contract_id)
        .where(models.ContractItem.item_id == item_id)
        .where(models.RentalContract.status.in_(("active", "overdue")))
    ).scalar_one()
    if int(busy) > 0:
        raise HTTPException(status_code=409, detail="cannot move: item is busy in active/overdue contract")

    rp = db.execute(select(models.RentalPoint).where(models.RentalPoint.rental_point_id == payload.to_point_id)).scalar_one_or_none()
    if not rp:
        raise HTTPException(status_code=400, detail="to_point_id not found")

    obj.rental_point_id = payload.to_point_id
    db.commit()
    db.refresh(obj)
    return schemas.ItemOut(
        item_id=obj.item_id,
        product_id=obj.product_id,
        product_name=obj.product.name if obj.product else None,
        rental_point_id=obj.rental_point_id,
        inventory_number=obj.inventory_number,
        color=obj.color,
        size=obj.size,
        condition_status=obj.condition_status,
        is_available=bool(obj.is_available),
    )


@router.put("/items/{item_id}/status", response_model=schemas.ItemOut)
def admin_set_item_status(
    item_id: int,
    payload: schemas.ItemStatus,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin",))),
):
    obj = db.execute(select(models.Item).where(models.Item.item_id == item_id).options(selectinload(models.Item.product))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="item not found")

    obj.condition_status = payload.condition_status
    obj.is_available = payload.is_available

    if obj.condition_status in ("broken", "lost"):
        obj.is_available = False

    db.commit()
    db.refresh(obj)
    return schemas.ItemOut(
        item_id=obj.item_id,
        product_id=obj.product_id,
        product_name=obj.product.name if obj.product else None,
        rental_point_id=obj.rental_point_id,
        inventory_number=obj.inventory_number,
        color=obj.color,
        size=obj.size,
        condition_status=obj.condition_status,
        is_available=bool(obj.is_available),
    )


# -------------------------
# Reports
# -------------------------

@router.get("/reports/point/{point_id}", response_model=schemas.PointReportOut)
def report_point(
    point_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin", "manager"))),
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
):
    # manager can only view own point
    e = user.employee
    assert e is not None
    if e.role != "admin" and e.rental_point_id != point_id:
        raise HTTPException(status_code=403, detail="manager can view only own point")

    # contracts count (by created_at date)
    contracts_cnt = db.execute(
        select(func.count())
        .select_from(models.RentalContract)
        .where(models.RentalContract.rental_point_id == point_id)
        .where(func.date(models.RentalContract.created_at) >= from_date)
        .where(func.date(models.RentalContract.created_at) <= to_date)
    ).scalar_one()

    # payments sums (by payment_date date)
    pay_base = (
        select(models.Payment.type, func.coalesce(func.sum(models.Payment.amount), 0))
        .select_from(models.Payment)
        .join(models.RentalContract, models.RentalContract.contract_id == models.Payment.contract_id)
        .where(models.RentalContract.rental_point_id == point_id)
        .where(func.date(models.Payment.payment_date) >= from_date)
        .where(func.date(models.Payment.payment_date) <= to_date)
        .group_by(models.Payment.type)
    )
    rows = db.execute(pay_base).all()
    sums = {t: _d(s) for t, s in rows}

    rent_income = sums.get("rent", Decimal("0")).quantize(Decimal("0.01"))
    deposit_in = sums.get("deposit", Decimal("0")).quantize(Decimal("0.01"))
    deposit_refund = sums.get("deposit_refund", Decimal("0")).quantize(Decimal("0.01"))  # usually negative
    penalties = sums.get("penalty", Decimal("0")).quantize(Decimal("0.01"))

    overdue_cnt = db.execute(
        select(func.count())
        .select_from(models.RentalContract)
        .where(models.RentalContract.rental_point_id == point_id)
        .where(models.RentalContract.status == "overdue")
        .where(func.date(models.RentalContract.created_at) >= from_date)
        .where(func.date(models.RentalContract.created_at) <= to_date)
    ).scalar_one()

    # popular products (by contract start_date within range)
    pop_q = (
        select(
            models.Product.product_id,
            models.Product.name,
            func.count().label("uses"),
        )
        .select_from(models.ContractItem)
        .join(models.RentalContract, models.RentalContract.contract_id == models.ContractItem.contract_id)
        .join(models.Item, models.Item.item_id == models.ContractItem.item_id)
        .join(models.Product, models.Product.product_id == models.Item.product_id)
        .where(models.RentalContract.rental_point_id == point_id)
        .where(models.RentalContract.start_date >= from_date)
        .where(models.RentalContract.start_date <= to_date)
        .group_by(models.Product.product_id, models.Product.name)
        .order_by(func.count().desc())
        .limit(10)
    )
    pop = db.execute(pop_q).all()
    popular = [schemas.PopularProductOut(product_id=int(pid), name=name, uses=int(uses)) for pid, name, uses in pop]

    return schemas.PointReportOut(
        point_id=point_id,
        from_date=from_date,
        to_date=to_date,
        contracts_count=int(contracts_cnt),
        rent_income=rent_income,
        deposit_in=deposit_in,
        deposit_refund=deposit_refund,
        penalties_income=penalties,
        overdue_contracts=int(overdue_cnt),
        popular_products=popular,
    )
