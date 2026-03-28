from __future__ import annotations
from typing import Dict, List, Optional, Any
"""
Seed script — populates the database with 2 realistic tenants,
20 customers each, and ~55 orders per tenant (random statuses,
shipment records, and status history).

Usage:
    # From project root:
    python src/scripts/seed_orders.py

    # Or with explicit DB URL:
    DATABASE_URL=postgresql://user:pass@localhost/econify python src/scripts/seed_orders.py
"""


import asyncio
import os
import random
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# ── Bootstrap Python path ──────────────────────────────────────────────────────
_src = Path(__file__).parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/agentevoz",
)

# ── Imports (after path setup) ──────────────────────────────────────────────────

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import AsyncSessionLocal, engine, Base
import models  # noqa — registers all ORM models with metadata

from models.tenant import Tenant
from models.customer import Customer
from models.order import Order, OrderItem, OrderStatusHistory, OrderStatus
from models.shipment import Shipment

# ── Colombian seed data ────────────────────────────────────────────────────────

TENANTS_DATA = [
    {
        "name": "TiendaEco Colombia",
        "subdomain": "tiendaeco",
        "plan": "pro",
        "settings": {
            "brand_name": "TiendaEco",
            "brand_colors": {"primary": "#2E7D32", "secondary": "#A5D6A7"},
            "agent_name": "Ana",
            "welcome_message": "Hola, soy Ana de TiendaEco. ¿En qué te puedo ayudar?",
            "company_info": {
                "city": "Bogotá",
                "email": "soporte@tiendaeco.co",
                "phone": "+5713001234",
            },
        },
    },
    {
        "name": "ModaRápida SAS",
        "subdomain": "modarapida",
        "plan": "basic",
        "settings": {
            "brand_name": "ModaRápida",
            "brand_colors": {"primary": "#AD1457", "secondary": "#F48FB1"},
            "agent_name": "Carlos",
            "welcome_message": "Bienvenido a ModaRápida. Soy Carlos, ¿cómo te ayudo?",
            "company_info": {
                "city": "Medellín",
                "email": "atencion@modarapida.co",
                "phone": "+5742601234",
            },
        },
    },
]

FIRST_NAMES = [
    "Valentina", "Santiago", "Camila", "Sebastián", "Isabella",
    "Mateo", "Sofia", "Daniel", "Daniela", "Andrés",
    "Natalia", "David", "Gabriela", "Julián", "Laura",
    "Carlos", "María", "Jorge", "Paola", "Felipe",
]

LAST_NAMES = [
    "García", "Rodríguez", "Martínez", "López", "González",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Flores",
    "Rivera", "Gómez", "Díaz", "Reyes", "Morales",
    "Cruz", "Herrera", "Medina", "Castro", "Vargas",
]

CITIES = [
    "Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena",
    "Bucaramanga", "Pereira", "Manizales", "Ibagué", "Pasto",
]

CARRIERS = [
    "Coordinadora", "Servientrega", "TCC", "Envia", "Deprisa",
    "InterRapidísimo", "4-72 Servicios Postales",
]

PRODUCTS = [
    # Electronics
    ("Samsung Galaxy A54 128GB", "ELEC-001", Decimal("1_299_000")),
    ("Audífonos Bluetooth JBL Tune 510BT", "ELEC-002", Decimal("189_000")),
    ("Laptop Lenovo IdeaPad 3 14\" 8GB/256GB", "ELEC-003", Decimal("2_499_000")),
    ("Cargador Inalámbrico 15W", "ELEC-004", Decimal("89_000")),
    ("Smartwatch Xiaomi Band 7", "ELEC-005", Decimal("299_000")),
    # Clothing
    ("Camiseta Polo Hombre Talla M", "ROPA-001", Decimal("79_000")),
    ("Jean Slim Mujer Talla 28", "ROPA-002", Decimal("149_000")),
    ("Chaqueta Impermeable Unisex", "ROPA-003", Decimal("279_000")),
    ("Tenis Deportivos Adidas Cloudfoam", "ROPA-004", Decimal("329_000")),
    ("Vestido Casual Floral Talla S", "ROPA-005", Decimal("129_000")),
    # Home
    ("Olla a Presión Imusa 4.5L", "HOG-001", Decimal("199_000")),
    ("Juego de Sábanas 200 hilos Queen", "HOG-002", Decimal("119_000")),
    ("Licuadora Oster 600W 6 velocidades", "HOG-003", Decimal("159_000")),
    ("Organizador Closet 6 cubos", "HOG-004", Decimal("89_000")),
    ("Lámpara LED Escritorio USB", "HOG-005", Decimal("59_000")),
    # Food & Gourmet
    ("Café Juan Valdez Premium 500g", "CAFE-001", Decimal("39_000")),
    ("Caja Aromáticas Colección Colombia 30 sobres", "CAFE-002", Decimal("25_000")),
    ("Chocolate Santander 70% Cacao 100g x6", "GOUR-001", Decimal("48_000")),
]

