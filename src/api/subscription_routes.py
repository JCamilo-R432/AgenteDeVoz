from __future__ import annotations
"""subscription_routes.py — Subscription management endpoints."""


import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.auth.authentication import AuthenticationManager, TokenData, oauth2_scheme
from src.subscriptions.plan_manager import PlanManager

logger  = logging.getLogger(__name__)
router  = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])
_auth   = AuthenticationManager()
_plans  = PlanManager()


def _current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    data = _auth.decode_token(token)
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return data


class SubscriptionCreate(BaseModel):
    plan_id          : str
    billing_cycle    : str = "monthly"
    payment_method_id: Optional[str] = None

class SubscriptionUpgrade(BaseModel):
    new_plan_id  : str
    billing_cycle: str = "monthly"
    prorate      : bool = True

class CancelRequest(BaseModel):
    at_period_end: bool = True


@router.get("/plans")
async def list_plans():
    """Return all available plans with prices and features."""
    return [
        {
            "id"           : p.id,
            "name"         : p.name,
            "description"  : p.description,
            "price_monthly": str(p.price_monthly),
            "price_yearly" : str(p.price_yearly),
            "trial_days"   : p.trial_days,
            "features"     : p.features,
            "limits"       : p.limits,
        }
        for p in _plans.get_all_plans()
    ]


@router.get("/me")
async def get_my_subscription(user: TokenData = Depends(_current_user)):
    plan = _plans.get_plan(user.subscription_plan or "free")
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {
        "plan_id"      : plan.id,
        "plan_name"    : plan.name,
        "status"       : "active",
        "billing_cycle": "monthly",
        "price"        : str(plan.price_monthly),
        "days_remaining": 18,
        "cancel_at_period_end": False,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_subscription(body: SubscriptionCreate, user: TokenData = Depends(_current_user)):
    plan = _plans.get_plan(body.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{body.plan_id}' not found")

    price = _plans.calculate_price(body.plan_id, body.billing_cycle)
    logger.info("Subscription created: user=%s plan=%s", user.user_id, body.plan_id)
    return {
        "user_id"      : user.user_id,
        "plan_id"      : body.plan_id,
        "billing_cycle": body.billing_cycle,
        "price"        : str(price),
        "status"       : "active",
    }


@router.put("/upgrade")
async def upgrade_plan(body: SubscriptionUpgrade, user: TokenData = Depends(_current_user)):
    current = user.subscription_plan or "free"
    if not _plans.can_upgrade(current, body.new_plan_id):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot upgrade from '{current}' to '{body.new_plan_id}'",
        )
    logger.info("Plan upgrade: %s → %s for user %s", current, body.new_plan_id, user.user_id)
    return {"old_plan": current, "new_plan": body.new_plan_id, "status": "upgraded"}


@router.put("/cancel")
async def cancel_subscription(body: CancelRequest, user: TokenData = Depends(_current_user)):
    logger.info("Subscription cancel: user=%s at_period_end=%s", user.user_id, body.at_period_end)
    return {
        "cancelled"    : True,
        "at_period_end": body.at_period_end,
        "message"      : "Tu suscripción se cancelará al final del período actual."
                         if body.at_period_end else "Suscripción cancelada inmediatamente.",
    }


@router.get("/billing-portal")
async def billing_portal(user: TokenData = Depends(_current_user)):
    """Return Stripe billing portal URL."""
    from config.payment_config import PaymentConfig
    if not PaymentConfig.is_stripe_configured():
        raise HTTPException(status_code=503, detail="Payment gateway not configured")
    # In production: create actual Stripe billing portal session
    return {"url": f"/pricing?user={user.user_id}", "message": "Configure Stripe to enable billing portal"}


@router.post("/checkout")
async def create_checkout(body: SubscriptionCreate, user: TokenData = Depends(_current_user)):
    """Create a Stripe checkout session and return the URL."""
    from config.payment_config import PaymentConfig
    plan = _plans.get_plan(body.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if not PaymentConfig.is_stripe_configured():
        # Return mock checkout URL for dev
        return {"checkout_url": f"/pricing/checkout?plan={body.plan_id}&cycle={body.billing_cycle}"}

    from src.payments.stripe_integration import StripePaymentGateway
    gw       = StripePaymentGateway(PaymentConfig.STRIPE_SECRET_KEY, PaymentConfig.STRIPE_WEBHOOK_SECRET)
    price_id = PaymentConfig.stripe_price_id(body.plan_id, body.billing_cycle)
    if not price_id:
        raise HTTPException(status_code=400, detail="Stripe price ID not configured for this plan")

    # In production: look up stripe_customer_id from DB
    checkout_url = gw.create_checkout_session(
        customer_id= "cus_demo",
        price_id   = price_id,
        success_url= "/dashboard?payment=success",
        cancel_url = "/pricing",
    )
    return {"checkout_url": checkout_url}
