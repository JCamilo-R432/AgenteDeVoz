from __future__ import annotations
"""
quota_manager.py — Enforces plan-based usage quotas.
"""


import logging
from typing import Optional

from config.subscription_config import PLAN_LIMITS, QUOTA_WARNING_PERCENT

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    def __init__(self, resource: str, limit: int, used: int, upgrade_url: str = "/pricing"):
        self.resource    = resource
        self.limit       = limit
        self.used        = used
        self.upgrade_url = upgrade_url
        super().__init__(
            f"Quota exceeded: {resource} ({used}/{limit}). Upgrade at {upgrade_url}"
        )


class QuotaManager:
    """Check and enforce per-plan resource quotas."""

    def __init__(self, usage_tracker=None):
        self._tracker = usage_tracker

    # ── Public interface ─────────────────────────────────────────

    def check_call_quota(self, plan_id: str, current_count: int) -> None:
        """Raise QuotaExceededError if the user has no calls left."""
        limit = self._get_limit(plan_id, "monthly_calls")
        if limit == -1:
            return  # unlimited
        if current_count >= limit:
            raise QuotaExceededError("monthly_calls", limit, current_count)

    def check_api_quota(self, plan_id: str, daily_requests: int) -> None:
        limit = self._get_limit(plan_id, "api_requests_per_day")
        if limit == -1:
            return
        if daily_requests >= limit:
            raise QuotaExceededError("api_requests_per_day", limit, daily_requests)

    def check_concurrent_sessions(self, plan_id: str, active_sessions: int) -> None:
        limit = self._get_limit(plan_id, "concurrent_sessions")
        if limit == -1:
            return
        if active_sessions >= limit:
            raise QuotaExceededError("concurrent_sessions", limit, active_sessions)

    def is_near_limit(self, plan_id: str, resource: str, current: int) -> bool:
        """Returns True when usage is at or above QUOTA_WARNING_PERCENT of limit."""
        limit = self._get_limit(plan_id, resource)
        if limit <= 0:
            return False
        return (current / limit * 100) >= QUOTA_WARNING_PERCENT

    def remaining(self, plan_id: str, resource: str, current: int) -> Optional[int]:
        """Calls remaining; None = unlimited."""
        limit = self._get_limit(plan_id, resource)
        if limit == -1:
            return None
        return max(0, limit - current)

    def usage_summary(self, plan_id: str, call_count: int, api_count: int) -> dict:
        return {
            "monthly_calls": {
                "used"     : call_count,
                "limit"    : self._get_limit(plan_id, "monthly_calls"),
                "remaining": self.remaining(plan_id, "monthly_calls", call_count),
                "near_limit": self.is_near_limit(plan_id, "monthly_calls", call_count),
            },
            "api_requests": {
                "used"     : api_count,
                "limit"    : self._get_limit(plan_id, "api_requests_per_day"),
                "remaining": self.remaining(plan_id, "api_requests_per_day", api_count),
                "near_limit": self.is_near_limit(plan_id, "api_requests_per_day", api_count),
            },
        }

    # ── Internal ──────────────────────────────────────────────────

    def _get_limit(self, plan_id: str, key: str) -> int:
        return PLAN_LIMITS.get(plan_id, PLAN_LIMITS["free"]).get(key, 0)
