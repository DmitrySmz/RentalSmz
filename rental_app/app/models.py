# app/models.py
from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import (
    String, Integer, Boolean, DateTime, Date, Text, ForeignKey,
    CheckConstraint, Index, Numeric
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# --- ENUM типы (совпадают со скриптом init_db.sql) ---
role_enum = ENUM('admin','manager','cashier', name='role_enum', create_type=False)
condition_status_enum = ENUM('new','good','worn','broken','lost', name='condition_status_enum', create_type=False)
contract_status_enum = ENUM('draft','active','closed','overdue','canceled', name='contract_status_enum', create_type=False)
payment_type_enum = ENUM('rent','deposit','deposit_refund','penalty', name='payment_type_enum', create_type=False)
payment_method_enum = ENUM('cash','card','online', name='payment_method_enum', create_type=False)

# --- Таблицы ---
class Client(Base):
    __tablename__ = "clients"
    client_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    contracts: Mapped[list[RentalContract]] = relationship(back_populates="client")  # noqa: F821

class RentalPoint(Base):
    __tablename__ = "rental_points"
    rental_point_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))

    employees: Mapped[list[Employee]] = relationship(back_populates="rental_point")  # noqa
    items: Mapped[list[Item]] = relationship(back_populates="rental_point")  # noqa
    contracts: Mapped[list[RentalContract]] = relationship(back_populates="rental_point")  # noqa

class Employee(Base):
    __tablename__ = "employees"
    employee_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(role_enum)
    rental_point_id: Mapped[int] = mapped_column(ForeignKey("rental_points.rental_point_id"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    rental_point: Mapped[RentalPoint] = relationship(back_populates="employees")
    contracts: Mapped[list[RentalContract]] = relationship(back_populates="employee")  # noqa

class Category(Base):
    __tablename__ = "categories"
    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    products: Mapped[list[Product]] = relationship(back_populates="category")  # noqa

class Product(Base):
    __tablename__ = "products"
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.category_id"))
    name: Mapped[str] = mapped_column(String(200), index=True)
    brand: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    volume_liters: Mapped[int | None] = mapped_column(Integer)
    people_count: Mapped[int | None] = mapped_column(Integer)
    temperature_min: Mapped[int | None] = mapped_column(Integer)
    default_daily_price: Mapped[float] = mapped_column(Numeric(10, 2))
    default_deposit: Mapped[float] = mapped_column(Numeric(10, 2))

    category: Mapped[Category] = relationship(back_populates="products")
    items: Mapped[list[Item]] = relationship(back_populates="product")  # noqa

    __table_args__ = (
        CheckConstraint("default_daily_price >= 0 AND default_deposit >= 0", name="ck_products_prices_nonneg"),
        Index("ix_products_category", "category_id"),
    )

class Item(Base):
    __tablename__ = "items"
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    rental_point_id: Mapped[int] = mapped_column(ForeignKey("rental_points.rental_point_id"))
    inventory_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    color: Mapped[str | None] = mapped_column(String(50))
    size: Mapped[str | None] = mapped_column(String(50))
    condition_status: Mapped[str] = mapped_column(condition_status_enum)
    is_available: Mapped[bool] = mapped_column(Boolean, server_default="true")

    product: Mapped[Product] = relationship(back_populates="items")
    rental_point: Mapped[RentalPoint] = relationship(back_populates="items")
    contract_items: Mapped[list[ContractItem]] = relationship(back_populates="item")  # noqa

    __table_args__ = (
        Index("ix_items_product", "product_id"),
        Index("ix_items_point_available", "rental_point_id", "is_available"),
    )

class RentalContract(Base):
    __tablename__ = "rental_contracts"
    contract_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.client_id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.employee_id"))
    rental_point_id: Mapped[int] = mapped_column(ForeignKey("rental_points.rental_point_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    start_date: Mapped[date] = mapped_column(Date)
    planned_end_date: Mapped[date] = mapped_column(Date)
    actual_end_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(contract_status_enum)
    total_rent_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    total_deposit_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))

    client: Mapped[Client] = relationship(back_populates="contracts")
    employee: Mapped[Employee] = relationship(back_populates="contracts")
    rental_point: Mapped[RentalPoint] = relationship(back_populates="contracts")
    items: Mapped[list[ContractItem]] = relationship(back_populates="contract", cascade="all, delete-orphan")  # noqa
    payments: Mapped[list[Payment]] = relationship(back_populates="contract")  # noqa

    __table_args__ = (
        CheckConstraint("planned_end_date >= start_date", name="ck_contract_dates"),
        CheckConstraint("(actual_end_date IS NULL) OR (actual_end_date >= start_date)", name="ck_contract_actual"),
        CheckConstraint("(total_rent_amount IS NULL OR total_rent_amount >= 0) AND (total_deposit_amount IS NULL OR total_deposit_amount >= 0)", name="ck_contract_totals_nonneg"),
        Index("ix_contracts_client", "client_id"),
        Index("ix_contracts_status", "status"),
        Index("ix_contracts_period", "start_date", "planned_end_date"),
    )

class ContractItem(Base):
    __tablename__ = "contract_items"
    contract_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("rental_contracts.contract_id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.item_id"))
    daily_price: Mapped[float] = mapped_column(Numeric(10, 2))
    deposit_amount: Mapped[float] = mapped_column(Numeric(10, 2))

    contract: Mapped[RentalContract] = relationship(back_populates="items")
    item: Mapped[Item] = relationship(back_populates="contract_items")

    __table_args__ = (
        CheckConstraint("daily_price >= 0 AND deposit_amount >= 0", name="ck_contract_item_prices_nonneg"),
        Index("ix_contract_items_contract", "contract_id"),
        Index("ix_contract_items_item", "item_id"),
    )

class Payment(Base):
    __tablename__ = "payments"
    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("rental_contracts.contract_id", ondelete="CASCADE"))
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    type: Mapped[str] = mapped_column(payment_type_enum)
    method: Mapped[str | None] = mapped_column(payment_method_enum)

    contract: Mapped[RentalContract] = relationship(back_populates="payments")

    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_payment_nonzero"),
        Index("ix_payments_contract", "contract_id"),
        Index("ix_payments_date", "payment_date"),
    )
