"""
Unit tests for the OrderService and OrderRepository.
Uses SQLite in-memory via aiosqlite.
"""

import re
import sys
import os
import uuid
import asyncio
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
async def db_engine():
    """Create all tables in an in-memory SQLite database."""
    # Import after path is set
    from database import engine, Base
    import models  # noqa: F401 — registers all models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Provide a transactional session that rolls back after each test."""
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def sample_customer(db_session):
    """Insert and return a minimal Customer for tests."""
    from models.customer import Customer
    customer = Customer(
        id=str(uuid.uuid4()),
        phone="3161234567",
        full_name="Test User",
        email="test@example.com",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(customer)
    await db_session.flush()
    return customer


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_order_by_number_not_found(db_session):
    """Querying a non-existent order number should return None."""
    from services.order_service import OrderService

    service = OrderService(db_session)
    result = await service.get_by_order_number("ECO-9999-999999")
    assert result is None


@pytest.mark.asyncio
async def test_create_order_generates_number(db_session, sample_customer):
    """Creating an order should assign a valid ECO-YYYY-NNNNNN order number."""
    from services.order_service import OrderService
    from schemas.order import CreateOrderRequest, OrderItemCreate

    service = OrderService(db_session)
    request = CreateOrderRequest(
        customer_id=sample_customer.id,
        items=[
            OrderItemCreate(
                product_name="Test Product",
                quantity=1,
                unit_price=Decimal("50000"),
            )
        ],
        currency="COP",
    )
    order = await service.create_order(request)
    assert order is not None
    assert re.match(r"ECO-\d{4}-\d{6}", order.order_number)


@pytest.mark.asyncio
async def test_order_number_format(db_session, sample_customer):
    """Order number must strictly match ECO-YYYY-NNNNNN format."""
    from services.order_service import OrderService
    from schemas.order import CreateOrderRequest, OrderItemCreate

    service = OrderService(db_session)
    request = CreateOrderRequest(
        customer_id=sample_customer.id,
        items=[
            OrderItemCreate(
                product_name="Formato Test",
                quantity=2,
                unit_price=Decimal("75000"),
            )
        ],
        currency="COP",
    )
    order = await service.create_order(request)
    pattern = r"^ECO-\d{4}-\d{6}$"
    assert re.match(pattern, order.order_number), (
        f"Order number '{order.order_number}' does not match pattern {pattern}"
    )


@pytest.mark.asyncio
async def test_update_status_creates_history(db_session, sample_customer):
    """Updating an order status should create a history record."""
    from services.order_service import OrderService
    from schemas.order import CreateOrderRequest, OrderItemCreate
    from repositories.order_repository import OrderRepository

    service = OrderService(db_session)
    repo = OrderRepository(db_session)

    request = CreateOrderRequest(
        customer_id=sample_customer.id,
        items=[
            OrderItemCreate(
                product_name="History Test Product",
                quantity=1,
                unit_price=Decimal("100000"),
            )
        ],
        currency="COP",
    )
    order = await service.create_order(request)

    # Update status to confirmed
    updated = await service.update_status(
        order_id=order.id,
        status="confirmed",
        notes="Payment received",
        changed_by="test_admin",
    )
    assert updated.status == "confirmed"

    # Reload order with history
    reloaded = await repo.get_by_id(order.id)
    assert reloaded is not None
    # Should have at least 2 history entries: pending + confirmed
    assert len(reloaded.status_history) >= 2
    statuses = [h.new_status for h in reloaded.status_history]
    assert "confirmed" in statuses


@pytest.mark.asyncio
async def test_get_orders_by_phone_empty(db_session):
    """Querying orders for an unknown phone number should return an empty list."""
    from services.order_service import OrderService

    service = OrderService(db_session)
    result = await service.get_by_customer_phone("9990000000")
    assert result == []


@pytest.mark.asyncio
async def test_create_order_calculates_total(db_session, sample_customer):
    """Total amount should equal sum of (unit_price * quantity) across all items."""
    from services.order_service import OrderService
    from schemas.order import CreateOrderRequest, OrderItemCreate

    service = OrderService(db_session)
    request = CreateOrderRequest(
        customer_id=sample_customer.id,
        items=[
            OrderItemCreate(product_name="Item A", quantity=2, unit_price=Decimal("50000")),
            OrderItemCreate(product_name="Item B", quantity=1, unit_price=Decimal("30000")),
        ],
        currency="COP",
    )
    order = await service.create_order(request)
    expected_total = Decimal("130000")
    assert order.total_amount == expected_total


@pytest.mark.asyncio
async def test_cancel_order(db_session, sample_customer):
    """Cancelling an order should set its status to 'cancelled'."""
    from services.order_service import OrderService
    from schemas.order import CreateOrderRequest, OrderItemCreate

    service = OrderService(db_session)
    request = CreateOrderRequest(
        customer_id=sample_customer.id,
        items=[
            OrderItemCreate(
                product_name="Cancel Me",
                quantity=1,
                unit_price=Decimal("60000"),
            )
        ],
        currency="COP",
    )
    order = await service.create_order(request)
    cancelled = await service.cancel_order(
        order_id=order.id, reason="Test cancellation"
    )
    assert cancelled.status == "cancelled"
    assert cancelled.cancellation_reason == "Test cancellation"
