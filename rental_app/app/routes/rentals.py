# app/routes/rentals.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from .. import models, schemas
from ..dependencies import require_user, require_employee, CurrentUser

router = APIRouter(tags=["rentals"])


# -------------------------
# Helpers
# -------------------------

def _d(x) -> Decimal:
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _days_inclusive(start: date, end: date) -> int:
    days = (end - start).days + 1
    if days <= 0:
        raise HTTPException(status_code=400, detail="planned_end_date must be >= start_date")
    return days


def _contract_access_or_404(db: Session, contract_id: int) -> models.RentalContract:
    q = (
        select(models.RentalContract)
        .where(models.RentalContract.contract_id == contract_id)
        .options(
            selectinload(models.RentalContract.items)
            .selectinload(models.ContractItem.item)
            .selectinload(models.Item.product),
            selectinload(models.RentalContract.payments),
        )
    )
    obj = db.execute(q).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="contract not found")
    return obj


def _ensure_can_view(user: CurrentUser, c: models.RentalContract):
    if user.kind == "client":
        if not user.client or c.client_id != user.client.client_id:
            raise HTTPException(status_code=403, detail="forbidden")
        return

    # employee
    e = user.employee
    if not e:
        raise HTTPException(status_code=403, detail="forbidden")
    if e.role == "admin":
        return
    if e.rental_point_id != c.rental_point_id:
        raise HTTPException(status_code=403, detail="forbidden")


def _ensure_can_operate_as_employee(user: CurrentUser, c: models.RentalContract):
    if user.kind != "employee" or not user.employee:
        raise HTTPException(status_code=403, detail="employee access required")
    e = user.employee
    if e.role != "admin" and e.rental_point_id != c.rental_point_id:
        raise HTTPException(status_code=403, detail="employee of this point required")


def _calc_totals(c: models.RentalContract) -> Tuple[Decimal, Decimal]:
    days = _days_inclusive(c.start_date, c.planned_end_date)
    sum_daily = sum((_d(ci.daily_price) for ci in c.items), Decimal("0"))
    sum_deposit = sum((_d(ci.deposit_amount) for ci in c.items), Decimal("0"))
    total_rent = (sum_daily * Decimal(days)).quantize(Decimal("0.01"))
    total_deposit = sum_deposit.quantize(Decimal("0.01"))
    return total_rent, total_deposit


def _sum_payments(c: models.RentalContract, p_type: str) -> Decimal:
    # amount is stored as NUMERIC(10,2) -> Decimal
    s = sum((_d(p.amount) for p in c.payments if p.type == p_type), Decimal("0"))
    return s.quantize(Decimal("0.01"))


def _lock_items(db: Session, item_ids: List[int]) -> List[models.Item]:
    if not item_ids:
        return []
    q = (
        select(models.Item)
        .where(models.Item.item_id.in_(item_ids))
        .with_for_update()
        .options(selectinload(models.Item.product))
    )
    items = db.execute(q).scalars().all()
    if len(items) != len(set(item_ids)):
        raise HTTPException(status_code=400, detail="some item_id not found")
    return items


def _check_overlap(
    db: Session,
    *,
    item_ids: List[int],
    start: date,
    end: date,
    exclude_contract_id: Optional[int] = None,
    statuses: Tuple[str, ...] = ("draft", "active", "overdue"),
) -> List[Tuple[int, int]]:
    """
    Return list of (item_id, contract_id) conflicts.
    """
    if not item_ids:
        return []

    q = (
        select(models.ContractItem.item_id, models.RentalContract.contract_id)
        .join(models.RentalContract, models.RentalContract.contract_id == models.ContractItem.contract_id)
        .where(models.ContractItem.item_id.in_(item_ids))
        .where(models.RentalContract.status.in_(statuses))
        .where(~(models.RentalContract.planned_end_date < start))
        .where(~(models.RentalContract.start_date > end))
    )
    if exclude_contract_id is not None:
        q = q.where(models.RentalContract.contract_id != exclude_contract_id)

    return db.execute(q).all()


