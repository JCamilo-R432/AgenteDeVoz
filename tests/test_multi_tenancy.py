"""
Integration tests for multi-tenancy: tenant isolation, API key auth,
and order/customer scoping.

Uses SQLite in-memory — no external DB required.
Run with:
    pytest tests/test_multi_tenancy.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio

# ── Path & env setup (must happen before any src imports) ──────────────────────
_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


# ── Session-scoped event loop ──────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create all tables once for the test session."""
    from database import engine, Base
    import models  # noqa — registers all models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Transactional session that rolls back after each test."""
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _uid() -> str:
    return str(uuid.uuid4())


async def _make_tenant(session, name: str, subdomain: str, plan: str = "basic") -> object:
    from models.tenant import Tenant
    from datetime import datetime, timezone

    t = Tenant(
        id=_uid(),
        name=name,
        subdomain=subdomain,
        plan=plan,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(t)
    await session.flush()
    await session.refresh(t)
    return t


async def _make_customer(session, tenant_id: str, phone: str, email: str = None) -> object:
    from models.customer import Customer
    from datetime import datetime, timezone

    c = Customer(
        id=_uid(),
        tenant_id=tenant_id,
        full_name="Test Customer",
        phone=phone,
        email=email,
        created_at=datetime.now(timezone.utc),
    )
    session.add(c)
    await session.flush()
    await session.refresh(c)
    return c


async def _make_order(session, tenant_id: str, customer_id: str, order_number: str) -> object:
    from models.order import Order, OrderStatus
    from datetime import datetime, timezone

    o = Order(
        id=_uid(),
        tenant_id=tenant_id,
        order_number=order_number,
        customer_id=customer_id,
        status=OrderStatus.pending.value,
        total_amount=Decimal("100000.00"),
        currency="COP",
        created_at=datetime.now(timezone.utc),
    )
    session.add(o)
    await session.flush()
    await session.refresh(o)
    return o


# ══════════════════════════════════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestTenantModel:
    """Unit tests for Tenant model helpers."""

    @pytest.mark.asyncio
    async def test_api_key_generated_on_create(self, db_session):
        tenant = await _make_tenant(db_session, "Acme", "acme-test")
        assert tenant.api_key.startswith("ak_")
        assert len(tenant.api_key) > 20

    @pytest.mark.asyncio
    async def test_regenerate_api_key(self, db_session):
        tenant = await _make_tenant(db_session, "Beta Corp", "beta-test")
        old_key = tenant.api_key
        new_key = tenant.regenerate_api_key()
        assert new_key != old_key
        assert new_key.startswith("ak_")

    @pytest.mark.asyncio
    async def test_plan_limits_basic(self, db_session):
        tenant = await _make_tenant(db_session, "Small Co", "small-test", plan="basic")
        limits = tenant.get_plan_limits()
        assert limits["requests_per_minute"] == 60
        assert limits["requests_per_day"] == 10_000

    @pytest.mark.asyncio
    async def test_plan_limits_enterprise(self, db_session):
        tenant = await _make_tenant(db_session, "Big Corp", "big-test", plan="enterprise")
        limits = tenant.get_plan_limits()
        assert limits["max_customers"] == -1  # unlimited


class TestTenantService:
    """Tests for TenantService business logic."""

    @pytest.mark.asyncio
    async def test_register_tenant(self, db_session):
        from services.tenant_service import TenantService
        from schemas.tenant import TenantRegisterRequest

        svc = TenantService(db_session)
        req = TenantRegisterRequest(name="NuevoCliente", subdomain="nuevo-cliente-1")
        tenant = await svc.register(req)

        assert tenant.id is not None
        assert tenant.subdomain == "nuevo-cliente-1"
        assert tenant.api_key.startswith("ak_")
        assert tenant.plan == "basic"
        assert tenant.is_active is True

    @pytest.mark.asyncio
    async def test_duplicate_subdomain_raises(self, db_session):
        from services.tenant_service import TenantService
        from schemas.tenant import TenantRegisterRequest

        svc = TenantService(db_session)
        req = TenantRegisterRequest(name="XX", subdomain="dupe-test-1")
        await svc.register(req)

        with pytest.raises(ValueError, match="already taken"):
            await svc.register(TenantRegisterRequest(name="YY", subdomain="dupe-test-1"))

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session):
        from services.tenant_service import TenantService
        from schemas.tenant import TenantRegisterRequest

        svc = TenantService(db_session)
        created = await svc.register(TenantRegisterRequest(name="FindMe", subdomain="find-me-1"))
        found = await svc.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id

    @pytest.mark.asyncio
    async def test_update_settings(self, db_session):
        from services.tenant_service import TenantService
        from schemas.tenant import TenantRegisterRequest

        svc = TenantService(db_session)
        tenant = await svc.register(TenantRegisterRequest(name="Branding", subdomain="brand-test-1"))
        updated = await svc.update_settings(tenant.id, {"agent_name": "Maria", "color": "#FF0000"})
        assert updated.settings["agent_name"] == "Maria"
        assert updated.settings["color"] == "#FF0000"

    @pytest.mark.asyncio
    async def test_get_usage(self, db_session):
        from services.tenant_service import TenantService
        from schemas.tenant import TenantRegisterRequest

        svc = TenantService(db_session)
        tenant = await svc.register(TenantRegisterRequest(name="Usage Co", subdomain="usage-test-1"))
        usage = await svc.get_usage(tenant.id)
        assert usage.tenant_id == tenant.id
        assert usage.usage["customers"] == 0
        assert usage.usage["orders"] == 0


