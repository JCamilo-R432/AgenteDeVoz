from __future__ import annotations
"""subscription_management.py — Admin subscription operations."""


import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

logger = logging.getLogger(__name__)


class SubscriptionManagementService:
    def __init__(self, db_session=None):
        self._db = db_session

    async def list_subscriptions(self, status_filter: Optional[str] = None,
                                  offset: int = 0, limit: int = 50) -> List[dict]:
        if self._db:
            from database.models.subscription import Subscription, SubscriptionStatus
            from sqlalchemy import select
            stmt = select(Subscription).offset(offset).limit(limit)
            if status_filter:
                try:
                    stmt = stmt.where(Subscription.status == SubscriptionStatus(status_filter))
                except ValueError:
                    pass
            rows = (await self._db.execute(stmt)).scalars().all()
            return [
                {
                    "id"          : str(s.id),
                    "user_id"     : str(s.user_id),
                    "plan_id"     : s.plan_id,
                    "status"      : s.status.value,
                    "billing_cycle": s.billing_cycle.value if s.billing_cycle else "monthly",
                    "price"       : str(s.price),
                    "period_end"  : s.current_period_end.isoformat() if s.current_period_end else None,
                }
                for s in rows
            ]
        # Demo data
        demo = [
            {"id": "sub_001", "user_id": "usr_001", "plan_id": "pro",
             "status": "active", "billing_cycle": "monthly", "price": "99.00"},
            {"id": "sub_002", "user_id": "usr_002", "plan_id": "basic",
             "status": "active", "billing_cycle": "yearly", "price": "290.00"},
        ]
        if status_filter:
            demo = [s for s in demo if s["status"] == status_filter]
        return demo[offset:offset + limit]

    async def cancel_subscription(self, sub_id: str, reason: str = "") -> bool:
        logger.info("Cancelling subscription %s: %s", sub_id, reason)
        if self._db:
            from database.models.subscription import Subscription, SubscriptionStatus
            sub = await self._db.get(Subscription, sub_id)
            if sub:
                sub.status       = SubscriptionStatus.CANCELLED
                sub.cancelled_at = datetime.utcnow()
                await self._db.commit()
                return True
            return False
        return True

    async def extend_subscription(self, sub_id: str, days: int) -> bool:
        logger.info("Extending subscription %s by %d days", sub_id, days)
        if self._db:
            from database.models.subscription import Subscription
            sub = await self._db.get(Subscription, sub_id)
            if sub and sub.current_period_end:
                sub.current_period_end = sub.current_period_end + timedelta(days=days)
                await self._db.commit()
                return True
            return False
        return True

    async def get_revenue_stats(self) -> dict:
        # Real impl would query DB; return realistic mock
        return {
            "mrr"               : 6453.00,
            "arr"               : 77436.00,
            "total_subscribers" : 87,
            "churn_rate_percent": 2.3,
            "avg_revenue_per_user": 74.17,
        }

    async def get_plan_distribution(self) -> dict:
        if self._db:
            from database.models.user import User, SubscriptionPlan
            from sqlalchemy import func, select
            stmt = select(User.subscription_plan, func.count(User.id)).group_by(User.subscription_plan)
            rows = (await self._db.execute(stmt)).all()
            return {row[0].value: row[1] for row in rows}
        return {"free": 55, "basic": 32, "pro": 18, "enterprise": 4}
