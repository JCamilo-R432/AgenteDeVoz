from __future__ import annotations
"""payment_routes.py — Payment history, webhooks, and invoices."""


import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from src.auth.authentication import AuthenticationManager, TokenData, oauth2_scheme

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/payments", tags=["payments"])
_auth  = AuthenticationManager()


def _current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    data = _auth.decode_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid token")
    return data

def _require_admin(user: TokenData = Depends(_current_user)) -> TokenData:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user


class RefundRequest(BaseModel):
    reason: Optional[str] = None


# ── Payment history ───────────────────────────────────────────────

@router.get("/history")
async def payment_history(
    page : int = 1,
    limit: int = 20,
    user: TokenData = Depends(_current_user),
):
    return {
        "page"    : page,
        "limit"   : limit,
        "total"   : 3,
        "payments": [
            {"id": "pay_001", "amount": 99.00, "currency": "USD",
             "status": "succeeded", "method": "card", "date": "2026-03-01",
             "description": "AgenteDeVoz Pro — monthly"},
            {"id": "pay_002", "amount": 99.00, "currency": "USD",
             "status": "succeeded", "method": "card", "date": "2026-02-01",
             "description": "AgenteDeVoz Pro — monthly"},
        ],
    }


@router.get("/{payment_id}")
async def get_payment(payment_id: str, user: TokenData = Depends(_current_user)):
    return {
        "id"         : payment_id,
        "amount"     : 99.00,
        "currency"   : "USD",
        "status"     : "succeeded",
        "method"     : "card",
        "date"       : "2026-03-01",
        "receipt_url": None,
    }


# ── Webhooks ──────────────────────────────────────────────────────

@router.post("/webhook/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
):
    """Receive and process Stripe webhook events."""
    from config.payment_config import PaymentConfig
    if not PaymentConfig.is_stripe_configured():
        logger.debug("Stripe webhook received (not configured)")
        return {"received": True}

    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    from src.payments.stripe_integration import StripePaymentGateway
    from src.payments.webhook_handler import WebhookHandler
    gw      = StripePaymentGateway(PaymentConfig.STRIPE_SECRET_KEY, PaymentConfig.STRIPE_WEBHOOK_SECRET)
    handler = WebhookHandler(stripe_gateway=gw)

    try:
        result = await handler.handle_stripe(payload, stripe_signature)
        return result
    except Exception as exc:
        logger.error("Stripe webhook error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/webhook/paypal", status_code=status.HTTP_200_OK)
async def paypal_webhook(request: Request):
    payload = await request.body()
    import json
    event   = json.loads(payload)
    logger.info("PayPal webhook: %s", event.get("event_type"))
    return {"received": True}


# ── Invoices ──────────────────────────────────────────────────────

@router.get("/invoices")
async def list_invoices(user: TokenData = Depends(_current_user)):
    return {
        "invoices": [
            {"id": "inv_001", "date": "2026-03-01", "amount": 99.00,
             "status": "paid", "pdf_url": None},
            {"id": "inv_002", "date": "2026-02-01", "amount": 99.00,
             "status": "paid", "pdf_url": None},
        ]
    }


# ── Refund (admin only) ───────────────────────────────────────────

@router.post("/refund/{payment_id}")
async def refund_payment(
    payment_id: str,
    body: RefundRequest,
    admin: TokenData = Depends(_require_admin),
):
    logger.info("Refund requested for payment %s by admin %s", payment_id, admin.user_id)
    return {
        "payment_id": payment_id,
        "refunded"  : True,
        "reason"    : body.reason,
    }
