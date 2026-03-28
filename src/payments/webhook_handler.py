from __future__ import annotations
"""
webhook_handler.py — Central dispatcher for payment provider webhooks.
Handles Stripe events and updates subscriptions / user status accordingly.
"""


import logging
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)

# Stripe event → handler method name
_STRIPE_EVENT_MAP = {
    "customer.subscription.created"  : "on_subscription_created",
    "customer.subscription.updated"  : "on_subscription_updated",
    "customer.subscription.deleted"  : "on_subscription_deleted",
    "invoice.payment_succeeded"      : "on_payment_succeeded",
    "invoice.payment_failed"         : "on_payment_failed",
    "customer.subscription.trial_will_end": "on_trial_ending",
    "checkout.session.completed"     : "on_checkout_completed",
}


class WebhookHandler:
    """
    Parses and dispatches incoming payment provider webhooks.
    Register custom handlers with `register(event, callable)`.
    """

    def __init__(self, stripe_gateway=None, db_session=None, email_service=None):
        self._stripe  = stripe_gateway
        self._db      = db_session
        self._email   = email_service
        self._handlers: Dict[str, Callable] = {}

    # ── Registration ──────────────────────────────────────────────

    def register(self, event_type: str, handler: Callable) -> None:
        self._handlers[event_type] = handler

    # ── Stripe dispatch ───────────────────────────────────────────

    async def handle_stripe(self, payload: bytes, signature: str) -> dict:
        if not self._stripe:
            raise RuntimeError("No Stripe gateway configured")

        event = self._stripe.handle_webhook(payload, signature)
        event_type = event["type"]
        logger.info("Stripe webhook: %s", event_type)

        # Custom registered handlers take priority
        if event_type in self._handlers:
            await self._handlers[event_type](event)
            return {"processed": True, "event": event_type}

        # Built-in handlers
        method_name = _STRIPE_EVENT_MAP.get(event_type)
        if method_name and hasattr(self, method_name):
            await getattr(self, method_name)(event["data"]["object"])
        else:
            logger.debug("Unhandled Stripe event: %s", event_type)

        return {"processed": True, "event": event_type}

    # ── Built-in Stripe event handlers ───────────────────────────

    async def on_subscription_created(self, obj: Dict[str, Any]) -> None:
        logger.info("Subscription created: %s status=%s", obj.get("id"), obj.get("status"))

    async def on_subscription_updated(self, obj: Dict[str, Any]) -> None:
        sub_id = obj.get("id")
        status = obj.get("status")
        logger.info("Subscription updated: %s status=%s", sub_id, status)
        # Update user subscription_status in DB based on new status
        if self._db and status in ("active", "past_due", "canceled"):
            await self._sync_subscription_status(sub_id, status)

    async def on_subscription_deleted(self, obj: Dict[str, Any]) -> None:
        logger.info("Subscription deleted: %s", obj.get("id"))
        if self._db:
            await self._sync_subscription_status(obj.get("id"), "cancelled")

    async def on_payment_succeeded(self, obj: Dict[str, Any]) -> None:
        logger.info("Payment succeeded: invoice=%s amount=%s",
                    obj.get("id"), obj.get("amount_paid"))
        if self._email:
            customer_email = obj.get("customer_email")
            if customer_email:
                await self._email.send_payment_receipt(
                    email      = customer_email,
                    amount     = obj.get("amount_paid", 0) / 100,
                    invoice_url= obj.get("hosted_invoice_url"),
                )

    async def on_payment_failed(self, obj: Dict[str, Any]) -> None:
        logger.warning("Payment FAILED: invoice=%s customer=%s",
                       obj.get("id"), obj.get("customer"))
        if self._email:
            customer_email = obj.get("customer_email")
            if customer_email:
                await self._email.send_payment_failed_notice(customer_email)

    async def on_trial_ending(self, obj: Dict[str, Any]) -> None:
        logger.info("Trial ending soon for subscription: %s", obj.get("id"))

    async def on_checkout_completed(self, obj: Dict[str, Any]) -> None:
        logger.info("Checkout completed: session=%s", obj.get("id"))

    # ── DB helpers ────────────────────────────────────────────────

    async def _sync_subscription_status(self, stripe_sub_id: str, status: str) -> None:
        logger.debug("Syncing subscription %s → %s", stripe_sub_id, status)