def _pick_employee_for_point(db: Session, point_id: int) -> int:
    # when client creates contract, employee_id in rental_contracts is NOT NULL,
    # so we attach "some" active employee of this point (prefer cashier -> manager -> admin).
    role_rank = case(
        (models.Employee.role == "cashier", 1),
        (models.Employee.role == "manager", 2),
        (models.Employee.role == "admin", 3),
        else_=9,
    )
    q = (
        select(models.Employee.employee_id)
        .where(models.Employee.rental_point_id == point_id)
        .where(models.Employee.is_active.is_(True))
        .order_by(role_rank.asc(), models.Employee.employee_id.asc())
        .limit(1)
    )
    eid = db.execute(q).scalar_one_or_none()
    if not eid:
        raise HTTPException(status_code=409, detail="no active employees for this rental point")
    return int(eid)


def _as_contract_out(c: models.RentalContract) -> schemas.ContractOut:
    items_out: List[schemas.ContractItemOut] = []
    for ci in c.items:
        it = ci.item
        prod = it.product if it else None
        items_out.append(
            schemas.ContractItemOut(
                contract_item_id=ci.contract_item_id,
                item_id=ci.item_id,
                product_id=prod.product_id if prod else None,
                product_name=prod.name if prod else None,
                inventory_number=it.inventory_number if it else None,
                color=it.color if it else None,
                size=it.size if it else None,
                daily_price=_d(ci.daily_price),
                deposit_amount=_d(ci.deposit_amount),
            )
        )

    return schemas.ContractOut(
        contract_id=c.contract_id,
        client_id=c.client_id,
        employee_id=c.employee_id,
        rental_point_id=c.rental_point_id,
        created_at=c.created_at,
        start_date=c.start_date,
        planned_end_date=c.planned_end_date,
        actual_end_date=c.actual_end_date,
        status=c.status,
        total_rent_amount=_d(c.total_rent_amount),
        total_deposit_amount=_d(c.total_deposit_amount),
        items=items_out,
    )


# -------------------------
# Contracts
# -------------------------

@router.post("/contracts", response_model=schemas.ContractOut)
def create_contract(
    payload: schemas.ContractCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="items cannot be empty")

    # determine client_id and employee_id
    if user.kind == "client":
        client_id = user.client.client_id  # type: ignore[union-attr]
        employee_id = _pick_employee_for_point(db, payload.rental_point_id)
    else:
        # employee creates for client
        if not payload.client_id:
            raise HTTPException(status_code=400, detail="client_id is required for employee")
        client_id = payload.client_id
        employee_id = user.employee.employee_id  # type: ignore[union-attr]

    # transaction
    item_ids = [i.item_id for i in payload.items]
    item_ids_uniq = list(dict.fromkeys(item_ids))

    # lock items to avoid races
    items = _lock_items(db, item_ids_uniq)

    # validate point + condition
    for it in items:
        if it.rental_point_id != payload.rental_point_id:
            raise HTTPException(status_code=400, detail=f"item {it.item_id} belongs to another rental point")
        if it.condition_status in ("broken", "lost"):
            raise HTTPException(status_code=409, detail=f"item {it.item_id} is not rentable (condition={it.condition_status})")
        # is_available is maintained only for active/overdue, but still useful filter:
        if it.is_available is False:
            raise HTTPException(status_code=409, detail=f"item {it.item_id} is not available")

    # prevent overlap with other draft/active/overdue contracts
    conflicts = _check_overlap(db, item_ids=item_ids_uniq, start=payload.start_date, end=payload.planned_end_date)
    if conflicts:
        # show first few
        sample = [{"item_id": int(i), "contract_id": int(cid)} for i, cid in conflicts[:10]]
        raise HTTPException(status_code=409, detail={"message": "items are busy in overlapping contracts", "conflicts": sample})

    c = models.RentalContract(
        client_id=client_id,
        employee_id=employee_id,
        rental_point_id=payload.rental_point_id,
        start_date=payload.start_date,
        planned_end_date=payload.planned_end_date,
        status="draft",
    )
    db.add(c)
    db.flush()  # get contract_id

    # build product map for defaults
    prod_ids = list({it.product_id for it in items})
    prod_q = select(models.Product).where(models.Product.product_id.in_(prod_ids))
    products = {p.product_id: p for p in db.execute(prod_q).scalars().all()}

    # insert contract items
    by_id = {it.item_id: it for it in items}
    for req in payload.items:
        it = by_id[req.item_id]
        prod = products[it.product_id]
        daily_price = _d(req.daily_price) if req.daily_price is not None else _d(prod.default_daily_price)
        deposit_amount = _d(req.deposit_amount) if req.deposit_amount is not None else _d(prod.default_deposit)

        db.add(
            models.ContractItem(
                contract_id=c.contract_id,
                item_id=it.item_id,
                daily_price=daily_price,
                deposit_amount=deposit_amount,
            )
        )

    db.flush()
    db.refresh(c)  # load items via relationship next select

    # reload with relationships
    c = _contract_access_or_404(db, c.contract_id)
    total_rent, total_deposit = _calc_totals(c)
    c.total_rent_amount = total_rent
    c.total_deposit_amount = total_deposit
    db.commit()

    c = _contract_access_or_404(db, c.contract_id)
    return _as_contract_out(c)


