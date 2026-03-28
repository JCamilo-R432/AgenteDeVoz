from __future__ import annotations
from typing import Dict, List, Any
"""
Admin service — platform-wide metrics and tenant management.
Used by the admin dashboard endpoints.
"""


import time
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.tenant import Tenant
from models.customer import Customer
from models.order import Order
from models.auth import OTPCode, AuthAuditLog


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    # ── Platform overview ──────────────────────────────────────────────────────

    async def get_platform_stats(self) -> Dict[str, Any]:
        """Aggregate stats across ALL tenants."""
        stats: Dict[str, Any] = {}

        # Tenants
        r = await self._db.execute(select(func.count()).select_from(Tenant))
        stats["tenants_total"] = r.scalar_one_or_none() or 0

        r = await self._db.execute(
            select(func.count()).where(Tenant.is_active.is_(True))
        )
        stats["tenants_active"] = r.scalar_one_or_none() or 0

        # Plan breakdown
        plan_rows = await self._db.execute(
            select(Tenant.plan, func.count().label("cnt")).group_by(Tenant.plan)
        )
        stats["tenants_by_plan"] = {row.plan: row.cnt for row in plan_rows}

        # Customers
        r = await self._db.execute(select(func.count()).select_from(Customer))
        stats["customers_total"] = r.scalar_one_or_none() or 0

        # Orders
        r = await self._db.execute(select(func.count()).select_from(Order))
        stats["orders_total"] = r.scalar_one_or_none() or 0

        status_rows = await self._db.execute(
            select(Order.status, func.count().label("cnt")).group_by(Order.status)
        )
        stats["orders_by_status"] = {row.status: row.cnt for row in status_rows}

        # OTP activity (last 30 days)
        since_30d = datetime.now(timezone.utc) - timedelta(days=30)
        r = await self._db.execute(
            select(func.count()).where(OTPCode.created_at >= since_30d)
        )
        stats["otp_sends_30d"] = r.scalar_one_or_none() or 0

        # Auth audit (last 24h)
        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        r = await self._db.execute(
            select(func.count()).where(AuthAuditLog.created_at >= since_24h)
        )
        stats["auth_events_24h"] = r.scalar_one_or_none() or 0

        # DB ping
        t0 = time.monotonic()
        await self._db.execute(text("SELECT 1"))
        stats["db_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)

        stats["generated_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    # ── Tenant list ────────────────────────────────────────────────────────────

    async def list_tenants(
        self,
        page: int = 1,
        page_size: int = 20,
        plan: Optional[str] = None,
        active_only: bool = False,
    ) -> Dict[str, Any]:
        query = select(Tenant).order_by(Tenant.created_at.desc())

        if plan:
            query = query.where(Tenant.plan == plan)
        if active_only:
            query = query.where(Tenant.is_active.is_(True))

        # Count total - forma compatible con async
        count_query = select(func.count(Tenant.id))
        if plan:
            count_query = count_query.where(Tenant.plan == plan)
        if active_only:
            count_query = count_query.where(Tenant.is_active.is_(True))
        
        total_r = await self._db.execute(count_query)
        total = total_r.scalar_one_or_none() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        rows = await self._db.execute(query)
        tenants = rows.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
            "items": [self._tenant_summary(t) for t in tenants],
        }

    # ── Per-tenant details ─────────────────────────────────────────────────────

    async def get_tenant_detail(self, tenant_id: str) -> Dict[str, Any]:
        result = await self._db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if tenant is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Orders count
        r = await self._db.execute(
            select(func.count()).where(Order.tenant_id == tenant_id)
        )
        orders_count = r.scalar_one_or_none() or 0

        # Customers count
        r = await self._db.execute(
            select(func.count()).where(Customer.tenant_id == tenant_id)
        )
        customers_count = r.scalar_one_or_none() or 0

        # OTP sends (30d)
        since_30d = datetime.now(timezone.utc) - timedelta(days=30)
        r = await self._db.execute(
            select(func.count()).where(
                OTPCode.tenant_id == tenant_id,
                OTPCode.created_at >= since_30d,
            )
        )
        otp_30d = r.scalar_one_or_none() or 0

        return {
            **self._tenant_summary(tenant),
            "orders_total": orders_count,
            "customers_total": customers_count,
            "otp_sends_30d": otp_30d,
            "settings": tenant.settings,
        }

    # ── Recent auth events ─────────────────────────────────────────────────────

    async def recent_auth_events(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        query = (
            select(AuthAuditLog)
            .order_by(AuthAuditLog.created_at.desc())
            .limit(limit)
        )
        if tenant_id:
            query = query.where(AuthAuditLog.tenant_id == tenant_id)

        rows = await self._db.execute(query)
        events = rows.scalars().all()

        return [
            {
                "id": str(e.id),
                "tenant_id": e.tenant_id,
                "phone": e.phone,
                "email": e.email,
                "action": e.action,
                "status": e.status,
                "ip_address": e.ip_address,
                "detail": e.detail,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _tenant_summary(t: Tenant) -> dict:
        return {
            "id": t.id,
            "name": t.name,
            "subdomain": t.subdomain,
            "plan": t.plan,
            "is_active": t.is_active,
            "created_at": t.created_at.isoformat(),
        }