STATUSES_WEIGHTED = [
    ("delivered", 35),
    ("shipped", 20),
    ("in_transit", 15),
    ("processing", 10),
    ("confirmed", 8),
    ("pending", 7),
    ("cancelled", 4),
    ("refunded", 1),
]

_STATUS_CHOICES, _STATUS_WEIGHTS = zip(*STATUSES_WEIGHTED)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid.uuid4())


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


def _days_from_now(n: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=n)


def _phone(tenant_idx: int, customer_idx: int) -> str:
    """Generate unique Colombian cellphone: +573XXXXXXXXX"""
    base = 3_100_000_000 + (tenant_idx * 1_000) + customer_idx
    return f"+57{base}"


def _order_number(year: int, seq: int) -> str:
    return f"ECO-{year}-{seq:06d}"


def _build_status_history(
    order_id: str,
    final_status: str,
    created_at: datetime,
) -> List[OrderStatusHistory]:
    """Build the status transition chain leading to final_status."""
    pipeline = [
        "pending", "confirmed", "processing", "shipped",
        "in_transit", "out_for_delivery", "delivered",
    ]
    if final_status == "cancelled":
        pipeline = ["pending", "cancelled"]
    elif final_status == "refunded":
        pipeline = ["pending", "confirmed", "processing", "shipped", "delivered", "refunded"]

    history = []
    current_time = created_at
    prev_status = None
    for s in pipeline:
        current_time += timedelta(hours=random.randint(2, 24))
        history.append(
            OrderStatusHistory(
                id=_uuid(),
                order_id=order_id,
                previous_status=prev_status,
                new_status=s,
                changed_at=current_time,
                changed_by="system",
                notes=None,
            )
        )
        prev_status = s
        if s == final_status:
            break
    return history


# ── Seed logic ─────────────────────────────────────────────────────────────────

async def create_tenant(session: AsyncSession, data: dict, api_key: str) -> Tenant:
    existing = (
        await session.execute(
            select(Tenant).where(Tenant.subdomain == data["subdomain"])
        )
    ).scalar_one_or_none()

    if existing:
        print(f"  [skip] Tenant '{data['subdomain']}' already exists")
        return existing

    tenant = Tenant(
        id=_uuid(),
        name=data["name"],
        subdomain=data["subdomain"],
        api_key=api_key,
        plan=data["plan"],
        is_active=True,
        created_at=_days_ago(90),
        settings=data.get("settings", {}),
    )
    session.add(tenant)
    await session.flush()
    print(f"  [+] Tenant: {tenant.name} | subdomain={tenant.subdomain} | api_key={tenant.api_key}")
    return tenant


async def create_customers(
    session: AsyncSession, tenant: Tenant, tenant_idx: int, count: int = 20
) -> List[Customer]:
    customers = []
    for i in range(count):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        phone = _phone(tenant_idx, i)
        email = f"{first.lower()}.{last.lower()}{i}@gmail.com"

        customer = Customer(
            id=_uuid(),
            tenant_id=tenant.id,
            full_name=name,
            phone=phone,
            email=email,
            created_at=_days_ago(random.randint(10, 365)),
            metadata_json={
                "city": random.choice(CITIES),
                "source": random.choice(["web", "whatsapp", "call"]),
            },
        )
        session.add(customer)
        customers.append(customer)

    await session.flush()
    print(f"  [+] {len(customers)} customers created for tenant {tenant.subdomain}")
    return customers


