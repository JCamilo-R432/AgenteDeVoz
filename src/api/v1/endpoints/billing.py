from __future__ import annotations
"""
Billing endpoints — Module 4.

GET  /api/v1/billing/subscription          — get current subscription
POST /api/v1/billing/checkout              — create Stripe Checkout session
POST /api/v1/billing/cancel                — cancel subscription at period end
POST /api/v1/billing/reactivate            — undo cancellation
GET  /api/v1/billing/invoices              — list invoices
GET  /api/v1/billing/invoices/{id}         — get invoice detail
POST /api/v1/billing/webhook               — Stripe webhook (no auth)
"""


import logging
from typing import List, Dict, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from models.billing import Subscription, Invoice
from schemas.billing import (
    SubscriptionResponse,
    InvoiceResponse,
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
    CancelSubscriptionResponse,
)
from services.stripe_service import stripe_service
from services.invoice_service import InvoiceService

router = APIRouter(tags=["billing"])
logger = logging.getLogger(__name__)


def _require_tenant(request: Request) -> str:
    tenant_id: Optional[str] = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="X-API-Key required")
    return tenant_id


# ── Subscription ───────────────────────────────────────────────────────────────

@router.get("/subscription", response_model=Optional[SubscriptionResponse])
async def get_subscription(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[Subscription]:
    tenant_id = _require_tenant(request)
    result = await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


# ── Checkout ───────────────────────────────────────────────────────────────────

@router.post("/checkout", response_model=CreateCheckoutSessionResponse)
async def create_checkout(
    body: CreateCheckoutSessionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CreateCheckoutSessionResponse:
    """Create a Stripe Checkout Session for the given plan."""
    tenant_id = _require_tenant(request)
    tenant = getattr(request.state, "tenant", None)

    valid_plans = {"basic", "pro", "enterprise"}
    if body.plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Plan must be one of {valid_plans}")

    # Resolve or create Stripe customer
    email = (tenant.settings or {}).get("billing_email", "") if tenant else ""
    name = tenant.name if tenant else tenant_id

    stripe_customer_id = await stripe_service.create_or_get_customer(
        tenant_id=tenant_id,
        tenant_name=name,
        email=email,
    )

    # Persist customer ID if not stored yet
    result = await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        if not sub.stripe_customer_id:
            sub.stripe_customer_id = stripe_customer_id
            await db.flush()
    else:
        from services.stripe_service import PLAN_AMOUNT_CENTS
        sub = Subscription(
            tenant_id=tenant_id,
            stripe_customer_id=stripe_customer_id,
            plan=body.plan,
            status="incomplete",
            amount_usd=PLAN_AMOUNT_CENTS.get(body.plan, 0),
        )
        db.add(sub)
        await db.flush()

    session_data = await stripe_service.create_checkout_session(
        stripe_customer_id=stripe_customer_id,
        plan=body.plan,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
        tenant_id=tenant_id,
    )

    return CreateCheckoutSessionResponse(
        checkout_url=session_data["checkout_url"],
        session_id=session_data["session_id"],
    )


# ── Cancel ─────────────────────────────────────────────────────────────────────

@router.post("/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CancelSubscriptionResponse:
    tenant_id = _require_tenant(request)

    result = await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription found")
    if not sub.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="Subscription not linked to Stripe yet")

    stripe_result = await stripe_service.cancel_subscription(
        sub.stripe_subscription_id, at_period_end=True
    )
    sub.cancel_at_period_end = True
    await db.flush()

    return CancelSubscriptionResponse(
        subscription_id=sub.id,
        cancel_at_period_end=True,
        message="Subscription will be cancelled at the end of the current billing period.",
    )


# ── Reactivate ─────────────────────────────────────────────────────────────────

@router.post("/reactivate", response_model=CancelSubscriptionResponse)
async def reactivate_subscription(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CancelSubscriptionResponse:
    tenant_id = _require_tenant(request)

    result = await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")
    if not sub.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="Subscription not linked to Stripe")

    await stripe_service.reactivate_subscription(sub.stripe_subscription_id)
    sub.cancel_at_period_end = False
    await db.flush()

    return CancelSubscriptionResponse(
        subscription_id=sub.id,
        cancel_at_period_end=False,
        message="Subscription reactivated successfully.",
    )


# ── Invoices ───────────────────────────────────────────────────────────────────

@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> List[Invoice]:
    tenant_id = _require_tenant(request)
    svc = InvoiceService(db)
    return await svc.list_invoices(tenant_id, limit=limit, offset=offset)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Invoice:
    tenant_id = _require_tenant(request)
    svc = InvoiceService(db)
    invoice = await svc.get_invoice(invoice_id, tenant_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


# ── Stripe Webhook ─────────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Stripe sends signed webhook events here.
    Handles: checkout.session.completed, invoice.paid,
             customer.subscription.updated, customer.subscription.deleted
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    event = stripe_service.construct_event(payload, sig_header)
    if event is None:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event.get("type") if isinstance(event, dict) else event.type
    data_obj = (event.get("data", {}).get("object", {})
                if isinstance(event, dict)
                else event.data.object)

    logger.info(f"Stripe webhook received: {event_type}")

    try:
        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(data_obj, db)

        elif event_type == "invoice.paid":
            await _handle_invoice_paid(data_obj, db)

        elif event_type == "customer.subscription.updated":
            await _handle_subscription_updated(data_obj, db)

        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(data_obj, db)

    except Exception as exc:
        logger.error(f"Webhook handler error [{event_type}]: {exc}", exc_info=True)
        # Return 200 to prevent Stripe from retrying on handler errors
        # (Stripe will retry on non-2xx responses)

    return Response(content='{"received": true}', media_type="application/json")


# ── Webhook handlers ───────────────────────────────────────────────────────────

async def _handle_checkout_completed(data: dict, db: AsyncSession) -> None:
    """Link Stripe subscription ID after successful checkout."""
    stripe_sub_id = data.get("subscription")
    stripe_customer_id = data.get("customer")
    metadata = data.get("metadata", {})
    tenant_id = metadata.get("tenant_id", "")
    plan = metadata.get("plan", "basic")

    if not tenant_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    )
    sub = result.scalar_one_or_none()

    if sub:
        sub.stripe_subscription_id = stripe_sub_id
        sub.stripe_customer_id = stripe_customer_id
        sub.plan = plan
        sub.status = "active"
    else:
        from services.stripe_service import PLAN_AMOUNT_CENTS
        sub = Subscription(
            tenant_id=tenant_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_sub_id,
            plan=plan,
            status="active",
            amount_usd=PLAN_AMOUNT_CENTS.get(plan, 0),
        )
        db.add(sub)

    # Update tenant plan
    from models.tenant import Tenant
    t_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = t_result.scalar_one_or_none()
    if tenant:
        tenant.plan = plan

    await db.flush()
    logger.info(f"Subscription activated for tenant {tenant_id}, plan={plan}")


async def _handle_invoice_paid(data: dict, db: AsyncSession) -> None:
    """Persist paid invoice to local DB and generate PDF."""
    stripe_customer_id = data.get("customer")
    if not stripe_customer_id:
        return

    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_customer_id == stripe_customer_id
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        logger.warning(f"invoice.paid: no subscription for customer {stripe_customer_id}")
        return

    # Avoid duplicate invoice records
    existing = await db.execute(
        select(Invoice).where(Invoice.stripe_invoice_id == data.get("id"))
    )
    if existing.scalar_one_or_none():
        return

    svc = InvoiceService(db)
    invoice = await svc.create_from_stripe(
        subscription_id=sub.id,
        tenant_id=sub.tenant_id,
        stripe_data=data,
    )
    logger.info(f"Invoice {invoice.invoice_number} created for tenant {sub.tenant_id}")


async def _handle_subscription_updated(data: dict, db: AsyncSession) -> None:
    stripe_sub_id = data.get("id")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return

    sub.status = data.get("status", sub.status)
    sub.cancel_at_period_end = data.get("cancel_at_period_end", sub.cancel_at_period_end)

    from services.invoice_service import _ts_to_dt
    sub.current_period_start = _ts_to_dt(data.get("current_period_start"))
    sub.current_period_end = _ts_to_dt(data.get("current_period_end"))
    await db.flush()


async def _handle_subscription_deleted(data: dict, db: AsyncSession) -> None:
    stripe_sub_id = data.get("id")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = "canceled"
        from services.invoice_service import _ts_to_dt
        sub.canceled_at = _ts_to_dt(data.get("canceled_at"))
        await db.flush()

        # Downgrade tenant to basic
        from models.tenant import Tenant
        t_result = await db.execute(select(Tenant).where(Tenant.id == sub.tenant_id))
        tenant = t_result.scalar_one_or_none()
        if tenant:
            tenant.plan = "basic"
            await db.flush()
