from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal


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


# -------------------------
# AUTH schemas
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
    email: Optional[str] = None
    login: Optional[str] = None
    role: Optional[str] = None
    rental_point_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class AuthSessionOut(BaseModel):
    authenticated: bool
    remaining_seconds: int = Field(ge=0)