class TestTenantIsolation:
    """Core multi-tenancy tests: data isolation between tenants."""

    @pytest.mark.asyncio
    async def test_same_phone_in_different_tenants_allowed(self, db_session):
        """The same phone can exist in tenant A and tenant B (isolation)."""
        tenant_a = await _make_tenant(db_session, "Tenant A", "tenant-a-iso-1")
        tenant_b = await _make_tenant(db_session, "Tenant B", "tenant-b-iso-1")

        phone = "+573001111111"
        customer_a = await _make_customer(db_session, tenant_a.id, phone=phone)
        customer_b = await _make_customer(db_session, tenant_b.id, phone=phone)

        # Both customers exist with same phone in different tenants
        assert customer_a.tenant_id == tenant_a.id
        assert customer_b.tenant_id == tenant_b.id
        assert customer_a.id != customer_b.id

    @pytest.mark.asyncio
    async def test_order_repo_scoped_by_tenant(self, db_session):
        """get_by_order_number with tenant_id should not return another tenant's order."""
        tenant_a = await _make_tenant(db_session, "Scope A", "scope-a-1")
        tenant_b = await _make_tenant(db_session, "Scope B", "scope-b-1")

        # Create customer for tenant A
        cust_a = await _make_customer(db_session, tenant_a.id, phone="+573002222222")
        order_a = await _make_order(db_session, tenant_a.id, cust_a.id, "ECO-2026-901001")

        from repositories.order_repository import OrderRepository

        repo = OrderRepository(db_session)

        # Tenant A can find the order
        found = await repo.get_by_order_number("ECO-2026-901001", tenant_id=tenant_a.id)
        assert found is not None
        assert found.order_number == "ECO-2026-901001"

        # Tenant B cannot find tenant A's order
        not_found = await repo.get_by_order_number("ECO-2026-901001", tenant_id=tenant_b.id)
        assert not_found is None

    @pytest.mark.asyncio
    async def test_order_repo_no_tenant_returns_all(self, db_session):
        """Without tenant_id (admin mode), get_by_order_number returns any order."""
        tenant_c = await _make_tenant(db_session, "Admin View", "admin-view-1")
        cust_c = await _make_customer(db_session, tenant_c.id, phone="+573003333333")
        await _make_order(db_session, tenant_c.id, cust_c.id, "ECO-2026-902001")

        from repositories.order_repository import OrderRepository

        repo = OrderRepository(db_session)
        found = await repo.get_by_order_number("ECO-2026-902001", tenant_id=None)
        assert found is not None

    @pytest.mark.asyncio
    async def test_list_orders_scoped_by_tenant(self, db_session):
        """list_orders with tenant_id should only return that tenant's orders."""
        tenant_x = await _make_tenant(db_session, "List X", "list-x-1")
        tenant_y = await _make_tenant(db_session, "List Y", "list-y-1")

        cust_x = await _make_customer(db_session, tenant_x.id, phone="+573004444444")
        cust_y = await _make_customer(db_session, tenant_y.id, phone="+573005555555")

        await _make_order(db_session, tenant_x.id, cust_x.id, "ECO-2026-903001")
        await _make_order(db_session, tenant_x.id, cust_x.id, "ECO-2026-903002")
        await _make_order(db_session, tenant_y.id, cust_y.id, "ECO-2026-903003")

        from repositories.order_repository import OrderRepository

        repo = OrderRepository(db_session)

        orders_x, total_x = await repo.list_orders(tenant_id=tenant_x.id)
        assert total_x == 2
        for o in orders_x:
            assert o.tenant_id == tenant_x.id

        orders_y, total_y = await repo.list_orders(tenant_id=tenant_y.id)
        assert total_y == 1

    @pytest.mark.asyncio
    async def test_order_service_stamps_tenant_id(self, db_session):
        """OrderService.create_order should stamp tenant_id on new orders."""
        from services.order_service import OrderService
        from schemas.order import CreateOrderRequest, OrderItemCreate

        tenant = await _make_tenant(db_session, "Stamp Test", "stamp-test-1")
        cust = await _make_customer(db_session, tenant.id, phone="+573006666666")

        svc = OrderService(db_session, tenant_id=tenant.id)
        req = CreateOrderRequest(
            customer_id=cust.id,
            items=[OrderItemCreate(product_name="Test Product", quantity=1, unit_price=Decimal("50000"))],
        )
        order = await svc.create_order(req)

        assert order.tenant_id == tenant.id

    @pytest.mark.asyncio
    async def test_usage_counts_per_tenant(self, db_session):
        """TenantService.get_usage returns counts scoped to tenant."""
        from services.tenant_service import TenantService
        from schemas.tenant import TenantRegisterRequest

        svc = TenantService(db_session)
        tenant = await svc.register(TenantRegisterRequest(name="Usage Count", subdomain="usage-count-1"))

        cust = await _make_customer(db_session, tenant.id, phone="+573007777777")
        await _make_order(db_session, tenant.id, cust.id, "ECO-2026-904001")
        await _make_order(db_session, tenant.id, cust.id, "ECO-2026-904002")

        usage = await svc.get_usage(tenant.id)
        assert usage.usage["customers"] == 1
        assert usage.usage["orders"] == 2
