from __future__ import annotations
"""
stripe_integration.py — Stripe payment gateway adapter.
"""


import logging
from typing import Any, Dict, List, Optional

import stripe
from stripe import StripeError

from src.payments.payment_gateway import PaymentGateway

logger = logging.getLogger(__name__)


class StripePaymentGateway(PaymentGateway):
    """Full Stripe integration: customers, subscriptions, checkout, webhooks."""

    def __init__(self, secret_key: str, webhook_secret: str):
        stripe.api_key       = secret_key
        self._webhook_secret = webhook_secret

    # ── Customer ──────────────────────────────────────────────────

    def create_customer(self, email: str, name: str,
                        metadata: Dict[str, Any] = None) -> str:
        customer = stripe.Customer.create(
            email   = email,
            name    = name,
            metadata= metadata or {},
        )
        logger.info("Stripe customer created: %s", customer.id)
        return customer.id

    def update_customer(self, customer_id: str, **kwargs) -> None:
        stripe.Customer.modify(customer_id, **kwargs)

    # ── Subscription ──────────────────────────────────────────────

    def create_subscription(self, customer_id: str, price_id: str,
                            trial_days: int = 0) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "customer"        : customer_id,
            "items"           : [{"price": price_id}],
            "payment_behavior": "default_incomplete",
            "expand"          : ["latest_invoice.payment_intent"],
        }
        if trial_days > 0:
            params["trial_period_days"] = trial_days

        sub = stripe.Subscription.create(**params)
        logger.info("Stripe subscription created: %s", sub.id)

        return {
            "subscription_id"  : sub.id,
            "status"           : sub.status,
            "client_secret"    : sub.latest_invoice.payment_intent.client_secret
                                 if sub.latest_invoice else None,
            "current_period_end": sub.current_period_end,
        }

    def cancel_subscription(self, subscription_id: str,
                            at_period_end: bool = True) -> bool:
        try:
            if at_period_end:
                stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
            else:
                stripe.Subscription.cancel(subscription_id)
            logger.info("Stripe subscription cancelled: %s", subscription_id)
            return True
        except StripeError as exc:
            logger.error("Stripe cancel error: %s", exc)
            return False

    def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            return {
                "id"                 : sub.id,
                "status"             : sub.status,
                "current_period_end" : sub.current_period_end,
                "cancel_at_period_end": sub.cancel_at_period_end,
            }
        except StripeError:
            return None

    def update_subscription_plan(self, subscription_id: str,
                                  new_price_id: str) -> Dict[str, Any]:
        sub = stripe.Subscription.retrieve(subscription_id)
        updated = stripe.Subscription.modify(
            subscription_id,
            items=[{"id": sub["items"]["data"][0].id, "price": new_price_id}],
            proration_behavior="create_prorations",
        )
        return {"subscription_id": updated.id, "status": updated.status}

    # ── Checkout ──────────────────────────────────────────────────

    def create_checkout_session(self, customer_id: str, price_id: str,
                                success_url: str, cancel_url: str) -> str:
        session = stripe.checkout.Session.create(
            customer            = customer_id,
            payment_method_types= ["card"],
            line_items          = [{"price": price_id, "quantity": 1}],
            mode                = "subscription",
            success_url         = success_url,
            cancel_url          = cancel_url,
            metadata            = {"source": "web"},
        )
        logger.info("Stripe checkout session: %s", session.id)
        return session.url

    def create_billing_portal_session(self, customer_id: str,
                                       return_url: str) -> str:
        session = stripe.billing_portal.Session.create(
            customer  = customer_id,
            return_url= return_url,
        )
        return session.url

    # ── Payment Intent ────────────────────────────────────────────

    def create_payment_intent(self, amount_cents: int, currency: str = "usd",
                               customer_id: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "amount"                  : amount_cents,
            "currency"                : currency,
            "automatic_payment_methods": {"enabled": True},
        }
        if customer_id:
            params["customer"] = customer_id
        intent = stripe.PaymentIntent.create(**params)
        return {"client_secret": intent.client_secret, "payment_intent_id": intent.id}

    # ── Invoice ───────────────────────────────────────────────────

    def create_invoice(self, customer_id: str, items: List[Dict]) -> str:
        invoice = stripe.Invoice.create(customer=customer_id, auto_advance=True)
        for item in items:
            stripe.InvoiceItem.create(
                customer   = customer_id,
                invoice    = invoice.id,
                amount     = item["amount"],
                currency   = item.get("currency", "usd"),
                description= item["description"],
            )
        final = stripe.Invoice.finalize_invoice(invoice.id)
        return final.hosted_invoice_url

    # ── Webhook ───────────────────────────────────────────────────

    def handle_webhook(self, payload: bytes, signature: str) -> stripe.Event:
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self._webhook_secret
            )
            logger.info("Stripe webhook received: %s", event.type)
            return event
        except stripe.error.SignatureVerificationError:
            logger.error("Stripe webhook signature verification failed")
            raise
