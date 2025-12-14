# app/routes/equipment.py
from __future__ import annotations
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func, exists
from sqlalchemy.orm import Session

from ..database import get_db        # <= относительный импорт
from .. import models, schemas       # <= относительный импорт

router = APIRouter()


# ---------- CATALOG ----------

@router.get("/catalog/categories", response_model=List[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    q = select(models.Category).order_by(models.Category.name.asc())
    return db.execute(q).scalars().all()


@router.get("/catalog/products", response_model=List[schemas.ProductOut])
def list_products(
    db: Session = Depends(get_db),
    category_id: Optional[int] = None,
    name: Optional[str] = Query(None, description="Подстрока в названии (ILIKE)"),
    brand: Optional[str] = Query(None, description="Подстрока в бренде (ILIKE)"),
    price_max: Optional[float] = Query(None, ge=0),
    volume_liters_gte: Optional[int] = Query(None, ge=0),
    people_count: Optional[int] = Query(None, ge=1),
    temperature_min_lte: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    filters = []
    if category_id:
        filters.append(models.Product.category_id == category_id)
    if name:
        filters.append(models.Product.name.ilike(f"%{name}%"))
    if brand:
        filters.append(models.Product.brand.ilike(f"%{brand}%"))
    if price_max is not None:
        filters.append(models.Product.default_daily_price <= price_max)
    if volume_liters_gte is not None:
        filters.append(models.Product.volume_liters >= volume_liters_gte)
    if people_count is not None:
        filters.append(models.Product.people_count >= people_count)
    if temperature_min_lte is not None:
        filters.append(models.Product.temperature_min <= temperature_min_lte)

    q = (
        select(models.Product)
        .where(and_(*filters)) if filters else select(models.Product)
    ).order_by(models.Product.name.asc()).limit(limit).offset(offset)

    return db.execute(q).scalars().all()


@router.get("/catalog/products/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    prod = db.execute(
        select(models.Product).where(models.Product.product_id == product_id)
    ).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="product not found")
    return prod


# ---------- AVAILABILITY ----------

@router.get("/availability", response_model=schemas.AvailabilityResponse, tags=["availability"])
def availability(
    rental_point_id: int = Query(..., description="ID пункта проката"),
    product_id: int = Query(..., description="ID модели/продукта"),
    start: date = Query(..., description="Дата начала аренды (YYYY-MM-DD)"),
    end: date = Query(..., description="Дата окончания аренды (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    limit_ids: int = Query(200, ge=1, le=1000, description="Сколько item_id вернуть (для UI)"),
):
    if end < start:
        raise HTTPException(400, "end < start")

    # NOT EXISTS: исключаем предметы, занятые в активных/просроченных договорах,
    # пересекающихся с [start, end]; «сломанные/утерянные» не считаем доступными всегда.
    overlap_exists = (
        exists()
        .where(
            models.ContractItem.item_id == models.Item.item_id
        )
        .where(
            models.ContractItem.contract_id == models.RentalContract.contract_id
        )
        .where(
            models.RentalContract.status.in_(("active", "overdue"))
        )
        .where(
            and_(
                models.RentalContract.planned_end_date >= start,
                models.RentalContract.start_date <= end,
            )
        )
        .select()
    )

    q_items = (
        select(models.Item.item_id)
        .where(
            models.Item.product_id == product_id,
            models.Item.rental_point_id == rental_point_id,
            # исключаем больные статусы; "worn" остаётся допустимым
            models.Item.condition_status.notin_(("broken", "lost")),
            ~overlap_exists,
        )
        .order_by(models.Item.item_id.asc())
        .limit(limit_ids)
    )

    free_ids = [row[0] for row in db.execute(q_items).all()]
    # для общего количества без лимита:
    q_count = (
        select(func.count())
        .select_from(models.Item)
        .where(
            models.Item.product_id == product_id,
            models.Item.rental_point_id == rental_point_id,
            models.Item.condition_status.notin_(("broken", "lost")),
            ~overlap_exists,
        )
    )
    total_free = db.execute(q_count).scalar_one()

    return schemas.AvailabilityResponse(
        product_id=product_id,
        rental_point_id=rental_point_id,
        start=str(start),
        end=str(end),
        available_count=total_free,
        item_ids=free_ids,
    )
