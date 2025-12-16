# scripts/seed_demo.py
from __future__ import annotations

import os
import sys
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# чтобы работали "import app...." при запуске из scripts/
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app import models  # noqa
from app.utils.security import hash_password, norm_email, norm_login  # noqa


def days_inclusive(start: date, end: date) -> int:
    return (end - start).days + 1


def get_or_create(session: Session, model, defaults: dict | None = None, **kwargs):
    obj = session.execute(select(model).filter_by(**kwargs)).scalar_one_or_none()
    if obj:
        return obj
    data = dict(kwargs)
    if defaults:
        data.update(defaults)
    obj = model(**data)
    session.add(obj)
    session.flush()  # получить id
    return obj


def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")

    engine = create_engine(db_url, future=True)

    with Session(engine) as session:
        # ---------- rental_points ----------
        p1 = get_or_create(
            session,
            models.RentalPoint,
            rental_point_id=1,
            defaults={"name": "Main Point", "address": "Amsterdam center", "phone": "+31-000-000"},
        )
        p2 = get_or_create(
            session,
            models.RentalPoint,
            rental_point_id=2,
            defaults={"name": "North Point", "address": "Amsterdam Noord", "phone": "+31-000-111"},
        )

        # ---------- employees (если нет) ----------
        def ensure_employee(login: str, password: str, role: str, point_id: int):
            login_n = norm_login(login)
            emp = session.execute(select(models.Employee).where(models.Employee.login == login_n)).scalar_one_or_none()
            if emp:
                return emp
            emp = models.Employee(
                login=login_n,
                password_hash=hash_password(password),
                first_name=role.title(),
                last_name="User",
                role=role,
                rental_point_id=point_id,
                is_active=True,
            )
            session.add(emp)
            session.flush()
            return emp

        admin = ensure_employee("admin", "admin123", "admin", 1)
        manager = ensure_employee("manager", "manager123", "manager", 1)
        cashier = ensure_employee("cashier", "cashier123", "cashier", 2)

        # ---------- categories ----------
        cat_backpacks = get_or_create(
            session,
            models.Category,
            name="Backpacks",
            defaults={"description": "Tourist backpacks"},
        )
        cat_tents = get_or_create(
            session,
            models.Category,
            name="Tents",
            defaults={"description": "Tourist tents"},
        )

        # ---------- products (20 штук) ----------
        backpacks = [
            ("Deuter Aircontact 60+10", "Deuter", 60, Decimal("12.00"), Decimal("120.00")),
            ("Osprey Atmos AG 65", "Osprey", 65, Decimal("14.00"), Decimal("150.00")),
            ("Gregory Baltoro 75", "Gregory", 75, Decimal("15.00"), Decimal("160.00")),
            ("The North Face Banchee 50", "TNF", 50, Decimal("10.00"), Decimal("110.00")),
            ("Fjällräven Kajka 65", "Fjallraven", 65, Decimal("16.00"), Decimal("180.00")),
            ("Black Diamond Speed 40", "Black Diamond", 40, Decimal("9.00"), Decimal("90.00")),
            ("Salewa Alp Trainer 35", "Salewa", 35, Decimal("8.00"), Decimal("80.00")),
            ("Mammut Trion 50", "Mammut", 50, Decimal("11.00"), Decimal("115.00")),
            ("Tatonka Yukon 60+10", "Tatonka", 60, Decimal("10.50"), Decimal("105.00")),
            ("Ferrino Transalp 60", "Ferrino", 60, Decimal("9.50"), Decimal("95.00")),
        ]

        tents = [
            ("MSR Hubba Hubba NX 2", "MSR", 2, -5, Decimal("18.00"), Decimal("220.00")),
            ("Big Agnes Copper Spur HV UL2", "Big Agnes", 2, -3, Decimal("20.00"), Decimal("250.00")),
            ("Naturehike Cloud Up 2", "Naturehike", 2, 0, Decimal("12.00"), Decimal("140.00")),
            ("Hilleberg Nallo 2", "Hilleberg", 2, -15, Decimal("28.00"), Decimal("400.00")),
            ("MSR Elixir 3", "MSR", 3, -2, Decimal("19.00"), Decimal("230.00")),
            ("Coleman Darwin 3+", "Coleman", 3, 2, Decimal("10.00"), Decimal("120.00")),
            ("Vango Banshee 300", "Vango", 3, -1, Decimal("11.00"), Decimal("130.00")),
            ("Quechua 2 Seconds 2", "Quechua", 2, 5, Decimal("9.00"), Decimal("90.00")),
            ("Terra Nova Laser Compact 2", "Terra Nova", 2, -2, Decimal("22.00"), Decimal("280.00")),
            ("Nemo Dagger OSMO 2P", "Nemo", 2, -4, Decimal("21.00"), Decimal("270.00")),
        ]

        def upsert_product(category_id: int, name: str, defaults: dict):
            prod = session.execute(
                select(models.Product).where(models.Product.category_id == category_id, models.Product.name == name)
            ).scalar_one_or_none()
            if prod:
                return prod
            prod = models.Product(category_id=category_id, name=name, **defaults)
            session.add(prod)
            session.flush()
            return prod

        products: list[models.Product] = []

        for name, brand, vol, day, dep in backpacks:
            products.append(
                upsert_product(
                    cat_backpacks.category_id,
                    name,
                    {
                        "brand": brand,
                        "description": f"Backpack {vol}L",
                        "volume_liters": vol,
                        "people_count": None,
                        "temperature_min": None,
                        "default_daily_price": day,
                        "default_deposit": dep,
                    },
                )
            )

        for name, brand, ppl, tmin, day, dep in tents:
            products.append(
                upsert_product(
                    cat_tents.category_id,
                    name,
                    {
                        "brand": brand,
                        "description": f"Tent for {ppl} people",
                        "volume_liters": None,
                        "people_count": ppl,
                        "temperature_min": tmin,
                        "default_daily_price": day,
                        "default_deposit": dep,
                    },
                )
            )

        # ---------- items ----------
        colors = ["black", "blue", "green", "red", "gray"]
        sizes = ["S", "M", "L", "XL"]
        conds = ["good", "good", "good", "worn"]  # чаще good

        def item_exists(inv: str) -> bool:
            return session.execute(select(models.Item).where(models.Item.inventory_number == inv)).scalar_one_or_none() is not None

        inv_counter = 1
        for prod in products:
            # по 2 предмета в пункт 1 и 1 предмет в пункт 2
            for point in (p1, p1, p2):
                inv = f"INV-{inv_counter:04d}"
                inv_counter += 1
                if item_exists(inv):
                    continue
                it = models.Item(
                    product_id=prod.product_id,
                    rental_point_id=point.rental_point_id,
                    inventory_number=inv,
                    color=random.choice(colors),
                    size=random.choice(sizes),
                    condition_status=random.choice(conds),
                    is_available=True,
                )
                session.add(it)

        session.flush()

        # ---------- clients ----------
        def ensure_client(email: str, password: str, first: str, last: str):
            em = norm_email(email)
            c = session.execute(select(models.Client).where(models.Client.email == em)).scalar_one_or_none()
            if c:
                return c
            c = models.Client(
                email=em,
                password_hash=hash_password(password),
                phone="+79990000000",
                first_name=first,
                last_name=last,
                is_active=True,
            )
            session.add(c)
            session.flush()
            return c

        c1 = ensure_client("alice@gmail.com", "alice123", "Alice", "Walker")
        c2 = ensure_client("bob@gmail.com", "bob123", "Bob", "Stone")
        c3 = ensure_client("claire@gmail.com", "claire123", "Claire", "Moss")

        # ---------- helper: pick free items by point ----------
        def pick_items(point_id: int, count: int) -> list[models.Item]:
            rows = session.execute(
                select(models.Item)
                .where(models.Item.rental_point_id == point_id)
                .where(models.Item.condition_status.notin_(("broken", "lost")))
                .order_by(models.Item.item_id.asc())
            ).scalars().all()
            return rows[:count]

        # ---------- contracts + contract_items + payments ----------
        today = date.today()

        def create_contract(client, employee, point_id: int, start: date, end: date, status: str, items: list[models.Item], pay: bool):
            contract = models.RentalContract(
                client_id=client.client_id,
                employee_id=employee.employee_id,
                rental_point_id=point_id,
                start_date=start,
                planned_end_date=end,
                actual_end_date=None,
                status=status,
                total_rent_amount=Decimal("0.00"),
                total_deposit_amount=Decimal("0.00"),
            )
            session.add(contract)
            session.flush()

            total_dep = Decimal("0.00")
            total_rent = Decimal("0.00")
            d = days_inclusive(start, end)

            for it in items:
                prod = session.execute(select(models.Product).where(models.Product.product_id == it.product_id)).scalar_one()
                daily = Decimal(str(prod.default_daily_price))
                dep = Decimal(str(prod.default_deposit))
                session.add(
                    models.ContractItem(
                        contract_id=contract.contract_id,
                        item_id=it.item_id,
                        daily_price=daily,
                        deposit_amount=dep,
                    )
                )
                total_dep += dep
                total_rent += (daily * Decimal(d))

            contract.total_deposit_amount = total_dep
            contract.total_rent_amount = total_rent

            if pay:
                # депозит + аренда
                session.add(models.Payment(contract_id=contract.contract_id, amount=total_dep, type="deposit", method="card"))
                session.add(models.Payment(contract_id=contract.contract_id, amount=total_rent, type="rent", method="card"))

            return contract

        # active (оплачен)
        items_a = pick_items(1, 2)
        create_contract(c1, manager, 1, today - timedelta(days=1), today + timedelta(days=2), "active", items_a, pay=True)

        # draft (будущая бронь)
        items_d = pick_items(2, 1)
        create_contract(c2, cashier, 2, today + timedelta(days=3), today + timedelta(days=5), "draft", items_d, pay=False)

        # overdue (просрочка)
        items_o = pick_items(1, 1)[-1:]
        create_contract(c3, manager, 1, today - timedelta(days=10), today - timedelta(days=5), "overdue", items_o, pay=True)

        # closed (возврат депозита)
        items_c = pick_items(2, 1)
        closed = create_contract(c1, cashier, 2, today - timedelta(days=20), today - timedelta(days=18), "closed", items_c, pay=True)
        closed.actual_end_date = closed.planned_end_date
        # возврат депозита (как отрицательная сумма, чтобы было видно “движение”)
        if closed.total_deposit_amount and closed.total_deposit_amount != 0:
            session.add(models.Payment(contract_id=closed.contract_id, amount=-closed.total_deposit_amount, type="deposit_refund", method="cash"))

        session.commit()

    print("OK: demo data seeded")


if __name__ == "__main__":
    main()
