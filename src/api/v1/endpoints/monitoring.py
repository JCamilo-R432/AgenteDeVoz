from __future__ import annotations
from typing import Dict, List, Any
"""
Monitoring endpoints — Module 7.

GET  /api/v1/monitoring/health          — liveness (public)
GET  /api/v1/monitoring/health/full     — full health report (public)
GET  /api/v1/monitoring/metrics         — Prometheus-format metrics (public)
GET  /api/v1/monitoring/stats           — API usage stats per tenant (requires API key)
POST /api/v1/monitoring/test-alert      — fire a test alert (admin)
"""


import os
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from monitoring.health_checks import health_checker
from monitoring.metrics import registry

router = APIRouter(tags=["monitoring"])

_START_TIME = time.time()


# ── Liveness ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def liveness() -> dict:
    """Lightweight liveness probe — always returns 200 if process is alive."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "version": os.getenv("APP_VERSION", "2.0.0"),
    }


# ── Full health report ─────────────────────────────────────────────────────────

@router.get("/health/full")
async def full_health() -> Response:
    """
    Detailed health report for all components.
    Returns HTTP 200 (healthy), 207 (degraded), or 503 (unhealthy).
    """
    import json
    report = await health_checker.run_all()
    status_code = (
        200 if report.status == "healthy"
        else 503 if report.status == "unhealthy"
        else 207
    )
    return Response(
        content=json.dumps(report.to_dict()),
        status_code=status_code,
        media_type="application/json",
    )


# ── Prometheus metrics ─────────────────────────────────────────────────────────

@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Expose application metrics in Prometheus text format."""
    return Response(
        content=registry.to_prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ── Tenant usage stats ─────────────────────────────────────────────────────────

@router.get("/stats")
async def usage_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return usage statistics for the authenticated tenant.
    Requires a valid X-API-Key header.
    """
    tenant_id: Optional[str] = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="X-API-Key required")

    stats: Dict[str, Any] = {"tenant_id": tenant_id}

    try:
        # Orders count
        from models.order import Order
        orders_result = await db.execute(
            select(func.count()).where(Order.tenant_id == tenant_id)
        )
        stats["orders_total"] = orders_result.scalar_one_or_none() or 0

        # Customers count
        from models.customer import Customer
        customers_result = await db.execute(
            select(func.count()).where(Customer.tenant_id == tenant_id)
        )
        stats["customers_total"] = customers_result.scalar_one_or_none() or 0

        # OTP usage (last 30 days)
        from models.auth import OTPCode
        from datetime import datetime, timezone, timedelta
        since = datetime.now(timezone.utc) - timedelta(days=30)
        otp_result = await db.execute(
            select(func.count()).where(
                OTPCode.tenant_id == tenant_id,
                OTPCode.created_at >= since,
            )
        )
        stats["otp_sends_last_30d"] = otp_result.scalar_one_or_none() or 0

        # DB ping latency
        t0 = time.monotonic()
        await db.execute(text("SELECT 1"))
        stats["db_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)

    except Exception as exc:
        stats["error"] = str(exc)

    stats["uptime_seconds"] = round(time.time() - _START_TIME, 1)
    return stats


# ── Test alert ─────────────────────────────────────────────────────────────────

@router.post("/test-alert")
async def test_alert(request: Request) -> dict:
    """
    Fire a test alert to verify channel configuration.
    Admin-only — requires ADMIN_SECRET header.
    """
    secret = request.headers.get("X-Admin-Secret", "")
    expected = os.getenv("ADMIN_SECRET", "")
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Admin access required")

    from utils.alerts import alert_manager, AlertLevel
    await alert_manager.send(
        title="Test Alert — AgenteDeVoz",
        body="This is a test alert fired from /monitoring/test-alert. "
             "If you received this, your alert channels are configured correctly.",
        level=AlertLevel.INFO,
    )
    return {"status": "sent", "message": "Test alert dispatched to all configured channels"}