@router.get("/contracts/my", response_model=List[schemas.ContractOut])
def my_contracts(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    if user.kind != "client" or not user.client:
        raise HTTPException(status_code=403, detail="client access required")

    q = (
        select(models.RentalContract)
        .where(models.RentalContract.client_id == user.client.client_id)
        .order_by(models.RentalContract.contract_id.desc())
        .options(
            selectinload(models.RentalContract.items)
            .selectinload(models.ContractItem.item)
            .selectinload(models.Item.product),
            selectinload(models.RentalContract.payments),
        )
    )
    rows = db.execute(q).scalars().all()
    return [_as_contract_out(c) for c in rows]


@router.get("/contracts/{contract_id}", response_model=schemas.ContractOut)
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_view(user, c)
    return _as_contract_out(c)


@router.get("/contracts", response_model=List[schemas.ContractOut])
def list_contracts_for_employee(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin", "manager", "cashier"))),
    status: Optional[str] = Query(None),
    client_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    e = user.employee
    assert e is not None

    q = select(models.RentalContract).options(
        selectinload(models.RentalContract.items).selectinload(models.ContractItem.item).selectinload(models.Item.product),
        selectinload(models.RentalContract.payments),
    )

    if e.role != "admin":
        q = q.where(models.RentalContract.rental_point_id == e.rental_point_id)

    if status:
        q = q.where(models.RentalContract.status == status)
    if client_id:
        q = q.where(models.RentalContract.client_id == client_id)
    if from_date:
        q = q.where(models.RentalContract.start_date >= from_date)
    if to_date:
        q = q.where(models.RentalContract.start_date <= to_date)

    q = q.order_by(models.RentalContract.contract_id.desc())
    rows = db.execute(q).scalars().all()
    return [_as_contract_out(c) for c in rows]


# -------------------------
# Payments
# -------------------------

@router.post("/contracts/{contract_id}/payments", response_model=schemas.PaymentOut)
def create_payment(
    contract_id: int,
    payload: schemas.PaymentCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    if payload.amount == 0:
        raise HTTPException(status_code=400, detail="amount must be non-zero")

    # cashier/manager/admin can pay for any contract of their point; client only for own contract.
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_view(user, c)
    if user.kind == "employee":
        _ensure_can_operate_as_employee(user, c)

    if c.status in ("closed", "canceled"):
        raise HTTPException(status_code=409, detail=f"cannot pay for contract in status={c.status}")

    # lock contract row
    db.execute(
        select(models.RentalContract.contract_id)
        .where(models.RentalContract.contract_id == contract_id)
        .with_for_update()
    )

    # lock items to avoid activate race
    item_ids = [ci.item_id for ci in c.items]
    _lock_items(db, item_ids)

    p = models.Payment(
        contract_id=contract_id,
        amount=_d(payload.amount),
        type=payload.type,
        method=payload.method,
    )
    db.add(p)
    db.flush()

    # reload contract with updated payments
    c = _contract_access_or_404(db, contract_id)

    # keep totals up-to-date
    total_rent, total_deposit = _calc_totals(c)
    c.total_rent_amount = total_rent
    c.total_deposit_amount = total_deposit

    # activation rule: sufficient rent+deposit => active (only from draft)
    if c.status == "draft":
        paid_rent = _sum_payments(c, "rent")
        paid_deposit = _sum_payments(c, "deposit")

        # final safety overlap check right before activation
        conflicts = _check_overlap(
            db,
            item_ids=item_ids,
            start=c.start_date,
            end=c.planned_end_date,
            exclude_contract_id=c.contract_id,
            statuses=("draft", "active", "overdue"),
        )
        if conflicts:
            raise HTTPException(status_code=409, detail="cannot activate: some items overlap other contracts")

        if paid_rent >= total_rent and paid_deposit >= total_deposit:
            c.status = "active"

    db.commit()
    db.refresh(p)

    return schemas.PaymentOut(
        payment_id=p.payment_id,
        contract_id=p.contract_id,
        payment_date=p.payment_date,
        amount=_d(p.amount),
        type=p.type,
        method=p.method,
    )


@router.get("/contracts/{contract_id}/payments", response_model=List[schemas.PaymentOut])
def list_payments(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_view(user, c)

    q = (
        select(models.Payment)
        .where(models.Payment.contract_id == contract_id)
        .order_by(models.Payment.payment_id.asc())
    )
    rows = db.execute(q).scalars().all()
    return [
        schemas.PaymentOut(
            payment_id=p.payment_id,
            contract_id=p.contract_id,
            payment_date=p.payment_date,
            amount=_d(p.amount),
            type=p.type,
            method=p.method,
        )
        for p in rows
    ]


# -------------------------
# Cancel
# -------------------------

@router.post("/contracts/{contract_id}/cancel", response_model=schemas.OkOut)
def cancel_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_view(user, c)

    if c.status != "draft":
        raise HTTPException(status_code=409, detail="cancel is allowed only for draft contracts")

    # lock contract
    db.execute(
        select(models.RentalContract.contract_id)
        .where(models.RentalContract.contract_id == contract_id)
        .with_for_update()
    )

    c.status = "canceled"
    db.commit()
    return schemas.OkOut(ok=True)


# -------------------------
# Extend
# -------------------------

@router.post("/contracts/{contract_id}/extend-request", response_model=schemas.ExtendRequestOut)
def extend_request(
    contract_id: int,
    payload: schemas.ExtendRequestIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_view(user, c)

    if c.status not in ("draft", "active", "overdue"):
        return schemas.ExtendRequestOut(ok=False, extra_rent=Decimal("0.00"), reasons=[f"status={c.status}"])

    if payload.new_planned_end_date <= c.planned_end_date:
        return schemas.ExtendRequestOut(ok=False, extra_rent=Decimal("0.00"), reasons=["new_planned_end_date must be greater than current planned_end_date"])

    # check availability on tail
    tail_start = c.planned_end_date
    tail_end = payload.new_planned_end_date

    item_ids = [ci.item_id for ci in c.items]
    conflicts = _check_overlap(
        db,
        item_ids=item_ids,
        start=tail_start,
        end=tail_end,
        exclude_contract_id=c.contract_id,
        statuses=("draft", "active", "overdue"),
    )
    if conflicts:
        return schemas.ExtendRequestOut(ok=False, extra_rent=Decimal("0.00"), reasons=["some items are busy on extension interval"])

    extra_days = (payload.new_planned_end_date - c.planned_end_date).days
    sum_daily = sum((_d(ci.daily_price) for ci in c.items), Decimal("0"))
    extra_rent = (sum_daily * Decimal(extra_days)).quantize(Decimal("0.01"))

    return schemas.ExtendRequestOut(ok=True, extra_rent=extra_rent, reasons=[])


@router.post("/contracts/{contract_id}/extend", response_model=schemas.ContractOut)
def extend_apply(
    contract_id: int,
    payload: schemas.ExtendApplyIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin", "manager"))),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_operate_as_employee(user, c)

    if not payload.approve:
        raise HTTPException(status_code=400, detail="approve must be true")

    if c.status not in ("draft", "active", "overdue"):
        raise HTTPException(status_code=409, detail=f"cannot extend contract in status={c.status}")

    if payload.new_planned_end_date <= c.planned_end_date:
        raise HTTPException(status_code=400, detail="new_planned_end_date must be > current planned_end_date")

    # lock contract + items
    db.execute(
        select(models.RentalContract.contract_id)
        .where(models.RentalContract.contract_id == contract_id)
        .with_for_update()
    )
    item_ids = [ci.item_id for ci in c.items]
    _lock_items(db, item_ids)

    # re-check overlaps on tail
    tail_start = c.planned_end_date
    tail_end = payload.new_planned_end_date
    conflicts = _check_overlap(
        db,
        item_ids=item_ids,
        start=tail_start,
        end=tail_end,
        exclude_contract_id=c.contract_id,
        statuses=("draft", "active", "overdue"),
    )
    if conflicts:
        raise HTTPException(status_code=409, detail="cannot extend: items are busy on extension interval")

    extra_days = (payload.new_planned_end_date - c.planned_end_date).days
    sum_daily = sum((_d(ci.daily_price) for ci in c.items), Decimal("0"))
    extra_rent = (sum_daily * Decimal(extra_days)).quantize(Decimal("0.01"))

    c.planned_end_date = payload.new_planned_end_date

    # update totals
    c = _contract_access_or_404(db, contract_id)
    total_rent, total_deposit = _calc_totals(c)
    c.total_rent_amount = total_rent
    c.total_deposit_amount = total_deposit

    # record extra rent as payment (if any)
    if extra_rent > 0:
        db.add(models.Payment(contract_id=contract_id, amount=extra_rent, type="rent", method=payload.method))

    db.commit()
    c = _contract_access_or_404(db, contract_id)
    return _as_contract_out(c)


# -------------------------
# Change item (request + apply)
# -------------------------

@router.post("/contracts/{contract_id}/change-item-request", response_model=schemas.ChangeItemRequestOut)
def change_item_request(
    contract_id: int,
    payload: schemas.ChangeItemRequestIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_view(user, c)

    if c.status not in ("draft", "active", "overdue"):
        return schemas.ChangeItemRequestOut(ok=False, available_item_ids=[], extra_rent=Decimal("0.00"), extra_deposit=Decimal("0.00"), reasons=[f"status={c.status}"])

    old_ci = next((ci for ci in c.items if ci.item_id == payload.old_item_id), None)
    if not old_ci:
        raise HTTPException(status_code=400, detail="old_item_id not in this contract")

    if (payload.new_product_id is None) == (payload.new_item_id is None):
        raise HTTPException(status_code=400, detail="provide exactly one of new_product_id or new_item_id")

    available_ids: List[int] = []
    reasons: List[str] = []

    # compute deltas using defaults for new item
    old_daily = _d(old_ci.daily_price)
    old_deposit = _d(old_ci.deposit_amount)

    if payload.new_item_id is not None:
        it = db.execute(
            select(models.Item)
            .where(models.Item.item_id == payload.new_item_id)
            .options(selectinload(models.Item.product))
        ).scalar_one_or_none()
        if not it:
            raise HTTPException(status_code=400, detail="new_item_id not found")
        if it.rental_point_id != c.rental_point_id:
            raise HTTPException(status_code=400, detail="new item belongs to another rental point")
        if it.condition_status in ("broken", "lost"):
            return schemas.ChangeItemRequestOut(ok=False, available_item_ids=[], extra_rent=Decimal("0.00"), extra_deposit=Decimal("0.00"), reasons=["new item not rentable"])
        # check overlap
        conflicts = _check_overlap(
            db,
            item_ids=[it.item_id],
            start=c.start_date,
            end=c.planned_end_date,
            exclude_contract_id=c.contract_id,
            statuses=("draft", "active", "overdue"),
        )
        if conflicts:
            return schemas.ChangeItemRequestOut(ok=False, available_item_ids=[], extra_rent=Decimal("0.00"), extra_deposit=Decimal("0.00"), reasons=["new item is busy in overlapping contracts"])
        available_ids = [it.item_id]
        new_daily = _d(it.product.default_daily_price)
        new_deposit = _d(it.product.default_deposit)

    else:
        # list available items of given product_id in this point
        prod = db.execute(select(models.Product).where(models.Product.product_id == payload.new_product_id)).scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=400, detail="new_product_id not found")

        # candidates: same point, condition ok, is_available true
        candidates = db.execute(
            select(models.Item.item_id)
            .where(models.Item.product_id == prod.product_id)
            .where(models.Item.rental_point_id == c.rental_point_id)
            .where(models.Item.is_available.is_(True))
            .where(models.Item.condition_status.not_in(("broken", "lost")))
            .order_by(models.Item.item_id.asc())
            .limit(50)
        ).scalars().all()

        if not candidates:
            return schemas.ChangeItemRequestOut(ok=False, available_item_ids=[], extra_rent=Decimal("0.00"), extra_deposit=Decimal("0.00"), reasons=["no candidate items in point"])

        # filter by overlap
        good: List[int] = []
        for iid in candidates:
            conf = _check_overlap(
                db,
                item_ids=[int(iid)],
                start=c.start_date,
                end=c.planned_end_date,
                exclude_contract_id=c.contract_id,
                statuses=("draft", "active", "overdue"),
            )
            if not conf:
                good.append(int(iid))

        available_ids = good
        if not available_ids:
            return schemas.ChangeItemRequestOut(ok=False, available_item_ids=[], extra_rent=Decimal("0.00"), extra_deposit=Decimal("0.00"), reasons=["all candidate items are busy in overlapping contracts"])

        new_daily = _d(prod.default_daily_price)
        new_deposit = _d(prod.default_deposit)

    # deltas for whole contract duration (простая модель)
    days = _days_inclusive(c.start_date, c.planned_end_date)
    extra_rent = ((new_daily - old_daily) * Decimal(days)).quantize(Decimal("0.01"))
    extra_deposit = (new_deposit - old_deposit).quantize(Decimal("0.01"))

    return schemas.ChangeItemRequestOut(
        ok=True,
        available_item_ids=available_ids,
        extra_rent=extra_rent,
        extra_deposit=extra_deposit,
        reasons=reasons,
    )


@router.post("/contracts/{contract_id}/change-item", response_model=schemas.ContractOut)
def change_item_apply(
    contract_id: int,
    payload: schemas.ChangeItemApplyIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin", "manager"))),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_operate_as_employee(user, c)

    if c.status not in ("draft", "active", "overdue"):
        raise HTTPException(status_code=409, detail=f"cannot change items in status={c.status}")

    old_ci = next((ci for ci in c.items if ci.item_id == payload.old_item_id), None)
    if not old_ci:
        raise HTTPException(status_code=400, detail="old_item_id not in this contract")

    if payload.new_item_id == payload.old_item_id:
        raise HTTPException(status_code=400, detail="new_item_id must be different")

    # lock contract + old/new item rows
    db.execute(
        select(models.RentalContract.contract_id)
        .where(models.RentalContract.contract_id == contract_id)
        .with_for_update()
    )
    _lock_items(db, [payload.old_item_id, payload.new_item_id])

    new_item = db.execute(
        select(models.Item)
        .where(models.Item.item_id == payload.new_item_id)
        .options(selectinload(models.Item.product))
    ).scalar_one_or_none()
    if not new_item:
        raise HTTPException(status_code=400, detail="new_item_id not found")

    if new_item.rental_point_id != c.rental_point_id:
        raise HTTPException(status_code=400, detail="new item belongs to another rental point")
    if new_item.condition_status in ("broken", "lost"):
        raise HTTPException(status_code=409, detail="new item not rentable")

    # overlap check
    conflicts = _check_overlap(
        db,
        item_ids=[new_item.item_id],
        start=c.start_date,
        end=c.planned_end_date,
        exclude_contract_id=c.contract_id,
        statuses=("draft", "active", "overdue"),
    )
    if conflicts:
        raise HTTPException(status_code=409, detail="new item is busy in overlapping contracts")

    # replace in contract_items
    db.execute(
        models.ContractItem.__table__.delete().where(
            and_(
                models.ContractItem.contract_id == contract_id,
                models.ContractItem.item_id == payload.old_item_id,
            )
        )
    )
    db.add(
        models.ContractItem(
            contract_id=contract_id,
            item_id=new_item.item_id,
            daily_price=_d(new_item.product.default_daily_price),
            deposit_amount=_d(new_item.product.default_deposit),
        )
    )
    db.flush()

    # reload and update totals
    c = _contract_access_or_404(db, contract_id)
    total_rent, total_deposit = _calc_totals(c)
    c.total_rent_amount = total_rent
    c.total_deposit_amount = total_deposit

    # adjust already paid amounts to new totals (простая бухгалтерия)
    paid_rent = _sum_payments(c, "rent")
    paid_deposit = _sum_payments(c, "deposit")
    refunded_deposit = _sum_payments(c, "deposit_refund")  # usually negative

    # rent delta
    if paid_rent != total_rent:
        delta = (total_rent - paid_rent).quantize(Decimal("0.01"))
        if delta != 0:
            db.add(models.Payment(contract_id=contract_id, amount=delta, type="rent", method=payload.method))

    # deposit delta (take into account refunds)
    effective_deposit_paid = (paid_deposit + refunded_deposit).quantize(Decimal("0.01"))
    dep_delta = (total_deposit - effective_deposit_paid).quantize(Decimal("0.01"))
    if dep_delta != 0:
        # if need more deposit -> positive "deposit"; if need refund -> negative "deposit_refund"
        if dep_delta > 0:
            db.add(models.Payment(contract_id=contract_id, amount=dep_delta, type="deposit", method=payload.method))
        else:
            db.add(models.Payment(contract_id=contract_id, amount=dep_delta, type="deposit_refund", method=payload.method))

    db.commit()
    c = _contract_access_or_404(db, contract_id)
    return _as_contract_out(c)


# -------------------------
# Return / penalties
# -------------------------

@router.post("/contracts/{contract_id}/return", response_model=schemas.ContractOut)
def return_items(
    contract_id: int,
    payload: schemas.ReturnIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin", "manager", "cashier"))),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_operate_as_employee(user, c)

    if c.status not in ("active", "overdue"):
        raise HTTPException(status_code=409, detail=f"cannot return items for status={c.status}")

    # lock contract
    db.execute(
        select(models.RentalContract.contract_id)
        .where(models.RentalContract.contract_id == contract_id)
        .with_for_update()
    )

    current_item_ids = [ci.item_id for ci in c.items]
    to_return = payload.items if payload.items else current_item_ids

    # validate items
    to_return_set = set(to_return)
    if not to_return_set.issubset(set(current_item_ids)):
        raise HTTPException(status_code=400, detail="some items are not in contract")

    # lock item rows
    _lock_items(db, list(to_return_set))

    # apply damage statuses
    damage = payload.damage or {}
    if damage:
        # load items
        its = db.execute(select(models.Item).where(models.Item.item_id.in_(list(to_return_set)))).scalars().all()
        by_id = {it.item_id: it for it in its}
        for k, st in damage.items():
            iid = int(k)
            if iid not in to_return_set:
                continue
            it = by_id.get(iid)
            if not it:
                continue
            it.condition_status = st
            # if broken/lost -> never rentable
            if st in ("broken", "lost"):
                it.is_available = False

    # add penalties
    penalties_total = Decimal("0.00")
    for pen in payload.penalties or []:
        amt = _d(pen.amount).quantize(Decimal("0.01"))
        if amt <= 0:
            raise HTTPException(status_code=400, detail="penalty amount must be > 0")
        penalties_total += amt
        db.add(models.Payment(contract_id=contract_id, amount=amt, type="penalty", method=payload.method))

    # remove returned items from contract_items (releases availability by triggers)
    db.execute(
        models.ContractItem.__table__.delete().where(
            and_(
                models.ContractItem.contract_id == contract_id,
                models.ContractItem.item_id.in_(list(to_return_set)),
            )
        )
    )

    db.flush()
    c = _contract_access_or_404(db, contract_id)

    # if no items left -> close contract and refund deposit (minus penalties)
    if len(c.items) == 0:
        c.actual_end_date = payload.actual_end_date or date.today()
        c.status = "closed"

        paid_deposit = _sum_payments(c, "deposit")
        refunded_deposit = _sum_payments(c, "deposit_refund")  # negative if refunds were made
        already_refunded = (-refunded_deposit).quantize(Decimal("0.01")) if refunded_deposit < 0 else Decimal("0.00")

        refundable = (paid_deposit - already_refunded - penalties_total).quantize(Decimal("0.01"))
        if refundable > 0:
            db.add(models.Payment(contract_id=contract_id, amount=-refundable, type="deposit_refund", method=payload.method))

    db.commit()
    c = _contract_access_or_404(db, contract_id)
    return _as_contract_out(c)


# -------------------------
# Overdue / lost
# -------------------------

@router.post("/contracts/{contract_id}/mark-overdue", response_model=schemas.OverdueOut)
def mark_overdue(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin", "manager"))),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_operate_as_employee(user, c)

    if c.status != "active":
        raise HTTPException(status_code=409, detail="only active contract can be marked overdue")

    today = date.today()
    if today <= c.planned_end_date:
        raise HTTPException(status_code=409, detail="contract is not overdue yet")

    # lock
    db.execute(
        select(models.RentalContract.contract_id)
        .where(models.RentalContract.contract_id == contract_id)
        .with_for_update()
    )

    overdue_days = (today - c.planned_end_date).days
    sum_daily = sum((_d(ci.daily_price) for ci in c.items), Decimal("0"))
    penalty = (sum_daily * Decimal(overdue_days)).quantize(Decimal("0.01"))

    c.status = "overdue"
    if penalty > 0:
        db.add(models.Payment(contract_id=contract_id, amount=penalty, type="penalty", method="cash"))

    db.commit()
    return schemas.OverdueOut(ok=True, penalty_amount=penalty)


@router.post("/contracts/{contract_id}/close-as-lost", response_model=schemas.ContractOut)
def close_as_lost(
    contract_id: int,
    payload: schemas.CloseAsLostIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_employee(("admin", "manager"))),
):
    c = _contract_access_or_404(db, contract_id)
    _ensure_can_operate_as_employee(user, c)

    if c.status not in ("active", "overdue"):
        raise HTTPException(status_code=409, detail=f"cannot close as lost for status={c.status}")

    # lock contract
    db.execute(
        select(models.RentalContract.contract_id)
        .where(models.RentalContract.contract_id == contract_id)
        .with_for_update()
    )

    current_item_ids = [ci.item_id for ci in c.items]
    lost_items = payload.items if payload.items else current_item_ids

    if not set(lost_items).issubset(set(current_item_ids)):
        raise HTTPException(status_code=400, detail="some items are not in contract")

    _lock_items(db, lost_items)

    # mark items lost and unavailable
    its = db.execute(select(models.Item).where(models.Item.item_id.in_(lost_items))).scalars().all()
    for it in its:
        it.condition_status = "lost"
        it.is_available = False

    # optional penalty
    if payload.penalty_amount and _d(payload.penalty_amount) > 0:
        db.add(models.Payment(contract_id=contract_id, amount=_d(payload.penalty_amount), type="penalty", method=payload.method))

    # remove all contract_items and close
    db.execute(models.ContractItem.__table__.delete().where(models.ContractItem.contract_id == contract_id))
    c.actual_end_date = payload.actual_end_date or date.today()
    c.status = "closed"

    db.commit()
    c = _contract_access_or_404(db, contract_id)
    return _as_contract_out(c)