async def create_orders_for_tenant(
    session: AsyncSession,
    tenant: Tenant,
    customers: List[Customer],
    seq_start: int,
    count: int = 55,
) -> int:
    year = 2026
    orders_created = 0
    seq = seq_start

    for customer in customers:
        # 2-3 orders per customer
        num_orders = random.randint(2, 3)
        for _ in range(num_orders):
            if orders_created >= count:
                break

            seq += 1
            status_val = random.choices(_STATUS_CHOICES, weights=_STATUS_WEIGHTS, k=1)[0]
            created_at = _days_ago(random.randint(1, 120))
            order_id = _uuid()
            order_number = _order_number(year, seq)

            # Pick 1-3 random products
            chosen_products = random.sample(PRODUCTS, k=random.randint(1, 3))
            items = []
            total = Decimal("0")
            for prod_name, prod_sku, unit_price in chosen_products:
                qty = random.randint(1, 2)
                subtotal = unit_price * qty
                total += subtotal
                items.append(
                    OrderItem(
                        id=_uuid(),
                        order_id=order_id,
                        product_name=prod_name,
                        product_sku=prod_sku,
                        quantity=qty,
                        unit_price=unit_price,
                        subtotal=subtotal,
                    )
                )

            # Set timestamp fields based on status
            confirmed_at = shipped_at = delivered_at = estimated_delivery = None
            if status_val not in ("pending", "cancelled"):
                confirmed_at = created_at + timedelta(hours=random.randint(1, 12))
            if status_val in ("shipped", "in_transit", "out_for_delivery", "delivered", "refunded"):
                shipped_at = confirmed_at + timedelta(hours=random.randint(12, 48))
            if status_val == "delivered":
                delivered_at = shipped_at + timedelta(days=random.randint(1, 5))
                estimated_delivery = delivered_at - timedelta(hours=random.randint(-5, 5))
            elif shipped_at:
                estimated_delivery = shipped_at + timedelta(days=random.randint(2, 5))

            order = Order(
                id=order_id,
                tenant_id=tenant.id,
                order_number=order_number,
                customer_id=customer.id,
                status=status_val,
                total_amount=total,
                currency="COP",
                created_at=created_at,
                confirmed_at=confirmed_at,
                shipped_at=shipped_at,
                delivered_at=delivered_at,
                estimated_delivery=estimated_delivery,
                actual_delivery=delivered_at,
            )
            session.add(order)
            for item in items:
                session.add(item)

            # Status history
            for h in _build_status_history(order_id, status_val, created_at):
                session.add(h)

            # Shipment for shipped+ statuses
            if status_val in ("shipped", "in_transit", "out_for_delivery", "delivered", "refunded"):
                carrier = random.choice(CARRIERS)
                tracking = f"{carrier[:3].upper()}{random.randint(10_000_000, 99_999_999)}"
                shipment = Shipment(
                    id=_uuid(),
                    order_id=order_id,
                    tracking_number=tracking,
                    carrier=carrier,
                    service_type="Envío estándar",
                    current_location=random.choice(CITIES),
                    status=status_val if status_val != "refunded" else "delivered",
                    estimated_delivery=estimated_delivery,
                    delivered_at=delivered_at,
                    delivery_attempts=1 if status_val == "delivered" else 0,
                    status_history=[
                        {"status": "picked_up", "timestamp": str(shipped_at), "location": "Centro de Acopio"},
                        {"status": "in_transit", "timestamp": str(shipped_at + timedelta(hours=24)), "location": random.choice(CITIES)},
                    ],
                )
                session.add(shipment)

            orders_created += 1

        if orders_created >= count:
            break

    await session.flush()
    print(f"  [+] {orders_created} orders created for tenant {tenant.subdomain}")
    return seq


async def seed() -> None:
    print("=" * 60)
    print("Seeding database with tenants, customers, and orders...")
    print("=" * 60)

    # Hard-coded API keys so they're predictable in dev
    api_keys = [
        "ak_dev_tiendaeco_" + "a" * 16,   # Replace with real secrets in staging
        "ak_dev_modarapida_" + "b" * 15,
    ]

    async with AsyncSessionLocal() as session:
        seq = 1000  # Starting sequence for order numbers

        for idx, (tenant_data, api_key) in enumerate(zip(TENANTS_DATA, api_keys)):
            print(f"\n--- Tenant {idx + 1}: {tenant_data['name']} ---")
            tenant = await create_tenant(session, tenant_data, api_key)
            customers = await create_customers(session, tenant, idx)
            seq = await create_orders_for_tenant(session, tenant, customers, seq_start=seq)

        await session.commit()

    print("\n" + "=" * 60)
    print("Seed complete!")
    print("\nTenant API keys for testing:")
    for td, ak in zip(TENANTS_DATA, api_keys):
        print(f"  {td['subdomain']:20s}  X-API-Key: {ak}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
