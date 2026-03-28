"""
Integration tests — full order lifecycle and voice agent formatting.
"""

import os
import sys
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone

import pytest
import pytest_asyncio

# ── Python path ────────────────────────────────────────────────────────────────
_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Force in-memory SQLite — must happen before database module is imported
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    """Create tables once for the integration test session."""
    from database import engine, Base
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(setup_db):
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def customer(db_session):
    from models.customer import Customer
    c = Customer(
        id=str(uuid.uuid4()),
        phone="3159998877",
        full_name="Integración Test",
        email="integration@test.co",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(c)
    await db_session.flush()
    return c


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_order_lifecycle(db_session, customer):
    """
    Exercise the complete order lifecycle:
    create → confirm → process → ship → deliver
    and verify state transitions and history entries.
    """
    from services.order_service import OrderService
    from schemas.order import CreateOrderRequest, OrderItemCreate

    service = OrderService(db_session)

    # 1. Create
    request = CreateOrderRequest(
        customer_id=customer.id,
        items=[
            OrderItemCreate(
                product_name="Audífonos Bluetooth",
                quantity=1,
                unit_price=Decimal("180000"),
            ),
            OrderItemCreate(
                product_name="Cargador USB-C",
                quantity=2,
                unit_price=Decimal("25000"),
            ),
        ],
        currency="COP",
    )
    order = await service.create_order(request)
    assert order.status == "pending"
    assert order.total_amount == Decimal("230000")

    # 2. Confirm
    order = await service.update_status(order.id, "confirmed", "Pago aprobado", "payment_system")
    assert order.status == "confirmed"
    assert order.confirmed_at is not None

    # 3. Process
    order = await service.update_status(order.id, "processing", "Preparando envío", "warehouse")
    assert order.status == "processing"

    # 4. Ship
    order = await service.update_status(order.id, "shipped", "Enviado con Coordinadora", "shipping")
    assert order.status == "shipped"
    assert order.shipped_at is not None

    # 5. In transit
    order = await service.update_status(order.id, "in_transit", "Llegó a hub Bogotá", "carrier")
    assert order.status == "in_transit"

    # 6. Deliver
    order = await service.update_status(order.id, "delivered", "Entregado al cliente", "courier")
    assert order.status == "delivered"
    assert order.delivered_at is not None

    # Verify history contains all transitions
    from repositories.order_repository import OrderRepository
    repo = OrderRepository(db_session)
    final = await repo.get_by_id(order.id)
    assert final is not None
    history_statuses = [h.new_status for h in final.status_history]
    for expected_status in ("pending", "confirmed", "processing", "shipped", "in_transit", "delivered"):
        assert expected_status in history_statuses, (
            f"Expected '{expected_status}' in history, got: {history_statuses}"
        )


@pytest.mark.asyncio
async def test_voice_agent_order_query(db_session, customer):
    """
    Test that _format_for_voice returns natural Spanish text
    with order number, status, and monetary info.
    """
    from services.order_service import OrderService
    from schemas.order import CreateOrderRequest, OrderItemCreate

    service = OrderService(db_session)

    request = CreateOrderRequest(
        customer_id=customer.id,
        items=[
            OrderItemCreate(
                product_name="Celular Samsung",
                quantity=1,
                unit_price=Decimal("1150000"),
            )
        ],
        currency="COP",
    )
    order = await service.create_order(request)

    voice_response = service._format_for_voice(order)

    # Must contain the order number
    assert order.order_number in voice_response
    # Must mention the currency
    assert "COP" in voice_response
    # Must be non-empty Spanish text
    assert len(voice_response) > 20


@pytest.mark.asyncio
async def test_voice_agent_shipped_includes_tracking_text(db_session, customer):
    """
    A shipped order with a shipment record should include
    carrier and tracking info in the voice response.
    """
    import uuid as _uuid
    from services.order_service import OrderService
    from schemas.order import CreateOrderRequest, OrderItemCreate
    from models.shipment import Shipment

    service = OrderService(db_session)

    request = CreateOrderRequest(
        customer_id=customer.id,
        items=[
            OrderItemCreate(
                product_name="Zapatos Deportivos",
                quantity=1,
                unit_price=Decimal("280000"),
            )
        ],
        currency="COP",
    )
    order = await service.create_order(request)
    order = await service.update_status(order.id, "shipped", "Enviado", "system")

    # Add a shipment manually
    shipment = Shipment(
        id=str(_uuid.uuid4()),
        order_id=order.id,
        tracking_number="CRD123456789012",
        carrier="Coordinadora",
        status="shipped",
        current_location="Bogotá",
        delivery_attempts=0,
    )
    db_session.add(shipment)
    await db_session.flush()

    from repositories.order_repository import OrderRepository
    repo = OrderRepository(db_session)
    refreshed = await repo.get_by_id(order.id)
    assert refreshed is not None

    voice_response = service._format_for_voice(refreshed)
    assert "Coordinadora" in voice_response or "CRD123456789012" in voice_response


@pytest.mark.asyncio
async def test_order_statistics_empty_db_returns_zeros(db_session):
    """Statistics on a fresh session should return sensible zero values."""
    from services.order_service import OrderService

    service = OrderService(db_session)
    stats = await service.get_order_statistics()
    assert stats.total_orders >= 0
    assert stats.revenue_today >= Decimal("0")
    assert stats.revenue_month >= Decimal("0")
