from __future__ import annotations
from typing import Dict, List, Any
"""
Stripe integration service for AgenteDeVoz.

Environment variables required:
    STRIPE_SECRET_KEY       — Stripe API secret key (sk_live_... or sk_test_...)
    STRIPE_WEBHOOK_SECRET   — Stripe webhook endpoint secret (whsec_...)
    STRIPE_PRICE_BASIC      — Stripe price ID for Basic plan
    STRIPE_PRICE_PRO        — Stripe price ID for Pro plan
    STRIPE_PRICE_ENTERPRISE — Stripe price ID for Enterprise plan

When STRIPE_SECRET_KEY is not set, the service operates in stub/dev mode
and logs actions to console instead of calling Stripe.
"""


import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

PLAN_PRICE_MAP: Dict[str, str] = {
    "basic": os.getenv("STRIPE_PRICE_BASIC", ""),
    "pro": os.getenv("STRIPE_PRICE_PRO", ""),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
}

# USD amounts in cents per plan (for local record-keeping)
PLAN_AMOUNT_CENTS: Dict[str, int] = {
    "basic": 20_000,       # $200
    "pro": 50_000,         # $500
    "enterprise": 100_000, # $1 000
}


def _stripe():
    """Lazy-import stripe and configure API key."""
    try:
        import stripe  # type: ignore
        stripe.api_key = _STRIPE_KEY
        return stripe
    except ImportError:
        return None


class StripeService:
    """Wraps Stripe API calls. Falls back to stub mode when key not set."""

    def __init__(self) -> None:
        self._dev_mode = not bool(_STRIPE_KEY)
        if self._dev_mode:
            logger.warning("STRIPE_SECRET_KEY not set — running in stub/dev mode")

    # ── Customer ───────────────────────────────────────────────────────────────

    async def create_or_get_customer(
        self,
        *,
        tenant_id: str,
        tenant_name: str,
        email: str,
    ) -> str:
        """Return stripe_customer_id (create if not existing)."""
        if self._dev_mode:
            cid = f"cus_dev_{tenant_id[:8]}"
            logger.info(f"[STUB] Stripe customer: {cid}")
            return cid

        stripe = _stripe()
        customers = stripe.Customer.list(email=email, limit=1)
        if customers.data:
            return customers.data[0].id

        customer = stripe.Customer.create(
            email=email,
            name=tenant_name,
            metadata={"tenant_id": tenant_id},
        )
        return customer.id

    # ── Checkout session ───────────────────────────────────────────────────────

    async def create_checkout_session(
        self,
        *,
        stripe_customer_id: str,
        plan: str,
        success_url: str,
        cancel_url: str,
        tenant_id: str,
    ) -> Dict[str, str]:
        """Create a Stripe Checkout Session and return URL + session ID."""
        price_id = PLAN_PRICE_MAP.get(plan, "")

        if self._dev_mode or not price_id:
            logger.info(f"[STUB] Checkout session for plan={plan} tenant={tenant_id}")
            return {
                "checkout_url": f"{success_url}?dev=1&plan={plan}",
                "session_id": f"cs_dev_{tenant_id[:8]}",
            }

        stripe = _stripe()
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={"tenant_id": tenant_id, "plan": plan},
        )
        return {"checkout_url": session.url, "session_id": session.id}

    # ── Subscription management ────────────────────────────────────────────────

    async def cancel_subscription(
        self,
        stripe_subscription_id: str,
        *,
        at_period_end: bool = True,
    ) -> Dict[str, Any]:
        if self._dev_mode:
            logger.info(f"[STUB] Cancel subscription {stripe_subscription_id} at_period_end={at_period_end}")
            return {"id": stripe_subscription_id, "cancel_at_period_end": at_period_end}

        stripe = _stripe()
        if at_period_end:
            sub = stripe.Subscription.modify(
                stripe_subscription_id, cancel_at_period_end=True
            )
        else:
            sub = stripe.Subscription.cancel(stripe_subscription_id)
        return {"id": sub.id, "cancel_at_period_end": sub.cancel_at_period_end}

    async def reactivate_subscription(self, stripe_subscription_id: str) -> Dict[str, Any]:
        if self._dev_mode:
            logger.info(f"[STUB] Reactivate subscription {stripe_subscription_id}")
            return {"id": stripe_subscription_id, "cancel_at_period_end": False}

        stripe = _stripe()
        sub = stripe.Subscription.modify(
            stripe_subscription_id, cancel_at_period_end=False
        )
        return {"id": sub.id, "cancel_at_period_end": sub.cancel_at_period_end}

    async def get_upcoming_invoice(self, stripe_customer_id: str) -> Optional[dict]:
        if self._dev_mode:
            return None
        try:
            stripe = _stripe()
            inv = stripe.Invoice.upcoming(customer=stripe_customer_id)
            return {
                "amount_due": inv.amount_due,
                "currency": inv.currency,
                "next_payment_attempt": inv.next_payment_attempt,
            }
        except Exception as exc:
            logger.warning(f"Could not fetch upcoming invoice: {exc}")
            return None

    # ── Webhook verification ───────────────────────────────────────────────────

    def construct_event(self, payload: bytes, sig_header: str) -> Optional[Any]:
        """
        Verify and parse a Stripe webhook payload.
        Returns the event object or None if verification fails.
        """
        if self._dev_mode:
            import json
            try:
                return json.loads(payload)
            except Exception:
                return None

        stripe = _stripe()
        if stripe is None:
            return None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, _WEBHOOK_SECRET
            )
            return event
        except Exception as exc:
            logger.warning(f"Webhook signature verification failed: {exc}")
            return None


# Singleton
stripe_service = StripeService()
