#!/usr/bin/env python3
"""
Seed script — creates realistic Colombian test data for the order management system.

Usage:
    python scripts/seed_data.py

Requires:
    - DATABASE_URL env var set (or .env file in project root)
    - pip install aiosqlite (or asyncpg for PostgreSQL)
"""

import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# ── Python path ────────────────────────────────────────────────────────────────
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src = os.path.join(_project_root, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_project_root, ".env"))
except ImportError:
    pass

# ── Imports after path fix ─────────────────────────────────────────────────────
from database import AsyncSessionLocal, engine, Base  # noqa: E402
import models  # noqa: F401, E402


# ── Colombian test data ────────────────────────────────────────────────────────

COLOMBIAN_CUSTOMERS = [
    ("Juan Camilo Rivera",      "3161234567", "jcrivera@gmail.com"),
    ("María Fernanda López",    "3172345678", "mflopez@hotmail.com"),
    ("Andrés Felipe García",    "3183456789", "afgarcia@yahoo.com"),
    ("Laura Patricia Martínez", "3194567890", None),
    ("Carlos Eduardo Torres",   "3005678901", "cetorres@outlook.com"),
    ("Ana Sofía Ramírez",       "3016789012", "asramirez@gmail.com"),
    ("Diego Alejandro Vargas",  "3027890123", None),
    ("Valentina Gómez Herrera", "3038901234", "vgomez@gmail.com"),
    ("Sebastián Moreno Rojas",  "3049012345", "smoreno@empresa.co"),
    ("Isabela Castillo Niño",   "3050123456", "icastillo@correo.co"),
]

PRODUCTS = [
    ("Camiseta básica talla M",        "CMT-BAS-M",  Decimal("45000"),  1),
    ("Zapatos deportivos Nike talla 42","ZAP-NIK-42", Decimal("280000"), 1),
    ("Celular Samsung Galaxy A54",     "CEL-SAM-A54", Decimal("1150000"),1),
    ("Audífonos inalámbricos JBL",     "AUD-JBL-BT",  Decimal("180000"), 1),
    ("Libro: Cien años de soledad",    "LIB-CIEN-SOL",Decimal("35000"),  2),
    ("Teclado mecánico gamer",         "TEC-MEC-GAM", Decimal("220000"), 1),
    ("Mouse inalámbrico Logitech",     "MOU-LOG-WL",  Decimal("95000"),  1),
    ("Mochila escolar 30L",            "MCH-ESC-30L", Decimal("85000"),  1),
    ("Perfume importado 100ml",        "PRF-IMP-100", Decimal("320000"), 1),
    ("Reloj deportivo Casio",          "REL-CAS-DEP", Decimal("145000"), 1),
    ("Pijama de algodón talla L",      "PIJ-ALG-L",   Decimal("65000"),  2),
    ("Zapatos de cuero talla 38",      "ZAP-CUE-38",  Decimal("195000"), 1),
]

STATUSES = [
    "pending", "pending",
    "confirmed", "confirmed",
    "processing",
    "shipped",
    "in_transit", "in_transit",
    "out_for_delivery",
    "delivered", "delivered", "delivered",
    "cancelled",
]

CARRIERS = ["Coordinadora", "Servientrega", "90minutos"]
CARRIER_WEIGHTS = [0.4, 0.3, 0.3]

COLOMBIAN_CITIES = [
    "Bogotá", "Medellín", "Cali", "Barranquilla",
    "Cartagena", "Bucaramanga", "Pereira", "Manizales",
]


def _random_order_number(year: int = 2026) -> str:
    import random
    digits = "".join([str(random.randint(0, 9)) for _ in range(6)])
    return f"ECO-{year}-{digits}"


def _random_date(days_ago_min: int = 1, days_ago_max: int = 60) -> datetime:
    delta = random.randint(days_ago_min, days_ago_max)
    return datetime.now(timezone.utc) - timedelta(days=delta)


