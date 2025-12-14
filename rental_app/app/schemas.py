# app/schemas.py
from __future__ import annotations
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List


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
