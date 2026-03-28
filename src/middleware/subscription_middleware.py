from __future__ import annotations
"""
subscription_middleware.py — Enforces active subscription on protected API routes.
"""


import logging

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from config.subscription_config import PLAN_LIMITS

logger = logging.getLogger(__name__)

# Routes that require an active (non-free) subscription
_PRO_PATHS = [
    "/api/v1/voice/stream",
    "/api/v1/admin/",
]

# Routes that require at least a registered (any plan) subscription
_AUTH_PATHS = [
    "/api/v1/voice/process",
    "/api/v1/tickets",
    "/dashboard/",
    "/api/v1/licenses",
]


class SubscriptionMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, quota_manager=None):
        super().__init__(app)
        self._quota = quota_manager

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        user = getattr(request.state, "user", None)

        # Check pro-only routes
        if any(path.startswith(p) for p in _PRO_PATHS):
            if not user:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required"},
                )
            plan = getattr(user, "subscription_plan", "free")
            if plan not in ("pro", "enterprise"):
                return JSONResponse(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    content={
                        "detail"     : "This feature requires a Pro or Enterprise plan.",
                        "upgrade_url": "/pricing",
                    },
                )

        # Check quota on voice processing
        if path.startswith("/api/v1/voice/process") and user:
            plan          = getattr(user, "subscription_plan", "free")
            call_count    = getattr(user, "monthly_call_count", 0)
            monthly_limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["monthly_calls"]

            if monthly_limit != -1 and call_count >= monthly_limit:
                return JSONResponse(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    content={
                        "detail"     : f"Monthly call limit reached ({call_count}/{monthly_limit}).",
                        "upgrade_url": "/pricing",
                    },
                )

        return await call_next(request)
