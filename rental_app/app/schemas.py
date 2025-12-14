# app/schemas.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Literal, Dict

from pydantic import BaseModel, Field, ConfigDict


# -------------------------
# Common
# -------------------------

class OkOut(BaseModel):
    ok: bool


# -------------------------
# AUTH
# -------------------------

class ClientRegisterIn(BaseModel):
    email: str
    password: str
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    remember: bool = False


class ClientLoginIn(BaseModel):
    email: str
    password: str
    remember: bool = False


class EmployeeLoginIn(BaseModel):
    login: str
    password: str
    remember: bool = False


class AuthMeOut(BaseModel):
    kind: Literal["client", "employee"]
    id: int
    # client
    email: Optional[str] = None
    # employee
    login: Optional[str] = None
    role: Optional[str] = None
    rental_point_id: Optional[int] = None
    # both
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class AuthSessionOut(BaseModel):
    authenticated: bool
    remaining_seconds: int


# -------------------------
# CATALOG
# -------------------------

class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    name: str
    description: Optional[str] = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    category_id: int
    name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    volume_liters: Optional[int] = None
    people_count: Optional[int] = None
    temperature_min: Optional[int] = None
    default_daily_price: Decimal
    default_deposit: Decimal

class AvailabilityResponse(BaseModel):
    product_id: int
    rental_point_id: int
    start: str
    end: str
    available_count: int = Field(ge=0)
    item_ids: List[int]

class AvailabilityOut(BaseModel):
    available_count: int
    item_ids: List[int]


# -------------------------
# RENTALS / CONTRACTS
# -------------------------

class ContractItemIn(BaseModel):
    item_id: int
    daily_price: Optional[Decimal] = None
    deposit_amount: Optional[Decimal] = None


class ContractCreate(BaseModel):
    client_id: Optional[int] = None  # only when employee creates
    rental_point_id: int
    start_date: date
    planned_end_date: date
    items: List[ContractItemIn]


class ContractItemOut(BaseModel):
    contract_item_id: int
    item_id: int
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    inventory_number: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    daily_price: Decimal
    deposit_amount: Decimal


class ContractOut(BaseModel):
    contract_id: int
    client_id: int
    employee_id: int
    rental_point_id: int
    created_at: datetime
    start_date: date
    planned_end_date: date
    actual_end_date: Optional[date] = None
    status: str
    total_rent_amount: Decimal = Decimal("0.00")
    total_deposit_amount: Decimal = Decimal("0.00")
    items: List[ContractItemOut] = []


PaymentType = Literal["rent", "deposit", "deposit_refund", "penalty"]
PaymentMethod = Optional[Literal["cash", "card", "online"]]


class PaymentCreate(BaseModel):
    amount: Decimal
    type: PaymentType
    method: PaymentMethod = None


class PaymentOut(BaseModel):
    payment_id: int
    contract_id: int
    payment_date: datetime
    amount: Decimal
    type: PaymentType
    method: PaymentMethod = None


# -------------------------
# EXTEND
# -------------------------

class ExtendRequestIn(BaseModel):
    new_planned_end_date: date


class ExtendRequestOut(BaseModel):
    ok: bool
    extra_rent: Decimal
    reasons: List[str] = []


class ExtendApplyIn(BaseModel):
    new_planned_end_date: date
    approve: bool = True
    method: PaymentMethod = "cash"


# -------------------------
# CHANGE ITEM
# -------------------------

DamageStatus = Literal["new", "good", "worn", "broken", "lost"]


class ChangeItemRequestIn(BaseModel):
    old_item_id: int
    new_product_id: Optional[int] = None
    new_item_id: Optional[int] = None


class ChangeItemRequestOut(BaseModel):
    ok: bool
    available_item_ids: List[int]
    extra_rent: Decimal
    extra_deposit: Decimal
    reasons: List[str] = []


class ChangeItemApplyIn(BaseModel):
    old_item_id: int
    new_item_id: int
    method: PaymentMethod = "cash"


# -------------------------
# RETURN / OVERDUE / LOST
# -------------------------

class PenaltyIn(BaseModel):
    amount: Decimal
    reason: Optional[str] = None


class ReturnIn(BaseModel):
    items: Optional[List[int]] = None
    damage: Optional[Dict[int, DamageStatus]] = None
    penalties: Optional[List[PenaltyIn]] = None
    method: PaymentMethod = "cash"
    actual_end_date: Optional[date] = None


class OverdueOut(BaseModel):
    ok: bool
    penalty_amount: Decimal


class CloseAsLostIn(BaseModel):
    items: Optional[List[int]] = None
    penalty_amount: Optional[Decimal] = None
    method: PaymentMethod = "cash"
    actual_end_date: Optional[date] = None


# -------------------------
# ADMIN payloads
# -------------------------

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None


class ProductCreate(BaseModel):
    category_id: int
    name: str = Field(..., min_length=1, max_length=200)
    brand: Optional[str] = None
    description: Optional[str] = None
    volume_liters: Optional[int] = Field(None, ge=0)
    people_count: Optional[int] = Field(None, ge=1)
    temperature_min: Optional[int] = None
    default_daily_price: Decimal = Field(..., ge=0)
    default_deposit: Decimal = Field(..., ge=0)


class ProductUpdate(ProductCreate):
    pass


class ItemOut(BaseModel):
    item_id: int
    product_id: int
    product_name: Optional[str] = None
    rental_point_id: int
    inventory_number: str
    color: Optional[str] = None
    size: Optional[str] = None
    condition_status: str
    is_available: bool


class ItemCreate(BaseModel):
    product_id: int
    rental_point_id: int
    inventory_number: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = None
    size: Optional[str] = None
    condition_status: DamageStatus = "good"
    is_available: Optional[bool] = True


class ItemUpdate(BaseModel):
    color: Optional[str] = None
    size: Optional[str] = None
    condition_status: Optional[DamageStatus] = None
    is_available: Optional[bool] = None


class ItemMove(BaseModel):
    to_point_id: int


class ItemStatus(BaseModel):
    condition_status: DamageStatus
    is_available: bool


# -------------------------
# REPORTS
# -------------------------

class PopularProductOut(BaseModel):
    product_id: int
    name: str
    uses: int


class PointReportOut(BaseModel):
    point_id: int
    from_date: date
    to_date: date
    contracts_count: int
    rent_income: Decimal
    deposit_in: Decimal
    deposit_refund: Decimal
    penalties_income: Decimal
    overdue_contracts: int
    popular_products: List[PopularProductOut] = []
