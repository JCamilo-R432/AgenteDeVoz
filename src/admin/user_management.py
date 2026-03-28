from __future__ import annotations
"""user_management.py — Admin service for user CRUD and stats."""


import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

_DEMO_USERS = [
    {"id": "usr_001", "email": "alice@empresa.co", "full_name": "Alice Gómez",
     "plan": "pro", "is_active": True, "calls_this_month": 342, "created_at": "2026-01-15"},
    {"id": "usr_002", "email": "bob@startup.io",   "full_name": "Bob Martínez",
     "plan": "basic", "is_active": True, "calls_this_month": 87, "created_at": "2026-02-10"},
    {"id": "usr_003", "email": "carol@free.com",   "full_name": "Carol López",
     "plan": "free", "is_active": True, "calls_this_month": 12, "created_at": "2026-03-01"},
]


class UserManagementService:
    def __init__(self, db_session=None):
        self._db = db_session

    async def list_users(self, offset: int = 0, limit: int = 50,
                         plan_filter: Optional[str] = None) -> List[dict]:
        if self._db:
            from database.models.user import User
            from sqlalchemy import select
            stmt = select(User).offset(offset).limit(limit)
            if plan_filter:
                stmt = stmt.where(User.subscription_plan == plan_filter)
            rows = (await self._db.execute(stmt)).scalars().all()
            return [
                {
                    "id": str(u.id), "email": u.email, "full_name": u.full_name,
                    "plan": u.subscription_plan.value if u.subscription_plan else "free",
                    "is_active": u.is_active,
                    "calls_this_month": u.monthly_call_count,
                    "created_at": u.created_at.isoformat(),
                }
                for u in rows
            ]
        users = _DEMO_USERS[offset:offset + limit]
        if plan_filter:
            users = [u for u in users if u["plan"] == plan_filter]
        return users

    async def suspend_user(self, user_id: str, reason: str = "") -> bool:
        logger.info("Suspending user %s: %s", user_id, reason)
        if self._db:
            from database.models.user import User
            u = await self._db.get(User, user_id)
            if u:
                u.is_active = False
                await self._db.commit()
                return True
            return False
        return True

    async def activate_user(self, user_id: str) -> bool:
        logger.info("Activating user %s", user_id)
        if self._db:
            from database.models.user import User
            u = await self._db.get(User, user_id)
            if u:
                u.is_active = True
                await self._db.commit()
                return True
            return False
        return True

    async def change_plan(self, user_id: str, plan_id: str, limits_map: dict) -> bool:
        logger.info("Changing plan for user %s → %s", user_id, plan_id)
        if self._db:
            from database.models.user import User, SubscriptionPlan
            u = await self._db.get(User, user_id)
            if u:
                u.subscription_plan    = SubscriptionPlan(plan_id)
                u.monthly_call_limit   = limits_map.get("monthly_calls", 50)
                await self._db.commit()
                return True
            return False
        return True

    async def delete_user(self, user_id: str) -> bool:
        if self._db:
            from database.models.user import User
            u = await self._db.get(User, user_id)
            if u:
                await self._db.delete(u)
                await self._db.commit()
                return True
            return False
        logger.info("DEV: deleted user %s", user_id)
        return True

    async def get_user_stats(self, user_id: str) -> dict:
        if self._db:
            from database.models.user import User
            u = await self._db.get(User, user_id)
            if not u:
                return {}
            age = (datetime.utcnow() - u.created_at).days if u.created_at else 0
            return {
                "calls_this_month" : u.monthly_call_count,
                "monthly_limit"    : u.monthly_call_limit,
                "plan"             : u.subscription_plan.value if u.subscription_plan else "free",
                "account_age_days" : age,
                "is_active"        : u.is_active,
            }
        return {
            "calls_this_month": 42, "monthly_limit": 100,
            "plan": "free", "account_age_days": 15, "is_active": True,
        }
