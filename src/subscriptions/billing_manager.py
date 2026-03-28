from __future__ import annotations
"""
billing_manager.py — Orchestrates subscription lifecycle and billing events.
"""


import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class BillingManager:
    """
    Handles subscription creation, upgrades, downgrades, cancellation,
    and trial-to-paid conversion.
    Delegates actual charge processing to the payment gateway.
    """

    def __init__(self, plan_manager, payment_gateway=None, db_session=None,
                 email_service=None):
        self._plans    = plan_manager
        self._gw       = payment_gateway
        self._db       = db_session
        self._email    = email_service

    # ── Subscription lifecycle ───────────────────────────────────

    async def start_trial(self, user_id: str, plan_id: str) -> dict:
        """Activate a free trial for a user."""
        trial_days = self._plans.get_trial_duration(plan_id)
        now        = datetime.utcnow()
        return {
            "user_id"    : user_id,
            "plan_id"    : plan_id,
            "status"     : "trialing",
            "trial_start": now.isoformat(),
            "trial_end"  : (now + timedelta(days=trial_days)).isoformat(),
            "trial_days" : trial_days,
        }

    async def create_subscription(
        self, user_id: str, plan_id: str, billing_cycle: str,
        payment_method_id: Optional[str] = None,
    ) -> dict:
        """Create a paid subscription through the configured gateway."""
        plan = self._plans.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan '{plan_id}' not found")

        price = self._plans.calculate_price(plan_id, billing_cycle)
        logger.info("Creating subscription: user=%s plan=%s price=$%s", user_id, plan_id, price)

        result = {
            "user_id"       : user_id,
            "plan_id"       : plan_id,
            "billing_cycle" : billing_cycle,
            "price"         : str(price),
            "status"        : "active",
            "started_at"    : datetime.utcnow().isoformat(),
        }

        if self._gw and payment_method_id:
            try:
                gw_result = await self._gw.create_subscription_for_user(
                    user_id=user_id, plan_id=plan_id,
                    billing_cycle=billing_cycle,
                    payment_method_id=payment_method_id,
                )
                result.update(gw_result)
            except Exception as exc:
                logger.error("Payment gateway error: %s", exc)
                raise

        if self._email:
            await self._email.send_subscription_confirmation(user_id, plan_id, price)

        return result

    async def cancel_subscription(
        self, user_id: str, at_period_end: bool = True
    ) -> dict:
        """Cancel a subscription immediately or at end of current period."""
        logger.info("Cancelling subscription: user=%s at_period_end=%s", user_id, at_period_end)
        return {
            "user_id"        : user_id,
            "cancelled"      : True,
            "at_period_end"  : at_period_end,
            "cancelled_at"   : datetime.utcnow().isoformat(),
        }

    async def upgrade_subscription(
        self, user_id: str, new_plan_id: str, current_plan_id: str
    ) -> dict:
        if not self._plans.can_upgrade(current_plan_id, new_plan_id):
            raise ValueError(f"Cannot upgrade from '{current_plan_id}' to '{new_plan_id}'")
        logger.info("Upgrading: user=%s %s → %s", user_id, current_plan_id, new_plan_id)
        return {
            "user_id"     : user_id,
            "old_plan"    : current_plan_id,
            "new_plan"    : new_plan_id,
            "upgraded_at" : datetime.utcnow().isoformat(),
        }

    async def downgrade_subscription(
        self, user_id: str, new_plan_id: str, current_plan_id: str
    ) -> dict:
        if not self._plans.can_downgrade(current_plan_id, new_plan_id):
            raise ValueError(f"Cannot downgrade from '{current_plan_id}' to '{new_plan_id}'")
        return {
            "user_id"       : user_id,
            "old_plan"      : current_plan_id,
            "new_plan"      : new_plan_id,
            "downgraded_at" : datetime.utcnow().isoformat(),
        }

    def calculate_prorated_credit(
        self, current_price: Decimal, days_remaining: int, cycle_days: int = 30
    ) -> Decimal:
        """Prorate the refund for an upgrade mid-cycle."""
        if cycle_days <= 0:
            return Decimal("0")
        return round(current_price * days_remaining / cycle_days, 2)
