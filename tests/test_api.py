"""
API-level tests using httpx AsyncClient + pytest-asyncio.
Tests the FastAPI order management endpoints via HTTP.
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

# ── App & client fixtures ──────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_app():
    """Build a minimal FastAPI app with only the orders v1 router mounted."""
    from fastapi import FastAPI
    from api.v1.router import router as orders_v1_router
    from database import engine, Base
    import models  # noqa: F401

    app = FastAPI()
    app.include_router(orders_v1_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return app


@pytest_asyncio.fixture(scope="session")
async def client(test_app):
    """httpx AsyncClient bound to the test app."""
    import httpx
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as ac:
        yield ac


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client):
    """The /health endpoint should return status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_get_order_returns_404(client):
    """Requesting a non-existent order number should return HTTP 404."""
    response = await client.get("/api/v1/orders/ECO-9999-999999")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_get_order_by_phone_unknown_returns_404(client):
    """Requesting orders for an unknown phone should return 404."""
    response = await client.get("/api/v1/orders/customer/phone/9990000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_order_requires_auth(client):
    """POST /orders without JWT should return HTTP 401."""
    response = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": str(uuid.uuid4()),
            "items": [
                {
                    "product_name": "Test",
                    "quantity": 1,
                    "unit_price": "50000",
                }
            ],
            "currency": "COP",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_orders_requires_auth(client):
    """GET /orders (admin list) without JWT should return HTTP 401."""
    response = await client.get("/api/v1/orders")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_analytics_requires_auth(client):
    """GET /analytics/orders without JWT should return HTTP 401."""
    response = await client.get("/api/v1/analytics/orders")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_tracking_not_found(client):
    """Querying a non-existent tracking number should return 404."""
    response = await client.get("/api/v1/orders/tracking/XXXX0000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_order_by_phone_empty_known_customer(client):
    """A known customer with no orders should return empty orders list."""
    from database import AsyncSessionLocal
    from models.customer import Customer

    # Insert a customer directly
    async with AsyncSessionLocal() as session:
        customer = Customer(
            id=str(uuid.uuid4()),
            phone="3001112222",
            full_name="Prueba Sin Pedidos",
            email=None,
            created_at=datetime.now(timezone.utc),
        )
        session.add(customer)
        await session.commit()

    response = await client.get("/api/v1/orders/customer/phone/3001112222")
    assert response.status_code == 200
    body = response.json()
    assert body["total_orders"] == 0
    assert body["orders"] == []
