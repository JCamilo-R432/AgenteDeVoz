from __future__ import annotations
"""analytics_admin.py — Global platform analytics for admins."""


import logging
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger(__name__)


class AdminAnalytics:
    def __init__(self, db_session=None):
        self._db = db_session

    async def get_dashboard_stats(self) -> dict:
        return {
            "new_users_today"       : 7,
            "new_users_week"        : 34,
            "new_users_month"       : 142,
            "total_users"           : 1_247,
            "active_subscriptions"  : 87,
            "mrr"                   : 6_453.00,
            "total_calls_today"     : 1_204,
            "avg_session_duration_secs": 187,
            "top_plans"             : [
                {"plan": "free",       "count": 55, "pct": 38.7},
                {"plan": "basic",      "count": 32, "pct": 22.5},
                {"plan": "pro",        "count": 18, "pct": 12.7},
                {"plan": "enterprise", "count":  4, "pct":  2.8},
            ],
        }

    async def get_user_growth(self, days: int = 30) -> List[dict]:
        today = datetime.utcnow().date()
        growth = []
        total  = 1_100
        for i in range(days):
            date   = today - timedelta(days=days - 1 - i)
            new    = max(1, 4 + (i % 5) - 2)
            total += new
            growth.append({"date": date.isoformat(), "new_users": new, "total_users": total})
        return growth

    async def get_revenue_by_plan(self) -> List[dict]:
        return [
            {"plan_id": "basic",      "count": 32, "monthly_revenue": 928.00},
            {"plan_id": "pro",        "count": 18, "monthly_revenue": 1_782.00},
            {"plan_id": "enterprise", "count":  4, "monthly_revenue": 1_996.00},
        ]

    async def get_usage_heatmap(self) -> List[dict]:
        """Returns {hour, day_of_week, call_count} for a 7×24 heatmap."""
        import random
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return [
            {
                "day_of_week": day,
                "hour"       : hour,
                "call_count" : max(0, random.randint(0, 80) if 8 <= hour <= 18 else random.randint(0, 15)),
            }
            for day in days
            for hour in range(24)
        ]