async def main() -> None:
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, delete
        from models.customer import Customer
        from models.order import Order, OrderItem, OrderStatusHistory
        from models.shipment import Shipment

        print("Cleaning existing seed data...")
        await session.execute(delete(OrderStatusHistory))
        await session.execute(delete(Shipment))
        await session.execute(delete(OrderItem))
        await session.execute(delete(Order))
        await session.execute(delete(Customer))
        await session.commit()

        # ── Create customers ───────────────────────────────────────────────────
        print("Creating 10 customers...")
        customers = []
        for full_name, phone, email in COLOMBIAN_CUSTOMERS:
            customer = Customer(
                id=str(uuid.uuid4()),
                email=email,
                phone=phone,
                full_name=full_name,
                created_at=_random_date(30, 180),
            )
            session.add(customer)
            customers.append(customer)
        await session.commit()
        print(f"  ✓ {len(customers)} customers created")

        # ── Create orders ──────────────────────────────────────────────────────
        print("Creating 50 orders with items, shipments, and history...")
        orders_created = 0

        for i in range(50):
            customer = random.choice(customers)
            status = random.choice(STATUSES)
            order_date = _random_date(1, 30)

            # Pick 1-3 products
            selected = random.sample(PRODUCTS, k=random.randint(1, 3))
            total = Decimal("0.00")
            items_data = []
            for product_name, sku, unit_price, default_qty in selected:
                qty = random.randint(1, default_qty)
                subtotal = unit_price * qty
                total += subtotal
                items_data.append(
                    {
                        "id": str(uuid.uuid4()),
                        "product_name": product_name,
                        "product_sku": sku,
                        "quantity": qty,
                        "unit_price": unit_price,
                        "subtotal": subtotal,
                    }
                )

            # Timestamps based on status
            confirmed_at = None
            shipped_at = None
            delivered_at = None
            estimated_delivery = order_date + timedelta(days=3)
            actual_delivery = None
            cancellation_reason = None

            if status in ("confirmed", "processing", "shipped", "in_transit",
                          "out_for_delivery", "delivered"):
                confirmed_at = order_date + timedelta(hours=2)
            if status in ("shipped", "in_transit", "out_for_delivery", "delivered"):
                shipped_at = order_date + timedelta(days=1)
            if status == "delivered":
                delivered_at = order_date + timedelta(days=random.randint(2, 4))
                actual_delivery = delivered_at
            if status == "cancelled":
                reasons = [
                    "Cliente solicitó cancelación",
                    "Pago no completado",
                    "Producto sin stock",
                ]
                cancellation_reason = random.choice(reasons)

            order = Order(
                id=str(uuid.uuid4()),
                order_number=_random_order_number(),
                customer_id=customer.id,
                status=status,
                total_amount=total,
                currency="COP",
                created_at=order_date,
                confirmed_at=confirmed_at,
                shipped_at=shipped_at,
                delivered_at=delivered_at,
                estimated_delivery=estimated_delivery,
                actual_delivery=actual_delivery,
                cancellation_reason=cancellation_reason,
            )
            session.add(order)
            await session.flush()

            # Items
            for item_data in items_data:
                session.add(OrderItem(order_id=order.id, **item_data))

            # Status history
            history_entries = [("pending", None, order_date, "Pedido creado")]
            if status != "pending":
                history_entries.append(
                    ("confirmed", "pending", order_date + timedelta(hours=2), "Pago confirmado")
                )
            if status in ("processing", "shipped", "in_transit", "out_for_delivery", "delivered"):
                history_entries.append(
                    ("processing", "confirmed", order_date + timedelta(hours=4), "En preparación")
                )
            if status in ("shipped", "in_transit", "out_for_delivery", "delivered"):
                history_entries.append(
                    ("shipped", "processing", order_date + timedelta(days=1), "Enviado con transportadora")
                )
            if status in ("in_transit", "out_for_delivery", "delivered"):
                history_entries.append(
                    ("in_transit", "shipped", order_date + timedelta(days=2), "En tránsito")
                )
            if status in ("out_for_delivery", "delivered"):
                history_entries.append(
                    ("out_for_delivery", "in_transit", order_date + timedelta(days=3), "En reparto")
                )
            if status == "delivered":
                history_entries.append(
                    ("delivered", "out_for_delivery", actual_delivery, "Entregado")
                )
            if status == "cancelled":
                history_entries.append(
                    ("cancelled", "pending", order_date + timedelta(hours=1), cancellation_reason)
                )

            for new_s, prev_s, ts, notes in history_entries:
                session.add(
                    OrderStatusHistory(
                        id=str(uuid.uuid4()),
                        order_id=order.id,
                        previous_status=prev_s,
                        new_status=new_s,
                        changed_at=ts,
                        changed_by="system",
                        notes=notes,
                    )
                )

            # Shipment (for orders past 'processing')
            if status in ("shipped", "in_transit", "out_for_delivery", "delivered"):
                carrier = random.choices(CARRIERS, weights=CARRIER_WEIGHTS, k=1)[0]
                prefixes = {
                    "Coordinadora": "CRD",
                    "Servientrega": "SRV",
                    "90minutos": "90M",
                }
                prefix = prefixes[carrier]
                tracking = f"{prefix}{''.join([str(random.randint(0,9)) for _ in range(12)])}"
                city = random.choice(COLOMBIAN_CITIES)

                tracking_events = [
                    {
                        "event": "picked_up",
                        "location": "Bogotá",
                        "timestamp": (order_date + timedelta(days=1)).isoformat(),
                        "description": "Paquete recolectado",
                    }
                ]
                if status in ("in_transit", "out_for_delivery", "delivered"):
                    tracking_events.append({
                        "event": "in_transit",
                        "location": city,
                        "timestamp": (order_date + timedelta(days=2)).isoformat(),
                        "description": "En tránsito",
                    })
                if status in ("out_for_delivery", "delivered"):
                    tracking_events.append({
                        "event": "out_for_delivery",
                        "location": city,
                        "timestamp": (order_date + timedelta(days=3)).isoformat(),
                        "description": "En reparto",
                    })
                if status == "delivered":
                    tracking_events.append({
                        "event": "delivered",
                        "location": city,
                        "timestamp": actual_delivery.isoformat() if actual_delivery else None,
                        "description": "Entregado exitosamente",
                    })

                shipment = Shipment(
                    id=str(uuid.uuid4()),
                    order_id=order.id,
                    tracking_number=tracking,
                    carrier=carrier,
                    service_type="Estándar",
                    current_location=city,
                    status=status if status in (
                        "pending", "picked_up", "in_transit",
                        "out_for_delivery", "delivered",
                    ) else "in_transit",
                    status_history=tracking_events,
                    estimated_delivery=estimated_delivery,
                    delivered_at=actual_delivery,
                    delivery_attempts=1 if status == "delivered" else 0,
                )
                session.add(shipment)

            orders_created += 1

        await session.commit()
        print(f"  ✓ {orders_created} orders created")

    print("\nSeed data created successfully!")
    print("Customers: 10")
    print("Orders: 50")
    print("Run: uvicorn src.server:app --reload --port 8001")


if __name__ == "__main__":
    asyncio.run(main())
